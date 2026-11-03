from __future__ import annotations

import json
import os
from pathlib import Path

from .core import ROOT

DEFAULT_SETTINGS = {
    "text_provider": "demo",
    "llama_cpp_base_url": "http://127.0.0.1:8081/v1",
    "llama_cpp_model": "",
    "gigachat_model": "",
    "gigachat_cloud_ack": False,
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


def load_settings() -> dict:
    try:
        stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(stored, dict):
            stored = {}
    except (OSError, ValueError):
        stored = {}
    result = {**DEFAULT_SETTINGS, **stored}
    env = _local_env()
    result["text_provider"] = env.get("FACTORY_TEXT_PROVIDER", result["text_provider"])
    result["llama_cpp_base_url"] = env.get("LLAMA_CPP_BASE_URL", result["llama_cpp_base_url"])
    result["llama_cpp_model"] = env.get("LLAMA_CPP_MODEL", result["llama_cpp_model"])
    result["gigachat_model"] = env.get("GIGACHAT_MODEL", result["gigachat_model"])
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
    # Validate and constrain the endpoint to loopback. This prevents sending script text to a remote host.
    from .providers import _base_url
    base_url = _base_url(base_url)
    persisted = {"text_provider": provider, "llama_cpp_base_url": base_url, "llama_cpp_model": model,
                 "gigachat_model": gigachat_model, "gigachat_cloud_ack": gigachat_cloud_ack}
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**persisted, "gigachat_credentials_configured": bool(gigachat_credentials()["client_id"] and gigachat_credentials()["client_secret"])}
