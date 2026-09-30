"""Incremental engineering workspace on the existing project API."""
from typing import Literal
from contextlib import asynccontextmanager
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update

from intentflow_core.models import EngineeringDraft, EngineeringObject, Revision, serialize, uid
from intentflow_core.versioning import Versioning, VersionConflict
from intentflow_core.behavior import Action, transition
from intentflow_core.impact import analyze
from intentflow_core.impact.runtime import ExecutionManager, evidence_state, public_run
from adapters.execution import capabilities
from adapters.git import commit, repository


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Change(Strict):
    id: str | None = Field(default=None, max_length=36)
    kind: Literal["RULE", "CODE", "TEST", "ARCHITECTURE"] | None = None
    title: str = Field(default="", max_length=300)
    content: dict = Field(default_factory=dict)
    delete: bool = False


class Relation(Strict):
    source_id: str = Field(min_length=1, max_length=36)
    target_id: str = Field(min_length=1, max_length=36)
    kind: Literal["implements", "verifies", "depends_on", "constrains", "supports", "refutes"]
    details: dict = Field(default_factory=dict)


class Confirm(Strict):
    expected_baseline_id: str
    confirmed: Literal[True]
    title: str = Field(min_length=1, max_length=300)
    changes: list[Change] = Field(default_factory=list, max_length=100)
    relations: list[Relation] = Field(default_factory=list, max_length=200)


class DraftInput(Strict):
    expected_baseline_id: str
    changes: list[Change] = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)


class DraftConfirm(Strict):
    expected_baseline_id: str
    confirmed: Literal[True]


class PrototypeInput(Strict):
    rule_id: str
    expected_baseline_id: str


class CodeSnapshot(DraftConfirm):
    ref: str = Field(default="HEAD", min_length=1, max_length=100)


class VerificationInput(DraftConfirm):
    mode: Literal["native", "docker"] = "native"
    trusted_project: bool = False
    full: bool = False
    request_id: str = Field(min_length=8, max_length=100)


