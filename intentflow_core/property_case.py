"""Rich local example. Case drafts are references, not model or field evidence."""
from pathlib import Path
import difflib
import json
import shutil
import sys
import tempfile
import threading

from sqlalchemy import select
from adapters.git import git, commit, repository
from adapters.execution import snapshot, bounded_run
from intentflow_core.models import Artifact, EngineeringDraft, Project, SkillRun, uid
from intentflow_core.rules import matches

MARKER = "        # CONTACT_DISPLAY: pending implementation"
REPLACEMENT = '        "contact_time": ticket.get("expected_contact") if ticket["status"] in {"assigned", "processing"} else None,'
LEGACY_PROBLEM_STATEMENT = "内部已有预计联系时间，但居民详情未返回该信息。"
PROPERTY_PROBLEM_STATEMENT = "实际：后端已存储预计联系时间，但详情接口未下发。期望：居民端能正常显示该时间。差距：居民看不到，导致反复咨询。"
PROPERTY_ITERATION_GOALS = [
    "跑通居民提交、客服派单、维修处理和居民确认的最小可用报修原型。",
    "将原型前向部署给居民、客服和维修人员，通过角色体验与访谈记录真实反馈。",
    "分析 12 条模拟工单、催办记录与运行日志，从数据中确定联系时间展示需求。",
    "在运行维护中处理状态规则、旧工单兼容、权限保护与后续业务变更。",
]


def refresh_legacy_reference_drafts(session_factory):
    """Refresh only untouched legacy reference text in pending property drafts."""
    refreshed = 0
    with session_factory.begin() as session:
        runs = session.scalars(select(SkillRun).where(
            SkillRun.skill_id == "evidence-analysis",
            SkillRun.mode == "manual",
            SkillRun.status == "DRAFT",
        )).all()
        for run in runs:
            project = session.get(Project, run.project_id)
            suggestion = dict(run.suggestion or {})
            if (project and project.details.get("example_kind") == "property-management"
                    and suggestion.get("problem_statement") == LEGACY_PROBLEM_STATEMENT):
                suggestion["problem_statement"] = PROPERTY_PROBLEM_STATEMENT
                run.suggestion = suggestion
                refreshed += 1
    return refreshed


def require_property(service, pid):
    project = service.project(pid)
    if project.details.get("example_kind") != "property-management":
        raise ValueError("此操作只适用于物业管理示例")
    return project


def create_property(service, name, description="", ai=None, agile=None):
    p = service.create_project(name or "青禾社区物业管理", description or "围绕报修进度透明度完成一次软件改进",
                               ai=ai, iteration_count=(agile or {}).get("iteration_count", 4),
                               iteration_length_weeks=(agile or {}).get("length_weeks", 2),
                               iteration_goals=PROPERTY_ITERATION_GOALS)
    source = service.root / "examples" / "property-management"
    target = service.data_root / "repositories" / uid()
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    git(target, "init", "-b", "main")
    git(target, "add", ".")
    git(target, "-c", "user.name=IntentFlow", "-c", "user.email=local@intentflow.invalid", "commit", "-m", "初始化物业报修项目与可复现的问题材料")
    p.repository = str(target)
    p.source_type = "case"
    p.details = {**p.details, "example_kind": "property-management", "scenario_version": "1",
                 "dataset_name": "intentflow-property", "instance_id": "qinghe-maintenance-001",
                 "base_commit": commit(target, "HEAD"), "problem_statement": "居民详情未显示维修人员已填写的预计联系时间"}
    catalog = json.loads((source / "case-materials" / "catalog.json").read_text(encoding="utf-8"))
    for item in catalog:
        service.put(p.id, "Evidence", item["title"], {"type": item["type"],
            "content": (source / "case-materials" / item["file"]).read_text(encoding="utf-8"),
            "origin": "case-materials/" + item["file"], "source_label": "虚构场景与模拟数据"})
    return p


