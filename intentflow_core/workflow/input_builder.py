"""Automatically assemble confirmed predecessor outputs for each step."""
from sqlalchemy import select
from intentflow_core.models import Artifact, serialize
from .steps import step
from .trace import ancestors

def _all(service, project_id):
    from intentflow_core.versioning import Versioning
    return Versioning(service.s).current_artifacts(project_id)

def _latest(objects, kind, predicate=lambda item: True):
    return next((item for item in reversed(objects) if item.kind == kind and item.status == "CONFIRMED" and predicate(item)), None)

def _used(objects, source_id, kinds):
    return any(item.kind in kinds and source_id in item.sources for item in objects)

def build(service, project_id, step_id):
    definition = step(step_id)
    project = service.project(project_id)
    objects = _all(service, project_id)
    selected = []

    if step_id == "project-context":
        selected = [item for item in objects if item.kind == "Evidence"]
    elif step_id == "problem-evidence":
        context = _latest(objects, "Context")
        pending = _latest(objects, "CandidateProblem", lambda item: item.data.get("status") == "AWAITING_CONFIRMATION")
        evidence = [item for item in objects if item.kind in {"Evidence", "RuntimeEvidence"}]
        selected = ([context] if context else []) + evidence + ([pending] if pending else [])
    elif step_id == "specification":
        problem = _latest(objects, "Problem", lambda item: not _used(objects, item.id, {"Specification"}))
        if problem:
            selected = ancestors(service, project_id, [problem])
            context = _latest(objects, "Context")
            if context and context not in selected:
                selected.insert(0, context)
    elif step_id == "engineering-intent":
        specification = _latest(objects, "Specification", lambda item: not _used(objects, item.id, {"EngineeringIntent"}))
        if specification:
            selected = ancestors(service, project_id, [specification])
            context = _latest(objects, "Context")
            if context and context not in selected:
                selected.insert(0, context)
    elif step_id == "software-change":
        item = _latest(objects, "EngineeringIntent", lambda value: not _used(objects, value.id, {"ChangeRecord"}))
        selected = [item] if item else []
    elif step_id == "verification":
        item = _latest(objects, "ChangeRecord", lambda value: value.data.get("status") == "OPEN")
        selected = ancestors(service, project_id, [item]) if item else []
    elif step_id == "runtime-outcome":
        verification = _latest(objects, "Verification", lambda value: not _used(objects, value.id, {"EngineeringEvaluation"}))
        after = _latest(objects, "RuntimeEvidence", lambda value: verification is not None and verification.id in value.sources)
        if verification:
            selected = ancestors(service, project_id, [verification])
        if after and after not in selected:
            selected.append(after)
    elif step_id == "next-change":
        evaluation = _latest(objects, "EngineeringEvaluation")
        candidate = _latest(objects, "CandidateProblem", lambda item: item.data.get("status") == "AWAITING_CONFIRMATION")
        selected = ([evaluation] if evaluation else []) + ([candidate] if candidate else [])

    # Preserve order and never expose non-artifact research data.
    unique = list({item.id: item for item in selected if item is not None}.values())
    kinds = {item.kind for item in unique}
    missing = []
    if step_id == "project-context":
        if not project.repository and not project.description:
            missing.append("代码仓库或项目说明")
    elif step_id == "problem-evidence":
        if "Context" not in kinds:
            missing.append("正式项目上下文")
        if not kinds.intersection({"Evidence", "RuntimeEvidence"}):
            missing.append("原始证据")
    elif step_id == "specification" and "Problem" not in kinds:
        missing.append("已确认问题")
    elif step_id == "engineering-intent":
        if "Specification" not in kinds:
            missing.append("正式需求规格")
        if not project.repository:
            missing.append("代码仓库")
    elif step_id == "software-change":
        if "EngineeringIntent" not in kinds:
            missing.append("正式工程意图")
        if not project.repository:
            missing.append("代码仓库")
    elif step_id == "verification" and "ChangeRecord" not in kinds:
        missing.append("待验证变更记录")
    elif step_id == "runtime-outcome":
        if "Verification" not in kinds:
            missing.append("正式验证结果")
        if "RuntimeEvidence" not in kinds:
            missing.append("变更后运行证据")
    elif step_id == "next-change" and "EngineeringEvaluation" not in kinds:
        missing.append("正式工程评估")
    return {
        "step": definition.as_dict(),
        "ready": not missing,
        "missing": missing,
        "sources": [serialize(item) for item in unique],
        "project_context": service.project_context(project_id),
    }
