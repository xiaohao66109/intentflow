"""Human-readable next action."""
def describe(workflow):
    current = next(item for item in workflow["steps"] if item["id"] == workflow["current_step"])
    if current["status"] == "blocked":
        return "缺少：" + "、".join(current["missing"])
    return current["next_action"]
