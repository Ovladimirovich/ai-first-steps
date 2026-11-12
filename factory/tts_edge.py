"""Microsoft Edge TTS (edge-tts) provider: cloud neural voices for dialogue lines.

Unlike Piper this provider needs internet: text is sent to Microsoft's
endpoint. No API key and no billing are involved, but the endpoint can be
rate-limited or temporarily unavailable, so every synthesis retries with
exponential backoff.
"""
from __future__ import annotations

import asyncio
import importlib.metadata
import random
import time
from pathlib import Path

from .voice import VoiceProviderError

DEFAULT_EDGE_VOICES = {"h1": "ru-RU-DmitryNeural", "h2": "ru-RU-SvetlanaNeural"}
DEFAULT_EDGE_RATES = {"h1": "+0%", "h2": "-10%"}
EDGE_PACKAGE_NAME = "edge-tts"
EDGE_SAMPLE_TEXT = "Привет! Это проверка голоса. Я говорю по-русски: шесть, ёжик, яркое солнце."
EDGE_ATTEMPTS = 5
EDGE_JOB_ATTEMPTS = 10
# Jittered backoff schedule (seconds) for service no-audio windows: background
# jobs run EDGE_JOB_ATTEMPTS attempts spanning roughly six minutes.
_EDGE_RETRY_BACKOFF_S = (2, 5, 10, 20, 30, 45, 60, 90, 120, 180)


def edge_package_version() -> str:
    try:
        return importlib.metadata.version(EDGE_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        return ""


def _import_edge_tts():
    try:
        import edge_tts
    except ImportError as exc:
        raise VoiceProviderError(
            "Не установлен пакет edge-tts. Выполните: python -m pip install edge-tts "
            "в окружении фабрики."
        ) from exc
    return edge_tts


def edge_voice(settings: dict, hero_id: str) -> str:
    value = str(settings.get(f"edge_voice_{hero_id}") or "").strip() or DEFAULT_EDGE_VOICES.get(hero_id, "")
    if not value:
        raise VoiceProviderError(f"Укажите голос Edge TTS для героя {hero_id}.")
    return value


def edge_rate(settings: dict, hero_id: str) -> str:
    value = str(settings.get(f"edge_rate_{hero_id}") or "").strip() or DEFAULT_EDGE_RATES.get(hero_id, "+0%")
    # edge-tts требует явный знак у скорости: «5%» приводится к «+5%».
    if value and not value[0] in "+-":
        value = "+" + value
    return value


def edge_service_rate(rate: str) -> str:
    """Точная нулевая скорость сервису не пройдёт (отдаёт «нет аудио»),
    поэтому «+0%» отправляется как «+1%» — для слушателя разницы нет.

    Возвращаемое значение предназначено только для запросов edge_tts;
    в настройках, отчётах и fingerprint'ах остаётся исходная скорость.
    """
    number = rate.lstrip("+-")
    if number in ("0%", "0.0%"):
        return "+1%"
    return rate


def edge_signature(settings: dict, hero_id: str) -> dict:
    """Fingerprint-safe description of the exact synthesis configuration."""
    try:
        return {"provider": "edge-tts", "version": edge_package_version() or "missing",
                "voice": edge_voice(settings, hero_id), "rate": edge_rate(settings, hero_id)}
    except VoiceProviderError:
        return {"provider": "edge-tts", "version": edge_package_version() or "missing",
                "voice": "", "rate": "+0%"}


def _run_edge_once(edge_tts, text: str, voice: str, rate: str, out_path: Path) -> None:
    async def stream() -> None:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        with out_path.open("wb") as handle:
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    handle.write(chunk["data"])

    asyncio.run(stream())


def _backoff_sleep(attempt: int, cancelled=None) -> None:
    """Jittered sleep before the next attempt.

    The interval is split into <=2 s chunks and ``cancelled`` is polled before
    every chunk, so a cancelled job stops promptly instead of sleeping through
    the whole interval.
    """
    base = _EDGE_RETRY_BACKOFF_S[min(attempt - 1, len(_EDGE_RETRY_BACKOFF_S) - 1)]
    remaining = base * (0.75 + random.random() * 0.5)
    while remaining > 0:
        step = min(2.0, remaining)
        if cancelled is not None:
            cancelled()
        time.sleep(step)
        remaining -= step


def synthesize_edge_line(settings: dict, hero_id: str, text: str, out_path: Path,
                         cancelled=None, attempts: int = EDGE_ATTEMPTS) -> None:
    """Synthesize one line to ``out_path`` (MP3).

    ``cancelled`` is a zero-argument callable invoked before every attempt and
    polled every <=2 s during backoff sleeps; it may raise JobCancelled (or
    any exception) to stop the job immediately.
    """
    edge_tts = _import_edge_tts()
    voice = edge_voice(settings, hero_id)
    rate = edge_service_rate(edge_rate(settings, hero_id))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)
    last_error: Exception | None = None
    try:
        for attempt in range(1, attempts + 1):
            if cancelled is not None:
                cancelled()
            try:
                _run_edge_once(edge_tts, text, voice, rate, out_path)
                if out_path.is_file() and out_path.stat().st_size >= 1024:
                    return
                last_error = VoiceProviderError(f"edge-tts вернул пустой файл (голос {voice}).")
            except VoiceProviderError as exc:
                last_error = exc
            except Exception as exc:  # NoAudioReceived, aiohttp/network errors
                last_error = exc
            if attempt < attempts:
                _backoff_sleep(attempt, cancelled)
    except BaseException:
        out_path.unlink(missing_ok=True)
        raise
    out_path.unlink(missing_ok=True)
    raise VoiceProviderError(
        f"Edge TTS не смог синтезировать реплику для {hero_id} ({voice}) после "
        f"{attempts} попыток: {last_error}"
    )


def check_edge_settings(settings: dict, sample_dir: Path | None = None) -> dict:
    """Synthesize short cloud voice samples, optionally retaining them for playback."""
    import tempfile

    if sample_dir is not None:
        sample_dir = Path(sample_dir).resolve()
        sample_dir.mkdir(parents=True, exist_ok=True)
        keep_samples = True
    else:
        sample_dir = Path(tempfile.mkdtemp(prefix="factory-edge-test-"))
        keep_samples = False
    generated = {}
    for hero_id in ("h1", "h2"):
        output = sample_dir / f"{hero_id}.mp3"
        synthesize_edge_line(settings, hero_id, EDGE_SAMPLE_TEXT, output, attempts=3)
        entry = {"voice": edge_voice(settings, hero_id), "rate": edge_rate(settings, hero_id)}
        if keep_samples:
            entry["sample_url"] = f"/api/settings/voice/samples/{hero_id}.mp3"
        generated[hero_id] = entry
    return {"connected": True, "provider": "edge-tts", "version": edge_package_version(),
            "voices": generated}
