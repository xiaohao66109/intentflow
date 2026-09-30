"""Local single-user API. Start with python -m uvicorn apps.api.main:app."""
import os
import subprocess
import threading
import httpx
from pathlib import Path
from typing import Literal, Annotated
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict, SecretStr
from sqlalchemy import select
from intentflow_core.models import database, Project, Artifact, SkillRun, serialize
from intentflow_core.service import Service, SINGLETON_FORMAL_KINDS
from skill_runtime import catalog
from adapters.llm import public_catalog
from adapters.llm.openai_compatible import OpenAICompatibleProvider
from adapters.llm.providers import PROVIDERS
from intentflow_core.versioning import VersionConflict, Versioning
from apps.api.engineering import install_engineering
from intentflow_core.release import VERSION, RELEASE_STAGE

ROOT = Path(__file__).resolve().parents[2]

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class NewProject(Strict):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    mode: Literal["blank", "git", "case", "property", "benchmark"] = "blank"
    repository: str = ""
    branch: str = ""
    base_commit: str = "HEAD"
    problem_statement: str = ""
    raw_materials: list = []
    manifest_path: str = ""
    ai_enabled: bool = False
    ai_provider: Literal["bigmodel", "siliconflow"] = "bigmodel"
    ai_model: str = "glm-4-flash-250414"
    api_key: SecretStr | None = None
    iteration_count: int = Field(default=4, ge=4, le=8)
    iteration_length_weeks: int = Field(default=2, ge=1, le=4)
    iteration_goals: list[str] = Field(default_factory=list, max_length=8)

class EvidenceInput(Strict):
    title: str = Field(min_length=1, max_length=300)
    type: Literal["User Feedback", "Runtime Log", "Metric", "Business Data", "Issue", "Observation", "Interview", "Document", "Manual Observation"]
    content: str = Field(min_length=1, max_length=100000)

class RuntimeInput(Strict):
    title: str = Field(min_length=1)
    verification_id: str
    content: str = Field(min_length=1)
    metrics: dict[str, Annotated[float, Field(strict=True, allow_inf_nan=False)]]

class RepositoryInput(Strict):
    repository: str = Field(min_length=1)

class ProjectDescriptionInput(Strict):
    description: str = Field(min_length=1, max_length=10000)

class RunInput(Strict):
    skill_id: str
    sources: list[str] = []
    mode: Literal["manual", "llm"] = "manual"

class WorkflowRunInput(Strict):
    mode: Literal["manual", "llm"] | None = None

class AITestInput(Strict):
    provider: Literal["bigmodel", "siliconflow"] = "bigmodel"
    model: str = Field(min_length=1, max_length=200)
    api_key: SecretStr

class ReviewInput(Strict):
    decision: Literal["accept", "reject"]
    output: dict
    checklist: list[bool] = []

class ChangeInput(Strict):
    intent_id: str
    branch: str = ""

class SubmitInput(Strict):
    final_commit: str = "HEAD"
    execute_tests: Literal[True]

class ExplainInput(Strict):
    verification_id: str

