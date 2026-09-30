"""SQLAlchemy persistence; immutable versioned objects and explicit provenance."""
import uuid
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, String, Text, ForeignKey, Integer, UniqueConstraint, create_engine, inspect, text, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def uid():
    return str(uuid.uuid4())

def now():
    return datetime.now(timezone.utc).isoformat()

class Base(DeclarativeBase):
    pass

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    repository: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(30), default="blank")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class LearningNote(Base):
    __tablename__ = "learning_notes"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    stage: Mapped[str] = mapped_column(String(50), primary_key=True)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[str] = mapped_column(String(50), default=now)

class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(300))
    data: Mapped[dict] = mapped_column(JSON)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    actor: Mapped[str] = mapped_column(String(100), default="local-user")
    status: Mapped[str] = mapped_column(String(30), default="CONFIRMED")
    workflow_step: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class SkillRun(Base):
    __tablename__ = "skill_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    skill_id: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(30))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    sources: Mapped[list] = mapped_column(JSON)
    inputs: Mapped[dict] = mapped_column(JSON)
    suggestion: Mapped[dict] = mapped_column(JSON, default=dict)
    result_ids: Mapped[list] = mapped_column(JSON, default=list)
    workflow_step: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class AISuggestion(Base):
    __tablename__ = "ai_suggestions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    workflow_step: Mapped[str] = mapped_column(String(50), index=True)
    skill_run_id: Mapped[str] = mapped_column(ForeignKey("skill_runs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(200))
    input_snapshot_hash: Mapped[str] = mapped_column(String(64))
    output: Mapped[dict] = mapped_column(JSON)
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="GENERATED")
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class EngineeringObject(Base):
    """Stable identity. Its approved content lives exclusively in revisions."""
    __tablename__ = "engineering_objects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(60))
    current_revision: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class Revision(Base):
    __tablename__ = "object_revisions"
    __table_args__ = (UniqueConstraint("object_id", "number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    object_id: Mapped[str] = mapped_column(ForeignKey("engineering_objects.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[str] = mapped_column(String(36), default="")
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(100), default="local-user")
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class Baseline(Base):
    __tablename__ = "requirement_baselines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    parent_id: Mapped[str] = mapped_column(String(36), default="")
    title: Mapped[str] = mapped_column(String(300))
    members: Mapped[dict] = mapped_column(JSON, default=dict)
    code_commit: Mapped[str] = mapped_column(String(64), default="")
    actor: Mapped[str] = mapped_column(String(100), default="local-user")
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class Iteration(Base):
    __tablename__ = "work_iterations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    baseline_id: Mapped[str] = mapped_column(ForeignKey("requirement_baselines.id"))
    number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class ProjectState(Base):
    __tablename__ = "project_version_state"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    baseline_id: Mapped[str] = mapped_column(ForeignKey("requirement_baselines.id"))
    iteration_id: Mapped[str] = mapped_column(ForeignKey("work_iterations.id"))
    generation: Mapped[int] = mapped_column(Integer, default=0)

class ArtifactScope(Base):
    __tablename__ = "artifact_iteration_scope"
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), primary_key=True)
    iteration_id: Mapped[str] = mapped_column(ForeignKey("work_iterations.id"), index=True)
    baseline_id: Mapped[str] = mapped_column(ForeignKey("requirement_baselines.id"))

class TypedRelation(Base):
    __tablename__ = "typed_relations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("engineering_objects.id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("engineering_objects.id"))
    kind: Mapped[str] = mapped_column(String(30))
    baseline_id: Mapped[str] = mapped_column(ForeignKey("requirement_baselines.id"))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class EngineeringRun(Base):
    __tablename__ = "engineering_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    baseline_id: Mapped[str] = mapped_column(ForeignKey("requirement_baselines.id"))
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="QUEUED")
    inputs: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(50), default=now)
    finished_at: Mapped[str] = mapped_column(String(50), default="")

class EngineeringEvent(Base):
    __tablename__ = "engineering_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(50), default=now)

class EngineeringDraft(Base):
    __tablename__ = "engineering_drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    baseline_id: Mapped[str] = mapped_column(ForeignKey("requirement_baselines.id"))
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(50), default=now)

def _immutable(mapper, connection, target):
    raise ValueError("已确认修订、基线与历史事件不可覆盖或删除，请创建新修订")

for _record in (Revision, Baseline, Iteration, TypedRelation, EngineeringEvent, ArtifactScope):
    event.listen(_record, "before_update", _immutable)
    event.listen(_record, "before_delete", _immutable)

