from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from .core import RENDERER_VERSION, ROOT, artifact_state, digest, legacy_who, project_dir, renderer_timing
from .fingerprints import project_fingerprints, verify_asset_record, verify_project_file
from .assets import register_asset_file

JOBS: dict[str, dict] = {}
PLANS: dict[str, dict] = {}
_worker_lock = threading.Lock()


def _engine_module():
    path = ROOT / "tools" / "build_ffmpeg_video.py"
    spec = importlib.util.spec_from_file_location("factory_legacy_renderer", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _read_cache(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}-{uuid.uuid4().hex}.tmp")
    try:
        shutil.copyfile(source, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_cached_file(root: Path, relative: str | None) -> Path | None:
    if not relative:
        return None
    candidate = (root / str(relative)).resolve()
    return candidate if root.resolve() in candidate.parents else None


def _asset_records(root: Path) -> dict[str, dict]:
    manifest = _read_cache(root / "studio" / "assets.json")
    return {str(item.get("asset_id")): item for item in manifest.get("assets", [])
            if isinstance(item, dict) and item.get("asset_id")}


def _cached_output_is_valid(root: Path, entry, fallback: Path, asset_records: dict[str, dict]) -> bool:
    if isinstance(entry, dict) and entry.get("file"):
        path = _safe_cached_file(root, entry["file"])
    else:
        path = fallback
    if not path or not path.is_file():
        return False
    if isinstance(entry, dict) and entry.get("asset_id"):
        record = asset_records.get(str(entry["asset_id"]))
        if not record:
            return False
        verified = verify_asset_record(record, root)
        return bool(verified.get("available") and verified.get("integrity_ok"))
    return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_fingerprint(value) -> str | None:
    if isinstance(value, str):
        return value
    return str(value.get("fingerprint") or value.get("key")) if isinstance(value, dict) and (value.get("fingerprint") or value.get("key")) else None


def _voice_mix_fingerprint(fingerprints: dict) -> str:
    return digest({"fingerprint_version": fingerprints["fingerprint_version"],
                   "timing": fingerprints["components"]["timing"],
                   "lines": {key: item["fingerprint"] for key, item in fingerprints["voice_lines"].items()}})


def _voice_key(line: dict, hero: dict, project: dict | None = None) -> str:
    if project is not None:
        return project_fingerprints(project)["voice_lines"][str(line["id"])]["fingerprint"]
    return digest({"text": line["text"], "voice": hero.get("voice"), "provider": "demo-silence-v1"})


def _frame_key(scene: dict, spec: dict, project: dict | None = None) -> str:
    if project is not None:
        return project_fingerprints(project)["frames"][str(scene["id"])]["fingerprint"]
    return digest({"scene": scene, "look": spec.get("look"), "renderer": RENDERER_VERSION})


def _segment_entry(scene: dict, spec: dict, kind: str, project: dict | None = None,
                   fingerprints: dict | None = None) -> dict:
    if project is not None:
        data = fingerprints or project_fingerprints(project)
        return data["segments"][str(scene["id"])][kind]
    dependencies = {"scene": digest(scene), "look": digest(spec.get("look")),
                    "format": digest(spec.get("format")), "renderer": RENDERER_VERSION,
                    "quality": kind}
    key = digest(dependencies)
    return {"fingerprint": key, "dependencies": dependencies}


def _segment_key(scene: dict, spec: dict, kind: str, project: dict | None = None,
                 fingerprints: dict | None = None) -> str:
    return _segment_entry(scene, spec, kind, project, fingerprints)["fingerprint"]


def _pending_voice_count(project: dict) -> int:
    root = project_dir(project["id"])
    cache = _read_cache(root / "voice-cache.json")
    data = project_fingerprints(project)
    asset_records = _asset_records(root)
    lines = [line for scene in project["spec"]["script"]["scenes"] for line in scene.get("lines", [])]
    def current(line):
        entry = cache.get(line["id"])
        return (_cache_fingerprint(entry) == data["voice_lines"][str(line["id"])]["fingerprint"]
                and _cached_output_is_valid(root, entry, root / "audio" / f"{line['id']}.mp3", asset_records))
    return sum(1 for line in lines if not current(line))


def _pending_frame_count(project: dict) -> int:
    root = project_dir(project["id"])
    cache = _read_cache(root / "frames-cache.json")
    scenes = project["spec"]["script"]["scenes"]
    data = project_fingerprints(project)
    asset_records = _asset_records(root)
    def current(scene):
        entry = cache.get(scene["id"])
        return (_cache_fingerprint(entry) == data["frames"][str(scene["id"])]["fingerprint"]
                and _cached_output_is_valid(root, entry, root / "frames" / f"{scene['id']}.jpg", asset_records))
    return sum(1 for scene in scenes if not current(scene))


def _pending_scene_count(project: dict, kind: str) -> int:
    root = project_dir(project["id"])
    cache = _segment_cache(project)
    data = project_fingerprints(project)
    pending = 0
    for scene in project["spec"].get("script", {}).get("scenes", []):
        if not scene.get("lines"):
            continue
        key = _segment_key(scene, project["spec"], kind, project, data)
        entry = cache.get(f"{scene['id']}:{key}", {})
        cached_file = _safe_cached_file(root, entry.get("file")) if isinstance(entry, dict) else None
        valid_file = bool(cached_file and cached_file.is_file())
        if valid_file and int(project.get("schema_version", 1)) >= 2:
            expected_sha = entry.get("content_sha256") if isinstance(entry, dict) else None
            valid_file = bool(expected_sha and verify_project_file(root, str(entry["file"]), expected_sha).get("integrity_ok"))
        if not valid_file:
            pending += 1
    return pending


def plan(project: dict, stage: str, kind: str | None = None) -> dict:
    artifacts = artifact_state(project)
    spec = project["spec"]
    total_units = 0
    if not spec.get("script", {}).get("scenes"):
        raise ValueError("Сначала подготовьте сценарий")
    if stage == "voice":
        line_units = artifacts["voice_units"]
        total_units = line_units + 1  # per-line assets plus the assembled dialogue mix
        units = _pending_voice_count(project) + int(artifacts["voice"] != "ready")
        estimate = 1 if units == 0 else max(1, int(units * 0.25 + 1))
        message = f"Обновятся {units} из {total_units} демо-дорожек/сведений · примерно {estimate} сек. Стоимость: 0 ₽."
    elif stage == "frames":
        total_units = artifacts["scene_units"]
        units = _pending_frame_count(project)
        estimate = max(1, units * 2)
        message = f"Обновятся {units} из {total_units} кадров. Стоимость: 0 ₽."
    else:
        if artifacts["voice"] != "ready" or artifacts["frames"] != "ready":
            raise ValueError("Сначала обновите и проверьте озвучку и картинки")
        total_scenes = artifacts["scene_units"]
        total_units = total_scenes
        units = _pending_scene_count(project, kind or "draft")
        estimate = 3 if units == 0 else max(5, int(artifacts["duration_s"] * 0.65 * units / max(1, total_scenes)))
        message = f"Пересоберутся {units} из {total_scenes} сцен · финальная склейка около {estimate} секунд. Стоимость: 0 ₽."
    plan_id = uuid.uuid4().hex
    entry = {"id": plan_id, "project_id": project["id"], "stage": stage, "kind": kind,
             "revision": project["revision"], "spec_hash": digest(spec), "created_at": time.time(),
             "units": units, "total_units": total_units or units, "estimate_s": estimate, "cost": 0, "message": message}
    PLANS[plan_id] = entry
    return entry


def _start_job(project: dict, plan_entry: dict) -> dict:
    # A single lock serializes expensive work on the local machine.
    job_id = uuid.uuid4().hex
    job = {"id": job_id, "project_id": project["id"], "stage": plan_entry["stage"], "state": "queued",
           "progress": 0, "message": "В очереди", "log": [], "started_at": None, "finished_at": None}
    JOBS[job_id] = job
    thread = threading.Thread(target=_run_job, args=(job_id, project, plan_entry), daemon=True)
    thread.start()
    return job


def run(project: dict, plan_id: str, stage: str, kind: str | None = None) -> dict:
    plan_entry = PLANS.get(plan_id)
    if not plan_entry or plan_entry["project_id"] != project["id"] or plan_entry["stage"] != stage:
        raise ValueError("Смета не найдена или устарела. Обновите её перед запуском.")
    if plan_entry["revision"] != project["revision"] or plan_entry["spec_hash"] != digest(project["spec"]):
        raise ValueError("Замысел изменился после сметы. Проверьте обновлённую смету.")
    if stage == "render" and plan_entry["kind"] != kind:
        raise ValueError("Тип сборки не совпадает со сметой.")
    del PLANS[plan_id]
    return _start_job(project, plan_entry)


def _append(job, message, progress=None):
    job["message"] = message
    job["log"].append(message)
    job["log"] = job["log"][-40:]
    if progress is not None:
        job["progress"] = progress


def _run_job(job_id: str, project: dict, plan_entry: dict) -> None:
    job = JOBS[job_id]
    with _worker_lock:
        try:
            job["state"] = "running"
            job["started_at"] = time.time()
            if plan_entry["stage"] == "voice":
                _make_voice(project, job)
            elif plan_entry["stage"] == "frames":
                _make_frames(project, job)
            else:
                _make_render(project, job, plan_entry["kind"])
            job["state"] = "done"
            job["progress"] = 100
            _append(job, "Готово", 100)
        except Exception as exc:
            job["state"] = "error"
            job["error"] = str(exc)
            _append(job, f"Не получилось: {exc}")
        finally:
            job["finished_at"] = time.time()


def _make_voice(project: dict, job: dict) -> None:
    import imageio_ffmpeg
    root = project_dir(project["id"])
    audio_dir = root / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    data = renderer_timing(project["spec"])
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    root = project_dir(project["id"])
    cache_path = root / "voice-cache.json"
    try:
        line_cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        line_cache = {}
    line_specs = {line["id"]: line for scene in project["spec"]["script"]["scenes"] for line in scene["lines"]}
    fingerprint_data = project_fingerprints(project)
    native_v2 = int(project.get("schema_version", 1)) >= 2
    asset_records = _asset_records(root)
    for index, row in enumerate(data["lines"], 1):
        output = audio_dir / f"{row['id']}.mp3"
        line = line_specs[row["id"]]
        entry = fingerprint_data["voice_lines"][str(row["id"])]
        key = entry["fingerprint"]
        duration = max(0.5, float(row["dur"]))
        old_entry = line_cache.get(row["id"])
        immutable_file = _safe_cached_file(root, old_entry.get("file")) if isinstance(old_entry, dict) and old_entry.get("file") else None
        reused = _cache_fingerprint(old_entry) == key and _cached_output_is_valid(root, old_entry, output, asset_records)
        if reused and immutable_file and not output.is_file():
            _atomic_copy(immutable_file, output)
        if not reused:
            generated = audio_dir / (f".{row['id']}-{uuid.uuid4().hex}.mp3" if native_v2 else f"{row['id']}.mp3")
            subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
                            "-t", f"{duration:.3f}", "-q:a", "9", "-acodec", "libmp3lame", str(generated)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if native_v2:
                record = register_asset_file(project["id"], generated, asset_type="dialogue_audio",
                                             target={"line_id": str(row["id"])}, extension=".mp3",
                                             mime="audio/mpeg", input_fingerprint=key)
                immutable_file = root / record["path"]
                _atomic_copy(immutable_file, output)
                generated.unlink(missing_ok=True)
                line_cache[row["id"]] = {"fingerprint": key, "dependencies": entry["dependencies"],
                                          "asset_id": record["asset_id"], "asset_version": record["asset_version"],
                                          "file": record["path"]}
            else:
                line_cache[row["id"]] = {"fingerprint": key, "dependencies": entry["dependencies"]}
        action = "использую прежнюю" if reused else "создана"
        _append(job, f"Дорожка {index}/{len(data['lines'])}: {action}", int(index / max(1, len(data["lines"])) * 65))
    cache_path.write_text(json.dumps(line_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    track = audio_dir / "voice_track.mp3"
    mix_fingerprint = _voice_mix_fingerprint(fingerprint_data)
    mix_record = None
    if native_v2:
        previous_meta = _read_cache(root / "voice.meta.json")
        asset_manifest = _read_cache(root / "studio" / "assets.json")
        records = {str(item.get("asset_id")): item for item in asset_manifest.get("assets", [])
                   if isinstance(item, dict) and item.get("asset_id")}
        candidate = records.get(str(previous_meta.get("asset_id", "")))
        if previous_meta.get("hash") == mix_fingerprint and candidate and candidate.get("input_fingerprint") == mix_fingerprint:
            integrity = verify_asset_record(candidate, root)
            if integrity.get("available") and integrity.get("integrity_ok"):
                mix_record = candidate
                alias = verify_project_file(root, "audio/voice_track.mp3", candidate.get("sha256"))
                if not alias.get("integrity_ok"):
                    _atomic_copy(root / candidate["path"], track)
    if mix_record is None:
        generated_track = audio_dir / f".voice-track-{uuid.uuid4().hex}.mp3" if native_v2 else track
        total = max(0.5, float(data["total"]))
        subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-t", f"{total:.3f}", "-q:a", "9", "-acodec", "libmp3lame", str(generated_track)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if native_v2:
            mix_record = register_asset_file(project["id"], generated_track, asset_type="dialogue_mix",
                                             target={"mix": "voice_track"}, extension=".mp3",
                                             mime="audio/mpeg", input_fingerprint=mix_fingerprint)
            _atomic_copy(root / mix_record["path"], track)
            generated_track.unlink(missing_ok=True)
    (root / "timing.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # A lightweight SRT matching the same timeline.
    def stamp(seconds):
        ms = int(round(seconds * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    srt = "\n\n".join(f"{i}\n{stamp(x['start'])} --> {stamp(x['end'])}\n{x['text']}" for i, x in enumerate(data["lines"], 1))
    (root / "subtitles.srt").write_text(srt + "\n", encoding="utf-8")
    voice_state = artifact_state(project)
    voice_meta = {"hash": voice_state["voice_hash"],
                  "fingerprint_version": voice_state["fingerprint_version"],
                  "dependencies": {"timing": fingerprint_data["components"]["timing"],
                                   "line_fingerprints": {key: value["fingerprint"] for key, value in fingerprint_data["voice_lines"].items()}},
                  "demo": True}
    if mix_record:
        voice_meta.update({"asset_id": mix_record["asset_id"], "asset_version": mix_record["asset_version"],
                           "path": mix_record["path"], "sha256": mix_record["sha256"]})
    (root / "voice.meta.json").write_text(json.dumps(voice_meta, ensure_ascii=False), encoding="utf-8")
    _append(job, "Демо-озвучка готова. Это тишина с длительностью по тексту, не настоящий голос.", 95)


def _make_frames(project: dict, job: dict) -> None:
    from PIL import Image
    from .core import PALETTES
    module = _engine_module()
    spec = project["spec"]
    scenes = sorted(spec["script"]["scenes"], key=lambda x: x.get("order", 0))
    module.SCENE_TITLES = {s["id"]: s.get("title", f"Сцена {i+1}") for i, s in enumerate(scenes)}
    colors = PALETTES.get(spec.get("look", {}).get("style_preset"), PALETTES["warm_workshop"])
    bg = colors["bg"]
    module.P["bg"] = bg
    module.P["yellow"] = colors["highlight"]
    module.P["teal"] = colors["accent"]
    root = project_dir(project["id"])
    frame_dir = root / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    cache_path = root / "frames-cache.json"
    try:
        frame_cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        frame_cache = {}
    fingerprint_data = project_fingerprints(project)
    native_v2 = int(project.get("schema_version", 1)) >= 2
    asset_records = _asset_records(root)
    for index, scene in enumerate(scenes, 1):
        frame_path = frame_dir / f"{scene['id']}.jpg"
        entry = fingerprint_data["frames"][str(scene["id"])]
        key = entry["fingerprint"]
        old_entry = frame_cache.get(scene["id"])
        immutable_file = _safe_cached_file(root, old_entry.get("file")) if isinstance(old_entry, dict) and old_entry.get("file") else None
        reused = _cache_fingerprint(old_entry) == key and _cached_output_is_valid(root, old_entry, frame_path, asset_records)
        if reused and immutable_file and not frame_path.is_file():
            _atomic_copy(immutable_file, frame_path)
        if not reused:
            first = (scene.get("lines") or [{}])[0]
            text = first.get("text", "")
            hero = legacy_who(first.get("hero", "h1"), spec)
            bg_path = None
            image_ref = scene.get("image", {})
            if image_ref.get("mode") == "upload" and image_ref.get("path"):
                candidate = (root / image_ref["path"]).resolve()
                if root.resolve() in candidate.parents and candidate.is_file():
                    bg_path = candidate
            # Existing renderer's exact drawing function; a static representative frame.
            image = module.draw_pixar_image(text, hero, scene["id"], W=1920, H=1080, bg_path=bg_path, is_gap=False, bg_strength=0.82 if bg_path else 0.18)
            generated = frame_dir / (f".{scene['id']}-{uuid.uuid4().hex}.jpg" if native_v2 else f"{scene['id']}.jpg")
            image.save(generated, "JPEG", quality=91)
            if native_v2:
                record = register_asset_file(project["id"], generated, asset_type="scene_frame",
                                             target={"scene_id": str(scene["id"])}, extension=".jpg",
                                             mime="image/jpeg", input_fingerprint=key)
                immutable_file = root / record["path"]
                _atomic_copy(immutable_file, frame_path)
                generated.unlink(missing_ok=True)
                frame_cache[scene["id"]] = {"fingerprint": key, "dependencies": entry["dependencies"],
                                             "asset_id": record["asset_id"], "asset_version": record["asset_version"],
                                             "file": record["path"]}
            else:
                frame_cache[scene["id"]] = {"fingerprint": key, "dependencies": entry["dependencies"]}
        action = "взял из кэша" if reused else "перерисовал"
        _append(job, f"Кадр «{scene['title']}» ({index}/{len(scenes)}): {action}", int(index / len(scenes) * 90))
    cache_path.write_text(json.dumps(frame_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    state = artifact_state(project)
    (root / "frames.meta.json").write_text(
        json.dumps({"hash": state["frame_hash"], "fingerprint_version": state["fingerprint_version"],
                    "demo": True}, ensure_ascii=False), encoding="utf-8")


def _segment_cache(project: dict) -> dict:
    path = project_dir(project["id"]) / "segment-cache.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _make_render(project: dict, job: dict, kind: str) -> None:
    import imageio_ffmpeg
    root = project_dir(project["id"])
    out_dir = root / "renders"
    out_dir.mkdir(parents=True, exist_ok=True)
    compatibility_output = out_dir / ("draft.mp4" if kind == "draft" else "final.mp4")
    native_v2 = int(project.get("schema_version", 1)) >= 2
    output = out_dir / f".{kind}-{uuid.uuid4().hex}.partial.mp4" if native_v2 else compatibility_output
    spec = project["spec"]
    data = renderer_timing(spec)
    fingerprint_data = project_fingerprints(project)
    if native_v2 and artifact_state(project)["artifact_details"]["renders"][kind]["status"] == "ready":
        _append(job, f"{kind}: использую проверенную неизменяемую версию render", 100)
        return
    timing_path = root / "timing.json"
    timing_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    title_path = root / "scene-titles.json"
    title_path.write_text(json.dumps({s["id"]: s.get("title", "") for s in spec["script"]["scenes"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    scenes = sorted(spec["script"]["scenes"], key=lambda x: x.get("order", 0))
    rows_by_scene = {scene["id"]: [row for row in data["lines"] if row["scene"] == scene["id"]] for scene in scenes}
    render_scenes = [scene for scene in scenes if rows_by_scene[scene["id"]]]
    cache_path = root / "segment-cache.json"
    cache = _segment_cache(project)
    segment_dir = root / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    scene_bg_dir = root / "active-scene-backgrounds"
    scene_bg_dir.mkdir(parents=True, exist_ok=True)
    active_backgrounds = set()
    for scene in scenes:
        image_ref = scene.get("image", {})
        if image_ref.get("mode") != "upload" or not image_ref.get("path"):
            continue
        source = (root / image_ref["path"]).resolve()
        if root.resolve() not in source.parents or not source.is_file():
            continue
        target = scene_bg_dir / f"{scene['id']}.jpg"
        shutil.copyfile(source, target)
        active_backgrounds.add(target.name)
    for old_background in scene_bg_dir.iterdir():
        if old_background.is_file() and old_background.name not in active_backgrounds:
            old_background.unlink()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    python = sys.executable
    renderer = str(ROOT / "tools" / "build_ffmpeg_video.py")
    segment_paths = []
    rendered_count = 0
    for scene_index, scene in enumerate(render_scenes):
        rows = rows_by_scene[scene["id"]]
        if not rows:
            continue
        segment_fingerprint = fingerprint_data["segments"][str(scene["id"])][kind]
        key = segment_fingerprint["fingerprint"]
        cache_id = f"{scene['id']}:{key}"
        cached = cache.get(cache_id, {})
        if not isinstance(cached, dict):
            cached = {}
        segment = _safe_cached_file(root, cached.get("file"))
        content_valid = bool(segment and segment.is_file())
        if content_valid and native_v2:
            expected_sha = cached.get("content_sha256") if isinstance(cached, dict) else None
            content_valid = bool(expected_sha and verify_project_file(root, str(cached["file"]), expected_sha).get("integrity_ok"))
        if cached.get("key") != key or not content_valid:
            first_start = float(rows[0]["start"])
            local_rows = []
            for row in rows:
                local_start = float(row["start"]) - first_start
                local_rows.append({**row, "start": round(local_start, 3), "end": round(local_start + float(row["dur"]), 3)})
            if scene_index + 1 < len(render_scenes):
                next_rows = rows_by_scene[render_scenes[scene_index + 1]["id"]]
                tail = max(0.0, float(next_rows[0]["start"]) - float(rows[-1]["end"])) if next_rows else 0.0
            else:
                tail = max(0.0, float(data["total"]) - float(rows[-1]["end"]))
            local_total = float(local_rows[-1]["end"]) + tail
            local_data = {"fps": data["fps"], "total": round(local_total, 3), "lines": local_rows, "cues": []}
            local_timing = segment_dir / f"{scene['id']}-{key[:10]}.json"
            local_timing.write_text(json.dumps(local_data, ensure_ascii=False, indent=2), encoding="utf-8")
            segment = segment_dir / f"{scene['id']}-{key[:12]}.mp4"
            command = [python, "-u", renderer, "--timing", str(local_timing), "--scene-titles", str(title_path),
                       "--scene-bg-dir", str(scene_bg_dir), "--output", str(segment), "--width", "1920", "--height", "1080",
                       "--motion", "0", "--no-audio", "--preset", "ultrafast" if kind == "draft" else "medium",
                       "--crf", "23" if kind == "draft" else "18", "--concurrency", "2"]
            _append(job, f"Готовлю сцену «{scene.get('title', scene['id'])}»…", 10 + int(scene_index / max(1, len(render_scenes)) * 72))
            process = subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace", bufsize=1)
            for line in process.stdout:
                if line.strip():
                    _append(job, line.strip()[:240])
            if process.wait():
                raise RuntimeError(f"Не удалось собрать сцену «{scene.get('title', scene['id'])}». Проверьте Pillow и MoviePy.")
            cache[cache_id] = {"key": key, "fingerprint": key,
                               "dependencies": segment_fingerprint["dependencies"],
                               "file": str(segment.relative_to(root)),
                               "content_sha256": _sha256_file(segment),
                               "size_bytes": segment.stat().st_size}
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            rendered_count += 1
        segment_paths.append(segment)
        _append(job, f"Сцена «{scene.get('title', scene['id'])}»: {'пересобрана' if cached.get('key') != key else 'взята из кэша'}",
                10 + int((scene_index + 1) / max(1, len(render_scenes)) * 72))
    if not segment_paths:
        raise RuntimeError("В сценарии нет сцен для сборки")
    concat_list = segment_dir / "concat.txt"
    concat_list.write_text("\n".join("file '" + str(p.resolve()).replace("\\", "/").replace("'", "'\\''") + "'" for p in segment_paths) + "\n", encoding="utf-8")
    voice = root / "audio" / "voice_track.mp3"
    command = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-i", str(voice),
               "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
               "-t", f"{data['total']:.3f}", "-movflags", "+faststart", str(output)]
    _append(job, f"Склеиваю сцены и озвучку: новых сцен {rendered_count} из {len(segment_paths)}", 88)
    completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError("Не удалось склеить сцены в MP4: " + (completed.stderr[-700:] if completed.stderr else "ошибка FFmpeg"))
    render_fingerprint = fingerprint_data["renders"][kind]
    previous_sidecar = _read_cache(out_dir / f"{kind}.meta.json")
    asset_record = None
    if native_v2:
        asset_record = register_asset_file(project["id"], output,
                                           asset_type="preview" if kind == "draft" else "final_render",
                                           target={"kind": kind}, extension=".mp4", mime="video/mp4",
                                           input_fingerprint=render_fingerprint["fingerprint"])
        immutable_output = root / asset_record["path"]
        _atomic_copy(immutable_output, compatibility_output)
        output.unlink(missing_ok=True)
    else:
        asset_record = {"path": compatibility_output.relative_to(root).as_posix(),
                        "render_version": int(previous_sidecar.get("render_version", 0)) + 1,
                        "asset_id": None, "sha256": None}
    sidecar = {"fingerprint": render_fingerprint["fingerprint"], "hash": render_fingerprint["fingerprint"],
               "fingerprint_version": fingerprint_data["fingerprint_version"],
               "dependencies": render_fingerprint["dependencies"], "kind": kind,
               "render_version": int(asset_record["render_version"]), "asset_id": asset_record["asset_id"],
               "path": asset_record["path"], "sha256": asset_record["sha256"], "created_at": time.time()}
    (out_dir / f"{kind}.meta.json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
    # Keep the legacy metadata mirror for the existing UI and pipeline readers.
    (root / "render.meta.json").write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")
    _append(job, f"Видео готово: {compatibility_output.name}", 96)


def get_job(job_id: str) -> dict | None:
    return JOBS.get(job_id)
