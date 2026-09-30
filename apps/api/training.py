"""Local practice endpoints reuse versioned rules, evidence and event records."""
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from typing import Literal

from intentflow_core.models import EngineeringDraft, serialize
from intentflow_core.service import Service
from intentflow_core.training import CASES, create_case, score
from intentflow_core.versioning import Versioning, VersionConflict
from intentflow_core.impact import analyze
from intentflow_core.impact.runtime import evidence_state


def install_training(app, router, factory, data_root, root, DraftConfirm):
    cases_router = APIRouter(prefix="/api/engineering")

    class CreateCase(BaseModel):
        model_config = ConfigDict(extra="forbid")
        domain: Literal["campus", "inventory", "reservation"]
        confirmed: Literal[True]

    class TrainingStart(DraftConfirm):
        rule_id: str | None = None

    @cases_router.get("/cases")
    def cases():
        return [{"domain": domain, **config} for domain, config in CASES.items()]

    @cases_router.post("/cases", status_code=201)
    def new_case(body: CreateCase):
        with factory.begin() as s:
            return serialize(create_case(Service(s, data_root, root), body.domain))

    @router.post("/impact-review")
    def impact_review(pid: str, body: DraftConfirm):
        with factory.begin() as s:
            v = Versioning(s)
            if v.ensure(pid).baseline_id != body.expected_baseline_id:
                raise VersionConflict("基线已更新，请刷新后审阅影响")
            plan = analyze(v, pid)
            v.event(pid, "IMPACT_REVIEWED", {"baseline_id": body.expected_baseline_id,
                                           "affected": plan["affected"], "unknown": plan["unknown"]})
            return plan

    @router.post("/training", status_code=201)
    def start(pid: str, body: TrainingStart):
        with factory.begin() as s:
            v = Versioning(s)
            baseline = v.baseline(pid)
            if baseline.id != body.expected_baseline_id:
                raise VersionConflict("请刷新后开始实践")
            rules = [o for o in v.objects(pid) if o["kind"] == "RULE"]
            if not rules:
                raise ValueError("请先登记一条容量小于上限的领域规则")
            rule = next((r for r in rules if r["id"] == body.rule_id), None) if body.rule_id else rules[0]
            if not rule or rule["content"]["capacity"] >= 100000:
                raise ValueError("请选择容量小于上限的当前业务规则")
            evidence = evidence_state(s, pid)
            if not evidence["baseline_supported"]:
                raise ValueError("请先完成当前版本的复验，再开始需求变更实践")
            item = EngineeringDraft(project_id=pid, baseline_id=baseline.id, kind="TRAINING",
                content={"scenario_version": "1", "seed": 0, "rule_id": rule["id"],
                    "initial_code_commit": baseline.code_commit, "initial_supported": evidence["baseline_supported"],
                    "target_capacity": rule["content"]["capacity"] + 1,
                    "prompt": "临时需求：容量增加 1。先审阅影响，再在开发工具中修改默认容量及相应测试，审阅新映射并复验。"})
            s.add(item)
            s.flush()
            v.event(pid, "TRAINING_STARTED", {"session_id": item.id, "scenario_version": "1", "seed": 0})
            return serialize(item)

    def get_session(s, pid, sid):
        item = s.get(EngineeringDraft, sid)
        if not item or item.project_id != pid or item.kind != "TRAINING":
            raise ValueError("实践会话不存在")
        return item

    @router.post("/training/{sid}/change")
    def inject(pid: str, sid: str, body: DraftConfirm):
        with factory.begin() as s:
            v = Versioning(s)
            item = get_session(s, pid, sid)
            if item.status != "DRAFT" or item.content.get("change_baseline"):
                raise ValueError("本次事件已经注入或实践已结束")
            if item.baseline_id != body.expected_baseline_id:
                raise VersionConflict("开始实践后规则已变化，请新建实践会话")
            rule = next((o for o in v.objects(pid) if o["id"] == item.content["rule_id"]), None)
            if not rule:
                raise ValueError("情境规则已移除，请重新开始")
            result = v.confirm(pid, body.expected_baseline_id, [{"id": rule["id"], "kind": "RULE",
                "title": rule["title"], "content": {**rule["content"], "capacity": item.content["target_capacity"]}}],
                "确认实践事件：容量增加 1")
            item.content = {**item.content, "change_baseline": result["id"]}
            v.event(pid, "TRAINING_CHANGE", {"session_id": sid, "baseline_id": result["id"]})
            return serialize(item)

    @router.get("/training/{sid}/score")
    def current_score(pid: str, sid: str):
        with factory.begin() as s:
            item = get_session(s, pid, sid)
            return item.content["submission"] if item.status == "SUBMITTED" else score(s, pid, item)

    @router.post("/training/{sid}/submit")
    def submit(pid: str, sid: str, body: DraftConfirm):
        with factory.begin() as s:
            v = Versioning(s)
            item = get_session(s, pid, sid)
            if item.status != "DRAFT":
                raise ValueError("本次实践已提交，请新建会话后继续")
            if v.ensure(pid).baseline_id != body.expected_baseline_id:
                raise VersionConflict("提交基线已经变化，请重新审阅")
            report = score(s, pid, item)
            item.content = {**item.content, "submission": report}
            item.status = "SUBMITTED"
            v.event(pid, "TRAINING_SUBMITTED", {"session_id": sid, "report": report})
            return serialize(item)

    app.include_router(cases_router)
