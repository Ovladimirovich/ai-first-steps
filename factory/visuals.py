from __future__ import annotations

import copy
import re
import time
from pathlib import Path

from .actions import append_action_event, verify_action_log
from .assets import register_asset_bytes
from .core import (get_studio_document, load_project, project_dir, save_project)
from .fingerprints import project_fingerprints, verify_asset_record

_ASSET_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_MAX_PROMPT = 4000
_MAX_DESCRIPTION = 2000
_MAX_REFERENCES = 8


def _project_and_studio(project_id: str) -> tuple[dict, dict]:
    project = load_project(project_id)
    if int(project.get("schema_version", 1)) < 2:
        raise ValueError("Для истории визуальных вариантов требуется явная миграция проекта на v2")
    return project, get_studio_document(project_id)


def _scene_exists(studio: dict, scene_id: str) -> bool:
    return any(str(scene.get("id")) == str(scene_id)
               for scene in studio["spec"].get("script", {}).get("scenes", []))


def _clean_prompt(value, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Поле {field} должно быть текстом")
    cleaned = value.strip()
    if len(cleaned) > _MAX_PROMPT:
        raise ValueError(f"Поле {field} не должно превышать {_MAX_PROMPT} символов")
    return cleaned


def _asset_by_id(studio: dict, asset_id: str) -> dict:
    if not _ASSET_ID.fullmatch(str(asset_id)):
        raise FileNotFoundError(asset_id)
    asset = next((item for item in studio["assets"].get("assets", [])
                  if str(item.get("asset_id")) == str(asset_id)), None)
    if not asset or asset.get("type") != "scene_image":
        raise FileNotFoundError(asset_id)
    return asset


def _asset_lifecycle(project_id: str, studio: dict) -> dict[str, str]:
    state: dict[str, str] = {}
    for event in verify_action_log(project_id)["events"]:
        if not event.get("event_type", "").startswith("visual_variant_"):
            continue
        asset_id = str(event.get("data", {}).get("asset_id", ""))
        if not asset_id:
            continue
        kind = event["event_type"]
        if kind == "visual_variant_created":
            state.setdefault(asset_id, "created")
        elif kind == "visual_variant_reviewed":
            if state.get(asset_id) != "rejected":
                state[asset_id] = "reviewed"
        elif kind == "visual_variant_selected":
            state[asset_id] = "selected"
        elif kind == "visual_variant_deselected":
            if state.get(asset_id) != "rejected":
                state[asset_id] = "reviewed"
        elif kind == "visual_variant_rejected":
            state[asset_id] = "rejected"
    for scene_id, visual in studio["production"].get("visuals", {}).items():
        selected = visual.get("selected_asset_id")
        if selected:
            state[str(selected)] = "selected"
    return state


def list_visual_variants(project_id: str, scene_id: str | None = None) -> dict:
    project, studio = _project_and_studio(project_id)
    valid_scenes = {str(scene.get("id")) for scene in studio["spec"].get("script", {}).get("scenes", [])}
    if scene_id is not None and str(scene_id) not in valid_scenes:
        raise ValueError("Сцена не найдена в проекте")
    lifecycle = _asset_lifecycle(project_id, studio)
    current_inputs = project_fingerprints(project).get("image_generation", {})
    variants = []
    for record in studio["assets"].get("assets", []):
        if record.get("type") != "scene_image":
            continue
        target_scene = str(record.get("target", {}).get("scene_id", ""))
        if target_scene not in valid_scenes or (scene_id is not None and target_scene != str(scene_id)):
            continue
        status = lifecycle.get(str(record.get("asset_id")), "created")
        integrity = verify_asset_record(record, project_dir(project_id))
        if not integrity.get("available"):
            status = "missing"
        elif integrity.get("integrity_ok") is False:
            status = "damaged"
        current_fingerprint = current_inputs.get(target_scene, {}).get("fingerprint")
        recorded_fingerprint = record.get("input_fingerprint")
        variants.append({**record, "state": status, "available": integrity.get("available", False),
                         "integrity_ok": integrity.get("integrity_ok"),
                         "stale": bool(recorded_fingerprint and current_fingerprint and
                                       recorded_fingerprint != current_fingerprint),
                         "legacy_unverified": not bool(recorded_fingerprint and record.get("prompt")),
                         "is_selected": status == "selected"})
    variants.sort(key=lambda item: (str(item.get("target", {}).get("scene_id", "")),
                                    int(item.get("asset_version", 0))))
    return {"project_id": project_id, "project_revision": project["revision"], "variants": variants}


def _save_production(project: dict, studio: dict, production: dict, *, reason: str) -> dict:
    project["_native_update"] = {"spec": copy.deepcopy(studio["spec"]),
                                 "production": copy.deepcopy(production)}
    project["revision"] = int(project["revision"]) + 1
    project["updated_at"] = time.time()
    save_project(project, actor="user", reason=reason)
    return load_project(project["id"])


def update_visual_prompt(project_id: str, scene_id: str, body: dict) -> dict:
    project, studio = _project_and_studio(project_id)
    if int(body.get("expected_revision", -1)) != int(project["revision"]):
        raise ValueError("Проект изменился после просмотра. Обновите prompt перед сохранением.")
    if not _scene_exists(studio, scene_id):
        raise ValueError("Сцена не найдена в проекте")
    prompt_text = _clean_prompt(body.get("prompt", ""), "prompt")
    negative = _clean_prompt(body.get("negative_prompt", ""), "negative_prompt")
    description = body.get("description", "")
    if not isinstance(description, str) or len(description.strip()) > _MAX_DESCRIPTION:
        raise ValueError(f"Описание должно быть текстом длиной не более {_MAX_DESCRIPTION} символов")
    references = body.get("reference_asset_ids", [])
    if not isinstance(references, list) or len(references) > _MAX_REFERENCES:
        raise ValueError(f"Можно указать не более {_MAX_REFERENCES} reference-ассетов")
    manifest = studio["assets"].get("assets", [])
    by_id = {str(item.get("asset_id")): item for item in manifest}
    normalized_refs = []
    for ref in references:
        record = by_id.get(str(ref))
        if not record or record.get("type") != "scene_image":
            raise ValueError(f"Reference image {ref} не принадлежит этому проекту или не является изображением")
        normalized_refs.append(str(ref))
    if len(set(normalized_refs)) != len(normalized_refs):
        raise ValueError("Список reference-ассетов содержит дубликаты")
    production = copy.deepcopy(studio["production"])
    visual = production.setdefault("visuals", {}).setdefault(str(scene_id), {
        "description": "", "prompt": {"text": "", "negative": ""},
        "image_mode": "style", "legacy_path": None, "selected_asset_id": None,
        "reference_asset_ids": [],
    })
    previous_prompt = copy.deepcopy(visual.get("prompt", {}))
    previous_description = str(visual.get("description", ""))
    previous_refs = list(visual.get("reference_asset_ids", []))
    visual["prompt"] = {"text": prompt_text, "negative": negative}
    visual["description"] = description.strip()
    visual["reference_asset_ids"] = normalized_refs
    if (previous_prompt == visual["prompt"] and previous_description == visual["description"]
            and previous_refs == normalized_refs):
        return {"project": project, "studio": studio, "unchanged": True}
    append_action_event(project_id, "visual_prompt_update_requested", actor="user", data={
        "scene_id": str(scene_id), "expected_revision": project["revision"],
        "prompt": {"text": prompt_text, "negative": negative},
        "description": description.strip(), "reference_asset_ids": normalized_refs,
    })
    updated = _save_production(project, studio, production, reason="visual_prompt_updated")
    updated_studio = get_studio_document(project_id)
    append_action_event(project_id, "visual_prompt_updated", actor="user", data={
        "scene_id": str(scene_id), "production_revision": updated_studio["production_revision"],
        "prompt": {"text": prompt_text, "negative": negative},
        "description": description.strip(), "reference_asset_ids": normalized_refs,
    })
    return {"project": updated, "studio": updated_studio, "unchanged": False}


def create_visual_variant(project_id: str, scene_id: str, image_bytes: bytes, *,
                          expected_revision: int, mime: str, extension: str,
                          prompt: dict | None = None) -> dict:
    project, studio = _project_and_studio(project_id)
    if int(expected_revision) != int(project["revision"]):
        raise ValueError("Проект изменился перед сохранением варианта. Обновите сцену и повторите загрузку.")
    if not _scene_exists(studio, scene_id):
        raise ValueError("Сцена не найдена в проекте")
    if mime not in ("image/png", "image/jpeg", "image/webp"):
        raise ValueError("Поддерживаются только PNG, JPG и WebP")
    if not image_bytes or len(image_bytes) > 3_500_000:
        raise ValueError("Размер варианта изображения должен быть от 1 байта до 3,5 МБ")
    prompt = prompt if isinstance(prompt, dict) else {}
    prompt_record = {"text": _clean_prompt(prompt.get("text", ""), "prompt"),
                     "negative": _clean_prompt(prompt.get("negative", ""), "negative_prompt")}
    visual = studio["production"].get("visuals", {}).get(str(scene_id), {})
    if not prompt_record["text"] and not prompt_record["negative"]:
        current_prompt = visual.get("prompt", {})
        prompt_record = {"text": str(current_prompt.get("text", "")),
                         "negative": str(current_prompt.get("negative", ""))}
    fingerprint = project_fingerprints(project)["image_generation"][str(scene_id)]["fingerprint"]
    record = register_asset_bytes(project_id, image_bytes, asset_type="scene_image",
                                  target={"scene_id": str(scene_id)}, extension=extension, mime=mime,
                                  source="uploaded", provenance="visual_variant_upload",
                                  input_fingerprint=fingerprint,
                                  metadata={"prompt": prompt_record, "created_by": "user"})
    append_action_event(project_id, "visual_variant_created", actor="user", data={
        "scene_id": str(scene_id), "asset_id": record["asset_id"],
        "asset_version": record["asset_version"], "input_fingerprint": fingerprint,
    })
    return {"variant": record, "state": "created", "project_revision": project["revision"]}


def review_visual_variant(project_id: str, asset_id: str) -> dict:
    project, studio = _project_and_studio(project_id)
    asset = _asset_by_id(studio, asset_id)
    lifecycle = _asset_lifecycle(project_id, studio)
    state = lifecycle.get(asset_id, "created")
    if state in ("rejected", "missing", "damaged"):
        raise ValueError(f"Нельзя просмотреть вариант в состоянии {state}")
    integrity = verify_asset_record(asset, project_dir(project_id))
    if not integrity.get("available") or not integrity.get("integrity_ok"):
        raise ValueError("Файл варианта отсутствует или повреждён")
    if state != "selected":
        append_action_event(project_id, "visual_variant_reviewed", actor="user", data={
            "asset_id": asset_id, "scene_id": asset.get("target", {}).get("scene_id"),
            "asset_version": asset.get("asset_version"),
        })
    return {"asset_id": asset_id, "state": "selected" if state == "selected" else "reviewed"}


def select_visual_variant(project_id: str, asset_id: str, expected_revision: int) -> dict:
    project, studio = _project_and_studio(project_id)
    if int(expected_revision) != int(project["revision"]):
        raise ValueError("Проект изменился после просмотра варианта. Обновите историю перед выбором.")
    asset = _asset_by_id(studio, asset_id)
    scene_id = str(asset.get("target", {}).get("scene_id", ""))
    if not _scene_exists(studio, scene_id):
        raise ValueError("Сцена варианта отсутствует в текущем проекте")
    lifecycle = _asset_lifecycle(project_id, studio)
    state = lifecycle.get(asset_id, "created")
    if state == "rejected":
        raise ValueError("Отклонённый вариант нельзя выбрать")
    integrity = verify_asset_record(asset, project_dir(project_id))
    if not integrity.get("available") or not integrity.get("integrity_ok"):
        raise ValueError("Файл варианта отсутствует или повреждён")
    production = copy.deepcopy(studio["production"])
    visual = production.setdefault("visuals", {}).setdefault(scene_id, {})
    previous_id = visual.get("selected_asset_id")
    if str(previous_id or "") == asset_id:
        return {"project": project, "already_selected": True, "asset_id": asset_id}
    if state != "reviewed":
        raise ValueError("Сначала просмотрите вариант, затем выберите его")
    append_action_event(project_id, "visual_variant_selection_requested", actor="user", data={
        "asset_id": asset_id, "scene_id": scene_id, "expected_revision": expected_revision,
    })
    visual["selected_asset_id"] = asset_id
    visual["image_mode"] = "upload"
    visual["legacy_path"] = None
    updated = _save_production(project, studio, production, reason="visual_variant_selected")
    if previous_id:
        append_action_event(project_id, "visual_variant_deselected", actor="user", data={
            "asset_id": str(previous_id), "scene_id": scene_id,
        })
    append_action_event(project_id, "visual_variant_selected", actor="user", data={
        "asset_id": asset_id, "scene_id": scene_id,
        "production_revision": updated.get("production_revision"),
    })
    return {"project": updated, "already_selected": False, "asset_id": asset_id}


def reject_visual_variant(project_id: str, asset_id: str, expected_revision: int) -> dict:
    project, studio = _project_and_studio(project_id)
    if int(expected_revision) != int(project["revision"]):
        raise ValueError("Проект изменился после просмотра варианта. Обновите историю перед отклонением.")
    asset = _asset_by_id(studio, asset_id)
    scene_id = str(asset.get("target", {}).get("scene_id", ""))
    lifecycle = _asset_lifecycle(project_id, studio)
    state = lifecycle.get(asset_id, "created")
    if state == "rejected":
        return {"asset_id": asset_id, "state": "rejected", "already_rejected": True}
    production = copy.deepcopy(studio["production"])
    visual = production.setdefault("visuals", {}).setdefault(scene_id, {})
    is_selected = str(visual.get("selected_asset_id") or "") == asset_id
    if is_selected:
        visual["selected_asset_id"] = None
        visual["image_mode"] = "style"
        visual["legacy_path"] = None
    append_action_event(project_id, "visual_variant_rejection_requested", actor="user", data={
        "asset_id": asset_id, "scene_id": scene_id, "expected_revision": expected_revision,
    })
    if is_selected:
        updated = _save_production(project, studio, production, reason="selected_visual_variant_rejected")
        append_action_event(project_id, "visual_variant_deselected", actor="user", data={
            "asset_id": asset_id, "scene_id": scene_id,
        })
    else:
        updated = project
    append_action_event(project_id, "visual_variant_rejected", actor="user", data={
        "asset_id": asset_id, "scene_id": scene_id,
        "production_revision": updated.get("production_revision"),
    })
    return {"project": updated, "asset_id": asset_id, "state": "rejected"}


def deselect_visual_variant(project_id: str, asset_id: str, expected_revision: int) -> dict:
    project, studio = _project_and_studio(project_id)
    if int(expected_revision) != int(project["revision"]):
        raise ValueError("Проект изменился после просмотра варианта. Обновите историю перед сбросом.")
    asset = _asset_by_id(studio, asset_id)
    scene_id = str(asset.get("target", {}).get("scene_id", ""))
    production = copy.deepcopy(studio["production"])
    visual = production.setdefault("visuals", {}).setdefault(scene_id, {})
    if str(visual.get("selected_asset_id") or "") != asset_id:
        return {"project": project, "already_deselected": True, "asset_id": asset_id}
    visual["selected_asset_id"] = None
    visual["image_mode"] = "style"
    visual["legacy_path"] = None
    append_action_event(project_id, "visual_variant_deselection_requested", actor="user", data={
        "asset_id": asset_id, "scene_id": scene_id, "expected_revision": expected_revision,
    })
    updated = _save_production(project, studio, production, reason="visual_variant_deselected")
    append_action_event(project_id, "visual_variant_deselected", actor="user", data={
        "asset_id": asset_id, "scene_id": scene_id,
        "production_revision": updated.get("production_revision"),
    })
    return {"project": updated, "already_deselected": False, "asset_id": asset_id}
