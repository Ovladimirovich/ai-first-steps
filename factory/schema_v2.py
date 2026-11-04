from __future__ import annotations

import copy
import re
from typing import Any


def _clone(value: Any) -> Any:
    return copy.deepcopy(value)


def empty_asset_manifest() -> dict:
    return {"manifest_version": 1, "assets": []}


def default_profile(kind: str, video_format: dict | None = None) -> dict:
    old = _clone(video_format or {})
    profile = {
        "profile_id": f"{kind}-default-v1",
        "kind": kind,
        "width": int(old.get("width", 1920)),
        "height": int(old.get("height", 1080)),
        "fps": int(old.get("fps", 30)),
        "captions": old.get("captions", "burned"),
        "container": "mp4",
        "video_codec": "h264",
        "audio_codec": "aac",
        "quality": "draft" if kind == "preview" else "final",
        "renderer": {"name": "legacy-ffmpeg", "version": "factory-ffmpeg-segments-v3"},
    }
    return profile


def v1_to_v2(legacy_spec: dict) -> tuple[dict, dict]:
    """Split the v1 mixed document into story content and production direction."""
    old = _clone(legacy_spec)
    story = {
        "spec_version": 2,
        "intent": _clone(old.get("intent", {})),
        "heroes": [],
        "script": {"generator": _clone(old.get("script", {}).get("generator", {})), "scenes": []},
    }
    production = {
        "production_version": 1,
        "look": _clone(old.get("look", {})),
        "timing_policy": _clone(old.get("timing_policy", {"preset": "legacy_v1"})),
        "hero_voices": {},
        "visuals": {},
        "dialogue": {},
        "music": {"brief": "", "cues": []},
        "profiles": {
            "preview": default_profile("preview", old.get("format")),
            "final": default_profile("final", old.get("format")),
        },
    }
    for hero in old.get("heroes", []):
        item = _clone(hero)
        voice = item.pop("voice", {"provider": "demo", "voice_id": "male-warm", "rate": 1.0})
        story["heroes"].append(item)
        production["hero_voices"][str(item.get("id", ""))] = voice
    for scene in old.get("script", {}).get("scenes", []):
        content = {key: _clone(value) for key, value in scene.items() if key not in ("visual_note", "image")}
        story["script"]["scenes"].append(content)
        image = _clone(scene.get("image", {"mode": "style", "path": None}))
        production["visuals"][str(scene.get("id", ""))] = {
            "description": str(scene.get("visual_note", "")),
            "prompt": {"text": "", "negative": ""},
            "image_mode": image.get("mode", "style"),
            "legacy_path": image.get("path"),
            "selected_asset_id": None,
            "reference_asset_ids": [],
        }
        for line in scene.get("lines", []):
            production["dialogue"][str(line.get("id", ""))] = {
                "delivery": {"emotion": "", "pace": 1.0, "emphasis": []},
                "selected_asset_id": None,
            }
    return story, production


def _asset_path_map(asset_manifest: dict | None) -> dict[str, str]:
    result = {}
    for asset in (asset_manifest or {}).get("assets", []):
        asset_id, path = asset.get("asset_id"), asset.get("path")
        if asset_id and path:
            result[str(asset_id)] = str(path)
    return result


def v2_to_v1(story: dict, production: dict, asset_manifest: dict | None = None) -> dict:
    """Build the compatibility view consumed by the current UI and renderer."""
    result = {
        "spec_version": 1,
        "intent": _clone(story.get("intent", {})),
        "heroes": [],
        "look": _clone(production.get("look", {})),
        "format": _clone(production.get("profiles", {}).get("final", {})),
        "timing_policy": _clone(production.get("timing_policy", {"preset": "legacy_v1"})),
        "script": {"generator": _clone(story.get("script", {}).get("generator", {})), "scenes": []},
    }
    result["format"] = {key: result["format"][key] for key in ("width", "height", "fps", "captions") if key in result["format"]}
    for hero in story.get("heroes", []):
        item = _clone(hero)
        item["voice"] = _clone(production.get("hero_voices", {}).get(str(hero.get("id", "")),
                                                                    {"provider": "demo", "voice_id": "male-warm", "rate": 1.0}))
        result["heroes"].append(item)
    paths = _asset_path_map(asset_manifest)
    for scene in story.get("script", {}).get("scenes", []):
        item = _clone(scene)
        visual = production.get("visuals", {}).get(str(scene.get("id", "")), {})
        item["visual_note"] = str(visual.get("description", ""))
        selected_id = visual.get("selected_asset_id")
        image_path = paths.get(str(selected_id)) if selected_id else None
        image_path = image_path or visual.get("legacy_path")
        image_mode = visual.get("image_mode", "style")
        item["image"] = {"mode": "upload" if image_path else image_mode, "path": image_path}
        result["script"]["scenes"].append(item)
    return result


