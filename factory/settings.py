from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .core import ROOT

DEFAULT_SETTINGS = {
    "text_provider": "demo",
    "llama_cpp_base_url": "http://127.0.0.1:8081/v1",
    "llama_cpp_model": "",
    "gigachat_model": "",
    "gigachat_cloud_ack": False,
    "voice_provider": "demo",
    "piper_executable": "piper",
    "piper_model_h1": "",
    "piper_model_h2": "",
    "gigachat_models": [],
    "comfyui_base_url": "http://127.0.0.1:8188",
    "comfyui_local_model": "",
}
SETTINGS_PATH = ROOT / ".factory" / "settings.json"
ENV_PATH = ROOT / ".env"


def _local_env() -> dict:
    values = {}
    try:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            values[key.strip()] = value
    except OSError:
        pass
    values.update(os.environ)
    return values


def gigachat_credentials() -> dict:
    env = _local_env()
    return {"client_id": env.get("GIGACHAT_CLIENT_ID", ""),
            "client_secret": env.get("GIGACHAT_CLIENT_SECRET", ""),
            "scope": env.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
            "ca_bundle": env.get("GIGACHAT_CA_BUNDLE", "")}


def _edge_rate(raw, default: str) -> str:
    text = str(raw).strip() or default
    if not re.fullmatch(r"[+-]?\d{1,3}(?:\.\d)?%", text):
        raise ValueError(f"Скорость Edge TTS задаётся процентами, например «+0%» или «-10%», а не {text!r}")
    # edge-tts требует явный знак у скорости: «5%» приводится к «+5%».
    if not text[0] in "+-":
        text = "+" + text
    return text


def load_settings() -> dict:
    try:
        stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(stored, dict):
            stored = {}
    except (OSError, ValueError):
        stored = {}
    result = {**DEFAULT_SETTINGS, **stored}
    if not isinstance(result.get("gigachat_models"), list):
        result["gigachat_models"] = []
    env = _local_env()
    result["text_provider"] = env.get("FACTORY_TEXT_PROVIDER", result["text_provider"])
    result["llama_cpp_base_url"] = env.get("LLAMA_CPP_BASE_URL", result["llama_cpp_base_url"])
    result["llama_cpp_model"] = env.get("LLAMA_CPP_MODEL", result["llama_cpp_model"])
    result["gigachat_model"] = env.get("GIGACHAT_MODEL", result["gigachat_model"])
    result["voice_provider"] = env.get("FACTORY_VOICE_PROVIDER", result["voice_provider"])
    result["piper_executable"] = env.get("PIPER_EXECUTABLE", result["piper_executable"])
    result["piper_model_h1"] = env.get("PIPER_MODEL_H1", result["piper_model_h1"])
    result["piper_model_h2"] = env.get("PIPER_MODEL_H2", result["piper_model_h2"])
    result["edge_voice_h1"] = env.get("EDGE_VOICE_H1", result["edge_voice_h1"])
    result["edge_voice_h2"] = env.get("EDGE_VOICE_H2", result["edge_voice_h2"])
    result["edge_rate_h1"] = env.get("EDGE_RATE_H1", result["edge_rate_h1"])
    result["edge_rate_h2"] = env.get("EDGE_RATE_H2", result["edge_rate_h2"])
    result["comfyui_base_url"] = env.get("COMFYUI_BASE_URL", result["comfyui_base_url"])
    result["gigachat_credentials_configured"] = bool(env.get("GIGACHAT_CLIENT_ID") and env.get("GIGACHAT_CLIENT_SECRET"))
    return result


def save_settings(value: dict) -> dict:
    current = load_settings()
    provider = str(value.get("text_provider", current["text_provider"]))
    if provider not in ("demo", "llama_cpp", "gigachat"):
        raise ValueError("Выберите демо-шаблон, локального помощника или GigaChat")
    base_url = str(value.get("llama_cpp_base_url", current["llama_cpp_base_url"])).strip().rstrip("/")
    model = str(value.get("llama_cpp_model", current["llama_cpp_model"])).strip()[:160]
    gigachat_model = str(value.get("gigachat_model", current["gigachat_model"])).strip()[:160]
    gigachat_cloud_ack = bool(value.get("gigachat_cloud_ack", current["gigachat_cloud_ack"]))
    voice_provider = str(value.get("voice_provider", current["voice_provider"]))
    if voice_provider not in ("demo", "piper"):
        raise ValueError("Выберите демо-тишину или локальный Piper")
    piper_executable = str(value.get("piper_executable", current["piper_executable"])).strip()[:2048] or "piper"
    piper_model_h1 = str(value.get("piper_model_h1", current["piper_model_h1"])).strip()[:2048]
    piper_model_h2 = str(value.get("piper_model_h2", current["piper_model_h2"])).strip()[:2048]
    # Validate and constrain the text endpoint to loopback to avoid remote script leakage.
    from .providers import _base_url
    base_url = _base_url(base_url)
    from .comfyui import normalize_comfyui_base_url
    comfyui_base_url = normalize_comfyui_base_url(value.get("comfyui_base_url", current.get("comfyui_base_url")))
    comfyui_local_model = str(value.get("comfyui_local_model", current.get("comfyui_local_model", ""))).strip()[:512]
    persisted = {"text_provider": provider, "llama_cpp_base_url": base_url, "comfyui_base_url": comfyui_base_url,
                 "comfyui_local_model": comfyui_local_model, "llama_cpp_model": model,
                 "gigachat_model": gigachat_model, "gigachat_cloud_ack": gigachat_cloud_ack,
                 "voice_provider": voice_provider, "piper_executable": piper_executable,
                 "piper_model_h1": piper_model_h1, "piper_model_h2": piper_model_h2,
                 "gigachat_models": [str(m)[:160] for m in value.get("gigachat_models", current.get("gigachat_models", [])) if isinstance(m, str) and m.strip()][:50]}
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**persisted, "gigachat_credentials_configured": bool(gigachat_credentials()["client_id"] and gigachat_credentials()["client_secret"])}
