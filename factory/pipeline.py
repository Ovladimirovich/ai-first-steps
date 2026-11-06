from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import queue
import threading
import time
import uuid
from pathlib import Path

from .core import RENDERER_VERSION, ROOT, artifact_state, digest, legacy_who, project_dir, renderer_timing
from .fingerprints import project_fingerprints, verify_asset_record, verify_project_file
from .assets import register_asset_file
from .actions import append_action_event, get_action
from .jobs import (JobCancelled, checkpoint as job_checkpoint, create_job, ensure_job_enqueued,
                  get_job as _get_job, is_cancel_requested, list_jobs, persist_job, set_executor)
from .storage import atomic_write_json, project_lock

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

def _plan_path(project_id: str, plan_id: str) -> Path:
    if not str(plan_id).isalnum():
        raise FileNotFoundError(plan_id)
    return project_dir(project_id) / "studio" / "plans" / f"{plan_id}.json"

def _stage_inputs(project: dict, stage: str, kind: str | None = None) -> dict:
    data = project_fingerprints(project)
    if stage == "voice":
        inputs = {"timing": data["components"]["timing"],
                  "voice_lines": {key: item["fingerprint"] for key, item in data["voice_lines"].items()}}
    elif stage == "frames":
        inputs = {"frames": {key: item["fingerprint"] for key, item in data["frames"].items()}}
    elif stage == "render":
        render_kind = kind or "draft"
        if render_kind not in ("draft", "final"):
            raise ValueError("Неизвестный вариант сборки")
        inputs = {"render": data["renders"][render_kind]["fingerprint"],
                  "segments": {key: item[render_kind]["fingerprint"]
                               for key, item in data["segments"].items()}}
    else:
        raise ValueError("Неизвестный этап производства")
    return {"fingerprint_version": data["fingerprint_version"], "inputs": inputs}

def stage_input_fingerprint(project: dict, stage: str, kind: str | None = None) -> str:
    return digest({"stage": stage, "kind": kind, "project_revision": project["revision"],
                   "spec_hash": digest(project["spec"]), "stage_inputs": _stage_inputs(project, stage, kind)})

def plan(project: dict, stage: str, kind: str | None = None) -> dict:
    artifacts = artifact_state(project)
    spec = project["spec"]
    total_units = 0
    if not spec.get("script", {}).get("scenes"):
        raise ValueError("Сначала подготовьте сценарий")
    if stage == "voice":
        from .settings import load_settings
        voice_provider = str(load_settings().get("voice_provider", "demo"))
        line_units = artifacts["voice_units"]
        total_units = line_units + 1
        units = _pending_voice_count(project) + int(artifacts["voice"] != "ready")
        estimate = 1 if units == 0 else max(1, int(units * (2.5 if voice_provider == "piper" else 0.25) + 1))
        provider_label = "локальных дорожек Piper" if voice_provider == "piper" else "демо-дорожек (тишина)"
        message = f"Обновятся {units} из {total_units} {provider_label}/сведений · примерно {estimate} сек. Стоимость: 0 ₽."
    elif stage == "frames":
        total_units = artifacts["scene_units"]
        units = _pending_frame_count(project)
        estimate = max(1, units * 2)
        message = f"Обновятся {units} из {total_units} кадров. Стоимость: 0 ₽."
    elif stage == "render":
        if artifacts["voice"] != "ready" or artifacts["frames"] != "ready":
            raise ValueError("Сначала обновите и проверьте озвучку и картинки")
        total_scenes = artifacts["scene_units"]
        total_units = total_scenes
        units = _pending_scene_count(project, kind or "draft")
        estimate = 3 if units == 0 else max(5, int(artifacts["duration_s"] * 0.65 * units / max(1, total_scenes)))
        message = f"Пересоберутся {units} из {total_scenes} сцен · финальная склейка около {estimate} секунд. Стоимость: 0 ₽."
    else:
        raise ValueError("Неизвестный этап производства")
    plan_id, action_id = uuid.uuid4().hex, uuid.uuid4().hex
    fingerprints = project_fingerprints(project)
    input_fingerprint = stage_input_fingerprint(project, stage, kind)
    entry = {"id": plan_id, "action_id": action_id, "project_id": project["id"], "stage": stage, "kind": kind,
             "revision": project["revision"], "spec_hash": digest(spec), "input_fingerprint": input_fingerprint,
             "fingerprint_version": fingerprints.get("fingerprint_version"), "created_at": time.time(),
             "units": units, "total_units": total_units or units, "estimate_s": estimate,
             "cost": 0, "cost_currency": "EUR", "provider": "local_pipeline", "message": message}
    atomic_write_json(_plan_path(project["id"], plan_id), entry)
    append_action_event(project["id"], "action_proposed", actor="user", data={
        "action_id": action_id, "kind": "production", "stage": stage, "render_kind": kind,
        "revision": project["revision"], "input_fingerprint": input_fingerprint,
        "provider": "local_pipeline", "cost_estimate": {"amount": 0, "currency": "EUR"},
        "privacy_scope": "local", "status": "proposed"})
    return entry