def install_engineering(app, factory, data_root, root):
    router = APIRouter(prefix="/api/projects/{pid}/engineering")
    manager = ExecutionManager(factory, data_root)
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with previous_lifespan(application) as state:
            manager.start()
            try:
                # Backfill historical projects before concurrent browser reads.
                from intentflow_core.models import Project, SkillRun, Artifact
                with factory.begin() as session:
                    for pid in session.scalars(select(Project.id)):
                        Versioning(session).ensure(pid)
                    for pending in session.scalars(select(SkillRun).where(SkillRun.status == "GENERATING")):
                        pending.status = "ERROR"
                    for change in session.scalars(select(Artifact).where(Artifact.kind == "ChangeRecord")):
                        if change.data.get("status") == "VERIFYING":
                            change.data = {**change.data, "status": "OPEN"}
                yield state
            finally:
                manager.stop()

    app.router.lifespan_context = lifespan

    def operation(fn):
        with factory.begin() as session:
            return fn(session, Versioning(session))

    @router.get("")
    def workspace(pid: str):
        return operation(lambda s, v: v.state(pid))

    @router.post("/confirm")
    def confirm(pid: str, body: Confirm):
        return operation(lambda s, v: v.confirm(pid, body.expected_baseline_id,
            [c.model_dump(exclude_none=True) for c in body.changes], body.title,
            relations=[e.model_dump() for e in body.relations]))

    @router.post("/code-snapshot")
    def code_snapshot(pid: str, body: CodeSnapshot):
        def run(s, v):
            from intentflow_core.models import Project
            v.ensure(pid)
            p = s.get(Project, pid)
            if not p.repository:
                raise ValueError("请先连接代码仓库")
            ref = commit(repository(p.repository), body.ref)
            return v.confirm(pid, body.expected_baseline_id, [], "确认代码版本 " + ref[:8], code_commit=ref)
        return operation(run)

    @router.get("/impact")
    def impact(pid: str):
        return operation(lambda s, v: analyze(v, pid))

    @router.get("/evidence")
    def evidence(pid: str):
        return operation(lambda s, v: evidence_state(s, pid))

    @router.get("/execution-capabilities")
    def execution_capabilities(pid: str):
        return operation(lambda s, v: (v.ensure(pid), capabilities())[1])

    @router.post("/runs", status_code=202)
    def run_tests(pid: str, body: VerificationInput):
        with factory.begin() as s:
            job, created = manager.queue(s, pid, body.expected_baseline_id, mode=body.mode,
                trusted=body.trusted_project, full=body.full, request_id=body.request_id)
            result = public_run(job)
        if created:
            manager.dispatch(result["id"])
        return result

    @router.post("/runs/{jid}/cancel")
    def cancel_run(pid: str, jid: str):
        return operation(lambda s, v: manager.cancel(s, pid, jid))

    @router.get("/objects/{oid}/history")
    def history(pid: str, oid: str):
        def run(s, v):
            v.ensure(pid)
            obj = s.get(EngineeringObject, oid)
            if not obj or obj.project_id != pid:
                raise ValueError("对象不存在或属于其他项目")
            return [serialize(r) for r in s.scalars(select(Revision).where(Revision.object_id == oid)
                                                   .order_by(Revision.number))]
        return operation(run)

    @router.post("/drafts", status_code=201)
    def draft(pid: str, body: DraftInput):
        def run(s, v):
            state = v.ensure(pid)
            if state.baseline_id != body.expected_baseline_id:
                raise VersionConflict("需求已变化，请刷新后编辑候选")
            from intentflow_core.behavior import validate_object
            for change in body.changes:
                if not change.delete:
                    validate_object(change.kind, change.content)
            item = EngineeringDraft(project_id=pid, baseline_id=state.baseline_id,
                kind="REQUIREMENT", content={"title": body.title,
                    "changes": [c.model_dump(exclude_none=True) for c in body.changes]})
            s.add(item)
            s.flush()
            return serialize(item)
        return operation(run)

    @router.get("/drafts")
    def drafts(pid: str):
        def run(s, v):
            v.ensure(pid)
            return [serialize(d) for d in s.scalars(select(EngineeringDraft)
                .where(EngineeringDraft.project_id == pid).order_by(EngineeringDraft.created_at))]
        return operation(run)

    @router.post("/drafts/{did}/confirm")
    def accept_draft(pid: str, did: str, body: DraftConfirm):
        def run(s, v):
            item = s.get(EngineeringDraft, did)
            if not item or item.project_id != pid or item.kind != "REQUIREMENT" or item.status != "DRAFT":
                raise ValueError("候选不存在或已处理")
            if item.baseline_id != body.expected_baseline_id:
                raise VersionConflict("请根据候选生成时的基线审阅")
            claimed = s.execute(update(EngineeringDraft).where(EngineeringDraft.id == did,
                EngineeringDraft.status == "DRAFT").values(status="CONFIRMED"))
            if claimed.rowcount != 1:
                raise VersionConflict("候选已被其他操作处理，请刷新")
            result = v.confirm(pid, body.expected_baseline_id, item.content["changes"], item.content["title"])
            item.status = "CONFIRMED"
            return result
        return operation(run)

    @router.post("/drafts/{did}/cancel")
    def cancel_draft(pid: str, did: str):
        def run(s, v):
            v.ensure(pid)
            item = s.get(EngineeringDraft, did)
            if not item or item.project_id != pid or item.status != "DRAFT":
                raise ValueError("候选不存在或已处理")
            claimed = s.execute(update(EngineeringDraft).where(EngineeringDraft.id == did,
                EngineeringDraft.status == "DRAFT").values(status="CANCELLED"))
            if claimed.rowcount != 1:
                raise VersionConflict("候选已被其他操作处理，请刷新")
            return serialize(item)
        return operation(run)

    @router.post("/prototypes", status_code=201)
    def prototype(pid: str, body: PrototypeInput):
        def run(s, v):
            state = v.ensure(pid)
            if state.baseline_id != body.expected_baseline_id:
                raise VersionConflict("请先刷新当前需求版本")
            rule = next((o for o in v.objects(pid) if o["id"] == body.rule_id and o["kind"] == "RULE"), None)
            if not rule:
                raise ValueError("请选择当前基线中的业务规则")
            item = EngineeringDraft(project_id=pid, baseline_id=state.baseline_id, kind="PROTOTYPE",
                content={"rule_id": rule["id"], "rule_revision": rule["revision_id"], "state": {"entries": []}, "events": []})
            s.add(item)
            s.flush()
            return serialize(item)
        return operation(run)

    @router.post("/prototypes/{sid}/actions")
    def prototype_action(pid: str, sid: str, body: Action):
        def run(s, v):
            item = s.get(EngineeringDraft, sid)
            if not item or item.project_id != pid or item.kind != "PROTOTYPE":
                raise ValueError("原型会话不存在")
            if item.baseline_id != v.ensure(pid).baseline_id:
                raise VersionConflict("规则版本已变化，请按最新规则重新开始预览；旧轨迹仍保留")
            if len(item.content["events"]) >= 1000:
                raise ValueError("本次预览已达到 1000 步，请新建预览")
            rule = s.get(Revision, item.content["rule_revision"])
            outcome = transition(rule.content, item.content["state"], body.model_dump())
            previous = item.content
            updated = {**previous, "state": outcome["state"], "events": previous["events"] + [outcome]}
            changed = s.execute(update(EngineeringDraft).where(EngineeringDraft.id == sid,
                EngineeringDraft.content == previous).values(content=updated))
            if changed.rowcount != 1:
                raise VersionConflict("原型被另一个操作更新，请刷新后重试")
            s.flush()
            return {"session": serialize(item), "outcome": outcome}
        return operation(run)

    from apps.api.engineering_extensions import install_extensions
    install_extensions(router, factory, Strict, DraftConfirm)
    from apps.api.training import install_training
    install_training(app, router, factory, data_root, root, DraftConfirm)
    app.include_router(router)
    return router
