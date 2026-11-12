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


def _submit_graph_and_wait(base_url: str, graph: dict, *, result_node: str, view_type: str,
                           allowed_subfolders: tuple, progress_text: str, rejected_text: str,
                           failed_text: str, timeout_text: str, prompt_id_text: str,
                           resume_prompt_id: str | None, cancel_requested, progress,
                           on_submitting, on_submitted, timeout: float, poll_interval: float) -> tuple[bytes, dict]:
    """Submit one validated workflow to loopback ComfyUI, wait for the result node, download the PNG.

    Cancellation removes a still-pending prompt; a running prompt is allowed to finish rather than
    using ComfyUI's global /interrupt endpoint, which could stop another user's workflow.
    """
    from .jobs import JobCancelled

    prompt_id = str(resume_prompt_id or "")
    if cancel_requested() and not prompt_id:
        raise JobCancelled()
    if not prompt_id:
        on_submitting()
        if cancel_requested():
            raise JobCancelled()
        client_id = uuid.uuid4().hex
        response = _post_json(base_url, "/prompt", {"prompt": graph, "client_id": client_id})
        prompt_id = str(response.get("prompt_id", ""))
        if response.get("node_errors"):
            raise ComfyUIError(rejected_text)
        if not prompt_id or len(prompt_id) > 128 or not all(c.isalnum() or c in "-_" for c in prompt_id):
            raise ComfyUIError(prompt_id_text)
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
            # Running prompts cannot be safely interrupted globally. Wait for the
            # workflow to finish, then discard its result so no candidate is registered.
        history = _get_json(base_url, "/history/" + urllib.parse.quote(prompt_id, safe=""), timeout=15)
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        if isinstance(entry, dict):
            status = entry.get("status", {}) if isinstance(entry.get("status"), dict) else {}
            if status.get("status_str") == "error" or entry.get("outputs") is None:
                raise ComfyUIError(failed_text)
            outputs = entry.get("outputs", {})
            result_output = outputs.get(result_node, {}) if isinstance(outputs, dict) else {}
            images = result_output.get("images", []) if isinstance(result_output, dict) else []
            if images:
                image = images[0]
                if not isinstance(image, dict) or not image.get("filename"):
                    raise ComfyUIError("ComfyUI завершил workflow без корректного файла изображения")
                filename = str(image["filename"])
                subfolder = str(image.get("subfolder", ""))
                image_type = str(image.get("type", view_type))
                if (len(filename) > 255 or filename in (".", "..") or "/" in filename or "\\" in filename
                        or any(ord(char) < 32 for char in filename) or subfolder not in allowed_subfolders
                        or image_type != view_type):
                    raise ComfyUIError("ComfyUI вернул небезопасный путь к файлу изображения")
                query = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
                data = _get_bytes(base_url, "/view?" + query, limit=3_500_000)
                if cancel_requested():
                    raise JobCancelled()
                return data, {"prompt_id": prompt_id, "elapsed_s": round(elapsed, 2)}
        if elapsed - last_progress >= 4:
            progress(progress_text)
            last_progress = elapsed
        time.sleep(max(0.1, min(float(poll_interval), 5.0)))
    # Avoid leaving work queued after timeout; don't interrupt a running ComfyUI task.
    queue_data = _get_json(base_url, "/queue", timeout=10)
    if _queue_contains(queue_data, prompt_id, "queue_pending"):
        _post_json(base_url, "/queue", {"delete": [prompt_id]}, timeout=10)
    raise ComfyUIError(timeout_text)


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
    data, info = _submit_graph_and_wait(
        base_url, built["prompt"], result_node="7", view_type="output",
        allowed_subfolders=("", "ai_video_factory"),
        progress_text="Жду локальный ComfyUI — workflow выполняется только на этом компьютере",
        rejected_text="ComfyUI отклонил граф при локальной проверке узлов; сверьте профиль с /object_info",
        failed_text="Локальный workflow завершился ошибкой; проверьте журнал/очередь только на своём компьютере",
        timeout_text="Локальный workflow не завершился за отведённое время; проверьте очередь ComfyUI",
        prompt_id_text="ComfyUI не вернул корректный prompt_id для локального workflow",
        resume_prompt_id=resume_prompt_id, cancel_requested=cancel_requested, progress=progress,
        on_submitting=on_submitting, on_submitted=on_submitted,
        timeout=timeout, poll_interval=poll_interval)
    return data, {**info, "model": model, "seed": seed, "steps": steps, "cfg": cfg,
                  "width": width, "height": height,
                  "sampler": sampler_inputs["sampler_name"], "scheduler": sampler_inputs["scheduler"]}


def generate_agnes_txt2img(settings: dict, *, prompt: str, quality: str, aspect_ratio: str,
                           seed: int, preprocess_prompt: bool = True,
                           text_preset: str = "Prompt Enhance",
                           cancel_requested=lambda: False, progress=lambda _message: None,
                           on_submitting=lambda: None, on_submitted=lambda _prompt_id: None,
                           resume_prompt_id: str | None = None, timeout: float = 3600,
                           poll_interval: float = 1.5) -> tuple[bytes, dict]:
    """Submit one explicitly requested Agnes cloud workflow to loopback ComfyUI and wait for output.

    The cloud Agnes call is made by the local ComfyUI instance that holds the API key; the factory
    only POSTs to the loopback /prompt. It never switches providers: on error there is no local
    or paid fallback.
    """
    from .comfyui_profiles import AGNES_PROFILE_ID, build_agnes_txt2img_workflow

    base_url = normalize_comfyui_base_url(settings.get("comfyui_base_url"))
    object_info = _get_json(base_url, "/object_info", timeout=20)
    built = build_agnes_txt2img_workflow(
        object_info, prompt=prompt, quality=quality, aspect_ratio=aspect_ratio, seed=seed,
        preprocess_prompt=preprocess_prompt, text_preset=text_preset)
    data, info = _submit_graph_and_wait(
        base_url, built["prompt"], result_node=built["result_node"], view_type="temp",
        allowed_subfolders=("",),
        progress_text="Жду Agnes cloud — генерация идёт через локальный ComfyUI; API-ключ остаётся на этом компьютере",
        rejected_text="ComfyUI отклонил Agnes-граф при локальной проверке узлов; сверьте профиль с /object_info",
        failed_text="Agnes cloud workflow завершился ошибкой; проверьте журнал локального ComfyUI. Платного fallback нет",
        timeout_text="Agnes cloud workflow не завершился за отведённое время; проверьте очередь локального ComfyUI. Платного fallback нет",
        prompt_id_text="ComfyUI не вернул корректный prompt_id для Agnes-графа",
        resume_prompt_id=resume_prompt_id, cancel_requested=cancel_requested, progress=progress,
        on_submitting=on_submitting, on_submitted=on_submitted,
        timeout=timeout, poll_interval=poll_interval)
    return data, {**info, "profile_id": AGNES_PROFILE_ID, "quality": quality, "aspect_ratio": aspect_ratio,
                  "preprocess_prompt": bool(preprocess_prompt),
                  "text_preset": text_preset if preprocess_prompt else None, "seed": seed}


def inspect_agnes_connection(settings: dict) -> dict:
    """Read-only Agnes cloud profile availability report; it never runs a workflow."""
    from .comfyui_profiles import inspect_agnes_profile
    return inspect_agnes_profile(get_comfyui_object_info(settings))


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
