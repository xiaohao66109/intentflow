"""Conservative typed-graph propagation and explicit test-selection reasons."""
from collections import defaultdict, deque
from fnmatch import fnmatchcase
from sqlalchemy import select
from intentflow_core.models import TypedRelation


def analyze(versioning, pid, before_id=None):
    current = versioning.baseline(pid)
    before = versioning.baseline(pid, before_id or current.parent_id) if (before_id or current.parent_id) else None
    objects = {o["id"]: o for o in versioning.objects(pid)}
    previous = {o["id"]: o for o in versioning.objects(pid, before.id)} if before else {}
    changed = {oid for oid in set(objects) | set(previous)
               if objects.get(oid, {}).get("revision_id") != previous.get(oid, {}).get("revision_id")}
    edges = defaultdict(list)
    relations = list(versioning.s.scalars(select(TypedRelation).where(
        TypedRelation.baseline_id.in_([current.id] + ([before.id] if before else [])))))
    for relation in relations:
        a, b = relation.source_id, relation.target_id
        if relation.kind in {"implements", "verifies", "depends_on"}:
            a, b = b, a
        edges[a].append((b, relation.kind))
    combined = {**previous, **objects}
    for obj in combined.values():
        if obj["kind"] == "TEST":
            for rid in obj["content"]["rule_ids"]:
                edges[rid].append((obj["id"], "verifies"))
            for code in combined.values():
                if code["kind"] == "CODE" and code["content"]["path"] in obj["content"]["code_paths"]:
                    edges[code["id"]].append((obj["id"], "code_test_mapping"))
        if obj["kind"] == "ARCHITECTURE":
            for code in combined.values():
                if code["kind"] == "CODE" and fnmatchcase(code["content"]["path"], obj["content"]["scope"]):
                    edges[obj["id"]].append((code["id"], "constrains"))
                    edges[code["id"]].append((obj["id"], "architecture_scan"))
    paths = {oid: [{"id": oid, "reason": "内容或引用修订改变"}] for oid in changed}
    queue = deque(sorted(changed))
    while queue:
        source = queue.popleft()
        for target, kind in edges[source]:
            if target not in paths:
                paths[target] = paths[source] + [{"id": target, "reason": kind}]
                queue.append(target)
    tests = [o for o in objects.values() if o["kind"] == "TEST"]
    unknown = []
    for oid in changed:
        obj = combined[oid]
        if obj["kind"] in {"RULE", "CODE"}:
            reachable = set()
            pending = [oid]
            while pending:
                node = pending.pop()
                if node in reachable:
                    continue
                reachable.add(node)
                pending.extend(target for target, _ in edges[node])
            if not any(t["id"] in reachable for t in tests):
                unknown.append({"id": oid, "reason": "没有可确认的测试覆盖，扩大复验范围"})
    if before and before.code_commit != current.code_commit:
        unknown.append({"id": "code_commit", "reason": "代码版本变化，保守复验全部已登记测试"})
    if not tests:
        unknown.append({"id": "coverage", "reason": "尚未登记真实测试，不能恢复工程结论"})
    selected = tests if unknown else [t for t in tests if t["id"] in paths]
    mapping_gaps = [t["id"] for t in selected if any(
        current.members.get(rid) != t["content"].get("rule_revisions", {}).get(rid)
        for rid in t["content"]["rule_ids"])]
    return {"baseline_id": current.id, "previous_baseline_id": before.id if before else "",
            "changed": sorted(changed), "affected": sorted(paths),
            "paths": paths, "unknown": unknown, "tests": selected,
            "test_mapping_gaps": mapping_gaps,
            "next_action": "请审阅测试是否覆盖新规则并重新确认测试映射" if mapping_gaps else
                           "请登记真实测试" if not tests else "审阅复验计划并选择执行环境"}
