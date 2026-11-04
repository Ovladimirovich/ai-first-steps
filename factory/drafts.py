from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .core import (_read_asset_manifest, _read_v2_state, digest, load_project,
                   project_dir, save_project, validate_spec)
from .schema_v2 import validate_production, validate_story_v2, v2_to_v1
from .storage import atomic_write_json, project_lock

_SESSION_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")


def _draft_path(project_root: Path, session_id: str) -> Path:
    if not _SESSION_ID.fullmatch(str(session_id)):
        raise ValueError("Некорректный ID черновика")
    return project_root / "studio" / "drafts" / f"{session_id}.json"


def _validate_state(project_root: Path, story: dict, production: dict, manifest: dict) -> None:
    validate_story_v2(story)
    validate_production(production)
    known_assets = {str(item.get("asset_id")) for item in manifest.get("assets", [])}
    for visual in production.get("visuals", {}).values():
        for asset_id in [visual.get("selected_asset_id"), *visual.get("reference_asset_ids", [])]:
            if asset_id and str(asset_id) not in known_assets:
                raise ValueError(f"Визуальная настройка ссылается на неизвестный asset_id: {asset_id}")
        path = visual.get("legacy_path")
        if path:
            relative = Path(str(path))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Путь production asset должен оставаться внутри каталога проекта")
    for dialogue in production.get("dialogue", {}).values():
        asset_id = dialogue.get("selected_asset_id")
        if asset_id and str(asset_id) not in known_assets:
            raise ValueError(f"Диалог ссылается на неизвестный asset_id: {asset_id}")
    legacy = v2_to_v1(story, production, manifest)
    if legacy.get("script", {}).get("scenes"):
        validate_spec(legacy)
    # Check all renderer-facing file references are contained by the project root.
    root = project_root.resolve()
    for scene in legacy.get("script", {}).get("scenes", []):
        image_path = scene.get("image", {}).get("path")
        if image_path and root not in (project_root / image_path).resolve().parents:
            raise ValueError("Путь фонового изображения выходит за каталог проекта")


def _current(project_id: str) -> tuple[dict, dict, dict, dict]:
    project = load_project(project_id)
    if int(project.get("schema_version", 1)) < 2:
        raise ValueError("Перед работой с черновиками явно мигрируйте проект на v2")
    root = project_dir(project_id)
    story, production = _read_v2_state(root, project)
    manifest = _read_asset_manifest(root)
    return project, story, production, manifest


def save_project_draft(project_id: str, session_id: str, body: dict) -> dict:
    root = project_dir(project_id)
    path = _draft_path(root, session_id)
    with project_lock(project_id):
        project, current_story, current_production, manifest = _current(project_id)
        story = body.get("spec")
        production = body.get("production")
        if not isinstance(story, dict) or not isinstance(production, dict):
            raise ValueError("Черновик должен содержать spec и production")
        _validate_state(root, story, production, manifest)
        now = time.time()
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = {}
        if old.get("status") == "committed":
            raise ValueError("Этот черновик уже принят; начните новую сессию редактирования")
        base_project_revision = int(body.get("base_project_revision", project.get("revision", 1)))
        base_spec_revision = int(body.get("base_spec_revision", project.get("spec_revision", 1)))
        base_production_revision = int(body.get("base_production_revision", project.get("production_revision", 1)))
        if old and (base_spec_revision != int(old.get("base_spec_revision", -1)) or
                    base_production_revision != int(old.get("base_production_revision", -1))):
            raise ValueError("Базовые ревизии черновика неизменяемы; для переноса правок создайте новую сессию")
        draft = {
            "draft_version": 1,
            "session_id": session_id,
            "project_id": project_id,
            "status": "draft",
            "base_project_revision": base_project_revision,
            "base_spec_revision": base_spec_revision,
            "base_production_revision": base_production_revision,
            "spec": story,
            "production": production,
            "created_at": old.get("created_at", now),
            "updated_at": now,
        }
        draft["conflict"] = (draft["base_spec_revision"] != int(project.get("spec_revision", 1)) or
                             draft["base_production_revision"] != int(project.get("production_revision", 1)))
        atomic_write_json(path, draft)
        return draft


def get_project_draft(project_id: str, session_id: str) -> dict:
    root = project_dir(project_id)
    path = _draft_path(root, session_id)
    project = load_project(project_id)
    if int(project.get("schema_version", 1)) < 2:
        raise ValueError("Перед работой с черновиками явно мигрируйте проект на v2")
    try:
        draft = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(session_id)
    draft["conflict"] = (draft.get("base_spec_revision") != int(project.get("spec_revision", 0)) or
                         draft.get("base_production_revision") != int(project.get("production_revision", 0)))
    return draft


def commit_project_draft(project_id: str, session_id: str, body: dict) -> dict:
    root = project_dir(project_id)
    path = _draft_path(root, session_id)
    with project_lock(project_id):
        project, current_story, current_production, manifest = _current(project_id)
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise FileNotFoundError(session_id)
        if draft.get("status") == "committed":
            return {"draft": draft, "project": project, "already_committed": True}
        story, production = draft["spec"], draft["production"]
        if body.get("base_spec_revision", draft.get("base_spec_revision")) != draft.get("base_spec_revision") or \
                body.get("base_production_revision", draft.get("base_production_revision")) != draft.get("base_production_revision"):
            raise ValueError("Подтверждение не совпадает с базовыми ревизиями черновика")
        if (int(draft.get("base_spec_revision", -1)) != int(project.get("spec_revision", 1)) or
                int(draft.get("base_production_revision", -1)) != int(project.get("production_revision", 1))):
            # Recover idempotently if the project commit succeeded before the draft status was written.
            if digest(story) == digest(current_story) and digest(production) == digest(current_production):
                draft["status"] = "committed"
                draft["conflict"] = False
                draft["applied_project_revision"] = int(project.get("revision", 1))
                draft["applied_spec_revision"] = int(project.get("spec_revision", 1))
                draft["applied_production_revision"] = int(project.get("production_revision", 1))
                draft["updated_at"] = time.time()
                atomic_write_json(path, draft)
                return {"draft": draft, "project": project, "already_committed": True}
            raise ValueError("Ревизии проекта изменились после начала черновика. Сравните версии и создайте новую сессию.")
        _validate_state(root, story, production, manifest)
        if digest(story) == digest(current_story) and digest(production) == digest(current_production):
            committed_project = project
        else:
            project["spec"] = v2_to_v1(story, production, manifest)
            project["_native_update"] = {"spec": story, "production": production}
            project["revision"] = int(project.get("revision", 1)) + 1
            project["title"] = str(story.get("intent", {}).get("theme") or "Новый ролик")[:80]
            project["updated_at"] = time.time()
            save_project(project)
            project.pop("_native_update", None)
            committed_project = project
        draft["status"] = "committed"
        draft["conflict"] = False
        draft["applied_project_revision"] = int(committed_project.get("revision", 1))
        draft["applied_spec_revision"] = int(committed_project.get("spec_revision", 1))
        draft["applied_production_revision"] = int(committed_project.get("production_revision", 1))
        draft["updated_at"] = time.time()
        atomic_write_json(path, draft)
        return {"draft": draft, "project": committed_project, "already_committed": False}
