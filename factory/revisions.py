from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from .storage import atomic_write_json


def _content_hash(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def revisions_dir(project_root: Path) -> Path:
    return project_root / "revisions"


def read_revision(project_root: Path, revision_id: str) -> dict:
    if not revision_id or "/" in revision_id or "\\" in revision_id or revision_id in (".", ".."):
        raise ValueError("Некорректный ID ревизии")
    directory = revisions_dir(project_root) / revision_id
    metadata_path = directory / "revision.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(revision_id)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["spec"] = json.loads((directory / "spec.json").read_text(encoding="utf-8"))
    metadata["production"] = json.loads((directory / "production.json").read_text(encoding="utf-8"))
    if metadata.get("spec_sha256") and _content_hash(metadata["spec"]) != metadata["spec_sha256"]:
        raise ValueError(f"Повреждён снимок содержания ревизии {revision_id}")
    if metadata.get("production_sha256") and _content_hash(metadata["production"]) != metadata["production_sha256"]:
        raise ValueError(f"Повреждён снимок production ревизии {revision_id}")
    return metadata

def list_revisions(project_root: Path) -> list[dict]:
    directory = revisions_dir(project_root)
    if not directory.is_dir():
        return []
    result = []
    for child in directory.iterdir():
        if not child.is_dir() or not (child / "revision.json").is_file():
            continue
        try:
            item = json.loads((child / "revision.json").read_text(encoding="utf-8"))
            result.append(item)
        except (OSError, ValueError):
            continue
    return sorted(result, key=lambda item: (item.get("sequence", 0), item.get("created_at", 0)))

def create_revision(project_root: Path, spec: dict, production: dict, *, sequence: int,
                    project_revision: int, spec_revision: int, production_revision: int,
                    parent_revision_id: str | None, changed_domains: list[str],
                    actor: str = "user", action_id: str | None = None,
                    restored_from: str | None = None, reason: str = "accepted_edit") -> dict:
    revision_id = f"r{sequence:06d}-{uuid.uuid4().hex[:8]}"
    directory = revisions_dir(project_root) / revision_id
    directory.mkdir(parents=True, exist_ok=False)
    atomic_write_json(directory / "spec.json", spec)
    atomic_write_json(directory / "production.json", production)
    metadata = {
        "revision_id": revision_id,
        "sequence": int(sequence),
        "project_revision": int(project_revision),
        "spec_revision": int(spec_revision),
        "production_revision": int(production_revision),
        "parent_revision_id": parent_revision_id,
        "changed_domains": sorted(set(changed_domains)),
        "actor": actor,
        "action_id": action_id,
        "restored_from": restored_from,
        "reason": reason,
        "spec_sha256": _content_hash(spec),
        "production_sha256": _content_hash(production),
        "created_at": time.time(),
    }
    atomic_write_json(directory / "revision.json", metadata)
    return metadata

def public_revision(metadata: dict, current_revision_id: str | None = None) -> dict:
    return {**metadata, "is_current": metadata.get("revision_id") == current_revision_id}
