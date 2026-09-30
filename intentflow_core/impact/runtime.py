"""Persistent jobs with short database transactions and inspectable evidence."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
from pathlib import Path
import threading

from sqlalchemy import select, update

from adapters.execution import capabilities, environment, execute
from adapters.git import commit, git, repository
from intentflow_core.models import EngineeringRun, Project, now, serialize
from intentflow_core.versioning import Versioning, VersionConflict
from intentflow_core.impact import analyze


class ExecutionManager:
    def __init__(self, factory, data_root):
        self.factory = factory
        self.data_root = Path(data_root)
        self.pool = None
        self.cancel_flags = {}
        self.lock = threading.Lock()
        self.file_lock = None

    def start(self):
        if self.pool:
            return
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.file_lock = (self.data_root / ".execution.lock").open("a+b")
        self.file_lock.seek(0, 2)
        if self.file_lock.tell() == 0:
            self.file_lock.write(b"0")
            self.file_lock.flush()
        self.file_lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file_lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file_lock.close()
            self.file_lock = None
            raise RuntimeError("此数据目录已有执行服务运行，请勿重复启动") from None
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="intentflow-execution")
        with self.factory.begin() as s:
            for job in s.scalars(select(EngineeringRun).where(EngineeringRun.status.in_(["RUNNING", "CANCELLING"]))):
                job.status = "INTERRUPTED"
                job.finished_at = now()
                job.result = {"reason": "服务中断；旧的部分结果不构成通过，请创建新运行"}
            queued = list(s.scalars(select(EngineeringRun.id).where(EngineeringRun.status == "QUEUED")))
        for jid in queued:
            self.dispatch(jid)

    def stop(self):
        with self.lock:
            for flag in self.cancel_flags.values():
                flag.set()
        if self.pool:
            self.pool.shutdown(wait=True)
            self.pool = None
        if self.file_lock:
            self.file_lock.close()
            self.file_lock = None

    def queue(self, s, pid, expected, *, mode, trusted, full, request_id):
        v = Versioning(s)
        baseline = v.baseline(pid)
        if expected != baseline.id:
            raise VersionConflict("需求已变化，请重新审阅复验计划")
        if mode == "native" and not trusted:
            raise ValueError("本机执行不是安全沙箱，只可在明确确认代码可信后运行")
        if not capabilities()[mode]["available"]:
            raise ValueError("所选执行环境不可用")
        existing = next((j for j in s.scalars(select(EngineeringRun).where(EngineeringRun.project_id == pid))
                         if j.inputs.get("request_id") == request_id), None)
        if existing:
            if any(existing.inputs.get(k) != val for k, val in {"mode": mode, "full": full}.items()) or existing.baseline_id != expected:
                raise VersionConflict("重复请求标识对应不同输入，请重新发起")
            return existing, False
        project = s.get(Project, pid)
        root = repository(project.repository) if project.repository else None
        if not root:
            raise ValueError("请先连接代码仓库")
        if not baseline.code_commit or commit(root, "HEAD") != baseline.code_commit:
            raise VersionConflict("请先确认当前代码提交，将代码版本纳入需求基线")
        if git(root, "status", "--porcelain", "--untracked-files=no").strip():
            raise ValueError("代码存在未提交修改，请先在开发工具中审阅并提交")
        plan = analyze(v, pid)
        tests = [o for o in v.objects(pid) if o["kind"] == "TEST"] if full else plan["tests"]
        if not tests:
            raise ValueError("没有可运行的测试，请先登记测试或选择全量复验")
        if len(tests) > 30:
            raise ValueError("首版每次最多执行 30 个登记测试")
        for test in tests:
            if any(baseline.members.get(rid) != test["content"].get("rule_revisions", {}).get(rid)
                   for rid in test["content"]["rule_ids"]):
                raise VersionConflict("测试映射仍指向旧规则，请先审阅测试内容并确认新映射")
        active_count = len(list(s.scalars(select(EngineeringRun.id).where(
            EngineeringRun.status.in_(["QUEUED", "RUNNING", "CANCELLING"])))))
        if active_count >= 8:
            raise ValueError("执行队列已满，请等待当前运行结束")
        item = EngineeringRun(project_id=pid, baseline_id=baseline.id, kind="VERIFICATION",
            inputs={"request_id": request_id, "mode": mode, "trusted_project": trusted, "full": full, "tests": tests,
                    "repository": str(root), "code_commit": baseline.code_commit,
                    "environment": environment(mode), "selection": plan,
                    "architecture_rules": [o for o in v.objects(pid) if o["kind"] == "ARCHITECTURE"],
                    "previous_commit": v.baseline(pid, baseline.parent_id).code_commit if baseline.parent_id else ""})
        s.add(item)
        s.flush()
        v.event(pid, "VERIFICATION_QUEUED", {"run_id": item.id, "baseline_id": baseline.id})
        return item, True

    def dispatch(self, jid):
        if not self.pool:
            raise RuntimeError("执行服务未启动")
        with self.lock:
            if jid in self.cancel_flags:
                return
            flag = threading.Event()
            self.cancel_flags[jid] = flag
        self.pool.submit(self._work, jid, flag)

    def _work(self, jid, flag):
        try:
            with self.factory.begin() as s:
                claimed = s.execute(update(EngineeringRun).where(EngineeringRun.id == jid,
                    EngineeringRun.status == "QUEUED").values(status="RUNNING"))
                if claimed.rowcount != 1:
                    return
                job = s.get(EngineeringRun, jid)
                inputs, pid = dict(job.inputs), job.project_id
            # No open SQLAlchemy session/transaction during subprocess execution.
            try:
                result = execute(inputs["repository"], inputs["code_commit"], inputs["tests"], inputs["mode"], flag)
                if inputs.get("architecture_rules") and not flag.is_set():
                    from intentflow_core.architecture import compare
                    result["architecture"] = compare(inputs["repository"], inputs["code_commit"],
                        inputs.get("previous_commit", ""), inputs["architecture_rules"])
                    result["architecture"]["rule_revisions"] = {r["id"]: r["revision_id"] for r in inputs["architecture_rules"]}
                    result["architecture"]["checked_date"] = date.today().isoformat()
                results = result["results"]
                if flag.is_set():
                    status = "CANCELLED"
                elif any(r.get("execution_status") == "TIMEOUT" for r in results):
                    status = "TIMEOUT"
                elif len(results) != len(inputs["tests"]) or any(r["verdict"] == "UNKNOWN" for r in results):
                    status = "UNKNOWN"
                else:
                    status = "SUCCEEDED"  # Individual verdicts still may FAIL.
            except Exception:
                # Exception repr may contain local paths or arbitrary test text.
                result, status = {"reason": "执行环境或快照准备失败，请核对仓库、测试与执行配置"}, "ERROR"
            with self.factory.begin() as s:
                job = s.get(EngineeringRun, jid)
                if job.status == "CANCELLING":
                    status = "CANCELLED"
                job.status, job.result, job.finished_at = status, result, now()
                Versioning(s).event(pid, "VERIFICATION_FINISHED", {"run_id": jid, "status": status})
        finally:
            with self.lock:
                self.cancel_flags.pop(jid, None)

    def cancel(self, s, pid, jid):
        job = s.get(EngineeringRun, jid)
        if not job or job.project_id != pid:
            raise ValueError("运行不存在")
        if job.status == "QUEUED":
            job.status, job.finished_at = "CANCELLED", now()
        elif job.status in {"RUNNING", "CANCELLING"}:
            job.status = "CANCELLING"
            with self.lock:
                if jid in self.cancel_flags:
                    self.cancel_flags[jid].set()
        s.flush()
        return public_run(job)


def public_run(job):
    result = serialize(job)
    result["inputs"] = {k: v for k, v in job.inputs.items() if k != "repository"}
    return result


def evidence_state(s, pid):
    v = Versioning(s)
    baseline = v.baseline(pid)
    objects = v.objects(pid)
    project = s.get(Project, pid)
    current_env = {mode: environment(mode) for mode in ("native", "docker")}
    actual_commit, clean = "", False
    if project.repository:
        try:
            actual_commit = commit(repository(project.repository), "HEAD")
            clean = not git(project.repository, "status", "--porcelain", "--untracked-files=no").strip()
        except ValueError:
            pass
    runs = list(s.scalars(select(EngineeringRun).where(EngineeringRun.project_id == pid,
        EngineeringRun.kind == "VERIFICATION").order_by(EngineeringRun.created_at.desc())))
    tests = [o for o in objects if o["kind"] == "TEST"]
    test_results = {}
    for test in tests:
        eligible = None
        for run in runs:
            attempted = any(t["id"] == test["id"] and t["revision_id"] == test["revision_id"]
                            for t in run.inputs.get("tests", []))
            if (attempted and run.status in {"ERROR", "UNKNOWN", "TIMEOUT", "INTERRUPTED", "CANCELLED"}
                    and run.inputs.get("code_commit") == baseline.code_commit == actual_commit and clean
                    and run.inputs.get("environment") == current_env.get(run.inputs.get("mode"))):
                eligible = {"verdict": "UNKNOWN", "run_id": run.id,
                            "reason": "最近一次同条件复验未完整完成，不能用更早的通过掩盖此结果"}
                break
            if (run.status != "SUCCEEDED" or run.result.get("code_commit") != baseline.code_commit
                    or actual_commit != baseline.code_commit or not clean
                    or run.result.get("environment") != current_env.get(run.inputs.get("mode"))):
                continue
            result = next((r for r in run.result.get("results", []) if r["test_id"] == test["id"]
                           and r.get("revision_id") == test["revision_id"]), None)
            if result and all(baseline.members.get(rid) == test["content"].get("rule_revisions", {}).get(rid)
                              for rid in test["content"]["rule_ids"]):
                eligible = {**result, "run_id": run.id, "reused": run.baseline_id != baseline.id,
                            "reuse_reason": "规则修订、测试修订、代码提交与环境指纹一致"}
                break
        test_results[test["id"]] = eligible or {"verdict": "STALE", "reason": "缺少当前规则、代码与环境下的完整运行证据"}
    conclusions = []
    for rule in (o for o in objects if o["kind"] == "RULE"):
        mapped = [t for t in tests if rule["id"] in t["content"]["rule_ids"]]
        verdicts = [test_results[t["id"]]["verdict"] for t in mapped]
        status = "UNKNOWN" if not mapped else "FAIL" if "FAIL" in verdicts else (
            "PASS" if all(value == "PASS" for value in verdicts) else "STALE")
        conclusions.append({"rule_id": rule["id"], "title": rule["title"], "status": status,
                            "test_ids": [t["id"] for t in mapped]})
    architecture_rules = [o for o in objects if o["kind"] == "ARCHITECTURE"]
    architecture = {"status": "NOT_CONFIGURED", "findings": [], "reason": "尚未登记架构约束，不代表架构已验证"}
    if architecture_rules:
        architecture = {"status": "STALE", "findings": [], "reason": "缺少当前架构约束和代码下的检查"}
        arch_runs = list(s.scalars(select(EngineeringRun).where(EngineeringRun.project_id == pid,
            EngineeringRun.kind.in_(["ARCHITECTURE", "VERIFICATION"])).order_by(EngineeringRun.created_at.desc())))
        expected_rules = {r["id"]: r["revision_id"] for r in architecture_rules}
        for run in arch_runs:
            report = run.result.get("architecture", {})
            if (run.status == "SUCCEEDED" and actual_commit == baseline.code_commit and clean
                    and run.result.get("code_commit") == baseline.code_commit
                    and report.get("rule_revisions") == expected_rules
                    and report.get("checked_date") == date.today().isoformat()):
                architecture = {**report, "run_id": run.id}
                break
    functional_supported = bool(conclusions) and all(c["status"] == "PASS" for c in conclusions)
    return {"baseline_id": baseline.id, "code_commit": actual_commit, "working_tree_clean": clean,
            "tests": test_results, "conclusions": conclusions,
            "functional_supported": functional_supported, "architecture": architecture,
            "baseline_supported": functional_supported and architecture["status"] in {"PASS", "NOT_CONFIGURED"},
            "support_scope": "仅覆盖已登记且人工确认映射的规则、测试和架构约束；不证明未登记需求",
            "runs": [public_run(r) for r in runs]}
