"""Loopback-only ComfyUI discovery, export, and explicitly confirmed local execution helpers."""
from __future__ import annotations

import json
import socket
import time
import uuid
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


def export_local_txt2img_workflow(settings: dict, request: dict) -> dict:
    """Build a local workflow JSON for export; this function never submits it."""
    from .comfyui_profiles import build_local_txt2img_workflow
    if not isinstance(request, dict):
        raise ComfyUIError("Ожидался JSON-объект параметров workflow")
    model = str(settings.get("comfyui_local_model", "")).strip()
    if not model:
        raise ComfyUIError("Сначала выберите локальную checkpoint-модель в настройках")
    requested_model = str(request.get("model", model)).strip()
    if requested_model != model:
        raise ComfyUIError("Для экспорта используйте модель, сохранённую в настройках фабрики")
    object_info = get_comfyui_object_info(settings)
    return build_local_txt2img_workflow(
        object_info, model=model, prompt=request.get("prompt", ""),
        negative_prompt=request.get("negative_prompt", ""),
        seed=request.get("seed", 42), width=request.get("width", 512),
        height=request.get("height", 512), steps=request.get("steps", 20),
        cfg=request.get("cfg", 7.0),
    )


def _post_json(base_url: str, path: str, payload: dict, timeout: float = 20) -> dict:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(base_url + path, data=raw,
                                     headers={"Accept": "application/json", "Content-Type": "application/json"},
                                     method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(4 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raise ComfyUIError(f"ComfyUI API ответил с ошибкой {exc.code} на {path}") from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        raise ComfyUIError("Не удалось отправить локальное задание в ComfyUI") from exc
    if len(body) > 4 * 1024 * 1024:
        raise ComfyUIError("Ответ ComfyUI слишком велик")
    try:
        result = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComfyUIError(f"ComfyUI вернул некорректный JSON на {path}") from exc
    if not isinstance(result, dict):
        raise ComfyUIError(f"ComfyUI вернул неожиданный ответ на {path}")
    return result


def _get_bytes(base_url: str, path: str, *, timeout: float = 30, limit: int = 50 * 1024 * 1024) -> bytes:
    request = urllib.request.Request(base_url + path, headers={"Accept": "image/*"}, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            data = response.read(limit + 1)
    except urllib.error.HTTPError as exc:
        raise ComfyUIError(f"ComfyUI не смог отдать изображение ({exc.code})") from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        raise ComfyUIError("Не удалось получить изображение из локального ComfyUI") from exc
    if not data or len(data) > limit:
        raise ComfyUIError("Файл изображения ComfyUI пуст или превышает лимит")
    return data


def _queue_contains(queue_data: dict, prompt_id: str, key: str) -> bool:
    entries = queue_data.get(key, [])
    if not isinstance(entries, list):
        return False
    return any(isinstance(entry, (list, tuple)) and len(entry) > 1 and str(entry[1]) == prompt_id
               for entry in entries)


def generate_local_txt2img(settings: dict, *, model: str, prompt: str, negative_prompt: str,
                           seed: int, width: int, height: int, steps: int, cfg: float,
                           cancel_requested=lambda: False, progress=lambda _message: None,
                           on_submitting=lambda: None, on_submitted=lambda _prompt_id: None,
                           resume_prompt_id: str | None = None, timeout: float = 3600,
                           poll_interval: float = 1.5) -> tuple[bytes, dict]:
    """Submit one explicitly requested local workflow, wait for its output, and return PNG bytes.

    This method targets only a validated loopback ComfyUI address. It never switches providers.
    A cancellation removes a still-pending prompt; a running prompt is allowed to finish rather
    than using ComfyUI's global /interrupt endpoint, which could stop another user's workflow.
    """
    from .comfyui_profiles import build_local_txt2img_workflow
    from .jobs import JobCancelled

    base_url = normalize_comfyui_base_url(settings.get("comfyui_base_url"))
    object_info = _get_json(base_url, "/object_info", timeout=20)
    built = build_local_txt2img_workflow(
        object_info, model=model, prompt=prompt, negative_prompt=negative_prompt, seed=seed,
        width=width, height=height, steps=steps, cfg=cfg)
    sampler_inputs = built["prompt"]["5"]["inputs"]
    prompt_id = str(resume_prompt_id or "")
    if cancel_requested() and not prompt_id:
        raise JobCancelled()
    if not prompt_id:
        on_submitting()
        if cancel_requested():
            raise JobCancelled()
        client_id = uuid.uuid4().hex
        response = _post_json(base_url, "/prompt", {"prompt": built["prompt"], "client_id": client_id})
        prompt_id = str(response.get("prompt_id", ""))
        if response.get("node_errors"):
            raise ComfyUIError("ComfyUI отклонил граф при локальной проверке узлов; сверьте профиль с /object_info")
        if not prompt_id or len(prompt_id) > 128 or not all(c.isalnum() or c in "-_" for c in prompt_id):
            raise ComfyUIError("ComfyUI не вернул корректный prompt_id для локального workflow")
        on_submitted(prompt_id)
    elif len(prompt_id) > 128 or not all(c.isalnum() or c in "-_" for c in prompt_id):
        raise ComfyUIError("Сохранённый ComfyUI prompt_id некорректен; workflow не будет отправлен повторно")
    started = time.monotonic()
    last_progress = 0.0
    while time.monotonic() - started < timeout:
        elapsed = time.monotonic() - started
        if cancel_requested():
            queue_data = _get_json(base_url, "/queue", timeout=10)
            if _queue_contains(queue_data, prompt_id, "queue_pending"):
                _post_json(base_url, "/queue", {"delete": [prompt_id]}, timeout=10)
                raise JobCancelled()
            # Running prompts cannot be safely interrupted globally. Wait for the local
            # workflow to finish, then discard its result so no candidate is registered.
        history = _get_json(base_url, "/history/" + urllib.parse.quote(prompt_id, safe=""), timeout=15)
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        if isinstance(entry, dict):
            status = entry.get("status", {}) if isinstance(entry.get("status"), dict) else {}
            if status.get("status_str") == "error" or entry.get("outputs") is None:
                raise ComfyUIError("Локальный workflow завершился ошибкой; проверьте журнал/очередь только на своём компьютере")
            outputs = entry.get("outputs", {})
            save_output = outputs.get("7", {}) if isinstance(outputs, dict) else {}
            images = save_output.get("images", []) if isinstance(save_output, dict) else []
            if images:
                image = images[0]
                if not isinstance(image, dict) or not image.get("filename"):
                    raise ComfyUIError("ComfyUI завершил workflow без корректного файла изображения")
                filename = str(image["filename"])
                subfolder = str(image.get("subfolder", ""))
                image_type = str(image.get("type", "output"))
                if (len(filename) > 255 or filename in (".", "..") or "/" in filename or "\\" in filename
                        or any(ord(char) < 32 for char in filename) or subfolder not in ("", "ai_video_factory")
                        or image_type != "output"):
                    raise ComfyUIError("ComfyUI вернул небезопасный путь к файлу изображения")
                query = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
                data = _get_bytes(base_url, "/view?" + query, limit=3_500_000)
                if cancel_requested():
                    raise JobCancelled()
                return data, {"prompt_id": prompt_id, "elapsed_s": round(elapsed, 2),
                              "model": model, "seed": seed, "steps": steps, "cfg": cfg,
                              "width": width, "height": height,
                              "sampler": sampler_inputs["sampler_name"],
                              "scheduler": sampler_inputs["scheduler"]}
        if elapsed - last_progress >= 4:
            progress("Жду локальный ComfyUI — workflow выполняется только на этом компьютере")
            last_progress = elapsed
        time.sleep(max(0.1, min(float(poll_interval), 5.0)))
    # Avoid leaving work queued after timeout; don't interrupt a running ComfyUI task.
    queue_data = _get_json(base_url, "/queue", timeout=10)
    if _queue_contains(queue_data, prompt_id, "queue_pending"):
        _post_json(base_url, "/queue", {"delete": [prompt_id]}, timeout=10)
    raise ComfyUIError("Локальный workflow не завершился за отведённое время; проверьте очередь ComfyUI")


def generate_agnes_image(settings: dict, *, prompt: str, seed: int, quality: str = "1K",
                         aspect_ratio: str = "4:3", cancel_requested=lambda: False,
                         progress=lambda _message: None, on_submitting=lambda: None,
                         on_submitted=lambda _prompt_id: None,
                         resume_prompt_id: str | None = None, timeout: float = 3600,
                         poll_interval: float = 1.5) -> tuple[bytes, dict]:
    """Run one explicitly consented AgnesImage T2I workflow through local ComfyUI.

    The cloud call is performed by the configured Agnes custom node, not by Arena or this
    process. This helper has no alternate provider, retry, or paid fallback.
    """
    from .comfyui_profiles import build_agnes_image_workflow
    from .jobs import JobCancelled
    from .pipeline import AGNES_IMAGE_RUNTIME_ENABLED

    if not AGNES_IMAGE_RUNTIME_ENABLED:
        raise ComfyUIError("AgnesImage выключен. Для бесплатной квоты задайте AGNES_IMAGE_BILLING_MODE=free_quota и AGNES_IMAGE_RUNTIME_ENABLED=true в локальном .env, затем перезапустите Factory.")
    base_url = normalize_comfyui_base_url(settings.get("comfyui_base_url"))
    object_info = _get_json(base_url, "/object_info", timeout=20)
    built = build_agnes_image_workflow(object_info, prompt=prompt, seed=seed,
                                       quality=quality, aspect_ratio=aspect_ratio)
    prompt_id = str(resume_prompt_id or "")
    if cancel_requested() and not prompt_id:
        raise JobCancelled()
    if not prompt_id:
        on_submitting()
        if cancel_requested():
            raise JobCancelled()
        response = _post_json(base_url, "/prompt", {
            "prompt": built["prompt"], "client_id": uuid.uuid4().hex,
        })
        if response.get("node_errors"):
            raise ComfyUIError("ComfyUI отклонил AgnesImage graph по проверке узлов; сверьте локальный /object_info")
        prompt_id = str(response.get("prompt_id", ""))
        if not prompt_id or len(prompt_id) > 128 or not all(c.isalnum() or c in "-_" for c in prompt_id):
            raise ComfyUIError("ComfyUI не вернул корректный prompt_id для AgnesImage")
        on_submitted(prompt_id)
    elif len(prompt_id) > 128 or not all(c.isalnum() or c in "-_" for c in prompt_id):
        raise ComfyUIError("Сохранённый AgnesImage prompt_id некорректен; workflow не будет отправлен повторно")

    started = time.monotonic()
    last_progress = 0.0
    while time.monotonic() - started < timeout:
        elapsed = time.monotonic() - started
        if cancel_requested():
            queue_data = _get_json(base_url, "/queue", timeout=10)
            if _queue_contains(queue_data, prompt_id, "queue_pending"):
                _post_json(base_url, "/queue", {"delete": [prompt_id]}, timeout=10)
                raise JobCancelled()
        history = _get_json(base_url, "/history/" + urllib.parse.quote(prompt_id, safe=""), timeout=15)
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        if isinstance(entry, dict):
            status = entry.get("status", {}) if isinstance(entry.get("status"), dict) else {}
            if status.get("status_str") == "error" or entry.get("outputs") is None:
                raise ComfyUIError("AgnesImage workflow завершился ошибкой; проверьте локальную очередь ComfyUI")
            output = entry.get("outputs", {}).get(built["output_node_id"], {})
            images = output.get("images", []) if isinstance(output, dict) else []
            if images:
                image = images[0]
                if not isinstance(image, dict) or not image.get("filename"):
                    raise ComfyUIError("ComfyUI завершил AgnesImage без корректного файла изображения")
                filename = str(image["filename"])
                subfolder = str(image.get("subfolder", ""))
                image_type = str(image.get("type", "temp"))
                if (len(filename) > 255 or filename in (".", "..") or "/" in filename or "\\" in filename
                        or any(ord(char) < 32 for char in filename) or subfolder not in ("",)
                        or image_type not in ("temp", "output")):
                    raise ComfyUIError("ComfyUI вернул небезопасный путь к результату AgnesImage")
                query = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
                data = _get_bytes(base_url, "/view?" + query, limit=20 * 1024 * 1024)
                if cancel_requested():
                    raise JobCancelled()
                return data, {"prompt_id": prompt_id, "elapsed_s": round(elapsed, 2),
                              "profile_id": built["profile_id"], "seed": seed,
                              "quality": quality, "aspect_ratio": aspect_ratio,
                              "output_node_id": built["output_node_id"]}
        if elapsed - last_progress >= 4:
            progress("Ожидание локального ComfyUI; он выполняет один запрос AgnesImage")
            last_progress = elapsed
        time.sleep(max(0.1, min(float(poll_interval), 5.0)))
    queue_data = _get_json(base_url, "/queue", timeout=10)
    if _queue_contains(queue_data, prompt_id, "queue_pending"):
        _post_json(base_url, "/queue", {"delete": [prompt_id]}, timeout=10)
    raise ComfyUIError("AgnesImage workflow не завершился за отведённое время; проверьте локальную очередь")


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