_ADDITIVE_COLUMNS = {
    "projects": {"source_type": "VARCHAR(30) NOT NULL DEFAULT 'blank'", "details": "JSON NOT NULL DEFAULT '{}'"},
    "artifacts": {"status": "VARCHAR(30) NOT NULL DEFAULT 'CONFIRMED'", "workflow_step": "VARCHAR(50) NOT NULL DEFAULT ''"},
    "skill_runs": {"workflow_step": "VARCHAR(50) NOT NULL DEFAULT ''"},
}


class DatabaseMigrationRequired(RuntimeError):
    """An existing database needs an explicitly authorised schema upgrade."""


class DatabaseMigrationError(RuntimeError):
    """A database upgrade could not complete safely."""


def _schema_gaps(bind):
    inspector = inspect(bind)
    existing = set(inspector.get_table_names())
    if not existing:
        return {"tables": [], "columns": {}}
    missing_tables = sorted(set(Base.metadata.tables) - existing)
    missing_columns = {}
    for table, columns in _ADDITIVE_COLUMNS.items():
        if table not in existing:
            continue
        found = {column["name"] for column in inspector.get_columns(table)}
        absent = sorted(set(columns) - found)
        if absent:
            missing_columns[table] = absent
    return {"tables": missing_tables, "columns": missing_columns}


def _migrate(bind):
    """Apply the small additive migration inside the caller's transaction."""
    existing = inspect(bind).get_table_names()
    if "projects" not in existing:
        return
    for table, columns in _ADDITIVE_COLUMNS.items():
        if table not in existing:
            continue
        found = {column["name"] for column in inspect(bind).get_columns(table)}
        for name, ddl in columns.items():
            if name not in found:
                bind.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _sqlite_path(url):
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite") or not parsed.database or parsed.database == ":memory:":
        return None
    return Path(parsed.database).expanduser().resolve()


def _backup_sqlite(source, destination):
    """Create and verify a backup without leaving a partial backup file."""
    partial = destination.with_suffix(destination.suffix + ".partial")
    try:
        with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)) as original, \
                closing(sqlite3.connect(partial)) as copy:
            original.backup(copy)
            if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise DatabaseMigrationError("数据库备份校验失败，已停止升级")
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def _restore_sqlite(source, backup):
    """Restore the pre-upgrade image after a failed migration."""
    with closing(sqlite3.connect(backup)) as original, closing(sqlite3.connect(source)) as restored:
        original.backup(restored)
        if restored.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise DatabaseMigrationError("数据库升级失败，且自动恢复后的完整性校验未通过")


def database(url, *, allow_migration=False):
    """Open the database, requiring explicit consent before upgrading an old schema."""
    source = _sqlite_path(url)
    source_existed = bool(source and source.is_file())
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    backup = None
    backup_directory_created = False
    try:
        gaps = _schema_gaps(engine)
        migration_required = bool(gaps["tables"] or gaps["columns"])
        if migration_required and not allow_migration:
            raise DatabaseMigrationRequired(
                "现有数据库需要升级；请先备份并显式设置 INTENTFLOW_ALLOW_DATABASE_MIGRATION=1"
            )
        if migration_required and source is not None:
            backups = source.parent / "backups"
            backup_directory_created = not backups.exists()
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / (source.name + ".pre-v2-" + uid() + ".sqlite")
            _backup_sqlite(source, backup)
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            _migrate(connection)
    except DatabaseMigrationRequired:
        engine.dispose()
        raise
    except Exception as exc:
        engine.dispose()
        if backup is not None and backup.is_file() and source is not None:
            try:
                _restore_sqlite(source, backup)
            except Exception as restore_exc:
                raise DatabaseMigrationError(
                    f"数据库升级失败，自动恢复也失败；原始备份保留在 {backup}"
                ) from restore_exc
        elif source is not None and not source_existed:
            source.unlink(missing_ok=True)
            Path(str(source) + "-wal").unlink(missing_ok=True)
            Path(str(source) + "-shm").unlink(missing_ok=True)
        if backup_directory_created and backup is not None and not backup.exists():
            try:
                backup.parent.rmdir()
            except OSError:
                pass
        if isinstance(exc, DatabaseMigrationError):
            raise
        raise DatabaseMigrationError("数据库初始化或升级失败，未保留半完成结构") from exc
    return engine, sessionmaker(engine, expire_on_commit=False)

def serialize(obj):
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
