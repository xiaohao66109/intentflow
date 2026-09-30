"""Property example actions use the existing project, evidence and review workflow."""
import json
import sys
import tempfile
import threading
from pathlib import Path
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from adapters.git import git, commit, repository
from adapters.execution import snapshot, bounded_run
from intentflow_core.models import Artifact, EngineeringDraft, serialize
from intentflow_core.service import Service
from intentflow_core.versioning import Versioning, VersionConflict
from intentflow_core.property_case import require_property, change_preview, apply_fix, run_replay
from intentflow_core.property_behavior import ACTORS, STATUS, simulate


def install_property_case(app, factory, data_root, root):
    router = APIRouter(prefix="/api/projects/{pid}/property")

    class Strict(BaseModel):
        model_config = ConfigDict(extra="forbid")

    class VersionInput(Strict):
        specification_id: str

    class ActionInput(Strict):
        actor: Literal["resident-a", "resident-b", "dispatcher", "worker-a", "worker-b"]
        event: Literal["submit", "accept", "assign", "start", "set_contact", "complete", "close", "cancel", "reopen", "view"]
        ticket_id: str = ""
        title: str = Field(default="", max_length=300)
        location: str = Field(default="", max_length=300)
        assignee: str = "worker-a"
        at: int = Field(default=540, ge=0, le=1000000)
        contact_at: int | None = Field(default=None, ge=0, le=1000000)
        result: str = Field(default="", max_length=3000)

    class DecisionInput(VersionInput):
        option: Literal["display", "sms", "promise"]
        reason: str = Field(min_length=1, max_length=3000)

    class Confirm(Strict):
        confirmed: Literal[True]

    def operation(pid, fn):
        with factory.begin() as s:
            svc = Service(s, data_root, root)
            require_property(svc, pid)
            return fn(svc, Versioning(s))

    def current_spec(svc, pid):
        return next((a for a in reversed(Versioning(svc.s).current_artifacts(pid)) if a.kind == "Specification"), None)

    def check_spec(svc, pid, expected):
        spec = current_spec(svc, pid)
        if not spec or spec.id != expected:
            raise VersionConflict("需求已经变化，请按当前已确认需求重新开始")
        return spec

    @router.get("")
    def state(pid: str):
        def read(svc, v):
            spec = current_spec(svc, pid)
            drafts = list(svc.s.scalars(select(EngineeringDraft).where(EngineeringDraft.project_id == pid,
                EngineeringDraft.kind.in_(["PROPERTY_PROTOTYPE", "PROPERTY_DECISION", "PROPERTY_CHECK"])).order_by(EngineeringDraft.created_at)))
            return {"specification_id": spec.id if spec else "", "drafts": [serialize(d) for d in drafts],
                    "actors": [{"id": key, "role": role, "name": name} for key, (role, name) in ACTORS.items()],
                    "statuses": STATUS, "base_commit": svc.project(pid).details["base_commit"]}
        return operation(pid, read)

    @router.post("/prototypes", status_code=201)
    def start(pid: str, body: VersionInput):
        def run(svc, v):
            check_spec(svc, pid, body.specification_id)
            item = EngineeringDraft(project_id=pid, baseline_id=v.ensure(pid).baseline_id, kind="PROPERTY_PROTOTYPE",
                content={"specification_id": body.specification_id, "state": {"tickets": [], "next_number": 1}, "events": []})
            svc.s.add(item); svc.s.flush()
            v.event(pid, "PROPERTY_PROTOTYPE_STARTED", {"session_id": item.id, "specification_id": body.specification_id})
            return serialize(item)
        return operation(pid, run)

    @router.post("/prototypes/{sid}/actions")
    def perform(pid: str, sid: str, body: ActionInput):
        def run(svc, v):
            item = svc.s.get(EngineeringDraft, sid)
            if not item or item.project_id != pid or item.kind != "PROPERTY_PROTOTYPE":
                raise ValueError("报修体验记录不存在")
            check_spec(svc, pid, item.content["specification_id"])
            if len(item.content["events"]) >= 500:
                raise ValueError("本次体验已满，请重新开始")
            previous = item.content
            result = simulate(previous["state"], body.model_dump())
            content = {**previous, "state": result["state"], "events": previous["events"] + [{**body.model_dump(), "accepted": result["accepted"], "reason": result["reason"]}]}
            changed = svc.s.execute(update(EngineeringDraft).where(EngineeringDraft.id == sid,
                EngineeringDraft.content == previous).values(content=content).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                raise VersionConflict("另一项操作已更新体验记录，请刷新后重试")
            svc.s.refresh(item)
            return {"session": serialize(item), "accepted": result["accepted"], "reason": result["reason"]}
        return operation(pid, run)

    @router.post("/decisions", status_code=201)
    def decide(pid: str, body: DecisionInput):
        def run(svc, v):
            check_spec(svc, pid, body.specification_id)
            if not body.reason.strip():
                raise ValueError("请填写选择方案的理由")
            item = EngineeringDraft(project_id=pid, baseline_id=v.ensure(pid).baseline_id, kind="PROPERTY_DECISION", status="CONFIRMED", content=body.model_dump())
            svc.s.add(item); svc.s.flush()
            v.event(pid, "PROPERTY_DECISION_SAVED", {"decision_id": item.id, "option": body.option})
            return serialize(item)
        return operation(pid, run)

    @router.get("/change-preview")
    def preview(pid: str):
        return operation(pid, lambda svc, v: {"diff": change_preview(svc, pid)[2]})

    @router.post("/apply-fix")
    def fix(pid: str, body: Confirm):
        return operation(pid, lambda svc, v: apply_fix(svc, pid))

    @router.post("/baseline-check")
    def baseline_check(pid: str, body: Confirm):
        def run(svc, v):
            p = svc.project(pid)
            with tempfile.TemporaryDirectory(prefix="intentflow-property-check-") as temp:
                root = Path(temp)
                checkout = root / "snapshot"
                ref = snapshot(p.repository, p.details["base_commit"], checkout, allowed_destination_root=root)
                result = bounded_run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], checkout, threading.Event())
            item = EngineeringDraft(project_id=pid, baseline_id=v.ensure(pid).baseline_id, kind="PROPERTY_CHECK", status="CONFIRMED",
                content={"code_commit": ref, "source": "初始版本真实测试", **result})
            svc.s.add(item); svc.s.flush()
            return serialize(item)
        return operation(pid, run)

    @router.post("/replay")
    def replay(pid: str, body: Confirm):
        return operation(pid, lambda svc, v: run_replay(svc, pid))

    app.include_router(router)
