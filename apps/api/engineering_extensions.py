"""Architecture and negotiated candidates share the engineering baseline."""
from datetime import date
from typing import Literal

from pydantic import Field
from sqlalchemy import select

from adapters.git import commit, repository
from intentflow_core.architecture import compare
from intentflow_core.models import EngineeringDraft, EngineeringRun, EngineeringEvent, Project, now, serialize
from intentflow_core.negotiation import solve
from intentflow_core.versioning import Versioning, VersionConflict


def install_extensions(router, factory, Strict, DraftConfirm):
    class Negotiate(DraftConfirm):
        rule_id: str
        existing: int = Field(ge=0, le=100000)
        incoming: int = Field(ge=0, le=100000)
        group: str = Field(default="普通", min_length=1, max_length=50)
        group_existing: int = Field(default=0, ge=0, le=100000)
        requested_start: int = Field(default=0, ge=0, le=1000000)
        requested_end: int = Field(default=60, ge=1, le=1000001)
        allow_waitlist: bool = False
        allow_capacity_increase: bool = False
        allow_window_expansion: bool = False
        capacity_limit: int = Field(default=100000, ge=1, le=100000)
        preference: Literal["least_change", "admit_more"] = "least_change"

    class Adopt(DraftConfirm):
        candidate_index: int = Field(ge=0, le=100)

    class SpecDocument(Strict):
        document: str = Field(default="", max_length=500000)

    class SpecImport(SpecDocument):
        expected_baseline_id: str

    class OutcomeInput(DraftConfirm):
        title: str = Field(min_length=1, max_length=300)
        observation: str = Field(min_length=1, max_length=10000)
        metrics: dict[str, float] = Field(default_factory=dict, max_length=50)
        decision: Literal["OBSERVE", "ADJUST", "CLOSE", "ROLLBACK"] = "OBSERVE"
        rationale: str = Field(min_length=1, max_length=5000)

    @router.post("/outcomes", status_code=201)
    def save_outcome(pid: str, body: OutcomeInput):
        import math
        from intentflow_core.impact.runtime import evidence_state
        with factory.begin() as s:
            v = Versioning(s)
            if v.ensure(pid).baseline_id != body.expected_baseline_id:
                raise VersionConflict("需求已经变化，请重新核对运行观察对应的基线")
            if any(not math.isfinite(value) for value in body.metrics.values()):
                raise ValueError("运行指标必须是有限数值")
            evidence = evidence_state(s, pid)
            if body.decision == "CLOSE" and not evidence["baseline_supported"]:
                raise ValueError("当前工程证据未齐全，不能确认结束；可记录观察或继续调整")
            sources = sorted({r["run_id"] for r in evidence["tests"].values() if r.get("run_id")})
            if evidence["architecture"].get("run_id"):
                sources = sorted(set(sources) | {evidence["architecture"]["run_id"]})
            item = EngineeringDraft(project_id=pid, baseline_id=body.expected_baseline_id,
                kind="OUTCOME", status="CONFIRMED", content={**body.model_dump(exclude={"expected_baseline_id", "confirmed"}),
                    "run_ids": sources, "code_commit": evidence["code_commit"],
                    "baseline_supported_at_confirmation": evidence["baseline_supported"],
                    "conclusions": evidence["conclusions"], "source": "人工现场观察，不是自动测量"})
            s.add(item)
            s.flush()
            v.event(pid, "OUTCOME_CONFIRMED", {"outcome_id": item.id, "baseline_id": item.baseline_id,
                "run_ids": sources, "decision": body.decision})
            return serialize(item)

    @router.post("/spec/export")
    def export_spec(pid: str, body: SpecDocument):
        from adapters.speckit import export
        with factory.begin() as s:
            return {"document": export(Versioning(s), pid, body.document), "filename": "intentflow-spec.md"}

    @router.post("/spec/import", status_code=201)
    def import_spec(pid: str, body: SpecImport):
        from adapters.speckit import import_changes
        with factory.begin() as s:
            v = Versioning(s)
            changes = import_changes(v, pid, body.expected_baseline_id, body.document)
            item = EngineeringDraft(project_id=pid, baseline_id=body.expected_baseline_id, kind="REQUIREMENT",
                content={"title": "从规格文件导入的候选修改", "changes": changes})
            s.add(item)
            s.flush()
            return serialize(item)

    @router.get("/events")
    def events(pid: str):
        with factory.begin() as s:
            Versioning(s).ensure(pid)
            return [serialize(e) for e in s.scalars(select(EngineeringEvent)
                .where(EngineeringEvent.project_id == pid).order_by(EngineeringEvent.created_at))]

    @router.post("/architecture-check")
    def architecture_check(pid: str, body: DraftConfirm):
        with factory.begin() as s:
            v = Versioning(s)
            baseline = v.baseline(pid)
            if baseline.id != body.expected_baseline_id:
                raise VersionConflict("需求已变化，请刷新后检查")
            rules = [o for o in v.objects(pid) if o["kind"] == "ARCHITECTURE"]
            project = s.get(Project, pid)
            if not project.repository or not baseline.code_commit or not rules:
                raise ValueError("请先连接仓库、确认代码版本并登记架构约束")
            root, ref = repository(project.repository), baseline.code_commit
            if commit(root, "HEAD") != ref:
                raise VersionConflict("当前代码已变化，请先确认代码版本")
            previous = v.baseline(pid, baseline.parent_id).code_commit if baseline.parent_id else ""
        # Git/AST analysis does not hold a database transaction or execute source.
        report = compare(root, ref, previous, rules)
        report.update(rule_revisions={r["id"]: r["revision_id"] for r in rules}, checked_date=date.today().isoformat())
        with factory.begin() as s:
            v = Versioning(s)
            item = EngineeringRun(project_id=pid, baseline_id=body.expected_baseline_id, kind="ARCHITECTURE",
                status="SUCCEEDED", inputs={"code_commit": ref},
                result={"code_commit": ref, "architecture": report}, finished_at=now())
            s.add(item)
            s.flush()
            v.event(pid, "ARCHITECTURE_CHECKED", {"run_id": item.id, "status": report["status"]})
            return serialize(item)

    @router.post("/negotiations", status_code=201)
    def negotiate(pid: str, body: Negotiate):
        with factory.begin() as s:
            v = Versioning(s)
            baseline = v.baseline(pid)
            if baseline.id != body.expected_baseline_id:
                raise VersionConflict("需求已变化，请重新确认协商输入")
            rule = next((o for o in v.objects(pid) if o["id"] == body.rule_id and o["kind"] == "RULE"), None)
            if not rule:
                raise ValueError("请选择当前正式规则")
            # Only one group and an already-overlapping reservation batch are
            # supported; not a general appointment scheduling solver.
            inputs = body.model_dump(exclude={"rule_id", "expected_baseline_id", "confirmed", "group"})
            config = rule["content"]
            inputs.update(capacity=config["capacity"], window_start=config["window_start"],
                          window_end=config["window_end"], group_quota=config["quotas"].get(body.group))
            try:
                result = solve(inputs)
            except ValueError:
                raise ValueError("协商输入不正确，请核对人数、组人数、时间和扩容上限") from None
            item = EngineeringDraft(project_id=pid, baseline_id=baseline.id, kind="NEGOTIATION",
                content={"rule_id": rule["id"], "rule_revision": rule["revision_id"], "group": body.group,
                         "result": result})
            s.add(item)
            s.flush()
            v.event(pid, "NEGOTIATION_SOLVED", {"draft_id": item.id, "status": result["status"]})
            return serialize(item)

    @router.post("/negotiations/{did}/adopt")
    def adopt(pid: str, did: str, body: Adopt):
        with factory.begin() as s:
            v = Versioning(s)
            item = s.get(EngineeringDraft, did)
            if not item or item.project_id != pid or item.kind != "NEGOTIATION" or item.status != "DRAFT":
                raise ValueError("协商候选不存在或已处理")
            if item.baseline_id != body.expected_baseline_id or v.ensure(pid).baseline_id != item.baseline_id:
                raise VersionConflict("规则已变化，请重新协商；不能采用旧方案")
            candidates = item.content["result"]["candidates"]
            if body.candidate_index >= len(candidates):
                raise ValueError("不存在该候选方案")
            chosen = candidates[body.candidate_index]
            rule = next(o for o in v.objects(pid) if o["id"] == item.content["rule_id"])
            content = {**rule["content"], **{k: chosen[k] for k in ("capacity", "window_start", "window_end")}}
            if chosen["waiting"]:
                content["waitlist_enabled"] = True
            result = v.confirm(pid, item.baseline_id, [{"id": rule["id"], "kind": "RULE",
                "title": rule["title"], "content": content}], "人工采用协商方案")
            item.status = "ADOPTED"
            v.event(pid, "NEGOTIATION_ADOPTED", {"draft_id": did, "candidate_index": body.candidate_index,
                "baseline_id": result["id"]})
            return result
