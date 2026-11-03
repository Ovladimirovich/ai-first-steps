"""Локальный llama.cpp и облачный GigaChat для черновиков сценария."""
from __future__ import annotations

import base64
import json
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


class ProviderError(RuntimeError):
    pass


GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1"
_GIGA_TOKENS = {}
_GIGA_TOKEN_LOCK = threading.Lock()


def _base_url(value: str) -> str:
    parsed = urllib.parse.urlparse((value or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ProviderError("Укажите адрес локального помощника, например http://127.0.0.1:8081/v1")
    if parsed.hostname.lower() not in ("127.0.0.1", "localhost", "::1") or parsed.username or parsed.password:
        raise ProviderError("Для приватности помощник должен быть доступен только на этом компьютере")
    path = parsed.path.rstrip("/") or "/v1"
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def _request_json(url: str, body: dict | None = None, timeout: float = 10.0) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"},
                                    method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise ProviderError(f"Локальный помощник ответил с ошибкой {exc.code}: {detail}") from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        raise ProviderError("Не удалось связаться с локальным помощником. Проверьте, что окно llama-server открыто и адрес верный.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("Локальный помощник прислал ответ, который не удалось прочитать как JSON") from exc
    if not isinstance(result, dict):
        raise ProviderError("Локальный помощник прислал неожиданный ответ")
    return result


def _scenario_prompt(spec: dict) -> tuple[str, int, int]:
    intent = spec.get("intent", {})
    heroes = spec.get("heroes", [])
    seconds = int(intent.get("target_duration_s", 60))
    expected = {30: 4, 45: 6, 60: 8, 90: 12, 120: 16}.get(seconds, 8)
    scene_count = 3 if seconds <= 60 else 4
    audience = intent.get("audience", {}).get("note", "школьники")
    theme = str(intent.get("theme", "")).strip()
    hero_lines = "\n".join(f"{h['id']} — {h['name']}, роль: {'объясняет' if h.get('role') == 'explains' else 'спрашивает'}; характер: {h.get('about', '')}" for h in heroes)
    prompt = f"""Напиши сценарий короткого познавательного видео на русском языке.
ТЕМА: {theme}
ЗРИТЕЛЬ: {audience}
ДЛИТЕЛЬНОСТЬ: около {seconds} секунд
ТОН: {intent.get('tone', 'дружелюбно и понятно')}
ГЕРОИ (в поле hero используй только ID слева):
{hero_lines}

Требования: {expected} коротких реплик, ровно {scene_count} сцены; один ясный смысл на сцену; первая сцена цепляет вопросом, в конце есть вывод и простое действие. Фразы естественные для устной речи, без выдуманных фактов и длинных вступлений. Реплики чередуют героев, но не обязаны идти строго по очереди.

Верни только корректный JSON, без Markdown и комментариев, по форме:
{{"scenes":[{{"title":"Короткий заголовок","purpose":"hook|point|check|payoff","goal":"что зритель поймёт","visual_note":"что можно показать","lines":[{{"hero":"h1","text":"Текст реплики"}}]}}]}}
"""
    return prompt, expected, scene_count


def _json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ProviderError("Помощник не вернул сценарий в нужном формате. Попробуйте ещё раз.")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Не удалось разобрать черновик помощника (позиция {exc.pos}).") from exc
    if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
        raise ProviderError("В ответе помощника не найдены сцены сценария")
    return data


def _normalize_scenario(spec: dict, data: dict, provider: str, model: str) -> dict:
    _, _, scene_count = _scenario_prompt(spec)
    heroes = spec.get("heroes", [])
    name_to_id = {str(h.get("name", "")).casefold(): h["id"] for h in heroes}
    allowed_ids = {h["id"] for h in heroes}
    scenes = []
    line_number = 1
    source_scenes = data["scenes"][:5]
    for scene_number, source in enumerate(source_scenes, 1):
        if not isinstance(source, dict):
            continue
        source_lines = source.get("lines", [])
        if not isinstance(source_lines, list):
            continue
        lines = []
        for item in source_lines:
            if not isinstance(item, dict):
                continue
            hero = str(item.get("hero", ""))
            hero_id = hero if hero in allowed_ids else name_to_id.get(hero.casefold())
            text = re.sub(r"\s+", " ", str(item.get("text", ""))).strip()
            if not hero_id or not text:
                continue
            lines.append({"id": f"l{line_number}", "hero": hero_id, "text": text, "pause_after_s": None})
            line_number += 1
        if not lines:
            continue
        purpose = source.get("purpose", "point")
        if purpose not in ("hook", "point", "check", "payoff"):
            purpose = "hook" if scene_number == 1 else ("payoff" if scene_number == len(source_scenes) else "point")
        scenes.append({"id": f"s{scene_number}", "order": scene_number,
                       "title": str(source.get("title", f"Сцена {scene_number}"))[:80],
                       "purpose": purpose, "goal": str(source.get("goal", ""))[:240],
                       "visual_note": str(source.get("visual_note", ""))[:240],
                       "image": {"mode": "style", "path": None}, "lines": lines})
    if not scenes or line_number <= 1:
        raise ProviderError("Помощник вернул пустой сценарий. Попробуйте ещё раз или переключитесь на демо-шаблон.")
    if len(scenes) < max(1, scene_count - 1):
        raise ProviderError("Помощник вернул слишком мало сцен. Попробуйте ещё раз.")
    spec["script"] = {"generator": {"provider": provider, "version": model}, "scenes": scenes}
    return spec


def test_connection(settings: dict) -> dict:
    """Проверка локального llama.cpp; не загружает модель и не генерирует текст."""
    base = _base_url(settings.get("llama_cpp_base_url", "http://127.0.0.1:8081/v1"))
    started = time.monotonic()
    result = _request_json(base + "/models", timeout=5)
    models = result.get("data", [])
    model_ids = [str(item.get("id", "")) for item in models if isinstance(item, dict) and item.get("id")]
    elapsed = round((time.monotonic() - started) * 1000)
    return {"connected": True, "base_url": base, "model": model_ids[0] if model_ids else "локальная модель",
            "models": model_ids, "latency_ms": elapsed}


def _giga_context(credentials: dict) -> ssl.SSLContext:
    ca_bundle = str(credentials.get("ca_bundle", "")).strip()
    if ca_bundle:
        if not Path(ca_bundle).is_file():
            raise ProviderError("Файл сертификата GigaChat не найден. Проверьте GIGACHAT_CA_BUNDLE в .env.")
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()


def _giga_json(url: str, *, body: dict | None, headers: dict, context: ssl.SSLContext, timeout: float = 25) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers,
                                    method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Не прокидываем тело auth-ошибки в UI: оно может содержать чувствительные детали.
        raise ProviderError(f"GigaChat ответил с ошибкой {exc.code}. Проверьте доступ к API и настройки учётных данных.") from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError, ssl.SSLError) as exc:
        raise ProviderError("Не удалось безопасно подключиться к GigaChat. Проверьте интернет и сертификат GIGACHAT_CA_BUNDLE.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("GigaChat прислал ответ, который не удалось прочитать") from exc
    if not isinstance(result, dict):
        raise ProviderError("GigaChat прислал неожиданный ответ")
    return result


def _gigachat_token(credentials: dict, force: bool = False) -> str:
    client_id = str(credentials.get("client_id", "")).strip()
    client_secret = str(credentials.get("client_secret", "")).strip()
    scope = str(credentials.get("scope", "GIGACHAT_API_PERS")).strip()
    if not client_id or not client_secret:
        raise ProviderError("Для GigaChat добавьте GIGACHAT_CLIENT_ID и GIGACHAT_CLIENT_SECRET в локальный файл .env")
    cache_key = (client_id, scope)
    now = time.time()
    with _GIGA_TOKEN_LOCK:
        cached = _GIGA_TOKENS.get(cache_key)
        if not force and cached and cached["expires"] > now + 60:
            return cached["token"]
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        request = urllib.request.Request(
            GIGACHAT_AUTH_URL,
            data=urllib.parse.urlencode({"scope": scope}).encode("ascii"),
            headers={"Authorization": f"Basic {auth}", "RqUID": str(uuid.uuid4()),
                     "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20, context=_giga_context(credentials)) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Не удалось получить токен GigaChat (ошибка {exc.code}). Проверьте Client ID, секрет и выбранный доступ.") from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError, ssl.SSLError) as exc:
            raise ProviderError("Не удалось безопасно подключиться к авторизации GigaChat. Проверьте интернет и сертификат.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("Сервис авторизации GigaChat прислал неожиданный ответ") from exc
        token = result.get("access_token")
        if not token:
            raise ProviderError("GigaChat не выдал токен. Проверьте тип доступа и учётные данные.")
        expires_at = float(result.get("expires_at", (now + 1500) * 1000))
        if expires_at > 10_000_000_000:
            expires_at /= 1000
        _GIGA_TOKENS[cache_key] = {"token": str(token), "expires": expires_at}
        return str(token)


def _gigachat_api(path: str, credentials: dict, body: dict | None = None, timeout: float = 30) -> dict:
    context = _giga_context(credentials)
    for attempt in range(2):
        token = _gigachat_token(credentials, force=attempt == 1)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            return _giga_json(GIGACHAT_API_URL + path, body=body, headers=headers, context=context, timeout=timeout)
        except ProviderError as exc:
            if attempt == 0 and "ошибкой 401" in str(exc):
                continue
            raise
    raise ProviderError("Не удалось авторизоваться в GigaChat")


def test_gigachat_connection(credentials: dict) -> dict:
    started = time.monotonic()
    result = _gigachat_api("/models", credentials, timeout=15)
    models = result.get("data", [])
    model_ids = [str(item.get("id", "")) for item in models if isinstance(item, dict) and item.get("id")]
    return {"connected": True, "model": model_ids[0] if model_ids else "GigaChat", "models": model_ids,
            "latency_ms": round((time.monotonic() - started) * 1000)}


def _model_from_list(result: dict, fallback: str) -> str:
    for item in result.get("data", []):
        if isinstance(item, dict) and item.get("id"):
            return str(item["id"])
    return fallback


def draft_with_llama(spec: dict, settings: dict) -> dict:
    base = _base_url(settings.get("llama_cpp_base_url", "http://127.0.0.1:8081/v1"))
    model = str(settings.get("llama_cpp_model", "")).strip()
    if not model:
        try:
            model = _model_from_list(_request_json(base + "/models", timeout=5), "local")
        except ProviderError:
            model = "local"
    prompt, _, _ = _scenario_prompt(spec)
    payload = {"model": model, "messages": [
        {"role": "system", "content": "Ты бережный редактор коротких образовательных видео для детей. Следуй формату JSON строго."},
        {"role": "user", "content": prompt},
    ], "temperature": 0.55, "max_tokens": 3200}
    response = _request_json(base + "/chat/completions", payload, timeout=240)
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Помощник не вернул текст сценария") from exc
    data = _json_object(content if isinstance(content, str) else str(content))
    return _normalize_scenario(spec, data, "llama_cpp", model)


def draft_with_gigachat(spec: dict, settings: dict, credentials: dict) -> dict:
    prompt, _, _ = _scenario_prompt(spec)
    model = str(settings.get("gigachat_model", "")).strip()
    if not model:
        model = _model_from_list(_gigachat_api("/models", credentials, timeout=20), "GigaChat")
    payload = {"model": model, "messages": [
        {"role": "system", "content": "Ты бережный редактор коротких образовательных видео для детей. Следуй формату JSON строго."},
        {"role": "user", "content": prompt},
    ], "temperature": 0.55, "max_tokens": 3200}
    response = _gigachat_api("/chat/completions", credentials, payload, timeout=180)
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("GigaChat не вернул текст сценария") from exc
    data = _json_object(content if isinstance(content, str) else str(content))
    return _normalize_scenario(spec, data, "gigachat", model)
