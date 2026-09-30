"""Domain operations. No model suggestion bypasses human confirmation."""
from pathlib import Path
import json
import shutil
import hashlib
from sqlalchemy import select, update
from intentflow_core.models import ArtifactScope, Project, Artifact, SkillRun, AISuggestion, serialize, uid
from intentflow_core.rules import target_passed
from adapters.git import repository, clone_repository, context, commit, git, verify
from adapters.llm import SecretStore, create_provider
from skill_runtime import load, validate
from intentflow_core.projects import import_manifest
from intentflow_core.workflow.input_builder import build
from intentflow_core.workflow.readiness import workflow_state
from intentflow_core.workflow.next_action import describe
from intentflow_core.versioning import Versioning, VersionConflict

KINDS = {"Evidence", "Context", "Problem", "Requirement", "ChangeProposal", "Specification",
         "EngineeringIntent", "ChangeRecord", "Verification", "RuntimeEvidence",
         "EngineeringEvaluation", "CandidateProblem", "VerificationPlan"}

SINGLETON_FORMAL_KINDS = {
    "Context", "Problem", "Requirement", "ChangeProposal", "Specification",
    "EngineeringIntent", "ChangeRecord", "Verification", "EngineeringEvaluation",
    "CandidateProblem", "VerificationPlan",
}
DEFAULT_ITERATION_PLAN = [
    {"number": 1, "title": "最小可用原型", "goal": "用最小范围跑通核心业务流程，交付可演示、可验证的版本。"},
    {"number": 2, "title": "前向部署与用户访谈", "goal": "把原型交给目标用户试用，通过访谈记录真实阻力、误解与新增需求。"},
    {"number": 3, "title": "从数据中获取需求", "goal": "分析运行指标、用户行为与异常数据，用证据确定下一批需求。"},
    {"number": 4, "title": "运行与维护", "goal": "处理业务变更、故障、性能与持续维护，并形成后续迭代计划。"},
]


def iteration_plan(count=4, length_weeks=2, goals=None):
    """Create a project-level agile delivery plan with four required foundation rounds."""
    count = max(4, min(int(count or 4), 8))
    length_weeks = max(1, min(int(length_weeks or 2), 4))
    supplied = [str(item).strip() for item in (goals or [])]
    rounds = []
    for index in range(count):
        if index < len(DEFAULT_ITERATION_PLAN):
            item = dict(DEFAULT_ITERATION_PLAN[index])
        else:
            item = {"number": index + 1, "title": f"持续改进 {index + 1}",
                    "goal": "根据上一轮反馈与运行证据，交付下一项可验证改进。"}
        if index < len(supplied) and supplied[index]:
            item["goal"] = supplied[index][:1000]
        item["length_weeks"] = length_weeks
        rounds.append(item)
    return {"method": "agile", "plan_type": "teaching_route",
            "progress_semantics": "planned_not_measured", "current_iteration": 1,
            "iteration_count": count, "length_weeks": length_weeks, "iterations": rounds}

def _normalize_output(skill_id, value):
    """Accept V0.2 drafts while storing the richer V1.0 contract."""
    output = dict(value)
    if skill_id == "project-understanding":
        output.setdefault("core_modules", ["Unknown - inspect repository"])
        output.setdefault("repository_structure", ["No repository structure supplied"])
    elif skill_id == "evidence-analysis":
        output.setdefault("problem_statement", output.get("observation", ""))
        output.setdefault("supporting_evidence", [output.get("observation", "")])
        output.setdefault("affected_area", output.get("affected_users", "Unknown"))
        output.setdefault("unknown_questions", [output.get("sufficiency", "Unknown")])
        output.setdefault("rationale", output.get("impact", "Evidence review required"))
    elif skill_id == "intent-design":
        if not output.get("acceptance_criteria"):
            output["acceptance_criteria"] = output.get("acceptance", [])
        if not output.get("invariant_tests"):
            output["invariant_tests"] = output.get("acceptance_tests", [])
        if not output.get("open_questions"):
            output["open_questions"] = ["None recorded"]
        if not output.get("rationale"):
            output["rationale"] = output.get("goal", "")
    return output

