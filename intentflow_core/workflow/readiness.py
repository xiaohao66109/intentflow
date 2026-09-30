"""Compute workflow progress from formal facts."""
from .input_builder import build
from .steps import STEPS

def workflow_state(service, project_id):
    from intentflow_core.versioning import Versioning
    current_objects = Versioning(service.s).current_artifacts(project_id)
    states = []
    current = STEPS[-1].id
    first_ready = None
    for definition in STEPS:
        assembled = build(service, project_id, definition.id)
        output_kinds = {
            "project-context": {"Context"}, "problem-evidence": {"Problem"},
            "specification": {"Specification"}, "engineering-intent": {"EngineeringIntent"},
            "software-change": {"ChangeRecord"}, "verification": {"Verification"},
            "runtime-outcome": {"EngineeringEvaluation"}, "next-change": set(),
        }[definition.id]
        completed = bool(output_kinds and any(
            source["kind"] in output_kinds for source in assembled["sources"]
        ))
        # Historic outputs never complete a new iteration.
        if output_kinds:
            completed = any(obj.kind in output_kinds and obj.status == "CONFIRMED" for obj in current_objects)
        status = "completed" if completed else ("ready" if assembled["ready"] else "blocked")
        if first_ready is None and status == "ready":
            first_ready = definition.id
        states.append({**definition.as_dict(), "status": status, "missing": assembled["missing"]})
    current = first_ready or next((item["id"] for item in states if item["status"] == "blocked"), STEPS[-1].id)
    return {"current_step": current, "steps": states}
