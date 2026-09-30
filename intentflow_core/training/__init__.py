"""Reproducible local practice scenarios; not a hidden competition evaluator."""
from pathlib import Path
import shutil

from sqlalchemy import select

from adapters.git import commit, git
from intentflow_core.models import EngineeringDraft, EngineeringEvent, serialize, uid
from intentflow_core.versioning import Versioning
from intentflow_core.impact.runtime import evidence_state

CASES = {
    "campus": {"title": "校园活动报名", "path": "enrollment.py", "test": "test_enrollment.py", "capacity": 2},
    "inventory": {"title": "库存扣减", "path": "stock.py", "test": "test_stock.py", "capacity": 3},
    "reservation": {"title": "预约冲突", "path": "booking.py", "test": "test_booking.py", "capacity": 1},
}


def create_case(service, domain):
    if domain not in CASES:
        raise ValueError("未知领域案例")
    config = CASES[domain]
    project = service.create_project("V3 示例 · " + config["title"], "公开的小型 Python 项目，可修改后重复验证")
    target = service.data_root / "repositories" / uid()
    source = service.root / "examples" / "v2" / domain
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", ".git", "*.pyc"))
    git(target, "init", "-b", "main")
    git(target, "add", ".")
    git(target, "-c", "user.name=IntentFlow", "-c", "user.email=local@intentflow.invalid",
        "commit", "-m", "初始化 V3 公开领域案例")
    project.repository = str(target)
    project.details = {**project.details, "v2_case": domain, "scenario_version": "1"}
    v = Versioning(service.s)
    rule_id, code_id, test_id = uid(), uid(), uid()
    changes = [
        {"id": rule_id, "kind": "RULE", "title": config["title"] + "容量规则",
         "content": {"domain": domain, "capacity": config["capacity"]}},
        {"id": code_id, "kind": "CODE", "title": "业务代码", "content": {"path": config["path"]}},
        {"id": test_id, "kind": "TEST", "title": "公开边界与回归测试",
         "content": {"path": config["test"], "rule_ids": [rule_id], "code_paths": [config["path"]]}},
        {"kind": "ARCHITECTURE", "title": "业务逻辑不直接发起外部网络请求",
         "content": {"scope": config["path"], "forbidden_imports": ["requests", "httpx", "urllib.request"],
                     "reason": "报名、库存和预约决策应可离线复现，不依赖外部网络状态。"}},
    ]
    # The caller explicitly confirms the published, visible example settings.
    v.confirm(project.id, v.ensure(project.id).baseline_id, changes, "确认公开示例初始规则与测试映射",
        code_commit=commit(target, "HEAD"), relations=[
            {"source_id": code_id, "target_id": rule_id, "kind": "implements"},
            {"source_id": test_id, "target_id": rule_id, "kind": "verifies"}])
    v.event(project.id, "CASE_CREATED", {"domain": domain, "scenario_version": "1"})
    return project


def score(session, pid, training):
    v = Versioning(session)
    state = evidence_state(session, pid)
    events = list(session.scalars(select(EngineeringEvent).where(EngineeringEvent.project_id == pid,
        EngineeringEvent.created_at >= training.created_at)))
    drafts = list(session.scalars(select(EngineeringDraft).where(EngineeringDraft.project_id == pid,
        EngineeringDraft.created_at >= training.created_at)))
    content = training.content
    changed = content.get("change_baseline", "")
    rule = next((o for o in v.objects(pid) if o["id"] == content["rule_id"]), None)
    target_met = bool(changed and rule and rule["content"]["capacity"] == content["target_capacity"])
    rows = [
        ("记录变化前的基线证据", 10, content.get("initial_supported", False), "开始时已登记规则有有效证据"),
        ("观察规则原型", 10, any(d.kind == "PROTOTYPE" and d.content.get("events") for d in drafts), "有本次过程内的原型操作轨迹"),
        ("确认情境变化", 10, target_met, "当前规则保留本次事件指定的新容量"),
        ("审阅变化影响", 10, bool(changed and any(e.kind == "IMPACT_REVIEWED" and
            e.details.get("baseline_id") == changed for e in events)), "审阅记录指向事件产生的基线"),
        ("修改代码并恢复当前证据", 40, bool(target_met and state["baseline_supported"] and
            state["code_commit"] != content["initial_code_commit"]), "新提交、当前测试映射和完整复验共同支持当前规则"),
        ("检查有理由的架构约束", 10, bool(changed and state["architecture"]["status"] == "PASS" and
            any(e.kind in {"ARCHITECTURE_CHECKED", "VERIFICATION_FINISHED"} for e in events)), "当前架构规则与代码检查通过"),
        ("留下可计算的协商记录", 10, any(d.kind == "NEGOTIATION" and d.content.get("result", {}).get("status")
            in {"FEASIBLE", "INFEASIBLE"} for d in drafts), "保存了确定性求解输入、冲突及结果；无解也有分析价值"),
    ]
    criteria = [{"title": title, "weight": weight, "earned": weight if passed else 0, "basis": reason}
                for title, weight, passed, reason in rows]
    return {"score": sum(r["earned"] for r in criteria), "maximum": 100, "criteria": criteria,
            "baseline_id": state["baseline_id"], "mode": "local_practice",
            "boundary": "仅公开流程参考分，不是独立隐藏测试成绩；不能用于防作弊排名。",
            "formal_evaluation_available": False}