def reference_draft(skill_id, service, pid):
    """Only known, bundled case references; never pretend this is an LLM answer."""
    command = lambda name: ["{python}", "-m", "unittest", "discover", "-s", "tests", "-p", name]
    values = {
        "project-understanding": {"stakeholders": ["居民林女士和周先生", "陈客服", "王师傅和赵师傅"],
            "system_boundary": "线上记录报修、受理、派单、维修结果和居民确认；线下维修、短信服务和费用结算不在本轮范围。",
            "core_modules": ["maintenance.py 管理权限与工单状态", "readmodel.py 组织居民详情", "replay.py 汇总模拟工单展示"],
            "business_objects": ["居民", "客服", "维修人员", "报修单", "预计联系时间", "处理记录"],
            "repository_structure": ["maintenance.py", "readmodel.py", "replay.py", "tests/", "case-materials/"],
            "workflow": "居民提交、客服受理和派单、维修处理、居民确认；派单前可取消，维修后可退回继续处理。",
            "constraints": ["居民只看本人报修", "维修人员只处理本人任务", "旧工单字段缺失仍可查询"],
            "unknown_questions": ["真实催办量和时间填写率仍需现场试用核验"]},
        "evidence-analysis": {"title": "居民无法得知已安排的联系时间", "problem_statement": PROPERTY_PROBLEM_STATEMENT,
            "supporting_evidence": ["居民访谈反映重复询问", "模拟日志记录王师傅填写10:30后居民详情仍无时间", "readmodel.py 尚未组装联系时间字段"],
            "affected_area": "居民报修详情", "unknown_questions": ["是否降低真实电话催办量不能由模拟数据证明"],
            "rationale": "访谈与日志指出信息缺口，代码检查可进一步验证字段遗漏。",
            "observation": "已派单报修单的内部预计时间为10:30，居民详情未显示。", "affected_users": "等待联系的居民和重复应答的客服",
            "current_state": "居民只看到状态", "expected_state": "有效状态显示已填写时间，未填写有明确提示",
            "sufficiency": "材料足以复现字段遗漏；实际服务效果需继续观察", "impact": "居民无法合理安排等待，客服重复沟通"},
        "requirement-engineering": {"title": "居民报修详情显示预计联系时间", "user_need": "居民希望知道负责人员已填写的联系安排。",
            "functional_requirements": ["已派单与处理中显示已填写时间", "未填写与旧工单显示待填写", "终态不显示未来联系承诺"],
            "quality_requirements": ["保留本人访问权限", "查询不修改工单", "兼容缺少字段的历史数据"],
            "business_rules": ["只有当前维修人员可以填写时间", "不能把预计联系时间当作上门保证", "取消和完成状态保持现有规则"],
            "constraints": ["仅调整居民详情", "不接入短信、不改变派单与状态规则"],
            "success_criteria": ["6条应显示的模拟工单均返回正确时间", "越权查询为0", "终态未来承诺为0", "全部回归和验收测试通过"],
            "why_change": "修复已复现的信息缺口，满足居民查看联系安排的需要", "decision": "GO"},
        "intent-design": {"title": "补齐联系时间展示并保护工单规则", "goal": "只修复readmodel.py的详情字段，不改变权限与流转。",
            "allowed_scope": ["readmodel.py"], "protected_scope": ["maintenance.py", "tests/**", "case-materials/**", "replay.py"],
            "protected_behavior": ["本人访问检查", "维修人员填写权限", "提交到关闭的流转和取消例外"],
            "invariants": ["查询不修改工单", "终态不显示未来承诺", "历史工单缺字段时正常返回"],
            "acceptance": ["在已派单和处理中返回当前联系时间", "全部14项验收和回归测试通过"],
            "acceptance_criteria": ["已填写、未填写、历史缺字段、终态、越权均有对应结果"],
            "preservation_tests": [command("test_workflow.py"), command("test_permissions.py")],
            "invariant_tests": [command("test_contact.py")], "acceptance_tests": [command("test_contact.py")],
            "open_questions": ["实际催办量改善留到现场观察"], "rationale": "问题位于详情组装层，最小修改可保护原有业务边界。",
            "field_target": ["contact_visible == 6", "unauthorized_visible == 0", "invalid_promises == 0"]},
    }
    if skill_id == "outcome-evaluation":
        return {"title": "物业报修联系信息改进评估", "effect_gap": "请结合下方当前回放指标与验证结果填写；模拟回放不证明真实催办量下降。",
                "new_problem": "", "recommended_action": "OBSERVE", "rationale": "先核对实际执行结果，再决定是否结束；后续需要真实使用观察。"}
    return values.get(skill_id, {})


