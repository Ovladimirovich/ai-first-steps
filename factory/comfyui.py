"""Local ComfyUI discovery and API helpers. This module never submits a workflow."""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request


class ComfyUIError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def normalize_comfyui_base_url(value: str | None) -> str:
    raw = str(value or "http://127.0.0.1:8188").strip().rstrip("/")
    parsed = urllib.parse.urlparse(raw)
    try:
        parsed.port
    except ValueError as exc:
        raise ComfyUIError("В адресе ComfyUI указан некорректный порт") from exc
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ComfyUIError("Укажите локальный адрес ComfyUI, например http://127.0.0.1:8188")
    if parsed.hostname.lower() not in ("127.0.0.1", "localhost", "::1"):
        raise ComfyUIError("Для этой проверки разрешён только ComfyUI на этом компьютере")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _get_json(base_url: str, path: str, timeout: float) -> dict:
    request = urllib.request.Request(base_url + path, headers={"Accept": "application/json"}, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(32 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raise ComfyUIError(f"ComfyUI API ответил с ошибкой {exc.code} на {path}") from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        raise ComfyUIError("Не удалось связаться с локальным ComfyUI. Проверьте, что он запущен на указанном адресе.") from exc
    if len(raw) > 32 * 1024 * 1024:
        raise ComfyUIError("Ответ ComfyUI слишком велик для проверки узлов")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComfyUIError(f"ComfyUI вернул некорректный JSON на {path}") from exc
    if not isinstance(result, dict):
        raise ComfyUIError(f"ComfyUI вернул неожиданный ответ на {path}")
    return result


def get_comfyui_object_info(settings: dict) -> dict:
    """Read the local node schema for building a validated workflow profile."""
    base_url = normalize_comfyui_base_url(settings.get("comfyui_base_url"))
    return _get_json(base_url, "/object_info", timeout=20)


def discover_local_txt2img_profile(settings: dict) -> dict:
    """Discover available core txt2img models/options without submitting a workflow."""
    from .comfyui_profiles import inspect_local_txt2img_profile
    return inspect_local_txt2img_profile(get_comfyui_object_info(settings))


def check_comfyui_connection(settings: dict) -> dict:
    """Check the local ComfyUI API and discover node classes without running any workflow."""
    base_url = normalize_comfyui_base_url(settings.get("comfyui_base_url"))
    stats = _get_json(base_url, "/system_stats", timeout=8)
    object_info = get_comfyui_object_info(settings)
    system = stats.get("system", {}) if isinstance(stats.get("system"), dict) else {}
    nodes = {
        "CheckpointLoaderSimple": "CheckpointLoaderSimple" in object_info,
        "KSampler": "KSampler" in object_info,
        "AgnesImage": "AgnesImage" in object_info,
        "AgnesText": "AgnesText" in object_info,
    }
    return {
        "connected": True,
        "base_url": base_url,
        "node_count": len(object_info),
        "nodes": nodes,
        "system": {
            "os": str(system.get("os", ""))[:80],
            "python_version": str(system.get("python_version", ""))[:80],
            "pytorch_version": str(system.get("pytorch_version", ""))[:80],
            "device_count": len(stats.get("devices", [])) if isinstance(stats.get("devices"), list) else 0,
        },
    }