def create_app(url=None, data_root=None, provider_client=None, *, allow_database_migration=None,
               allow_repository_path_repair=None):
    data = Path(data_root or os.environ.get("INTENTFLOW_DATA_DIR", ROOT / ".intentflow-data")).resolve()
    data.mkdir(parents=True, exist_ok=True)
    if allow_database_migration is None:
        allow_database_migration = os.environ.get("INTENTFLOW_ALLOW_DATABASE_MIGRATION") == "1"
    engine, factory = database(
        url or os.environ.get("INTENTFLOW_DATABASE_URL", "sqlite:///" + (data / "intentflow.db").as_posix()),
        allow_migration=allow_database_migration,
    )
    app = FastAPI(title="IntentFlow", version=VERSION)
    app.state.engine = engine

    # Built-in reference copy may be corrected between releases. Refresh only
    # untouched legacy text in pending example drafts; user edits are preserved.
    from intentflow_core.property_case import refresh_legacy_reference_drafts
    app.state.reference_drafts_refreshed = refresh_legacy_reference_drafts(factory)

    # Moving a local data directory can leave stored absolute repository paths stale.
    # Detect that condition on startup, but never rewrite records without explicit consent.
    from intentflow_core.projects import rebase_repository_path, repair_repository_paths
    repair_candidates = 0
    repositories_root = data / "repositories"
    if repositories_root.is_dir():
        with factory() as session:
            for project in session.scalars(select(Project)):
                stored = str(project.repository or "").strip()
                candidate = rebase_repository_path(stored, repositories_root)
                if stored and not Path(stored).is_dir() and candidate is not None and candidate.is_dir():
                    repair_candidates += 1
    if allow_repository_path_repair is None:
        allow_repository_path_repair = os.environ.get("INTENTFLOW_ALLOW_REPOSITORY_PATH_REPAIR") == "1"
    repaired = repair_repository_paths(factory, data) if allow_repository_path_repair else 0
    app.state.repository_paths = {"repair_candidates": repair_candidates, "repaired": repaired,
                                  "automatic_repair": bool(allow_repository_path_repair)}
    if repaired:
        print(f"IntentFlow: repaired {repaired} stale repository path(s) under {data}")

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in {f"http://{request.headers.get('host')}", "http://localhost:5173", "http://127.0.0.1:5173"}:
            return JSONResponse({"detail": "Cross-origin access refused"}, status_code=403)
        if request.headers.get("host", "").split(":")[0] not in {"localhost", "127.0.0.1", "testserver"}:
            return JSONResponse({"detail": "Local host required"}, status_code=403)
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(VersionConflict)
    async def version_conflict(request, exc):
        return JSONResponse({"detail": str(exc), "code": "STALE_BASELINE"}, status_code=409)

    @app.exception_handler(subprocess.TimeoutExpired)
    async def git_timeout(request, exc):
        return JSONResponse({"detail": "Git operation timed out; check repository size and accessibility"}, status_code=400)

    @app.exception_handler(httpx.HTTPError)
    async def provider_error(request, exc):
        return JSONResponse({"detail": "智能模型服务请求失败，请检查接口密钥、模型名称和网络连接，或改用手工模式。"}, status_code=502)

    def operation(fn):
        with factory.begin() as session:
            return fn(Service(session, data, ROOT))

    @app.get("/api/health")
    def health():
        return {"status": "ok", "application": "IntentFlow", "version": VERSION,
                "release_stage": RELEASE_STAGE, "ai": "project-configured", "engineering_workspace": True,
                "formal_hidden_evaluation": False, "repository_paths": app.state.repository_paths}

    @app.get("/api/ai/providers")
    def ai_providers():
        return public_catalog()

    @app.post("/api/ai/test")
    def test_ai(body: AITestInput):
        provider_config = PROVIDERS[body.provider]
        provider = OpenAICompatibleProvider(body.provider, provider_config["endpoint"], body.model,
                                            body.api_key.get_secret_value(), provider_client)
        return provider.test_connection()

    @app.get("/api/skills")
    def skills():
        return catalog()

    @app.get("/api/projects")
    def projects():
        return operation(lambda svc: [serialize(p) for p in svc.s.scalars(select(Project).order_by(Project.created_at))])

    @app.post("/api/projects", status_code=201)
    def add_project(body: NewProject):
        ai = {"enabled": body.ai_enabled, "provider": body.ai_provider, "model": body.ai_model,
              "api_key": body.api_key.get_secret_value() if body.api_key else ""}
        return operation(lambda svc: serialize(svc.create_project(body.name, body.description, body.mode,
            body.repository, branch=body.branch, base_commit=body.base_commit,
            problem_statement=body.problem_statement, raw_materials=body.raw_materials,
            manifest_path=body.manifest_path, ai=ai, iteration_count=body.iteration_count,
            iteration_length_weeks=body.iteration_length_weeks,
            iteration_goals=body.iteration_goals)))

    @app.get("/api/projects/{pid}/context")
    def project_context(pid: str):
        return operation(lambda svc: svc.project_context(pid))

    @app.patch("/api/projects/{pid}")
    def update_project(pid: str, body: ProjectDescriptionInput):
        return operation(lambda svc: serialize(svc.update_project_description(pid, body.description)))

    @app.post("/api/projects/{pid}/repository")
    def link_repository(pid: str, body: RepositoryInput):
        return operation(lambda svc: serialize(svc.link_repository(pid, body.repository)))

    @app.get("/api/projects/{pid}/artifacts")
    def artifacts(pid: str):
        def run(svc):
            svc.project(pid)
            current = {o.id for o in Versioning(svc.s).current_artifacts(pid)}
            items = list(svc.s.scalars(select(Artifact).where(Artifact.project_id == pid)
                                       .order_by(Artifact.created_at, Artifact.id)))
            active = {}
            for item in items:
                if (item.id in current and item.kind in SINGLETON_FORMAL_KINDS
                        and item.status == "CONFIRMED"):
                    active[(item.workflow_step, item.kind)] = item.id
            return [{**serialize(item), "current_iteration": item.id in current,
                     "current_result": item.kind not in SINGLETON_FORMAL_KINDS or
                     active.get((item.workflow_step, item.kind)) == item.id}
                    for item in items]
        return operation(run)

    @app.get("/api/projects/{pid}/workflow")
    def workflow(pid: str):
        return operation(lambda svc: svc.workflow(pid))

    @app.get("/api/projects/{pid}/workflow/{step_id}/input")
    def workflow_input(pid: str, step_id: str):
        return operation(lambda svc: svc.workflow_input(pid, step_id))

    @app.post("/api/projects/{pid}/workflow/{step_id}/runs", status_code=201)
    def workflow_run(pid: str, step_id: str, body: WorkflowRunInput):
        def run(svc):
            selected = body.mode or ("llm" if svc.project(pid).details.get("ai", {}).get("enabled") else "manual")
            provider = svc.project_provider(pid, provider_client) if selected == "llm" else None
            return serialize(svc.start_workflow_skill(pid, step_id, selected, provider, defer=True)), provider
        return generate_outside_transaction(pid, run)

    def generate_outside_transaction(pid, prepare):
        item, provider = operation(prepare)
        if item["mode"] != "llm":
            return item
        try:
            from skill_runtime import load
            response = provider.suggest(load(item["skill_id"]), item["inputs"])
            return operation(lambda svc: serialize(svc.complete_suggestion(pid, item["id"], response, provider)))
        except Exception:
            with factory.begin() as s:
                pending = s.get(SkillRun, item["id"])
                if pending and pending.status == "GENERATING":
                    pending.status = "ERROR"
            raise

    @app.get("/api/projects/{pid}/traceability")
    def trace(pid: str):
        objs = artifacts(pid)
        return {"nodes": objs, "edges": [{"from": s, "to": o["id"]} for o in objs for s in o["sources"]]}

    @app.post("/api/projects/{pid}/evidence", status_code=201)
    def evidence(pid: str, body: EvidenceInput):
        return operation(lambda svc: serialize(svc.put(pid, "Evidence", body.title, body.model_dump())))

    @app.post("/api/projects/{pid}/runtime", status_code=201)
    def runtime(pid: str, body: RuntimeInput):
        def run(svc):
            svc.artifact(pid, body.verification_id, "Verification")
            return serialize(svc.put(pid, "RuntimeEvidence", body.title, body.model_dump(), [body.verification_id]))
        return operation(run)

    @app.get("/api/projects/{pid}/runs")
    def runs(pid: str):
        return operation(lambda svc: [serialize(r) for r in svc.s.scalars(select(SkillRun).where(SkillRun.project_id == pid))])

    @app.get("/api/projects/{pid}/suggestions")
    def suggestions(pid: str):
        return operation(lambda svc: svc.suggestions(pid))

    @app.post("/api/projects/{pid}/runs", status_code=201)
    def start_run(pid: str, body: RunInput):
        def run(svc):
            provider = svc.project_provider(pid, provider_client) if body.mode == "llm" else None
            return serialize(svc.start_skill(pid, body.skill_id, body.sources, body.mode, provider, defer=True)), provider
        return generate_outside_transaction(pid, run)

    @app.post("/api/projects/{pid}/runs/{rid}/review")
    def review(pid: str, rid: str, body: ReviewInput):
        return operation(lambda svc: {"created": svc.review(pid, rid, body.decision, body.output, body.checklist)})

    @app.post("/api/projects/{pid}/evaluation-preview")
    def preview(pid: str, body: RunInput):
        return operation(lambda svc: svc.evaluation_preview(pid, [svc.artifact(pid, s) for s in body.sources]))

    @app.post("/api/projects/{pid}/changes", status_code=201)
    def changes(pid: str, body: ChangeInput):
        return operation(lambda svc: serialize(svc.start_change(pid, body.intent_id, body.branch)))

    @app.post("/api/projects/{pid}/demo/apply-fix")
    def apply_demo_fix(pid: str):
        return operation(lambda svc: svc.apply_demo_fix(pid))

    @app.post("/api/projects/{pid}/changes/{cid}/verify")
    def verify_change(pid: str, cid: str, body: SubmitInput):
        prepared = operation(lambda svc: svc.prepare_change(pid, cid, body.final_commit))
        try:
            from adapters.git import verify
            result = verify(prepared["repository"], prepared["baseline_commit"], prepared["final_commit"], prepared["contract"])
            return operation(lambda svc: serialize(svc.complete_change(pid, cid, prepared, result)))
        except Exception:
            with factory.begin() as s:
                change = s.get(Artifact, cid)
                if change and change.data.get("status") == "VERIFYING":
                    change.data = {**change.data, "status": "OPEN"}
            raise

    @app.post("/api/projects/{pid}/verification/explain")
    def explain(pid: str, body: ExplainInput):
        return operation(lambda svc: svc.explain_verification(pid, body.verification_id,
            svc.project_provider(pid, provider_client)))

    install_engineering(app, factory, data, ROOT)
    from apps.api.property_case import install_property_case
    install_property_case(app, factory, data, ROOT)
    from apps.api.learning import install_learning
    install_learning(app, factory)
    dist = ROOT / "apps" / "web" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app

class LazyApplication:
    """Delay local database and directory creation until the ASGI server actually starts."""

    def __init__(self, factory=create_app):
        self._factory = factory
        self._app = None
        self._lock = threading.Lock()

    def _get(self):
        if self._app is None:
            with self._lock:
                if self._app is None:
                    self._app = self._factory()
        return self._app

    async def __call__(self, scope, receive, send):
        await self._get()(scope, receive, send)


app = LazyApplication()
