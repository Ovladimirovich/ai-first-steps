from __future__ import annotations

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


def _voice_key(line: dict, hero: dict) -> str:
    return digest({"text": line["text"], "voice": hero.get("voice"), "provider": "demo-silence-v1"})


def _frame_key(scene: dict, spec: dict) -> str:
    return digest({"scene": scene, "look": spec.get("look"), "renderer": RENDERER_VERSION})


def _pending_voice_count(project: dict) -> int:
    root = project_dir(project["id"])
    cache = _read_cache(root / "voice-cache.json")
    heroes = {hero["id"]: hero for hero in project["spec"].get("heroes", [])}
    lines = [line for scene in project["spec"]["script"]["scenes"] for line in scene.get("lines", [])]
    return sum(1 for line in lines if not (cache.get(line["id"]) == _voice_key(line, heroes[line["hero"]])
                                             and (root / "audio" / f"{line['id']}.mp3").is_file()))


def _pending_frame_count(project: dict) -> int:
    root = project_dir(project["id"])
    cache = _read_cache(root / "frames-cache.json")
    scenes = project["spec"]["script"]["scenes"]
    return sum(1 for scene in scenes if not (cache.get(scene["id"]) == _frame_key(scene, project["spec"])
                                               and (root / "frames" / f"{scene['id']}.jpg").is_file()))


def _pending_scene_count(project: dict, kind: str) -> int:
    root = project_dir(project["id"])
    cache = _segment_cache(project)
    pending = 0
    for scene in project["spec"].get("script", {}).get("scenes", []):
        if not scene.get("lines"):
            continue
        key = _segment_key(scene, project["spec"], kind)
        entry = cache.get(f"{scene['id']}:{key}", {})
        cached_file = root / entry.get("file", "") if entry.get("file") else None
        if not cached_file or not cached_file.is_file():
            pending += 1
    return pending


def plan(project: dict, stage: str, kind: str | None = None) -> dict:
    artifacts = artifact_state(project)
    spec = project["spec"]
    total_units = 0
    if not spec.get("script", {}).get("scenes"):
        raise ValueError("Сначала подготовьте сценарий")
    if stage == "voice":
        total_units = artifacts["voice_units"]
        units = _pending_voice_count(project)
        estimate = 1 if units == 0 else max(1, int(units * 0.25 + 1))
        message = f"Обновятся {units} из {total_units} тихих демо-дорожек · примерно {estimate} сек. Стоимость: 0 ₽."
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
    hero_specs = {hero["id"]: hero for hero in project["spec"]["heroes"]}
    for index, row in enumerate(data["lines"], 1):
        output = audio_dir / f"{row['id']}.mp3"
        line = line_specs[row["id"]]
        key = _voice_key(line, hero_specs[line["hero"]])
        duration = max(0.5, float(row["dur"]))
        reused = output.exists() and line_cache.get(row["id"]) == key
        if not reused:
            subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=44100",
                            "-t", f"{duration:.3f}", "-q:a", "9", "-acodec", "libmp3lame", str(output)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            line_cache[row["id"]] = key
        action = "использую прежнюю" if reused else "создана"
        _append(job, f"Дорожка {index}/{len(data['lines'])}: {action}", int(index / max(1, len(data["lines"])) * 65))
    cache_path.write_text(json.dumps(line_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    track = audio_dir / "voice_track.mp3"
    total = max(0.5, float(data["total"]))
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-t", f"{total:.3f}", "-q:a", "9", "-acodec", "libmp3lame", str(track)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    (root / "timing.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # A lightweight SRT matching the same timeline.
    def stamp(seconds):
        ms = int(round(seconds * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    srt = "\n\n".join(f"{i}\n{stamp(x['start'])} --> {stamp(x['end'])}\n{x['text']}" for i, x in enumerate(data["lines"], 1))
    (root / "subtitles.srt").write_text(srt + "\n", encoding="utf-8")
    (root / "voice.meta.json").write_text(json.dumps({"hash": artifact_state(project)["voice_hash"], "demo": True}, ensure_ascii=False), encoding="utf-8")
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
    for index, scene in enumerate(scenes, 1):
        frame_path = frame_dir / f"{scene['id']}.jpg"
        key = _frame_key(scene, spec)
        reused = frame_path.exists() and frame_cache.get(scene["id"]) == key
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
            image.save(frame_path, "JPEG", quality=91)
            frame_cache[scene["id"]] = key
        action = "взял из кэша" if reused else "перерисовал"
        _append(job, f"Кадр «{scene['title']}» ({index}/{len(scenes)}): {action}", int(index / len(scenes) * 90))
    cache_path.write_text(json.dumps(frame_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "frames.meta.json").write_text(
        json.dumps({"hash": artifact_state(project)["frame_hash"], "demo": True}, ensure_ascii=False), encoding="utf-8")


def _segment_key(scene: dict, spec: dict, kind: str) -> str:
    return digest({"scene": scene, "look": spec.get("look"), "format": spec.get("format"),
                   "renderer": RENDERER_VERSION, "quality": kind})


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
    output = out_dir / ("draft.mp4" if kind == "draft" else "final.mp4")
    spec = project["spec"]
    data = renderer_timing(spec)
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
        key = _segment_key(scene, spec, kind)
        cache_id = f"{scene['id']}:{key}"
        cached = cache.get(cache_id, {})
        segment = root / cached.get("file", "") if cached.get("file") else None
        if cached.get("key") != key or not segment or not segment.is_file():
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
            cache[cache_id] = {"key": key, "file": str(segment.relative_to(root))}
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
    (root / "render.meta.json").write_text(json.dumps({"hash": artifact_state(project)["render_hash"], "kind": kind}, ensure_ascii=False), encoding="utf-8")
    _append(job, f"Видео готово: {output.name}", 96)


def get_job(job_id: str) -> dict | None:
    return JOBS.get(job_id)
