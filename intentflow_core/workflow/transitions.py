"""Allowed transitions are derived from formal outputs."""
def next_step(artifact_kind, action=""):
    if artifact_kind == "Context": return "problem-evidence"
    if artifact_kind == "Problem": return "specification"
    if artifact_kind == "Specification": return "engineering-intent"
    if artifact_kind == "EngineeringIntent": return "software-change"
    if artifact_kind == "ChangeRecord": return "verification"
    if artifact_kind == "Verification": return "runtime-outcome"
    if artifact_kind == "EngineeringEvaluation":
        return "problem-evidence" if action == "ADJUST" else "next-change"
    raise ValueError("No workflow transition for artifact")