class Service:
    def __init__(self, session, data_root, root):
        self.s = session
        self.data_root = Path(data_root)
        self.root = Path(root)

    def project(self, project_id):
        p = self.s.get(Project, project_id)
        if not p:
            raise ValueError("Project not found")
        return p

    def artifact(self, project_id, artifact_id, kind=None):
        obj = self.s.get(Artifact, artifact_id)
        if not obj or obj.project_id != project_id or (kind and obj.kind != kind):
            raise ValueError("Invalid source or cross-project reference")
        return obj

    def put(self, project_id, kind, title, data, sources=(), actor="local-user", workflow_step=""):
        self.project(project_id)
        for source in sources:
            self.artifact(project_id, source)
        versioning = Versioning(self.s)
        state = versioning.ensure(project_id)
        if workflow_step and kind in SINGLETON_FORMAL_KINDS:
            current = list(self.s.scalars(
                select(Artifact).join(ArtifactScope, ArtifactScope.artifact_id == Artifact.id).where(
                    Artifact.project_id == project_id,
                    Artifact.kind == kind,
                    Artifact.workflow_step == workflow_step,
                    Artifact.status == "CONFIRMED",
                    ArtifactScope.iteration_id == state.iteration_id,
                ).order_by(Artifact.created_at.desc(), Artifact.id.desc())
            ))
            for item in current:
                item.status = "SUPERSEDED"
        obj = Artifact(project_id=project_id, kind=kind, title=title, data=data,
                       sources=list(sources), actor=actor, workflow_step=workflow_step)
        self.s.add(obj)
        self.s.flush()
        versioning.record_artifact(obj, state)
        return obj

    def create_project(self, name, description="", mode="blank", repo_path="", *, branch="",
                       base_commit="HEAD", problem_statement="", raw_materials=None,
                       manifest_path="", ai=None, iteration_count=4,
                       iteration_length_weeks=2, iteration_goals=None):
        agile = iteration_plan(iteration_count, iteration_length_weeks, iteration_goals)
        if mode == "property":
            from intentflow_core.property_case import create_property
            return create_property(self, name, description, ai, agile)
        repo = ""
        details = {"agile": agile}
        source_type = "benchmark" if mode == "case" else mode
        imported_materials = list(raw_materials or [])
        if mode in {"git", "blank"} and repo_path:
            target = self.data_root / "repositories" / uid()
            cloned, resolved = clone_repository(repo_path, target, branch, base_commit)
            repo = str(cloned)
            details.update({"repo_url": repo_path, "base_commit": resolved, "branch": branch})
        elif mode == "git":
            raise ValueError("Repository URL or local path is required")
        elif mode == "case":
            source = self.root / "examples" / "campus-activity-half-finished"
            target = self.data_root / "repositories" / uid()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", ".git"))
            git(target, "init", "-b", "main")
            git(target, "add", ".")
            git(target, "-c", "user.name=IntentFlow", "-c", "user.email=local@intentflow.invalid",
                "commit", "-m", "初始化示例项目：源代码与原始证据")
            repo = str(target)
            details.update({"dataset_name": "intentflow-examples", "instance_id": "campus-activity-001",
                            "repo_url": str(source), "base_commit": commit(target, "HEAD"),
                            "language": "Python", "task_type": "repository-change",
                            "problem_statement": problem_statement or "并发报名可能突破活动容量上限。",
                            "evaluation_metadata": {"available": False}})
        elif mode == "benchmark":
            manifest, evaluation_metadata = import_manifest(manifest_path, self.data_root / "evaluation-only")
            target = self.data_root / "repositories" / uid()
            source_ref = manifest.repo_url
            local_ref = Path(source_ref).expanduser()
            if "://" not in source_ref and not local_ref.is_absolute():
                source_ref = str((Path(manifest_path).expanduser().resolve().parent / local_ref).resolve())
            source_path = Path(source_ref)
            if source_path.is_dir() and not (source_path / ".git").is_dir():
                shutil.copytree(source_path, target, ignore=shutil.ignore_patterns("__pycache__", ".git"))
                git(target, "init", "-b", "main"); git(target, "add", ".")
                git(target, "-c", "user.name=IntentFlow", "-c", "user.email=local@intentflow.invalid",
                    "commit", "-m", "导入基准案例基线快照")
                cloned, resolved = target, commit(target, "HEAD")
            else:
                cloned, resolved = clone_repository(source_ref, target, branch, manifest.base_commit)
            repo = str(cloned)
            name = name or manifest.project_name
            problem_statement = manifest.problem_statement
            imported_materials.extend(manifest.raw_materials)
            details.update({key: value for key, value in manifest.model_dump(exclude={"evaluation_only", "raw_materials"}).items()
                            if key not in {"project_name", "requirement_context", "planning_context"}})
            details["base_commit"] = resolved
            details["evaluation_metadata"] = evaluation_metadata
            if manifest.requirement_context is not None:
                imported_materials.append({"title": "需求上下文", "type": "Document", "content": manifest.requirement_context})
            if manifest.planning_context is not None:
                imported_materials.append({"title": "规划上下文", "type": "Document", "content": manifest.planning_context})
        elif mode != "blank":
            raise ValueError("Unknown project mode")
        if ai and ai.get("enabled"):
            store = SecretStore(self.data_root / ".intentflow-secrets")
            ref = store.put(ai.get("api_key", ""))
            model = str(ai.get("model", "")).strip()
            if not model or len(model) > 200:
                raise ValueError("A configurable model_id is required")
            provider_id = str(ai.get("provider", "bigmodel"))
            if provider_id not in {"bigmodel", "siliconflow"}:
                raise ValueError("不支持此智能辅助服务商")
            details["ai"] = {"enabled": True, "provider": provider_id, "model": model,
                             "credential_ref": ref, "masked": store.masked(ref)}
        else:
            details["ai"] = {"enabled": False}
        p = Project(name=name, description=description, repository=repo, source_type=source_type, details=details)
        self.s.add(p)
        self.s.flush()
        Versioning(self.s).ensure(p.id)
        if mode == "case":
            material_titles = {"interview-notes.md": "访谈记录", "operation-records.csv": "运营记录",
                               "runtime-log.txt": "运行日志", "user-feedback.md": "用户反馈"}
            for material in sorted((Path(repo) / "case-materials").iterdir()):
                if material.is_file():
                    self.put(p.id, "Evidence", material_titles.get(material.name, material.name),
                             {"type": "Document", "content": material.read_text(encoding="utf-8"),
                              "origin": str(material.relative_to(repo))})
        if problem_statement:
            self.put(p.id, "Evidence", "问题陈述", {"type": "Issue", "content": problem_statement,
                                                               "origin": "project-creation"})
        for index, material in enumerate(imported_materials):
            if isinstance(material, str):
                value = {"title": f"Raw material {index + 1}", "type": "Document", "content": material}
            elif isinstance(material, dict):
                value = dict(material)
            else:
                value = {"title": f"Raw material {index + 1}", "type": "Document", "content": json.dumps(material, ensure_ascii=False)}
            if "path" in value and "content" not in value:
                material_path = Path(value.pop("path"))
                if mode == "benchmark" and not material_path.is_absolute():
                    material_path = Path(manifest_path).expanduser().resolve().parent / material_path
                value["content"] = material_path.read_text(encoding="utf-8", errors="replace")[:100000]
                value["origin"] = str(material_path)
            self.put(p.id, "Evidence", str(value.pop("title", f"Raw material {index + 1}")),
                     {"type": value.pop("type", "Document"), **value})
        return p

    def project_context(self, project_id):
        p = self.project(project_id)
        state = Versioning(self.s).ensure(project_id)
        return {"project": serialize(p), "repository": context(p.repository) if p.repository else {},
                "engineering": {"objects": Versioning(self.s).objects(project_id),
                    "boundary": "已人工确认的结构化规则与设计约束；模型建议不得直接改变它们"},
                "version_basis": {"baseline_id": state.baseline_id, "iteration_id": state.iteration_id}}

    def update_project_description(self, project_id, description):
        project = self.project(project_id)
        project.description = description.strip()
        if not project.description:
            raise ValueError("Project description is required")
        self.s.flush()
        return project

    def link_repository(self, project_id, path):
        p = self.project(project_id)
        if p.repository:
            raise ValueError("Repository already linked; create another project to change repositories")
        p.repository = str(repository(path))
        self.s.flush()
        return p

    def workflow(self, project_id):
        state = workflow_state(self, project_id)
        state["next_action"] = describe(state)
        return state

    def workflow_input(self, project_id, step_id):
        return build(self, project_id, step_id)

    def project_provider(self, project_id, client=None):
        p = self.project(project_id)
        config = p.details.get("ai", {})
        if not config.get("enabled"):
            raise ValueError("AI assistance is unavailable; continue in manual mode")
        return create_provider(config, SecretStore(self.data_root / ".intentflow-secrets"), client)

    def start_workflow_skill(self, project_id, step_id, mode=None, provider=None, defer=False):
        assembled = build(self, project_id, step_id)
        if not assembled["ready"]:
            raise ValueError("Missing workflow input: " + ", ".join(assembled["missing"]))
        skill_id = assembled["step"]["skill"]
        if not skill_id:
            raise ValueError("This workflow step is deterministic")
        configured = self.project(project_id).details.get("ai", {}).get("enabled", False)
        selected_mode = mode or ("llm" if configured else "manual")
        return self.start_skill(project_id, skill_id, [item["id"] for item in assembled["sources"]],
                                selected_mode, provider or (self.project_provider(project_id) if selected_mode == "llm" else None),
                                workflow_step=step_id, prebuilt=assembled, defer=defer)

    def start_skill(self, project_id, skill_id, sources, mode="manual", provider=None,
                    workflow_step="", prebuilt=None, defer=False):
        skill = load(skill_id)
        objects = [self.artifact(project_id, i) for i in dict.fromkeys(sources)]
        current_ids = {o.id for o in Versioning(self.s).current_artifacts(project_id)}
        if any(o.id not in current_ids for o in objects):
            raise VersionConflict("所选正式产物属于旧轮次，请使用当前轮次的资料")
        kinds = {o.kind for o in objects}
        required = skill["requires_sources"]
        if skill_id == "evidence-analysis":
            if not kinds.intersection(required):
                raise ValueError("Select raw Evidence or RuntimeEvidence")
        elif not set(required).issubset(kinds):
            raise ValueError("Missing confirmed sources: " + ", ".join(required))
        if skill_id == "outcome-evaluation":
            self.evaluation_preview(project_id, objects)
        inputs = {"project_context": self.project_context(project_id), "sources": [serialize(o) for o in objects]}
        validate(skill["input_schema"], inputs)
        if mode not in {"manual", "llm"}:
            raise ValueError("Unknown skill mode")
        suggestion = {}
        rationale = ""
        if mode == "manual" and self.project(project_id).details.get("example_kind") == "property-management":
            from intentflow_core.property_case import reference_draft
            suggestion = reference_draft(skill_id, self, project_id)
            validate(skill["output_schema"], suggestion)
            inputs["draft_source"] = "案例参考草稿，需逐项核对后确认"
        if mode == "llm":
            if provider is None:
                raise ValueError("No LLM configured; manual mode is fully available")
            if not defer:
                response = provider.suggest(skill, inputs)
                suggestion, rationale = response if isinstance(response, tuple) else (response, "")
                suggestion = _normalize_output(skill_id, suggestion)
                validate(skill["output_schema"], suggestion)
        run = SkillRun(project_id=project_id, skill_id=skill_id, version=skill["version"],
                       mode=mode, sources=[o.id for o in objects], inputs=inputs, suggestion=suggestion,
                       workflow_step=workflow_step, status="GENERATING" if defer and mode == "llm" else "DRAFT")
        self.s.add(run)
        self.s.flush()
        if mode == "llm" and not defer:
            identity = getattr(provider, "identity", None)
            snapshot = json.dumps(inputs, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            self.s.add(AISuggestion(project_id=project_id, workflow_step=workflow_step or skill_id,
                                    skill_run_id=run.id, provider=getattr(identity, "provider", "configured"),
                                    model=getattr(identity, "model", "configured"),
                                    input_snapshot_hash=hashlib.sha256(snapshot).hexdigest(), output=suggestion,
                                    rationale=rationale, status="GENERATED"))
            self.s.flush()
        return run

    def complete_suggestion(self, project_id, run_id, response, provider):
        run = self.s.get(SkillRun, run_id)
        if not run or run.project_id != project_id or run.status != "GENERATING":
            raise VersionConflict("候选生成任务已经中断或处理")
        suggestion, rationale = response if isinstance(response, tuple) else (response, "")
        suggestion = _normalize_output(run.skill_id, suggestion)
        validate(load(run.skill_id)["output_schema"], suggestion)
        run.suggestion, run.status = suggestion, "DRAFT"
        identity = getattr(provider, "identity", None)
        snapshot = json.dumps(run.inputs, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        self.s.add(AISuggestion(project_id=project_id, workflow_step=run.workflow_step or run.skill_id,
            skill_run_id=run.id, provider=getattr(identity, "provider", "configured"),
            model=getattr(identity, "model", "configured"), input_snapshot_hash=hashlib.sha256(snapshot).hexdigest(),
            output=suggestion, rationale=rationale, status="GENERATED"))
        self.s.flush()
        return run

    def evaluation_preview(self, project_id, objects):
        if sum(o.kind == "Verification" for o in objects) != 1 or sum(o.kind == "RuntimeEvidence" for o in objects) != 1:
            raise ValueError("Select exactly one verification and one after-evidence record")
        ver = next((o for o in objects if o.kind == "Verification"), None)
        after = next((o for o in objects if o.kind == "RuntimeEvidence"), None)
        if not ver or not after or ver.id not in after.sources:
            raise ValueError("After evidence must reference the selected verification")
        change = self.artifact(project_id, ver.sources[0], "ChangeRecord")
        intent = self.artifact(project_id, change.sources[0], "EngineeringIntent")
        passed, gaps = target_passed(intent.data["field_target"], after.data["metrics"])
        before = []
        seen = set()
        def walk(obj):
            if obj.id in seen:
                return
            seen.add(obj.id)
            if obj.kind in {"Evidence", "RuntimeEvidence"}:
                before.append(serialize(obj))
            for source in obj.sources:
                walk(self.artifact(project_id, source))
        walk(intent)
        return {"implementation_result": ver.data["status"],
                "field_outcome": "PASS" if passed else "NOT_MET",
                "metric_gaps": gaps, "before_evidence": before,
                "after_evidence": serialize(after), "field_target": intent.data["field_target"]}

    def review(self, project_id, run_id, decision, output, checklist):
        run = self.s.get(SkillRun, run_id)
        if not run or run.project_id != project_id or run.status != "DRAFT":
            raise ValueError("Skill run is absent or already reviewed")
        if decision == "reject":
            claimed = self.s.execute(update(SkillRun).where(SkillRun.id == run.id, SkillRun.status == "DRAFT").values(status="REJECTED"))
            if claimed.rowcount != 1:
                raise ValueError("Skill run already reviewed")
            run.suggestion = output
            suggestion = self.s.scalar(select(AISuggestion).where(AISuggestion.skill_run_id == run.id))
            if suggestion:
                suggestion.status = "REJECTED"
            self.s.flush()
            return []
        if decision != "accept":
            raise ValueError("Review decision must be accept or reject")
        basis = run.inputs.get("project_context", {}).get("version_basis")
        current = Versioning(self.s).ensure(project_id)
        if (basis and basis.get("iteration_id") != current.iteration_id) or (not basis and current.generation > 0):
            raise VersionConflict("这份候选生成后需求版本已变化，请重新分析并确认")
        skill = load(run.skill_id)
        if len(checklist) != len(skill["checklist"]) or not all(checklist):
            raise ValueError("Complete all human review checks")
        output = _normalize_output(run.skill_id, output)
        validate(skill["output_schema"], output)
        objects = [self.artifact(project_id, i) for i in run.sources]
        if run.skill_id == "intent-design":
            for key in ("allowed_scope", "protected_scope"):
                if any(p.startswith(("/", "\\")) or ".." in p.replace("\\", "/").split("/") or ":" in p for p in output[key]):
                    raise ValueError("Scope globs must be repository-relative")
            _, gaps = target_passed(output["field_target"], {})
            if any(g.startswith("unsupported") for g in gaps):
                raise ValueError("Unsupported field target expression")
        if run.skill_id == "outcome-evaluation":
            preview = self.evaluation_preview(project_id, objects)
            if output["recommended_action"] == "CLOSE" and (
                preview["implementation_result"] != "PASS" or preview["field_outcome"] != "PASS" or output["new_problem"].strip()
            ):
                raise ValueError("CLOSE requires passed implementation, achieved field targets and no new problem")
            output = {**output, **preview}
        # Conditional update serializes accept/reject and prevents duplicate objects.
        claimed = self.s.execute(update(SkillRun).where(SkillRun.id == run.id, SkillRun.status == "DRAFT")
                                 .values(status="ACCEPTED"))
        if claimed.rowcount != 1:
            raise ValueError("Skill run already reviewed")
        ids = []
        sources = list(run.sources)
        suggestion = self.s.scalar(select(AISuggestion).where(AISuggestion.skill_run_id == run.id))
        if suggestion:
            suggestion.status = "ACCEPTED" if output == suggestion.output else "EDITED"
        if run.skill_id == "requirement-engineering":
            proposal = self.put(project_id, "ChangeProposal", output["title"],
                                {"why_change": output["why_change"], "decision": output["decision"],
                                 "skill_run": run.id}, sources, workflow_step=run.workflow_step)
            ids.append(proposal.id)
            if output["decision"] != "GO":
                run.result_ids = ids
                run.suggestion = output
                return ids
            requirement = self.put(project_id, "Requirement", output["title"], output, sources + [proposal.id], workflow_step=run.workflow_step)
            ids.append(requirement.id)
            sources += [proposal.id, requirement.id]
        kind = skill["outputs"][0]
        formal = self.put(project_id, kind, output.get("title", skill["name"]),
                          {**output, "skill_run": run.id}, sources, workflow_step=run.workflow_step)
        ids.append(formal.id)
        if kind == "EngineeringEvaluation" and output["new_problem"].strip():
            candidate = self.put(project_id, "CandidateProblem", output["new_problem"],
                                 {"observation": output["new_problem"], "status": "AWAITING_CONFIRMATION"},
                                 [formal.id] + run.sources, workflow_step="next-change")
            ids.append(candidate.id)
        run.result_ids = ids
        run.suggestion = output
        self.s.flush()
        return ids

    def suggestions(self, project_id):
        self.project(project_id)
        return [serialize(item) for item in self.s.scalars(select(AISuggestion).where(
            AISuggestion.project_id == project_id).order_by(AISuggestion.created_at))]

    def explain_verification(self, project_id, verification_id, provider=None):
        verification = self.artifact(project_id, verification_id, "Verification")
        change = self.artifact(project_id, verification.sources[0], "ChangeRecord")
        intent = self.artifact(project_id, change.sources[0], "EngineeringIntent")
        provider = provider or self.project_provider(project_id)
        pseudo_skill = {"id": "verification-explanation", "instructions":
            "Explain the deterministic result and cite the evidence matrix. Never change the verdict.",
            "output_schema": {"type": "object", "additionalProperties": False,
                "properties": {"explanation": {"type": "string", "minLength": 1}}, "required": ["explanation"]}}
        inputs = {"engineering_intent": intent.data, "verification_result": verification.data,
                  "git_diff_summary": verification.data.get("diff", "")[:20000]}
        output, rationale = provider.suggest(pseudo_skill, inputs)
        validate(pseudo_skill["output_schema"], output)
        run = SkillRun(project_id=project_id, skill_id="verification-explanation", version="1.0.0",
                       mode="llm", status="ACCEPTED", sources=[intent.id, verification.id], inputs=inputs,
                       suggestion=output, workflow_step="verification")
        self.s.add(run); self.s.flush()
        identity = provider.identity
        snapshot = json.dumps(inputs, ensure_ascii=False, sort_keys=True).encode("utf-8")
        suggestion = AISuggestion(project_id=project_id, workflow_step="verification", skill_run_id=run.id,
            provider=identity.provider, model=identity.model, input_snapshot_hash=hashlib.sha256(snapshot).hexdigest(),
            output=output, rationale=rationale, status="ACCEPTED")
        self.s.add(suggestion); self.s.flush()
        return serialize(suggestion)

    def start_change(self, project_id, intent_id, branch=""):
        intent = self.artifact(project_id, intent_id, "EngineeringIntent")
        p = self.project(project_id)
        root = repository(p.repository)
        baseline = commit(root, "HEAD")
        if branch:
            git(root, "check-ref-format", "--branch", branch)
            git(root, "branch", branch, baseline)
        return self.put(project_id, "ChangeRecord", "软件变更",
                        {"baseline_commit": baseline, "branch": branch, "status": "OPEN"},
                        [intent.id], workflow_step="software-change")

    def apply_demo_fix(self, project_id):
        """Apply the bundled concurrency fix, but only to the built-in demo repository."""
        p = self.project(project_id)
        if (p.details.get("dataset_name"), p.details.get("instance_id")) != (
            "intentflow-examples", "campus-activity-001"
        ):
            raise ValueError("此操作只适用于 IntentFlow 中文示例项目")
        change = self.s.scalar(select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.kind == "ChangeRecord",
        ).order_by(Artifact.created_at.desc()))
        if not change or change.data.get("status") != "OPEN":
            raise ValueError("请先完成工程意图，并点击“记录基线，开始示例变更”")
        root = repository(p.repository)
        if git(root, "status", "--porcelain").strip():
            raise ValueError("示例仓库存在未提交修改，请先处理后再应用演示修复")
        path = root / "enrollment.py"
        original = path.read_text(encoding="utf-8")
        if "self._lock = threading.Lock()" in original:
            return {"changed": False, "commit": commit(root, "HEAD")}
        required = ("import time", "        self.members = set()", "    def enroll(self, user):")
        if any(item not in original for item in required):
            raise ValueError("示例代码结构已变化，无法安全应用演示修复")
        updated = original.replace("import time", "import time\nimport threading", 1)
        updated = updated.replace(
            "        self.members = set()",
            "        self.members = set()\n        self._lock = threading.Lock()",
            1,
        )
        updated = updated.replace(
            "    def enroll(self, user):",
            "    def enroll(self, user):\n        with self._lock:\n            return self._enroll(user)\n\n    def _enroll(self, user):",
            1,
        )
        path.write_text(updated, encoding="utf-8")
        try:
            git(root, "add", "--", "enrollment.py")
            git(root, "-c", "user.name=IntentFlow Demo", "-c", "user.email=demo@intentflow.local",
                "commit", "-m", "fix: prevent over-capacity enrollment")
        except Exception:
            path.write_text(original, encoding="utf-8")
            git(root, "add", "--", "enrollment.py")
            raise
        return {"changed": True, "commit": commit(root, "HEAD")}

    def submit_change(self, project_id, change_id, final_ref):
        prepared = self.prepare_change(project_id, change_id, final_ref)
        result = verify(prepared["repository"], prepared["baseline_commit"], prepared["final_commit"], prepared["contract"])
        return self.complete_change(project_id, change_id, prepared, result)

    def prepare_change(self, project_id, change_id, final_ref):
        change = self.artifact(project_id, change_id, "ChangeRecord")
        v = Versioning(self.s)
        if change.id not in {o.id for o in v.current_artifacts(project_id)}:
            raise VersionConflict("变更合同属于旧轮次，请在当前轮次重新确认")
        if change.data["status"] != "OPEN":
            raise ValueError("Change already submitted; begin a new change")
        claimed = self.s.execute(update(Artifact).where(
            Artifact.id == change.id, Artifact.data["status"].as_string() == "OPEN"
        ).values(data={**change.data, "status": "VERIFYING"}))
        if claimed.rowcount != 1:
            raise ValueError("Change is already being verified")
        p = self.project(project_id)
        intent = self.artifact(project_id, change.sources[0], "EngineeringIntent")
        return {"repository": p.repository, "baseline_commit": change.data["baseline_commit"],
                "final_commit": commit(repository(p.repository), final_ref), "contract": intent.data,
                "iteration_id": v.ensure(project_id).iteration_id}

    def complete_change(self, project_id, change_id, prepared, result):
        change = self.artifact(project_id, change_id, "ChangeRecord")
        if change.data["status"] != "VERIFYING":
            raise VersionConflict("验证任务已中断或被处理")
        if Versioning(self.s).ensure(project_id).iteration_id != prepared["iteration_id"]:
            raise VersionConflict("执行过程中需求已变化，本次结果不能恢复当前轮次结论")
        result["traceability"] = list(change.sources)
        change.data = {**change.data, "final_commit": result["final_commit"], "status": "VERIFIED"}
        return self.put(project_id, "Verification", "版本与测试：" + ("通过" if result["status"] == "PASS" else "拒绝"),
                        result, [change.id], actor="deterministic-engine", workflow_step="verification")