def change_preview(service, pid):
    p = require_property(service, pid)
    path = repository(p.repository) / "readmodel.py"
    if path.is_symlink():
        raise ValueError("示例文件不能是链接")
    original = path.read_text(encoding="utf-8")
    if MARKER not in original and REPLACEMENT not in original:
        raise ValueError("代码已自行修改，请在开发工具中审阅和完成修改")
    updated = original.replace(MARKER, REPLACEMENT, 1)
    return original, updated, "".join(difflib.unified_diff(original.splitlines(True), updated.splitlines(True), fromfile="修改前/readmodel.py", tofile="修改后/readmodel.py"))


def apply_fix(service, pid):
    p = require_property(service, pid)
    change = service.s.scalar(select(Artifact).where(Artifact.project_id == pid, Artifact.kind == "ChangeRecord").order_by(Artifact.created_at.desc()))
    if not change or change.data.get("status") != "OPEN":
        raise ValueError("请先确认工程设计并记录修改前的代码版本")
    from intentflow_core.versioning import Versioning
    if change.id not in {a.id for a in Versioning(service.s).current_artifacts(pid)}:
        raise ValueError("请在当前轮次重新记录代码版本")
    intent = service.artifact(pid, change.sources[0], "EngineeringIntent")
    if not any(matches("readmodel.py", x) for x in intent.data["allowed_scope"]) or any(matches("readmodel.py", x) for x in intent.data["protected_scope"]):
        raise ValueError("当前修改约定不允许调整 readmodel.py，请先核对工程设计")
    root = repository(p.repository)
    if git(root, "status", "--porcelain").strip():
        raise ValueError("仓库有未提交修改，请先保存或处理后再应用参考修改")
    original, updated, _ = change_preview(service, pid)
    if original == updated:
        return {"changed": False, "commit": commit(root, "HEAD")}
    path = root / "readmodel.py"
    path.write_text(updated, encoding="utf-8")
    try:
        git(root, "add", "--", "readmodel.py")
        git(root, "-c", "user.name=IntentFlow Example", "-c", "user.email=example@intentflow.invalid", "commit", "-m", "显示居民报修预计联系时间，保留权限和旧工单兼容")
    except Exception:
        path.write_text(original, encoding="utf-8")
        git(root, "add", "--", "readmodel.py")
        raise
    return {"changed": True, "commit": commit(root, "HEAD")}


def run_replay(service, pid):
    p = require_property(service, pid)
    from intentflow_core.versioning import Versioning
    from intentflow_core.models import serialize
    objects = Versioning(service.s).current_artifacts(pid)
    verification = next((a for a in reversed(objects) if a.kind == "Verification" and a.data.get("status") == "PASS"), None)
    if not verification:
        raise ValueError("请先通过本轮代码验证，再记录前后回放结果")
    root = repository(p.repository)
    after_ref = verification.data["final_commit"]
    if git(root, "status", "--porcelain").strip() or commit(root, "HEAD") != after_ref:
        raise ValueError("当前代码与通过验证的版本不一致，请重新验证")
    change = service.artifact(pid, verification.sources[0], "ChangeRecord")
    def replay_at(ref):
        with tempfile.TemporaryDirectory(prefix="intentflow-property-replay-") as temp:
            replay_root = Path(temp)
            checkout = replay_root / "snapshot"
            snapshot(root, ref, checkout, allowed_destination_root=replay_root)
            result = bounded_run([sys.executable, "-B", "replay.py"], checkout, threading.Event(), timeout=20)
            if result["execution_status"] != "FINISHED" or result["exit_code"] != 0:
                raise ValueError("工单回放未完成，请检查代码和运行输出")
            return json.loads(result["output"])
    before, after = replay_at(change.data["baseline_commit"]), replay_at(after_ref)
    evidence = service.put(pid, "RuntimeEvidence", "同批物业工单修改前后回放", {
        "content": "对同一批12条模拟工单运行修改前后代码。结果只反映案例回放，不代表真实业务效果。",
        "metrics": after["metrics"], "before": before, "after": after,
        "source": "模拟工单回放", "code_commit": after_ref}, [verification.id], actor="case-replay", workflow_step="runtime-outcome")
    return serialize(evidence)
