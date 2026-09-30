"""Loss-aware managed Markdown bridge, without modifying upstream Spec Kit."""
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from intentflow_core.versioning import digest, VersionConflict

START = "<!-- INTENTFLOW MANAGED START -->"
END = "<!-- INTENTFLOW MANAGED END -->"
PATTERN = re.compile(re.escape(START) + r"\s*```json\s*\n(.*?)\n```\s*" + re.escape(END), re.S)
MAX_DOCUMENT_BYTES = 1_000_000


def _document_path(root, relative, *, must_exist=False):
    """Resolve a managed Markdown path without permitting traversal or links."""
    boundary = Path(root).expanduser().resolve(strict=True)
    if not boundary.is_dir():
        raise ValueError("规格根目录不存在或不是目录")
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.suffix.lower() != ".md":
        raise ValueError("规格文件必须是根目录内的相对 Markdown 路径")
    target = (boundary / candidate).resolve(strict=must_exist)
    if target == boundary or not target.is_relative_to(boundary):
        raise ValueError("规格文件路径越出允许范围")
    current = boundary
    for part in candidate.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("规格文件路径不允许符号链接")
    return target


def load_file(root, relative):
    """Read one bounded Markdown document without following an oversized input."""
    target = _document_path(root, relative, must_exist=True)
    if not target.is_file() or target.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError("规格文件不存在、不是普通文件或超过 1 MB")
    return target.read_text(encoding="utf-8")


def _publish_file(staging, target, overwrite):
    if overwrite:
        os.replace(staging, target)
    else:
        os.link(staging, target)
        staging.unlink()


def save_file(root, relative, document, *, overwrite=False, publisher=_publish_file):
    """Atomically publish one bounded Markdown document, refusing overwrite by default."""
    if not isinstance(document, str) or len(document.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise ValueError("规格文档必须是 UTF-8 文本且不超过 1 MB")
    target = _document_path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError("规格文件已存在；必须显式允许覆盖")
    staging = target.parent / f".{target.name}.partial-{uuid4().hex}"
    try:
        with staging.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(document)
            handle.flush()
            os.fsync(handle.fileno())
        publisher(staging, target, overwrite)
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    return target


def read(document):
    if len(document) > 500000 or document.count(START) != 1 or document.count(END) != 1:
        raise ValueError("只支持一个完整的 IntentFlow 托管区，文档最多 50 万字符")
    match = PATTERN.search(document)
    if not match:
        raise ValueError("托管区格式不正确，请使用导出的规格文件")
    try:
        payload = json.loads(match[1])
    except (ValueError, RecursionError):
        raise ValueError("托管区不是有效的 JSON") from None
    if not isinstance(payload, dict) or payload.get("format") != "intentflow-spec/1":
        raise ValueError("不支持此规格格式")
    if not isinstance(payload.get("objects"), list) or len(payload["objects"]) > 100:
        raise ValueError("规格对象列表无效或超过 100 项")
    return payload, match


def export(v, pid, existing=""):
    baseline = v.baseline(pid)
    objects = [{k: o[k] for k in ("id", "kind", "title", "content")} for o in v.objects(pid)]
    payload = {"format": "intentflow-spec/1", "project_id": pid, "baseline_id": baseline.id,
               "objects": objects, "export_hash": digest(objects)}
    block = START + "\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```\n" + END
    if START in existing or END in existing:
        old, match = read(existing)
        if old.get("project_id") != pid:
            raise ValueError("不能覆盖其他项目的规格托管区")
        if digest(old["objects"]) != old.get("export_hash"):
            raise VersionConflict("托管区有人工修改，请先导入并审阅；导出不会覆盖这些修改")
        return existing[:match.start()] + block + existing[match.end():]
    return (existing or "# 需求规格\n\n此处可继续填写用户故事、设计理由和人工说明。\n") + "\n" + block + "\n"


def import_changes(v, pid, expected, document):
    payload, _ = read(document)
    baseline = v.baseline(pid)
    if payload.get("project_id") != pid:
        raise ValueError("请导入当前项目导出的规格，不接受跨项目对象身份")
    if payload.get("baseline_id") != expected or baseline.id != expected:
        raise VersionConflict("规格来源基线已过期，请先对照当前规则处理差异")
    from intentflow_core.behavior import validate_object
    old = {o["id"]: o for o in v.objects(pid)}
    seen, changes = set(), []
    for item in payload["objects"]:
        if not isinstance(item, dict) or set(item) != {"id", "kind", "title", "content"}:
            raise ValueError("每个规格对象须包含且仅包含 id、kind、title、content")
        oid = item["id"]
        if not isinstance(oid, str) or not oid or len(oid) > 36 or oid in seen:
            raise ValueError("对象 ID 无效或重复")
        seen.add(oid)
        content = validate_object(item["kind"], item["content"])
        if oid not in old or old[oid]["content"] != content or old[oid]["title"] != item["title"]:
            changes.append({**item, "content": content})
    changes.extend({"id": oid, "delete": True} for oid in old.keys() - seen)
    if not changes:
        raise ValueError("规格没有变化，无需新建需求修订")
    return changes
