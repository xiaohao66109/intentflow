"""Project import helpers."""

import os
from pathlib import Path

from sqlalchemy import select

from .benchmark import BenchmarkProjectManifest, import_manifest
from intentflow_core.models import Project

__all__ = ["BenchmarkProjectManifest", "import_manifest",
           "rebase_repository_path", "repair_repository_paths",
           "repair_repository_paths_in_data_root"]


def rebase_repository_path(stored, repositories_root):
    """Re-point a stored repository path onto the current data directory.

    Repository paths are persisted as absolute paths. Once the project folder is moved
    or copied (another disk, another machine), every stored path still points at the old
    location while the working copies themselves moved along with the data directory.
    The generated directory name is stable - a UUID directly under
    ``<data>/repositories`` - so the tail after the last ``repositories`` segment can be
    re-joined onto the current root.

    Returns the rebased ``Path``, or ``None`` when the value cannot be rebased.
    """
    text = str(stored or "").strip()
    if not text:
        return None
    segments = [segment for segment in text.replace("\\", "/").split("/") if segment]
    positions = [index for index, segment in enumerate(segments) if segment.lower() == "repositories"]
    if not positions:
        return None
    tail = segments[positions[-1] + 1:]
    if not tail:
        return None
    return Path(repositories_root).joinpath(*tail)


def repair_repository_paths(session_factory, data_root):
    """Repair stale absolute repository paths in place and report how many were fixed.

    Only entries whose stored path is missing *and* whose rebased target actually exists
    are touched, so a genuinely deleted working copy still surfaces its own error.
    """
    repositories_root = Path(data_root) / "repositories"
    if not repositories_root.is_dir():
        return 0
    repaired = 0
    with session_factory.begin() as session:
        for project in session.scalars(select(Project)):
            stored = str(project.repository or "").strip()
            if not stored or Path(stored).is_dir():
                continue
            candidate = rebase_repository_path(stored, repositories_root)
            if candidate is not None and candidate.is_dir():
                project.repository = str(candidate)
                repaired += 1
    return repaired


def repair_repository_paths_in_data_root(data_root, url=None):
    """Repair managed repository paths in the configured application database.

    This is the launcher-facing entry point.  It is safe to run while an existing
    local server is active: each API operation opens its own short-lived database
    session, so subsequent requests see the repaired paths.
    """
    from intentflow_core.models import database

    data = Path(data_root).resolve()
    data.mkdir(parents=True, exist_ok=True)
    database_url = url or os.environ.get(
        "INTENTFLOW_DATABASE_URL", "sqlite:///" + (data / "intentflow.db").as_posix()
    )
    engine, factory = database(
        database_url,
        allow_migration=os.environ.get("INTENTFLOW_ALLOW_DATABASE_MIGRATION") == "1",
    )
    try:
        return repair_repository_paths(factory, data)
    finally:
        engine.dispose()
