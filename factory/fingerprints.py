from __future__ import annotations

import hashlib
import json
import math
import threading
from pathlib import Path
from typing import Any

from .schema_v2 import empty_asset_manifest, v1_to_v2, v2_to_v1
from .timing import TIMING_ENGINE_VERSION, pause_after_s, timing_for

FINGERPRINT_VERSION = 1
VOICE_ENGINE_VERSION = "factory-demo-silence-v1"
FRAME_ENGINE_VERSION = "factory-legacy-frame-v1"
_CONTENT_HASH_CACHE: dict[str, tuple[int, int, str]] = {}
_CONTENT_HASH_LOCK = threading.Lock()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(_safe_inputs(value))).hexdigest()


def _safe_inputs(value: Any) -> Any:
    """Exclude secrets and non-result metadata before hashing dependency summaries."""
    secret_fragments = ("secret", "token", "password", "api_key", "apikey", "authorization", "credential")
    volatile_keys = {"created_at", "updated_at", "timestamp", "action_id", "actor", "session_id",
                     "ui_state", "current_step", "revision_id", "project_revision", "spec_revision",
                     "production_revision"}
    if isinstance(value, dict):
        return {str(key): _safe_inputs(item) for key, item in value.items()
                if str(key).lower() not in volatile_keys
                and not any(fragment in str(key).lower() for fragment in secret_fragments)}
    if isinstance(value, (list, tuple)):
        return [_safe_inputs(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Fingerprint inputs cannot contain NaN or infinity")
        return int(value) if value.is_integer() else round(value, 12)
    return value


def _dep_hashes(**dependencies: Any) -> dict[str, str]:
    return {name: fingerprint(_safe_inputs(value)) for name, value in dependencies.items()}


def _combine(dependencies: dict[str, str], **extra: Any) -> str:
    return fingerprint({"fingerprint_version": FINGERPRINT_VERSION,
                        "dependencies": dependencies, **_safe_inputs(extra)})


def _file_hash(root: Path, relative: str, *, force: bool = False) -> tuple[str | None, bool, bool]:
    """Return actual digest, available, path-is-safe; never follows an asset outside the project."""
    try:
        candidate = (root / relative).resolve()
        base = root.resolve()
        if base not in candidate.parents:
            return None, False, False
        if not candidate.is_file():
            return None, False, True
        stat = candidate.stat()
        cache_key = str(candidate)
        with _CONTENT_HASH_LOCK:
            cached = _CONTENT_HASH_CACHE.get(cache_key)
        if not force and cached and cached[:2] == (stat.st_size, stat.st_mtime_ns):
            return cached[2], True, True
        hasher = hashlib.sha256()
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        value = hasher.hexdigest()
        with _CONTENT_HASH_LOCK:
            _CONTENT_HASH_CACHE[cache_key] = (stat.st_size, stat.st_mtime_ns, value)
        return value, True, True
    except OSError:
        return None, False, True


def verify_project_file(root: Path, relative: str, expected_sha256: str | None, *, force: bool = False) -> dict:
    actual, available, safe = _file_hash(root, relative, force=force)
    return {"sha256": actual, "available": available, "path_safe": safe,
            "integrity_ok": bool(available and safe and expected_sha256 and actual == expected_sha256)}


def verify_asset_record(record: dict, root: Path, *, force: bool = False) -> dict:
    asset_id = str(record.get("asset_id", ""))
    return _asset_state(asset_id, None, {asset_id: record}, root, force=force)


def _manifest_asset_summary(record: dict, root: Path) -> dict:
    asset_id = str(record.get("asset_id", ""))
    relative = str(record.get("path", ""))
    try:
        candidate = (root / relative).resolve()
        path_safe = root.resolve() in candidate.parents
        available = path_safe and candidate.is_file()
    except OSError:
        path_safe, available = False, False
    version = int(record.get("asset_version", record.get("sequence", 1)))
    sha = record.get("sha256")
    dependencies = _dep_hashes(asset_identity={"asset_id": asset_id, "asset_version": version},
                               declared_content=sha or "unverified", path_safe=path_safe)
    return {"asset_id": asset_id, "asset_version": version, "sha256": sha,
            "available": available, "integrity_ok": None, "integrity_checked": False,
            "path_safe": path_safe, "path": relative,
            "fingerprint": _combine(dependencies), "dependencies": dependencies}


def _asset_state(asset_id: str | None, legacy_path: str | None, by_id: dict[str, dict], root: Path,
                 *, force: bool = False) -> dict:
    record = by_id.get(str(asset_id)) if asset_id else None
    relative = str(record.get("path", "")) if record else str(legacy_path or "")
    actual_hash, available, safe_path = _file_hash(root, relative, force=force) if relative else (None, False, True)
    declared_hash = str(record.get("sha256", "")) if record else ""
    integrity = bool(available and (not declared_hash or declared_hash == actual_hash))
    version = int(record.get("asset_version", record.get("sequence", 1))) if record else 0
    identity = str(record.get("asset_id", asset_id or "legacy-path")) if record else str(asset_id or "legacy-path")
    dependencies = _dep_hashes(asset_identity={"asset_id": identity, "asset_version": version},
                               asset_content=actual_hash or declared_hash or "missing",
                               path_safe=safe_path)
    return {"asset_id": identity, "asset_version": version,
            "sha256": actual_hash or declared_hash or None,
            "available": available, "integrity_ok": integrity if record else available,
            "integrity_checked": True, "path_safe": safe_path, "fingerprint": _combine(dependencies),
            "dependencies": dependencies}


def load_project_fingerprint_inputs(project: dict) -> tuple[dict, dict, dict, Path]:
    """Load native v2 inputs when present; otherwise adapt v1 without writing or migrating it."""
    # Local import avoids a module cycle: core.artifact_state also consumes this module.
    from .core import _read_asset_manifest, _read_v2_state, project_dir

    root = project_dir(str(project.get("id", "")))
    try:
        metadata_path = root / "project.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if int(metadata.get("schema_version", 1)) >= 2:
            story, production = _read_v2_state(root, metadata)
            return story, production, _read_asset_manifest(root), root
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    story, production = v1_to_v2(project.get("spec", {}))
    return story, production, empty_asset_manifest(), root


def project_fingerprints(project: dict, *, story: dict | None = None,
                         production: dict | None = None, manifest: dict | None = None,
                         root: Path | None = None, force_hash: bool = False) -> dict:
    """Compute content-addressed inputs for story, production, per-line/per-scene and renders.

    The result contains hashes and safe dependency labels only; it never returns prompts,
    provider credentials, or other raw configuration values.
    """
    from .core import RENDERER_VERSION as current_renderer_version

    if story is None or production is None or manifest is None or root is None:
        loaded_story, loaded_production, loaded_manifest, loaded_root = load_project_fingerprint_inputs(project)
        story = story if story is not None else loaded_story
        production = production if production is not None else loaded_production
        manifest = manifest if manifest is not None else loaded_manifest
        root = root if root is not None else loaded_root

    legacy = v2_to_v1(story, production, manifest)
    timing = timing_for(legacy)
    from .settings import load_settings
    runtime_voice_settings = load_settings()
    voice_provider = str(runtime_voice_settings.get("voice_provider", "demo"))
    runtime_image_profile = {
        "provider": runtime_voice_settings.get("comfyui_image_provider", "local"),
        "profile_id": ("comfyui-agnes-image-v1" if runtime_voice_settings.get("comfyui_image_provider") == "agnes_image"
                       else "comfyui-core-txt2img-v1"),
        "base_url": runtime_voice_settings.get("comfyui_base_url", "http://127.0.0.1:8188"),
        "model": runtime_voice_settings.get("comfyui_local_model", ""),
        "quality": "1K", "aspect_ratio": "4:3",
        "width": 512, "height": 512, "steps": 20, "cfg": 7.0,
    }
    voice_engine_version = "factory-piper-cli-v1" if voice_provider == "piper" else VOICE_ENGINE_VERSION
    scenes = sorted(story.get("script", {}).get("scenes", []), key=lambda item: item.get("order", 0))
    legacy_scenes = {str(scene.get("id")): scene for scene in legacy.get("script", {}).get("scenes", [])}
    heroes = {str(hero.get("id")): hero for hero in story.get("heroes", [])}
    hero_voices = production.get("hero_voices", {})
    dialogue = production.get("dialogue", {})
    visuals = production.get("visuals", {})
    profile_map = production.get("profiles", {})
    records = manifest.get("assets", []) if isinstance(manifest, dict) else []
    by_id = {str(record.get("asset_id")): record for record in records if record.get("asset_id")}
    all_assets = {asset_id: _manifest_asset_summary(record, root) for asset_id, record in by_id.items()}

    timing_by_line = {str(row["id"]): row for row in timing.get("lines", [])}
    lines_by_scene: dict[str, list[dict]] = {}
    for scene in scenes:
        lines_by_scene[str(scene.get("id", ""))] = list(scene.get("lines", []))

    story_fp = fingerprint(_safe_inputs(story))
    production_fp = fingerprint(_safe_inputs(production))
    timing_inputs = {
        "scenes": [{"id": scene.get("id"), "order": scene.get("order"),
                    "lines": [{key: line.get(key) for key in ("id", "hero", "text", "pause_after_s")}
                              for line in scene.get("lines", [])]} for scene in scenes],
        "policy": production.get("timing_policy", {}),
        "fps": legacy.get("format", {}).get("fps", 30),
        "engine": TIMING_ENGINE_VERSION,
    }
    timing_fp = fingerprint(_safe_inputs(timing_inputs))

    voice_lines: dict[str, dict] = {}
    for scene in scenes:
        for line in scene.get("lines", []):
            line_id = str(line.get("id", ""))
            hero_id = str(line.get("hero", ""))
            hero_voice = hero_voices.get(hero_id, {})
            delivery = dialogue.get(line_id, {})
            row = timing_by_line.get(line_id, {})
            provider_generation = {
                "voice_generation": production.get("voice_generation", production.get("tts", {})),
                "models": production.get("models", {}),
                "providers": production.get("providers", {}),
                "voice_prompt_template": production.get("voice_prompt_template", ""),
            }
            if voice_provider == "piper":
                from .voice import executable_signature, model_signature
                provider_generation["runtime_voice"] = {
                    "provider": "piper", "executable": executable_signature(runtime_voice_settings),
                    "model": model_signature(runtime_voice_settings, hero_id),
                }
            dependencies = _dep_hashes(
                line_content={"line_id": line_id, "text": line.get("text", ""), "hero_id": hero_id},
                voice_selection=hero_voice,
                line_delivery=delivery,
                provider_model_and_generation=provider_generation,
                duration_and_parameters={"duration_s": row.get("dur"), "engine": voice_engine_version},
            )
            voice_lines[line_id] = {"fingerprint": _combine(dependencies), "dependencies": dependencies}

    image_assets: dict[str, dict] = {}
    image_generation: dict[str, dict] = {}
    frame_inputs: dict[str, dict] = {}
    frame_engine_settings = {"engine": FRAME_ENGINE_VERSION, "renderer": current_renderer_version}
    global_image_config = {key: production.get(key) for key in ("image_generation", "image_models", "providers") if key in production}
    for scene in scenes:
        scene_id = str(scene.get("id", ""))
        visual = visuals.get(scene_id, {})
        selected = _asset_state(visual.get("selected_asset_id"), visual.get("legacy_path"), by_id, root,
                                force=force_hash)
        references = [_asset_state(asset_id, None, by_id, root, force=force_hash)
                      for asset_id in visual.get("reference_asset_ids", [])]
        if visual.get("selected_asset_id") in by_id:
            all_assets[str(visual["selected_asset_id"])] = selected
        for reference_id, reference_state in zip(visual.get("reference_asset_ids", []), references):
            if str(reference_id) in by_id:
                all_assets[str(reference_id)] = reference_state
        image_assets[scene_id] = selected
        scene_text = [{"id": line.get("id"), "hero": line.get("hero"), "text": line.get("text")}
                      for line in lines_by_scene.get(scene_id, [])]
        generation_visual = {key: value for key, value in visual.items()
                             if key not in ("selected_asset_id", "legacy_path")}
        visual_deps = _dep_hashes(
            scene_context={key: scene.get(key) for key in ("id", "order", "title", "purpose", "goal", "lines")},
            prompt_and_visual_direction=generation_visual,
            image_model_prompt_and_parameters={
                "generation": global_image_config,
                "model": visual.get("model", production.get("image_model", {})),
                "prompt_template_version": visual.get("prompt_template_version", production.get("image_prompt_template_version")),
                "runtime_profile": runtime_image_profile,
            },
            reference_assets=[item["fingerprint"] for item in references],
        )
        image_generation[scene_id] = {"fingerprint": _combine(visual_deps), "dependencies": visual_deps}

        # Frame fingerprints cover the inputs used by today's legacy frame builder, plus
        # selected uploaded pixels and its own renderer version. This is separate from
        # image-generation fingerprints so codec changes cannot stale image variants.
        legacy_scene = legacy_scenes.get(scene_id, {})
        frame_deps = _dep_hashes(
            scene_text_and_layout={key: legacy_scene.get(key) for key in ("id", "order", "title", "lines", "visual_note")},
            style=legacy.get("look", {}),
            selected_background=selected["fingerprint"],
            frame_parameters=frame_engine_settings,
        )
        frame_inputs[scene_id] = {"fingerprint": _combine(frame_deps), "dependencies": frame_deps}

    timing_rows_by_scene: dict[str, list[dict]] = {str(scene.get("id", "")): [] for scene in scenes}
    for row in timing.get("lines", []):
        timing_rows_by_scene.setdefault(str(row.get("scene", "")), []).append(row)
    render_configurations = {
        "draft": {"pipeline_preset": "ultrafast", "crf": 23, "concat_video": "copy",
                  "audio_codec": "aac", "audio_bitrate": "160k", "container": "mp4"},
        "final": {"pipeline_preset": "medium", "crf": 18, "concat_video": "copy",
                  "audio_codec": "aac", "audio_bitrate": "160k", "container": "mp4"},
    }
    segment_inputs: dict[str, dict] = {}
    segment_values_by_kind = {kind: [] for kind in render_configurations}
    scenes_for_timing = [str(scene.get("id", "")) for scene in scenes]
    for index, scene in enumerate(scenes):
        scene_id = str(scene.get("id", ""))
        rows = timing_rows_by_scene.get(scene_id, [])
        first_start = float(rows[0]["start"]) if rows else 0.0
        timing_fps = int(timing.get("fps", 30))
        local_rows = [{"id": row.get("id"), "scene": row.get("scene"), "text": row.get("text"),
                       "start_frame": round((float(row["start"]) - first_start) * timing_fps),
                       "end_frame": round((float(row["end"]) - first_start) * timing_fps),
                       "duration_frames": round(float(row["dur"]) * timing_fps)} for row in rows]
        if index + 1 < len(scenes):
            next_rows = timing_rows_by_scene.get(scenes_for_timing[index + 1], [])
            tail = max(0.0, float(next_rows[0]["start"]) - float(rows[-1]["end"])) if rows and next_rows else 0.0
        else:
            final_line = (lines_by_scene.get(scene_id) or [{}])[-1]
            tail = pause_after_s(final_line) if rows else 0.0
        variants = {}
        for kind, effective_config in render_configurations.items():
            profile = profile_map.get("preview" if kind == "draft" else "final", {})
            dependencies = _dep_hashes(
                frame_input=frame_inputs.get(scene_id, {}).get("fingerprint"),
                local_timing={"rows": local_rows,
                              "tail_frames": round(round(tail, 3) * int(timing.get("fps", 30))),
                              "fps": int(timing.get("fps", 30))},
                segment_profile={key: profile.get(key) for key in ("width", "height", "fps", "captions")},
                renderer_and_encoder={"version": current_renderer_version, **effective_config},
            )
            variants[kind] = {"fingerprint": _combine(dependencies), "dependencies": dependencies}
            segment_values_by_kind[kind].append(variants[kind]["fingerprint"])
        segment_inputs[scene_id] = variants

    render_inputs: dict[str, dict] = {}
    for kind in render_configurations:
        profile = profile_map.get("preview" if kind == "draft" else "final", {})
        dependencies = _dep_hashes(
            story={"story_fingerprint": story_fp},
            timing={"timing_fingerprint": timing_fp},
            voice_mix={"line_fingerprints": {key: value["fingerprint"] for key, value in voice_lines.items()},
                       "music": production.get("music", {}), "duration_s": timing.get("total")},
            scene_segments=segment_values_by_kind[kind],
            profile=profile,
            renderer_and_encoder={"version": current_renderer_version, **render_configurations[kind]},
        )
        render_inputs[kind] = {"fingerprint": _combine(dependencies), "dependencies": dependencies}

    return {
        "fingerprint_version": FINGERPRINT_VERSION,
        "project_id": str(project.get("id", "")),
        "schema_version": int(project.get("schema_version", 1)),
        "components": {"story": story_fp, "production": production_fp, "timing": timing_fp},
        "voice_lines": voice_lines,
        "image_generation": image_generation,
        "assets": all_assets,
        "assets_by_scene": image_assets,
        "frames": frame_inputs,
        "segments": segment_inputs,
        "renders": render_inputs,
    }


def changed_dependencies(previous: dict | None, current: dict) -> list[str]:
    """Return safe dependency labels whose stored fingerprint differs from current."""
    if not isinstance(previous, dict) or not isinstance(previous.get("dependencies"), dict):
        return ["fingerprint_version_or_metadata"]
    old = previous["dependencies"]
    now = current.get("dependencies", {})
    return sorted(key for key in set(old) | set(now) if old.get(key) != now.get(key))