def merge_v1_view(legacy_spec: dict, base_story: dict, base_production: dict) -> tuple[dict, dict]:
    """Merge edits made by the legacy UI into v2 without dropping v2-only production data."""
    incoming = _clone(legacy_spec)
    story = _clone(base_story)
    production = _clone(base_production)
    story["intent"] = _clone(incoming.get("intent", {}))
    story["script"]["generator"] = _clone(incoming.get("script", {}).get("generator", {}))
    story["heroes"] = []
    for hero in incoming.get("heroes", []):
        item = _clone(hero)
        voice = item.pop("voice", None)
        hero_id = str(item.get("id", ""))
        if voice is not None:
            production.setdefault("hero_voices", {})[hero_id] = _clone(voice)
        story["heroes"].append(item)
    production["look"] = _clone(incoming.get("look", production.get("look", {})))
    production["timing_policy"] = _clone(incoming.get("timing_policy", production.get("timing_policy", {"preset": "legacy_v1"})))
    profile = production.setdefault("profiles", {}).setdefault("final", default_profile("final", incoming.get("format")))
    profile.update({key: _clone(value) for key, value in incoming.get("format", {}).items()})
    scenes = []
    for scene in incoming.get("script", {}).get("scenes", []):
        item = {key: _clone(value) for key, value in scene.items() if key not in ("visual_note", "image")}
        scene_id = str(scene.get("id", ""))
        visual = _clone(production.setdefault("visuals", {}).get(scene_id, {}))
        visual.setdefault("prompt", {"text": "", "negative": ""})
        visual.setdefault("selected_asset_id", None)
        visual.setdefault("reference_asset_ids", [])
        visual["description"] = str(scene.get("visual_note", ""))
        image = scene.get("image", {})
        visual["image_mode"] = image.get("mode", "style")
        visual["legacy_path"] = image.get("path")
        if visual["image_mode"] == "style":
            visual["selected_asset_id"] = None
            visual["legacy_path"] = None
        production["visuals"][scene_id] = visual
        for line in scene.get("lines", []):
            line_id = str(line.get("id", ""))
            production.setdefault("dialogue", {}).setdefault(line_id, {
                "delivery": {"emotion": "", "pace": 1.0, "emphasis": []},
                "selected_asset_id": None,
            })
        scenes.append(item)
    story["script"]["scenes"] = scenes
    return story, production


def validate_story_v2(story: dict) -> None:
    if not isinstance(story, dict) or story.get("spec_version") != 2:
        raise ValueError("Ожидалась спецификация содержания версии 2")
    if not isinstance(story.get("intent", {}), dict) or not isinstance(story.get("heroes", []), list):
        raise ValueError("Некорректная структура содержания v2")
    hero_ids = set()
    for hero in story.get("heroes", []):
        hero_id = str(hero.get("id", "")) if isinstance(hero, dict) else ""
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", hero_id) or hero_id in (".", "..") or hero_id in hero_ids:
            raise ValueError("ID героев v2 должны быть допустимыми и уникальными")
        hero_ids.add(hero_id)
    script = story.get("script", {})
    if not isinstance(script, dict) or not isinstance(script.get("scenes", []), list):
        raise ValueError("Некорректный список сцен v2")
    scene_ids = set()
    line_ids = set()
    for scene in script.get("scenes", []):
        scene_id = str(scene.get("id", "")) if isinstance(scene, dict) else ""
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", scene_id) or scene_id in (".", "..") or scene_id in scene_ids:
            raise ValueError("ID сцен v2 должны быть допустимыми и уникальными")
        scene_ids.add(scene_id)
        lines = scene.get("lines", [])
        if not isinstance(lines, list):
            raise ValueError(f"Некорректный список реплик в сцене {scene_id}")
        for line in lines:
            line_id = str(line.get("id", "")) if isinstance(line, dict) else ""
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", line_id) or line_id in (".", "..") or line_id in line_ids:
                raise ValueError("ID реплик v2 должны быть допустимыми и уникальными")
            if str(line.get("hero", "")) not in hero_ids:
                raise ValueError(f"Для реплики {line_id} не найден герой")
            line_ids.add(line_id)


def validate_production(production: dict) -> None:
    if not isinstance(production, dict) or production.get("production_version") != 1:
        raise ValueError("Ожидалась производственная спецификация версии 1")
    for field in ("profiles", "visuals", "hero_voices", "dialogue", "music"):
        if not isinstance(production.get(field), dict):
            raise ValueError(f"Некорректное поле production.{field}")
    for kind in ("preview", "final"):
        profile = production["profiles"].get(kind)
        if not isinstance(profile, dict):
            raise ValueError(f"Не задан производственный профиль {kind}")
        for dimension in ("width", "height", "fps"):
            if int(profile.get(dimension, 0)) <= 0:
                raise ValueError(f"Некорректный {dimension} в профиле {kind}")
    for hero_id, voice in production["hero_voices"].items():
        if not isinstance(voice, dict):
            raise ValueError(f"Некорректные настройки голоса героя {hero_id}")
    for line_id, dialogue in production["dialogue"].items():
        if not isinstance(dialogue, dict) or not isinstance(dialogue.get("delivery", {}), dict):
            raise ValueError(f"Некорректные настройки диалога реплики {line_id}")
    for scene_id, visual in production["visuals"].items():
        if not isinstance(visual, dict):
            raise ValueError(f"Некорректная визуальная настройка сцены {scene_id}")
        if visual.get("image_mode", "style") not in ("style", "upload", "generated"):
            raise ValueError(f"Неизвестный режим изображения сцены {scene_id}")
        if not isinstance(visual.get("prompt", {}), dict):
            raise ValueError(f"Некорректный prompt сцены {scene_id}")
        if not isinstance(visual.get("reference_asset_ids", []), list):
            raise ValueError(f"Некорректные reference asset IDs сцены {scene_id}")
    if not isinstance(production["music"].get("brief", ""), str) or not isinstance(production["music"].get("cues", []), list):
        raise ValueError("Некорректная музыкальная спецификация")
