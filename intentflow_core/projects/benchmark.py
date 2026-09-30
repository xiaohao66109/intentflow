"""Benchmark manifests with a hard visible/evaluation-only boundary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkProjectManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_name: str = Field(min_length=1, max_length=200)
    instance_id: str = Field(min_length=1, max_length=200)
    project_name: str = Field(min_length=1, max_length=200)
    repo_url: str = Field(min_length=1)
    base_commit: str = "HEAD"
    language: str = "unknown"
    task_type: str = "repository-change"
    problem_statement: str = Field(min_length=1)
    setup_command: list[str] = []
    test_command: list[str] = []
    raw_materials: list[Any] = []
    requirement_context: Any | None = None
    planning_context: Any | None = None
    evaluation_only: dict[str, Any] | None = None


def import_manifest(path: str | Path, evaluation_root: str | Path) -> tuple[BenchmarkProjectManifest, dict]:
    """Parse a manifest, persist hidden data separately, and return only visible metadata."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Benchmark manifest does not exist")
    manifest = BenchmarkProjectManifest.model_validate_json(source.read_text(encoding="utf-8"))
    hidden = manifest.evaluation_only
    metadata: dict[str, Any] = {"available": bool(hidden)}
    if hidden:
        encoded = json.dumps(hidden, ensure_ascii=False, sort_keys=True).encode("utf-8")
        metadata["sha256"] = hashlib.sha256(encoded).hexdigest()
        root = Path(evaluation_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / f"{manifest.dataset_name}--{manifest.instance_id}.json").resolve()
        if target.parent != root:
            raise ValueError("Invalid benchmark identity")
        target.write_bytes(encoded)
    return manifest.model_copy(update={"evaluation_only": None}), metadata
