"""Trace graph helpers; evaluation-only data is never an artifact."""
def ancestors(service, project_id, objects):
    result, seen = [], set()
    def visit(obj):
        if obj.id in seen:
            return
        seen.add(obj.id)
        for source_id in obj.sources:
            source = service.artifact(project_id, source_id)
            visit(source)
        result.append(obj)
    for obj in objects:
        visit(obj)
    return result
