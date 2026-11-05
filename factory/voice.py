"""Optional local Piper TTS helpers. No network calls or cloud credentials are used."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path


class VoiceProviderError(ValueError):
    pass


def resolve_piper_executable(settings: dict) -> str:
    configured = str(settings.get("piper_executable", "piper")).strip() or "piper"
    candidate = Path(configured).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    found = shutil.which(configured)
    if found:
        return found
    raise VoiceProviderError(
        "Не найден Piper. Установите `piper-tts` в окружение фабрики или укажите полный путь к piper.exe в настройках."
    )


def piper_model_path(settings: dict, hero_id: str) -> Path:
    key = f"piper_model_{hero_id}"
    configured = str(settings.get(key, "")).strip()
    if not configured:
        raise VoiceProviderError(f"Укажите файл голосовой модели Piper для героя {hero_id}.")
    model = Path(configured).expanduser()
    if not model.is_file() or model.suffix.lower() != ".onnx":
        raise VoiceProviderError(f"Файл модели Piper для героя {hero_id} не найден или это не .onnx файл: {configured}")
    config = Path(str(model) + ".json")
    if not config.is_file():
        raise VoiceProviderError(f"Рядом с моделью Piper должен быть файл настроек {config.name}.")
    return model.resolve()


def wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as audio:
            rate = audio.getframerate()
            frames = audio.getnframes()
            if rate <= 0 or frames <= 0:
                raise ValueError("empty wav")
            return frames / rate
    except (OSError, wave.Error, ValueError) as exc:
        raise VoiceProviderError(f"Piper не создал корректный WAV-файл: {path.name}") from exc


def check_piper_settings(settings: dict, sample_dir: Path | None = None) -> dict:
    """Synthesize short local voice samples, optionally retaining them for in-browser playback."""
    executable = resolve_piper_executable(settings)
    models = {hero_id: piper_model_path(settings, hero_id) for hero_id in ("h1", "h2")}
    voices = {}
    generated = {}
    with tempfile.TemporaryDirectory(prefix="factory-piper-test-") as tmp:
        temp_root = Path(tmp)
        for hero_id, model in models.items():
            output = temp_root / f"{hero_id}.wav"
            command = [executable, "--model", str(model), "--output_file", str(output)]
            try:
                result = subprocess.run(command, input="Привет! Это проверка голоса. Я говорю по-русски: шесть, ёжик, яркое солнце.\n",
                                        text=True, encoding="utf-8", errors="replace",
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        timeout=45, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise VoiceProviderError(f"Не удалось запустить Piper для героя {hero_id}: {exc}") from exc
            if result.returncode or not output.is_file():
                detail = (result.stdout or "").strip()[-500:]
                raise VoiceProviderError(f"Piper не синтезировал тестовую реплику для {hero_id}. {detail}")
            duration = wav_duration(output)
            voices[hero_id] = {"model": model.name, "sample_duration_s": round(duration, 2)}
            generated[hero_id] = output
        if sample_dir is not None:
            sample_dir = Path(sample_dir).resolve()
            sample_dir.mkdir(parents=True, exist_ok=True)
            for hero_id, output in generated.items():
                (sample_dir / f"{hero_id}.wav").write_bytes(output.read_bytes())
                voices[hero_id]["sample_url"] = f"/api/settings/voice/samples/{hero_id}.wav"
    return {"connected": True, "provider": "piper", "executable": executable, "voices": voices}


def model_signature(settings: dict, hero_id: str) -> dict:
    """Fingerprint model and sidecar metadata without hashing large files on every request."""
    try:
        model = piper_model_path(settings, hero_id)
        stat = model.stat()
        sidecar = Path(str(model) + ".json").stat()
        return {"name": model.name, "size_bytes": stat.st_size, "modified_ns": stat.st_mtime_ns,
                "config_size_bytes": sidecar.st_size, "config_modified_ns": sidecar.st_mtime_ns}
    except VoiceProviderError:
        return {"configured": bool(str(settings.get(f"piper_model_{hero_id}", "")).strip()),
                "available": False}


def executable_signature(settings: dict) -> dict:
    try:
        executable = Path(resolve_piper_executable(settings))
        stat = executable.stat()
        return {"name": executable.name, "size_bytes": stat.st_size, "modified_ns": stat.st_mtime_ns}
    except (VoiceProviderError, OSError):
        return {"configured": bool(str(settings.get("piper_executable", "")).strip()), "available": False}