def _load_plan(project_id: str, plan_id: str) -> dict | None:
    try:
        return json.loads(_plan_path(project_id, plan_id).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None

def run(project: dict, plan_id: str, stage: str, kind: str | None = None,
        confirmation: dict | None = None) -> dict:
    with project_lock(project["id"]):
        from .core import load_project
        metadata_path = project_dir(project["id"]) / "project.json"
        if metadata_path.is_file():
            project = load_project(project["id"])
        plan_entry = _load_plan(project["id"], plan_id)
        if not plan_entry or plan_entry["stage"] != stage:
            raise ValueError("Смета не найдена или устарела. Обновите её перед запуском.")
        if (plan_entry["revision"] != project["revision"] or plan_entry["spec_hash"] != digest(project["spec"]) or
                plan_entry.get("input_fingerprint") != stage_input_fingerprint(project, stage, kind)):
            raise ValueError("Замысел изменился или входные данные устарели после сметы. Проверьте обновлённую смету.")
        if stage == "render" and plan_entry["kind"] != kind:
            raise ValueError("Тип сборки не совпадает со сметой.")
        for existing in list_jobs(project["id"]):
            if existing.get("action_id") == plan_entry["action_id"]:
                if existing.get("state") == "queued":
                    return ensure_job_enqueued(project["id"], existing["id"])
                return existing
        action = get_action(project["id"], plan_entry["action_id"])
        if action["status"] != "proposed":
            raise ValueError("Действие уже подтверждено, отклонено или запущено")
        approval = confirmation or {"max_cost": 0, "currency": "EUR", "privacy_scope": "local", "consent": True}
        try:
            max_cost = float(approval.get("max_cost", -1))
        except (TypeError, ValueError):
            max_cost = -1
        if max_cost < float(plan_entry["cost"]) or str(approval.get("currency", "")).upper() != "EUR":
            raise ValueError("Подтвердите действующий предел стоимости в EUR")
        if approval.get("privacy_scope") != "local" or approval.get("consent") is not True:
            raise ValueError("Для запуска требуется явное согласие на локальную обработку")
        confirmed_at = time.time()
        confirmation_record = {"cost_ceiling": {"amount": max_cost, "currency": "EUR"},
                               "privacy_scope": "local", "consent": True,
                               "confirmed_at": confirmed_at, "expires_at": confirmed_at + 365 * 24 * 3600,
                               "input_fingerprint": plan_entry["input_fingerprint"]}
        return create_job(project["id"], action_id=plan_entry["action_id"], job_type="pipeline",
                          payload={"plan_id": plan_id, "revision": project["revision"],
                                   "spec_hash": plan_entry["spec_hash"], "stage": stage, "kind": kind},
                          input_fingerprint=plan_entry["input_fingerprint"], stage=stage, kind=kind,
                          approval=confirmation_record)

def _append(job, message, progress=None):
    if is_cancel_requested(job["project_id"], job["id"]):
        raise JobCancelled()
    job["message"] = message
    job.setdefault("log", []).append(message)
    job["log"] = job["log"][-40:]
    if progress is not None:
        job["progress"] = progress
    persist_job(job)

def _checkpoint(job, stage: str, completed: int, total: int, fingerprint: str | None = None):
    if is_cancel_requested(job["project_id"], job["id"]):
        raise JobCancelled()
    checkpoint = {"stage": stage, "completed": int(completed), "total": int(total),
                  "fingerprint": fingerprint, "created_at": time.time()}
    job_checkpoint(job, checkpoint)

def _execute_job(job: dict) -> None:
    if is_cancel_requested(job["project_id"], job["id"]):
        raise JobCancelled()
    if job.get("job_type") == "script_draft":
        from .action_service import execute_script_draft_job
        execute_script_draft_job(job)
        return
    from .core import load_project
    project = load_project(job["project_id"])
    payload = job.get("payload", {})
    if int(project["revision"]) != int(payload.get("revision", -1)) or digest(project["spec"]) != payload.get("spec_hash"):
        raise ValueError("Входные данные изменились после подтверждения; подготовьте новую смету")
    stage = payload["stage"]
    if stage_input_fingerprint(project, stage, payload.get("kind")) != job.get("input_fingerprint"):
        raise ValueError("Входные данные изменились до запуска; подготовьте новую смету")
    approval = job.get("approval") or {}
    if (approval.get("consent") is not True or approval.get("privacy_scope") != "local" or
            float(approval.get("expires_at", 0)) <= time.time()):
        raise ValueError("Для локальной задачи требуется актуальное подтверждение согласия")
    if stage == "voice":
        _make_voice(project, job)
    elif stage == "frames":
        _make_frames(project, job)
    elif stage == "render":
        _make_render(project, job, payload.get("kind") or "draft")
    else:
        raise ValueError("Неизвестный этап производства")

def get_job(job_id: str, project_id: str | None = None) -> dict | None:
    return _get_job(job_id, project_id)

set_executor(_execute_job)

def _run_cancellable(job: dict, command: list[str], *, cwd: str | None = None,
                     stdin_text: str | None = None) -> tuple[int, str]:
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE if stdin_text is not None else None,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace", bufsize=1)
    if stdin_text is not None and process.stdin is not None:
        try:
            process.stdin.write(stdin_text)
            process.stdin.close()
        except BrokenPipeError:
            pass
    output: list[str] = []
    lines: queue.Queue[str | None] = queue.Queue()

    def read_output():
        try:
            if process.stdout:
                for line in process.stdout:
                    lines.put(line)
        finally:
            lines.put(None)

    reader = threading.Thread(target=read_output, name="factory-process-output", daemon=True)
    reader.start()
    output_closed = False
    try:
        while process.poll() is None or not output_closed:
            if is_cancel_requested(job["project_id"], job["id"]):
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                if command and Path(command[-1]).is_absolute():
                    Path(command[-1]).unlink(missing_ok=True)
                raise JobCancelled()
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                output_closed = True
                continue
            text = line.strip()
            output.append(text)
            output = output[-12:]
            if text:
                _append(job, text[:240])
        return int(process.wait() or 0), "\n".join(output)[-1000:]
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if process.stdout:
            process.stdout.close()

def _atempo_filter(speed: float) -> str:
    """Build ffmpeg atempo chain; each individual filter accepts speeds from 0.5 to 2."""
    if speed <= 0:
        raise ValueError("Некорректная длительность реплики Piper")
    factors = []
    while speed > 2.0:
        factors.append(2.0)
        speed /= 2.0
    while speed < 0.5:
        factors.append(0.5)
        speed /= 0.5
    factors.append(speed)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def _synthesize_piper_line(job: dict, ffmpeg: str, executable: str, model: Path,
                           text: str, target_seconds: float, wav_path: Path,
                           output_mp3: Path) -> float:
    from .voice import wav_duration
    wav_path.unlink(missing_ok=True)
    output_mp3.unlink(missing_ok=True)
    command = [executable, "--model", str(model), "--output_file", str(wav_path)]
    try:
        return_code, error_tail = _run_cancellable(job, command, stdin_text=text.strip() + "\n")
        if return_code or not wav_path.is_file():
            raise RuntimeError("Piper не синтезировал реплику: " + (error_tail[-500:] or "WAV-файл отсутствует"))
        source_duration = wav_duration(wav_path)
        target_seconds = max(0.5, float(target_seconds))
        speed = source_duration / target_seconds
        # Never speed up TTS audio — it destroys intelligibility.
        # If Piper is slower than the slot, just let it run long (pause absorbs the delta).
        # If Piper is faster, slow down to fill the slot.
        capped_speed = min(speed, 1.0)
        out_duration = source_duration / capped_speed if capped_speed > 0 else target_seconds
        audio_filter = f"{_atempo_filter(capped_speed)},apad,atrim=duration={out_duration:.3f}"
        convert = [ffmpeg, "-y", "-i", str(wav_path), "-vn", "-af", audio_filter,
                   "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-q:a", "2", str(output_mp3)]
        return_code, error_tail = _run_cancellable(job, convert)
        if return_code or not output_mp3.is_file():
            raise RuntimeError("Не удалось привести Piper-аудио к таймингу проекта: " + error_tail[-500:])
        return source_duration
    finally:
        wav_path.unlink(missing_ok=True)
        if not output_mp3.is_file():
            output_mp3.unlink(missing_ok=True)


def _mix_piper_voice_track(job: dict, ffmpeg: str, rows: list[dict], audio_dir: Path,
                           output: Path, total_seconds: float) -> None:
    inputs = []
    filters = []
    for index, row in enumerate(rows):
        source = audio_dir / f"{row['id']}.mp3"
        if not source.is_file():
            raise RuntimeError(f"Не найдено Piper-аудио для реплики {row['id']}")
        inputs.extend(["-i", str(source)])
        delay_ms = max(0, int(round(float(row["start"]) * 1000)))
        filters.append(f"[{index}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={delay_ms}|{delay_ms}[a{index}]")
    labels = "".join(f"[a{index}]" for index in range(len(rows)))
    filters.append(f"{labels}amix=inputs={len(rows)}:duration=longest:normalize=0,"
                   f"alimiter=limit=0.95,apad,atrim=duration={total_seconds:.3f}[voice]")
    command = [ffmpeg, "-y", *inputs, "-filter_complex", ";".join(filters), "-map", "[voice]",
               "-t", f"{total_seconds:.3f}", "-c:a", "libmp3lame", "-q:a", "2", str(output)]
    return_code, error_tail = _run_cancellable(job, command)
    if return_code or not output.is_file():
        output.unlink(missing_ok=True)
        raise RuntimeError("Не удалось свести локальную Piper-озвучку: " + error_tail[-500:])


def _make_voice(project: dict, job: dict) -> None:
    import imageio_ffmpeg
    from .settings import load_settings
    from .voice import piper_model_path, resolve_piper_executable

    root = project_dir(project["id"])
    audio_dir = root / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    data = renderer_timing(project["spec"])
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    settings = load_settings()
    voice_provider = str(settings.get("voice_provider", "demo"))
    if voice_provider not in ("demo", "piper"):
        raise ValueError("Неизвестный поставщик голоса. Выберите демо или локальный Piper.")
    piper_executable = resolve_piper_executable(settings) if voice_provider == "piper" else ""
    cache_path = root / "voice-cache.json"
    line_cache = _read_cache(cache_path)
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
            generated = audio_dir / f".{row['id']}-{job['id']}.partial.mp3"
            source_duration = None
            if voice_provider == "piper":
                model = piper_model_path(settings, str(line.get("hero", "")))
                wav_path = audio_dir / f".{row['id']}-{job['id']}.piper.wav"
                source_duration = _synthesize_piper_line(job, ffmpeg, piper_executable, model,
                                                         str(line["text"]), duration, wav_path, generated)
            else:
                return_code, error_tail = _run_cancellable(job, [ffmpeg, "-y", "-f", "lavfi", "-i",
                    "anullsrc=channel_layout=mono:sample_rate=44100", "-t", f"{duration:.3f}",
                    "-q:a", "9", "-acodec", "libmp3lame", str(generated)])
                if return_code:
                    generated.unlink(missing_ok=True)
                    raise RuntimeError("Не удалось подготовить демо-аудио: " + error_tail[-500:])
            if native_v2:
                record = register_asset_file(project["id"], generated, asset_type="dialogue_audio",
                                             target={"line_id": str(row["id"])}, extension=".mp3",
                                             mime="audio/mpeg", input_fingerprint=key)
                immutable_file = root / record["path"]
                _atomic_copy(immutable_file, output)
                generated.unlink(missing_ok=True)
                line_cache[row["id"]] = {"fingerprint": key, "dependencies": entry["dependencies"],
                                          "asset_id": record["asset_id"], "asset_version": record["asset_version"],
                                          "file": record["path"], "source_duration_s": source_duration}
            else:
                _atomic_copy(generated, output)
                generated.unlink(missing_ok=True)
                line_cache[row["id"]] = {"fingerprint": key, "dependencies": entry["dependencies"],
                                          "source_duration_s": source_duration}
        action = "использую прежнюю" if reused else "создана"
        _append(job, f"Дорожка {index}/{len(data['lines'])}: {action}", int(index / max(1, len(data["lines"])) * 65))
        atomic_write_json(cache_path, line_cache)
        _checkpoint(job, "voice_line", index, len(data["lines"]), key)
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
        generated_track = audio_dir / f".voice-track-{job['id']}.partial.mp3"
        total = max(0.5, float(data["total"]))
        if voice_provider == "piper":
            _mix_piper_voice_track(job, ffmpeg, data["lines"], audio_dir, generated_track, total)
        else:
            return_code, error_tail = _run_cancellable(job, [ffmpeg, "-y", "-f", "lavfi", "-i",
                "anullsrc=channel_layout=stereo:sample_rate=44100", "-t", f"{total:.3f}",
                "-q:a", "9", "-acodec", "libmp3lame", str(generated_track)])
            if return_code:
                generated_track.unlink(missing_ok=True)
                raise RuntimeError("Не удалось свести демо-аудио: " + error_tail[-500:])
        if native_v2:
            mix_record = register_asset_file(project["id"], generated_track, asset_type="dialogue_mix",
                                             target={"mix": "voice_track"}, extension=".mp3",
                                             mime="audio/mpeg", input_fingerprint=mix_fingerprint)
            _atomic_copy(root / mix_record["path"], track)
            generated_track.unlink(missing_ok=True)
        else:
            generated_track.replace(track)
    atomic_write_json(root / "timing.json", data)
    # Speech is fitted to the established per-line timing, so the SRT and renderer stay aligned.
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
                  "demo": voice_provider == "demo", "provider": voice_provider}
    if mix_record:
        voice_meta.update({"asset_id": mix_record["asset_id"], "asset_version": mix_record["asset_version"],
                           "path": mix_record["path"], "sha256": mix_record["sha256"]})
    atomic_write_json(root / "voice.meta.json", voice_meta)
    message = "Piper-озвучка готова. Речь обработана локально и подогнана под тайминг проекта." if voice_provider == "piper" else "Демо-озвучка готова. Это тишина с длительностью по тексту, не настоящий голос."
    _append(job, message, 95)

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
            generated = frame_dir / f".{scene['id']}-{job['id']}.partial.jpg"
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
                _atomic_copy(generated, frame_path)
                generated.unlink(missing_ok=True)
                frame_cache[scene["id"]] = {"fingerprint": key, "dependencies": entry["dependencies"]}
        action = "взял из кэша" if reused else "перерисовал"
        _append(job, f"Кадр «{scene['title']}» ({index}/{len(scenes)}): {action}", int(index / len(scenes) * 90))
        atomic_write_json(cache_path, frame_cache)
        _checkpoint(job, "frame", index, len(scenes), key)
    state = artifact_state(project)
    atomic_write_json(root / "frames.meta.json",
                      {"hash": state["frame_hash"], "fingerprint_version": state["fingerprint_version"],
                       "demo": True})

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
    output = out_dir / f".{kind}-{job['id']}.partial.mp4"
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
            return_code, error_tail = _run_cancellable(job, command, cwd=str(ROOT))
            if return_code:
                raise RuntimeError(f"Не удалось собрать сцену «{scene.get('title', scene['id'])}»: {error_tail[-500:]}")
            cache[cache_id] = {"key": key, "fingerprint": key,
                               "dependencies": segment_fingerprint["dependencies"],
                               "file": str(segment.relative_to(root)),
                               "content_sha256": _sha256_file(segment),
                               "size_bytes": segment.stat().st_size}
            atomic_write_json(cache_path, cache)
            rendered_count += 1
        segment_paths.append(segment)
        _append(job, f"Сцена «{scene.get('title', scene['id'])}»: {'пересобрана' if cached.get('key') != key else 'взята из кэша'}",
                10 + int((scene_index + 1) / max(1, len(render_scenes)) * 72))
        _checkpoint(job, "render_scene", scene_index + 1, len(render_scenes), key)
    if not segment_paths:
        raise RuntimeError("В сценарии нет сцен для сборки")
    concat_list = segment_dir / "concat.txt"
    concat_list.write_text("\n".join("file '" + str(p.resolve()).replace("\\", "/").replace("'", "'\\''") + "'" for p in segment_paths) + "\n", encoding="utf-8")
    voice = root / "audio" / "voice_track.mp3"
    command = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-i", str(voice),
               "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
               "-t", f"{data['total']:.3f}", "-movflags", "+faststart", str(output)]
    _append(job, f"Склеиваю сцены и озвучку: новых сцен {rendered_count} из {len(segment_paths)}", 88)
    return_code, error_tail = _run_cancellable(job, command, cwd=str(ROOT))
    if return_code:
        output.unlink(missing_ok=True)
        raise RuntimeError("Не удалось склеить сцены в MP4: " + (error_tail[-700:] or "ошибка FFmpeg"))
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
        output.replace(compatibility_output)
        asset_record = {"path": compatibility_output.relative_to(root).as_posix(),
                        "render_version": int(previous_sidecar.get("render_version", 0)) + 1,
                        "asset_id": None, "sha256": None}
    sidecar = {"fingerprint": render_fingerprint["fingerprint"], "hash": render_fingerprint["fingerprint"],
               "fingerprint_version": fingerprint_data["fingerprint_version"],
               "dependencies": render_fingerprint["dependencies"], "kind": kind,
               "render_version": int(asset_record["render_version"]), "asset_id": asset_record["asset_id"],
               "path": asset_record["path"], "sha256": asset_record["sha256"], "created_at": time.time()}
    atomic_write_json(out_dir / f"{kind}.meta.json", sidecar)
    # Keep the legacy metadata mirror for the existing UI and pipeline readers.
    atomic_write_json(root / "render.meta.json", sidecar)
    _append(job, f"Видео готово: {compatibility_output.name}", 96)
