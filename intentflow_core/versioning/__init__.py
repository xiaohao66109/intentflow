"""Shared identities, immutable revisions and compare-and-swap baselines."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from sqlalchemy import select, update

from intentflow_core.models import (
    Artifact, ArtifactScope, Baseline, EngineeringEvent, EngineeringObject,
    Iteration, Project, ProjectState, Revision, TypedRelation, serialize, uid,
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


class VersionConflict(ValueError):
    pass


class Versioning:
    def __init__(self, session):
        self.s = session

    def ensure(self, pid):
        if not self.s.get(Project, pid):
            raise ValueError("项目不存在")
        state = self.s.get(ProjectState, pid)
        if state:
            return state
        baseline = Baseline(id=uid(), project_id=pid, title="V1.0 历史基线", members={})
        self.s.add(baseline)
        self.s.flush()
        iteration = Iteration(id=uid(), project_id=pid, baseline_id=baseline.id, number=1)
        self.s.add(iteration)
        self.s.flush()
        state = ProjectState(project_id=pid, baseline_id=baseline.id, iteration_id=iteration.id, generation=0)
        self.s.add(state)
        self.s.flush()
        # Additive migration: preserve the original artifacts and IDs. Unrecorded
        # historic versions are deliberately not invented.
        artifacts = list(self.s.scalars(select(Artifact).where(Artifact.project_id == pid)))
        for artifact in artifacts:
            self.record_artifact(artifact, state)
        self.event(pid, "MIGRATED", {"baseline_id": baseline.id, "artifact_count": len(artifacts),
                                    "history": "旧版未记录的修订和关系保持未知"})
        return state

    def event(self, pid, kind, details):
        item = EngineeringEvent(project_id=pid, kind=kind, details=deepcopy(details))
        self.s.add(item)
        self.s.flush()
        return item

    def record_artifact(self, artifact, state=None):
        state = state or self.ensure(artifact.project_id)
        if not self.s.get(EngineeringObject, artifact.id):
            rid = uid()
            self.s.add(EngineeringObject(id=artifact.id, project_id=artifact.project_id,
                                         kind=artifact.kind, current_revision=rid))
            self.s.flush()
            self.s.add(Revision(id=rid, object_id=artifact.id, number=1,
                                title=artifact.title, content=deepcopy(artifact.data),
                                content_hash=digest(artifact.data), actor=artifact.actor))
            self.s.flush()
        if not self.s.get(ArtifactScope, artifact.id):
            self.s.add(ArtifactScope(artifact_id=artifact.id, iteration_id=state.iteration_id,
                                     baseline_id=state.baseline_id))
            self.s.flush()

    def current_artifacts(self, pid):
        state = self.ensure(pid)
        # Evidence/context may be consulted as explicitly inherited historical
        # input. Formal outcomes from other iterations never count as completion.
        items = list(self.s.scalars(select(Artifact).where(Artifact.project_id == pid)
                                   .order_by(Artifact.created_at, Artifact.id)))
        return [item for item in items if item.kind in {"Evidence", "Context"}
                or (self.s.get(ArtifactScope, item.id)
                    and self.s.get(ArtifactScope, item.id).iteration_id == state.iteration_id)]

    def baseline(self, pid, bid=None):
        state = self.ensure(pid)
        baseline = self.s.get(Baseline, bid or state.baseline_id)
        if not baseline or baseline.project_id != pid:
            raise ValueError("基线不存在或属于其他项目")
        return baseline

    def objects(self, pid, bid=None):
        baseline = self.baseline(pid, bid)
        result = []
        for oid, rid in baseline.members.items():
            obj, rev = self.s.get(EngineeringObject, oid), self.s.get(Revision, rid)
            if not obj or not rev or obj.project_id != pid or rev.object_id != oid:
                raise ValueError("基线引用损坏，请从备份恢复后核对")
            result.append({"id": oid, "kind": obj.kind, "revision_id": rid, "number": rev.number,
                           "title": rev.title, "content": deepcopy(rev.content), "content_hash": rev.content_hash})
        return result

    def confirm(self, pid, expected, changes, title, *, code_commit=None, relations=()):
        """One transaction publishes an entire reviewed change set, or nothing."""
        state = self.ensure(pid)
        if not expected or state.baseline_id != expected:
            raise VersionConflict("需求版本已经变化，请刷新、审阅最新差异后重新确认")
        if not changes and not relations and code_commit is None:
            raise ValueError("没有需要确认的变化")
        # Claim the project BEFORE inserting revision numbers. Concurrent
        # confirmations then produce an explicit stale-version response instead
        # of colliding on the unique (object_id, revision_number) constraint.
        generation = state.generation
        claimed = self.s.execute(update(ProjectState).where(ProjectState.project_id == pid,
            ProjectState.baseline_id == expected, ProjectState.generation == generation)
            .values(generation=generation + 1).execution_options(synchronize_session=False))
        if claimed.rowcount != 1:
            raise VersionConflict("其他操作已经更新需求，请刷新后重新确认")
        base = self.baseline(pid)
        members = dict(base.members)
        # Rules are revised before test mappings in the same reviewed batch.
        changes = sorted(deepcopy(changes), key=lambda c: c.get("kind") != "RULE")
        changed = []
        from intentflow_core.behavior import validate_object
        for item in changes:
            oid = item.get("id") or uid()
            if oid in changed:
                raise ValueError("同一对象不能在一次确认中重复修改")
            existing = self.s.get(EngineeringObject, oid)
            if existing and (existing.project_id != pid or oid not in members):
                raise ValueError("对象不存在于当前基线或属于其他项目")
            if item.get("delete"):
                if not existing:
                    raise ValueError("不能删除不存在的对象")
                members.pop(oid)
                changed.append(oid)
                continue
            kind = item.get("kind") or (existing.kind if existing else "")
            if existing and existing.kind != kind:
                raise ValueError("对象类型不可改变")
            content = item.get("content", {})
            content = validate_object(kind, content)
            if kind == "TEST":
                rule_map = {}
                for rule_id in content["rule_ids"]:
                    rule_object = self.s.get(EngineeringObject, rule_id)
                    if rule_id not in members or not rule_object or rule_object.kind != "RULE":
                        raise ValueError("测试只能映射当前基线内的业务规则")
                    rule_map[rule_id] = members[rule_id]
                # The server binds the human-reviewed test to exact revisions.
                # Changing only a rule cannot silently re-approve the old test.
                content["rule_revisions"] = rule_map
            if not str(item.get("title", "")).strip() or len(item["title"]) > 300:
                raise ValueError("请输入不超过 300 字的标题")
            previous = self.s.get(Revision, members[oid]) if existing else None
            rid = uid()
            if existing:
                existing.current_revision = rid
            else:
                self.s.add(EngineeringObject(id=oid, project_id=pid, kind=kind, current_revision=rid))
                self.s.flush()
            revision = Revision(id=rid, object_id=oid, number=previous.number + 1 if previous else 1,
                                parent_id=previous.id if previous else "", title=item["title"],
                                content=content, content_hash=digest(content))
            self.s.add(revision)
            members[oid] = rid
            changed.append(oid)
        bid, iid = uid(), uid()
        baseline = Baseline(id=bid, project_id=pid, parent_id=base.id, title=title,
                            members=members, code_commit=base.code_commit if code_commit is None else code_commit)
        self.s.add(baseline)
        self.s.flush()
        iteration = Iteration(id=iid, project_id=pid, baseline_id=bid, number=generation + 2)
        self.s.add(iteration)
        self.s.flush()
        claimed = self.s.execute(update(ProjectState).where(ProjectState.project_id == pid,
            ProjectState.baseline_id == expected, ProjectState.generation == generation + 1)
            .values(baseline_id=bid, iteration_id=iid)
            .execution_options(synchronize_session=False))
        if claimed.rowcount != 1:
            raise VersionConflict("其他操作已经更新需求，请刷新后重新确认")
        self.s.expire(state)
        # Relations are baseline snapshots, including relation-only revisions.
        prior = list(self.s.scalars(select(TypedRelation).where(TypedRelation.baseline_id == expected)))
        edge_keys = set()
        for edge in [dict(source_id=e.source_id, target_id=e.target_id, kind=e.kind, details=e.details) for e in prior] + list(relations):
            key = (edge["source_id"], edge["target_id"], edge["kind"])
            if key in edge_keys:
                continue
            if edge["source_id"] not in members or edge["target_id"] not in members:
                if edge in relations:
                    raise ValueError("关系只能引用同一基线内的对象")
                continue
            if edge["kind"] not in {"implements", "verifies", "depends_on", "constrains", "supports", "refutes"}:
                raise ValueError("不支持的关系类型")
            self.s.add(TypedRelation(project_id=pid, baseline_id=bid, source_id=edge["source_id"],
                                    target_id=edge["target_id"], kind=edge["kind"], details=edge.get("details", {})))
            edge_keys.add(key)
        self.event(pid, "BASELINE_CONFIRMED", {"baseline_id": bid, "previous": expected, "changed": changed})
        self.s.flush()
        return serialize(baseline)

    def state(self, pid):
        state = self.ensure(pid)
        return {**serialize(state), "baseline": serialize(self.baseline(pid)), "objects": self.objects(pid),
                "history": [serialize(b) for b in self.s.scalars(select(Baseline).where(Baseline.project_id == pid)
                                                               .order_by(Baseline.created_at))],
                "relations": [serialize(e) for e in self.s.scalars(select(TypedRelation)
                    .where(TypedRelation.baseline_id == state.baseline_id))]}
