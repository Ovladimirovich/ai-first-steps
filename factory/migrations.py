from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path

from .schema_v2 import empty_asset_manifest, v1_to_v2, validate_production, validate_story_v2, v2_to_v1
from .storage import atomic_write_json, project_lock


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_project_file(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    base = root.resolve()
    return candidate if base in candidate.parents and candidate.is_file() else None


def _asset_id(relative: str, sha256: str) -> str:
    key = hashlib.sha256(f"{relative}|{sha256}".encode("utf-8")).hexdigest()[:20]
    return f"legacy-{key}"


def _asset_record(root: Path, relative: str, asset_type: str, target: dict, source: str) -> dict | None:
    path = _safe_project_file(root, relative)
    if path is None:
        return None
    digest = _sha256(path)
    return {
        "asset_id": _asset_id(relative, digest),
        "type": asset_type,
        "target": target,
        "sequence": 1,
        "asset_version": 1,
        **({"render_version": 1} if asset_type in ("preview", "final_render") else {}),
        "path": Path(relative).as_posix(),
        "sha256": digest,
        "mime": __import__("mimetypes").guess_type(path.name)[0] or "application/octet-stream",
        "size_bytes": path.stat().st_size,
        "source": source,
        "provenance": "legacy_unverified",
        "input_fingerprint": None,
        "created_at": path.stat().st_mtime,
    }


def _source_fingerprint(metadata_path: Path, spec_path: Path) -> str:
    digest = hashlib.sha256(b"factory-v1-migration-plan:v1|")
    digest.update(metadata_path.read_bytes())
    digest.update(b"|spec|")
    digest.update(spec_path.read_bytes())
    return digest.hexdigest()


def migration_plan(project_id: str) -> dict:
    from .core import project_dir

    root = project_dir(project_id)
    metadata_path = root / "project.json"
    spec_path = root / "spec.json"
    if not metadata_path.is_file() or not spec_path.is_file():
        raise FileNotFoundError(project_id)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    schema_version = int(metadata.get("schema_version", 1))
    if schema_version >= 2:
        return {"project_id": project_id, "from_version": schema_version, "to_version": 2,
                "can_migrate": False, "already_migrated": True, "revision": metadata.get("revision", 1),
                "source_fingerprint": _source_fingerprint(metadata_path, spec_path),
                "errors": [], "warnings": [], "assets": []}
    errors, warnings, uploads, existing_assets = [], [], [], []
    if spec.get("spec_version") != 1:
        errors.append("В project.json указана схема v1, но spec.json не содержит spec_version=1")
    scenes = spec.get("script", {}).get("scenes", [])
    for scene in scenes:
        image = scene.get("image", {})
        relative = image.get("path")
        if image.get("mode") == "upload" and relative:
            path = _safe_project_file(root, str(relative))
            if path:
                uploads.append({"scene_id": scene.get("id"), "path": Path(relative).as_posix(),
                                "size_bytes": path.stat().st_size})
            else:
                candidate = (root / str(relative)).resolve()
                if root.resolve() not in candidate.parents:
                    errors.append(f"Путь загруженного фона сцены {scene.get('id')} выходит за каталог проекта")
                else:
                    warnings.append(f"Фон сцены {scene.get('id')} отсутствует; ссылка будет сохранена как legacy")
    candidates = [
        ("audio/voice_track.mp3", "dialogue_mix"),
        ("renders/draft.mp4", "preview"),
        ("renders/final.mp4", "final_render"),
    ]
    for scene in scenes:
        candidates.append((f"frames/{scene.get('id', '')}.jpg", "scene_frame"))
    for relative, asset_type in candidates:
        path = _safe_project_file(root, relative)
        if path:
            existing_assets.append({"path": Path(relative).as_posix(), "type": asset_type,
                                    "size_bytes": path.stat().st_size})
    try:
        from .core import validate_spec
        validate_spec(spec) if scenes else None
    except ValueError as exc:
        errors.append(f"Спецификация v1 не проходит текущую проверку: {exc}")
    return {
        "project_id": project_id,
        "from_version": schema_version,
        "to_version": 2,
        "can_migrate": schema_version == 1 and not errors,
        "already_migrated": False,
        "revision": int(metadata.get("revision", 1)),
        "source_fingerprint": _source_fingerprint(metadata_path, spec_path),
        "scene_count": len(scenes),
        "line_count": sum(len(scene.get("lines", [])) for scene in scenes),
        "uploads": uploads,
        "legacy_outputs": existing_assets,
        "estimated_bytes_to_hash": sum(item["size_bytes"] for item in uploads + existing_assets),
        "errors": errors,
        "warnings": warnings,
    }


def apply_v1_migration(project_id: str, expected_revision: int, expected_source_fingerprint: str) -> dict:
    from .core import project_dir
    from .revisions import create_revision

    with project_lock(project_id):
        root = project_dir(project_id)
        metadata_path, spec_path = root / "project.json", root / "spec.json"
        if not metadata_path.is_file() or not spec_path.is_file():
            raise FileNotFoundError(project_id)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if int(metadata.get("revision", 1)) != int(expected_revision):
            raise ValueError("Проект изменился после плана миграции. Сначала обновите план.")
        if int(metadata.get("schema_version", 1)) >= 2:
            raise ValueError("Проект уже использует схему v2")
        current_fingerprint = _source_fingerprint(metadata_path, spec_path)
        if not expected_source_fingerprint or current_fingerprint != expected_source_fingerprint:
            raise ValueError("Данные проекта изменились после плана миграции. Сначала обновите план.")
        report = migration_plan(project_id)
        if not report["can_migrate"]:
            raise ValueError("Миграция невозможна: " + "; ".join(report["errors"]))
        legacy_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        story, production = v1_to_v2(legacy_spec)
        manifest = empty_asset_manifest()
        by_path: dict[str, dict] = {}

        def add(relative: str, asset_type: str, target: dict, source: str) -> dict | None:
            normalized = Path(relative).as_posix()
            if normalized in by_path:
                return by_path[normalized]
            record = _asset_record(root, normalized, asset_type, target, source)
            if record:
                by_path[normalized] = record
                manifest["assets"].append(record)
            return record

        for scene in legacy_spec.get("script", {}).get("scenes", []):
            scene_id = str(scene.get("id", ""))
            image = scene.get("image", {})
            if image.get("mode") == "upload" and image.get("path"):
                record = add(str(image["path"]), "scene_image", {"scene_id": scene_id}, "uploaded")
                if record:
                    production["visuals"][scene_id]["selected_asset_id"] = record["asset_id"]
        for scene in legacy_spec.get("script", {}).get("scenes", []):
            scene_id = str(scene.get("id", ""))
            add(f"frames/{scene_id}.jpg", "scene_frame", {"scene_id": scene_id}, "legacy")
        add("audio/voice_track.mp3", "dialogue_mix", {}, "legacy")
        add("renders/draft.mp4", "preview", {}, "legacy")
        add("renders/final.mp4", "final_render", {}, "legacy")
        validate_story_v2(story)
        validate_production(production)
        from .core import validate_spec
        validate_spec(v2_to_v1(story, production, manifest)) if story.get("script", {}).get("scenes") else None

        migration_id = uuid.uuid4().hex
        backup = root / "backups" / "v1" / migration_id
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(metadata_path, backup / "project.json")
        shutil.copy2(spec_path, backup / "spec.json")
        atomic_write_json(backup / "backup.json", {
            "migration_id": migration_id,
            "source_revision": int(metadata.get("revision", 1)),
            "created_at": time.time(),
            "files": ["project.json", "spec.json"],
        })

        studio_dir = root / "studio"
        studio_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(studio_dir / "assets.json", manifest)
        sequence = 1
        revision = create_revision(
            root, story, production,
            sequence=sequence,
            project_revision=int(metadata.get("revision", 1)),
            spec_revision=1,
            production_revision=1,
            parent_revision_id=None,
            changed_domains=["migration"],
            actor="system",
            reason="migration_v1_baseline",
        )
        updated = {**metadata,
                   "schema_version": 2,
                   "project_revision": int(metadata.get("revision", 1)),
                   "spec_revision": 1,
                   "production_revision": 1,
                   "current_revision_id": revision["revision_id"],
                   "revision_sequence": sequence,
                   "migration_v1": {"migration_id": migration_id, "backup_path": (backup.relative_to(root)).as_posix(),
                                    "completed_at": time.time()}}
        # This metadata pointer is the commit point. Before it is replaced, v1 remains active.
        atomic_write_json(metadata_path, updated)
        # Root files are readable mirrors; v2 loading uses the immutable snapshot pointer.
        atomic_write_json(spec_path, story)
        atomic_write_json(root / "production.json", production)
        return {"project_id": project_id, "schema_version": 2, "revision": updated.get("revision", 1),
                "spec_revision": 1, "production_revision": 1,
                "current_revision_id": revision["revision_id"], "migration_id": migration_id,
                "assets_migrated": len(manifest["assets"]), "backup_path": updated["migration_v1"]["backup_path"]}
