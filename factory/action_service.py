from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from .actions import append_action_event, get_action, verify_action_log
from .core import digest, draft_script, load_project, project_dir, save_project, validate_spec
from .jobs import (JobCancelled, create_job, ensure_job_enqueued, get_job, is_cancel_requested,
                  list_jobs, retry_job)
from .providers import draft_with_gigachat, draft_with_llama
from .settings import gigachat_credentials, load_settings
from .storage import atomic_write_json, project_lock
from .resources import LOCAL_MODEL_LOCK

PROMPT_VERSION = "script-draft-v1"
GENERATION_PARAMETERS = {"temperature": 0.55, "max_tokens": 3200}
QUOTE_TTL_SECONDS = 600

def _provider_settings() -> tuple[dict, str, str]:
    settings = load_settings()
    provider = str(settings.get("text_provider", "demo"))
    if provider not in ("demo", "llama_cpp", "gigachat"):
        raise ValueError("Неизвестный текстовый помощник")
    model = str(settings.get("llama_cpp_model", "") if provider == "llama_cpp" else
                settings.get("gigachat_model", "") if provider == "gigachat" else "rule-v1").strip()
    model = model or ("local-auto" if provider == "llama_cpp" else "GigaChat-auto" if provider == "gigachat" else "rule-v1")
    return settings, provider, model

def _fingerprint(project: dict, provider: str, model: str, settings: dict | None = None,
                 *, project_revision: int | None = None) -> str:
    settings = settings or {}
    provider_config = ({"local_endpoint": settings.get("llama_cpp_base_url", "")}
                       if provider == "llama_cpp" else {"api_profile": "gigachat-chat-completions-v1"}
                       if provider == "gigachat" else {"template": "local-rule-template"})
    revision = int(project["revision"] if project_revision is None else project_revision)
    return digest({"spec": project["spec"], "project_revision": revision,
                   "provider": provider, "model": model, "provider_config": provider_config,
                   "prompt_version": PROMPT_VERSION, "parameters": GENERATION_PARAMETERS})

def propose_script_draft(project_id: str) -> dict:
    project = load_project(project_id)
    if int(project.get("schema_version", 1)) < 2:
        raise ValueError("Для действия требуется проект v2; выполните отдельную явную миграцию без автоматического изменения проекта")
    if not str(project.get("spec", {}).get("intent", {}).get("theme", "")).strip():
        raise ValueError("Введите тему ролика")
    settings, provider, model = _provider_settings()
    if provider in ("llama_cpp", "gigachat") and not str(
            settings.get("llama_cpp_model" if provider == "llama_cpp" else "gigachat_model", "")).strip():
        raise ValueError("Перед созданием действия укажите точный ID модели в настройках, чтобы зафиксировать версию в отпечатке.")
    if provider == "gigachat" and not settings.get("gigachat_cloud_ack"):
        raise ValueError("Подтвердите в настройках, что сценарий отправляется в облачный GigaChat.")
    if provider == "gigachat":
        credentials = gigachat_credentials()
        if not credentials.get("client_id") or not credentials.get("client_secret"):
            raise ValueError("Для выбранного облачного помощника не настроены учётные данные")
    now = time.time()
    action_id = uuid.uuid4().hex
    input_fingerprint = _fingerprint(project, provider, model, settings)
    action = {
        "action_id": action_id,
        "kind": "script-draft",
        "status": "proposed",
        "base_project_revision": int(project["revision"]),
        "base_spec_hash": digest(project["spec"]),
        "input_fingerprint": input_fingerprint,
        "provider": provider,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "generation_parameters": GENERATION_PARAMETERS,
        "privacy_scope": "cloud" if provider == "gigachat" else "local",
        "requires_cloud_consent": provider == "gigachat",
        "cost_estimate": {"amount": None if provider == "gigachat" else 0,
                           "currency": "RUB", "basis": "user_ceiling_required" if provider == "gigachat" else "no_paid_provider"},
        "quote_created_at": now,
        "quote_expires_at": now + QUOTE_TTL_SECONDS,
    }
    append_action_event(project_id, "action_proposed", actor="user", data=action)
    return action

def _validate_action_base(project_id: str, action: dict) -> tuple[dict, dict, str]:
    project = load_project(project_id)
    if int(project.get("schema_version", 1)) < 2:
        raise ValueError("Действие устарело: для него требуется проект v2")
    settings, provider, model = _provider_settings()
    if digest(project["spec"]) != action.get("base_spec_hash"):
        raise ValueError("Сценарий изменился после предложения; создайте новое действие")
    current_fingerprint = _fingerprint(project, provider, model, settings,
                                       project_revision=int(action.get("base_project_revision", -1)))
    if current_fingerprint != action.get("input_fingerprint"):
        raise ValueError("Параметры модели или входной отпечаток изменились; создайте новое действие")
    return project, settings, current_fingerprint

def confirm_action(project_id: str, action_id: str, body: dict) -> dict:
    with project_lock(project_id):
        action = get_action(project_id, action_id)
        if action.get("kind") != "script-draft" or action.get("status") not in ("proposed", "confirmed"):
            raise ValueError("Подтвердить можно только ещё не запущенное предложение сценария")
        for existing in list_jobs(project_id):
            if existing.get("action_id") == action_id:
                if existing.get("state") == "queued":
                    return ensure_job_enqueued(project_id, existing["id"])
                return existing
        if action.get("job_id"):
            raise ValueError("Запись уже поставленной задачи отсутствует или повреждена")
        project, settings, current_fingerprint = _validate_action_base(project_id, action)
        base_spec_hash = digest(project["spec"])
        if body.get("input_fingerprint") != current_fingerprint:
            raise ValueError("Подтверждение не совпадает с текущим отпечатком входных данных")
        now = time.time()
        if now > float(action.get("quote_expires_at", 0)):
            raise ValueError("Смета устарела; создайте новое предложение")
        if body.get("consent") is not True:
            raise ValueError("Требуется явное подтверждение запуска")
        try:
            ceiling = float(body.get("cost_ceiling", {}).get("amount"))
        except (AttributeError, TypeError, ValueError):
            raise ValueError("Укажите актуальный предел стоимости перед запуском")
        if ceiling < 0:
            raise ValueError("Предел стоимости не может быть отрицательным")
        currency = str(body.get("cost_ceiling", {}).get("currency", "")).upper()
        if currency not in ("RUB", "EUR", "USD"):
            raise ValueError("Укажите валюту предела стоимости: RUB, EUR или USD")
        requires_cloud = bool(action.get("requires_cloud_consent"))
        if requires_cloud and ceiling <= 0:
            raise ValueError("Для облачного задания нужен положительный предел стоимости")
        if requires_cloud:
            if body.get("cloud_consent") is not True or not settings.get("gigachat_cloud_ack"):
                raise ValueError("Для облачного задания нужно текущее согласие пользователя в запросе и настройках")
            credentials = gigachat_credentials()
            if not credentials.get("client_id") or not credentials.get("client_secret"):
                raise ValueError("Учётные данные облачного помощника больше не настроены")
        elif body.get("privacy_scope") != "local":
            raise ValueError("Для локального помощника подтвердите обработку только на локальном устройстве")
        confirmation = {"consent": True, "privacy_scope": "cloud" if requires_cloud else "local",
                        "cloud_consent": bool(body.get("cloud_consent", False)),
                        "cost_ceiling": {"amount": ceiling, "currency": currency},
                        "input_fingerprint": current_fingerprint, "confirmed_at": now,
                        "expires_at": now + 3600}
        return create_job(project_id, action_id=action_id, job_type="script_draft",
                          payload={"base_project_revision": project["revision"], "base_spec_hash": base_spec_hash,
                                   "provider": action["provider"], "model": action["model"],
                                   "prompt_version": action["prompt_version"],
                                   "generation_parameters": action["generation_parameters"]},
                          input_fingerprint=current_fingerprint, approval=confirmation)

def candidate_path(project_id: str, action_id: str) -> Path:
    if not str(action_id).isalnum():
        raise FileNotFoundError(action_id)
    return project_dir(project_id) / "studio" / "action-candidates" / f"{action_id}.json"

def _publish_candidate(project_id: str, action_id: str, action: dict, candidate: dict,
                       provider: str, model: str) -> None:
    path = candidate_path(project_id, action_id)
    atomic_write_json(path, candidate)
    candidate_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    prior = action.get("candidate", {})
    if prior.get("sha256") == candidate_sha:
        return
    append_action_event(project_id, "action_candidate_ready", actor="system",
                        data={"action_id": action_id,
                              "candidate": {"path": str(path.relative_to(project_dir(project_id))),
                                            "sha256": candidate_sha, "provider": provider, "model": model}})

def execute_script_draft_job(job: dict) -> None:
    if is_cancel_requested(job["project_id"], job["id"]):
        raise JobCancelled()
    action = get_action(job["project_id"], job["action_id"])
    project = load_project(job["project_id"])
    if int(project.get("schema_version", 1)) < 2:
        raise ValueError("Действие устарело: для него требуется проект v2")
    approval = job.get("approval") or {}
    if time.time() > float(approval.get("expires_at", 0)):
        raise ValueError("Подтверждение устарело; запустите действие заново")
    ceiling = approval.get("cost_ceiling") or {}
    try:
        ceiling_amount = float(ceiling.get("amount"))
    except (TypeError, ValueError):
        raise ValueError("Не найден актуальный предел стоимости")
    if (approval.get("consent") is not True or approval.get("input_fingerprint") != job.get("input_fingerprint") or
            ceiling_amount < (0.0000001 if action.get("requires_cloud_consent") else 0) or
            str(ceiling.get("currency", "")).upper() not in ("RUB", "EUR", "USD")):
        raise ValueError("Подтверждение согласия или предел стоимости недействительны")
    if digest(project["spec"]) != action.get("base_spec_hash"):
        raise ValueError("Сценарий изменился до запуска; результат не будет применён")
    settings, provider, model = _provider_settings()
    if _fingerprint(project, provider, model, settings,
                    project_revision=int(action.get("base_project_revision", -1))) != job.get("input_fingerprint"):
        raise ValueError("Параметры помощника изменились; результат не будет применён")
    path = candidate_path(job["project_id"], job["action_id"])
    # If a crash happened after the candidate was durably written, reuse it rather than
    # repeating a potentially chargeable provider call.
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if (existing.get("input_fingerprint") == job["input_fingerprint"] and
                existing.get("base_spec_hash") == digest(project["spec"]) and
                existing.get("provider") == provider and existing.get("model") == model and
                existing.get("candidate_spec_hash") == digest(existing.get("spec"))):
            validate_spec(existing["spec"])
            _publish_candidate(job["project_id"], job["action_id"], action, existing, provider, model)
            return
    except (OSError, ValueError, TypeError):
        pass
    if provider == "gigachat":
        events = verify_action_log(job["project_id"])["events"]
        attempt = int(job.get("retry_count", 0))
        if any(event["event_type"] == "action_provider_call_started" and
               event.get("data", {}).get("job_id") == job["id"] and
               int(event.get("data", {}).get("attempt", -1)) >= attempt for event in events):
            raise ValueError("Результат облачного вызова неизвестен после прерывания; для повтора подтвердите новое задание")
        if not approval.get("cloud_consent") or not settings.get("gigachat_cloud_ack"):
            raise ValueError("Согласие на облачную обработку отозвано до выполнения")
        credentials = gigachat_credentials()
        if not credentials.get("client_id") or not credentials.get("client_secret"):
            raise ValueError("Учётные данные облачного помощника больше не настроены")
        append_action_event(job["project_id"], "action_provider_call_started", actor="system",
                            data={"action_id": job["action_id"], "job_id": job["id"],
                                  "attempt": attempt, "provider": provider,
                                  "input_fingerprint": job["input_fingerprint"],
                                  "cost_ceiling": ceiling})
        candidate_spec = draft_with_gigachat(project["spec"], settings, credentials)
    elif provider == "llama_cpp":
        with LOCAL_MODEL_LOCK:
            candidate_spec = draft_with_llama(project["spec"], settings)
    else:
        candidate_spec = draft_script(project["spec"])
    if is_cancel_requested(job["project_id"], job["id"]):
        raise JobCancelled()
    validate_spec(candidate_spec)
    candidate = {"action_id": job["action_id"], "project_id": job["project_id"],
                 "base_project_revision": project["revision"], "base_spec_hash": digest(project["spec"]),
                 "base_spec": project["spec"], "input_fingerprint": job["input_fingerprint"],
                 "candidate_spec_hash": digest(candidate_spec),
                 "provider": provider, "model": model, "spec": candidate_spec, "created_at": time.time()}
    _publish_candidate(job["project_id"], job["action_id"], action, candidate, provider, model)

def get_candidate(project_id: str, action_id: str) -> dict:
    action = get_action(project_id, action_id)
    if action.get("status") not in ("candidate_ready", "apply_pending"):
        raise ValueError("Кандидат ещё не готов к просмотру")
    path = candidate_path(project_id, action_id)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise ValueError("Файл кандидата отсутствует")
    expected = action.get("candidate", {}).get("sha256")
    if not expected or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Файл кандидата повреждён или изменён")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Файл кандидата содержит некорректный JSON") from exc

def apply_action(project_id: str, action_id: str, body: dict) -> dict:
    with project_lock(project_id):
        action = get_action(project_id, action_id)
        project = load_project(project_id)
        if int(project.get("schema_version", 1)) < 2:
            raise ValueError("Для применения требуется явная миграция проекта на v2; автоматическая миграция не выполняется")
        if action.get("status") == "applied":
            if digest(project["spec"]) == action.get("candidate_spec_hash"):
                return {"project": project, "already_applied": True}
            raise ValueError("Действие уже применено, но принятый сценарий изменился после этого")
        if action.get("status") not in ("candidate_ready", "apply_pending"):
            raise ValueError("Применить можно только готовое предложение после проверки")
        candidate = get_candidate(project_id, action_id)
        if body.get("input_fingerprint") != candidate.get("input_fingerprint"):
            raise ValueError("Подтверждение не совпадает с отпечатком предложения")
        candidate_revision = int(candidate.get("base_project_revision", -1))
        candidate_spec_hash = candidate.get("candidate_spec_hash")
        # Recover the commit point if the project save succeeded but the final journal append did not.
        if action.get("status") == "apply_pending" and digest(project["spec"]) == candidate_spec_hash:
            append_action_event(project_id, "action_applied", actor="user",
                                data={"action_id": action_id, "revision_id": project.get("current_revision_id"),
                                      "project_revision": project["revision"], "candidate_spec_hash": candidate_spec_hash})
            return {"project": project, "already_applied": True}
        if digest(project["spec"]) != candidate.get("base_spec_hash"):
            raise ValueError("Сценарий изменился после подготовки предложения; оно устарело")
        validate_spec(candidate["spec"])
        if digest(project["spec"]) == candidate_spec_hash:
            append_action_event(project_id, "action_apply_requested", actor="user",
                                data={"action_id": action_id, "base_project_revision": candidate_revision,
                                      "candidate_spec_hash": candidate_spec_hash,
                                      "input_fingerprint": candidate["input_fingerprint"], "no_change": True})
            append_action_event(project_id, "action_applied", actor="user",
                                data={"action_id": action_id, "revision_id": project.get("current_revision_id"),
                                      "project_revision": project["revision"], "candidate_spec_hash": candidate_spec_hash,
                                      "no_change": True})
            return {"project": project, "already_applied": False, "no_change": True}
        append_action_event(project_id, "action_apply_requested", actor="user",
                            data={"action_id": action_id, "base_project_revision": candidate_revision,
                                  "candidate_spec_hash": candidate_spec_hash,
                                  "input_fingerprint": candidate["input_fingerprint"]})
        project["spec"] = candidate["spec"]
        project["revision"] = int(project["revision"]) + 1
        project["updated_at"] = time.time()
        project["title"] = str(project["spec"].get("intent", {}).get("theme") or "Новый ролик")[:80]
        save_project(project, action_id=action_id, actor="user", reason="ai_action_applied")
        append_action_event(project_id, "action_applied", actor="user",
                            data={"action_id": action_id, "revision_id": project.get("current_revision_id"),
                                  "project_revision": project["revision"], "candidate_spec_hash": candidate_spec_hash})
        return {"project": project, "already_applied": False}

def reject_action(project_id: str, action_id: str) -> dict:
    with project_lock(project_id):
        action = get_action(project_id, action_id)
        if action.get("status") in ("applied", "rejected", "queued", "running", "confirmed"):
            raise ValueError("Действие уже запущено или завершено; сначала дождитесь отмены задачи")
        if action.get("status") == "apply_pending":
            candidate = get_candidate(project_id, action_id)
            project = load_project(project_id)
            if (int(project["revision"]) != int(candidate.get("base_project_revision", -1)) or
                    digest(project["spec"]) != candidate.get("base_spec_hash")):
                raise ValueError("Применение уже изменило проект; повторите запрос apply для фиксации истории")
        elif action.get("status") not in ("proposed", "candidate_ready", "failed", "cancelled"):
            raise ValueError("Действие нельзя отклонить в текущем состоянии")
        append_action_event(project_id, "action_rejected", actor="user", data={"action_id": action_id})
        return get_action(project_id, action_id)

def retry_action_job(project_id: str, job_id: str, body: dict) -> dict:
    old = get_job(job_id, project_id)
    if old is None:
        raise FileNotFoundError(job_id)
    action = get_action(project_id, old["action_id"])
    if action.get("status") in ("rejected", "applied", "apply_pending"):
        raise ValueError("Отклонённое или применённое действие нельзя повторить")
    project = load_project(project_id)
    if old.get("job_type") == "script_draft":
        _, settings, fingerprint = _validate_action_base(project_id, action)
        if time.time() > float(action.get("quote_expires_at", 0)):
            raise ValueError("Смета устарела; создайте новое предложение перед повтором")
        requires_cloud = bool(action.get("requires_cloud_consent"))
    else:
        payload = old.get("payload", {})
        if (int(project.get("revision", -1)) != int(payload.get("revision", -2)) or
                digest(project.get("spec")) != payload.get("spec_hash")):
            raise ValueError("Проект изменился после неудачной задачи; подготовьте новую смету")
        from .pipeline import stage_input_fingerprint
        fingerprint = stage_input_fingerprint(project, payload["stage"], payload.get("kind"))
        if fingerprint != old.get("input_fingerprint") or fingerprint != action.get("input_fingerprint"):
            raise ValueError("Производственные входы изменились; подготовьте новую смету")
        settings = load_settings()
        requires_cloud = False
    if body.get("input_fingerprint") != fingerprint:
        raise ValueError("Повтор не подтверждён актуальным отпечатком входных данных")
    request = body.get("confirmation")
    if not isinstance(request, dict) or request.get("consent") is not True:
        raise ValueError("Для повтора требуется новое явное подтверждение")
    try:
        amount = float(request.get("cost_ceiling", {}).get("amount"))
    except (AttributeError, TypeError, ValueError):
        raise ValueError("Для повтора укажите предел стоимости")
    currency = str(request.get("cost_ceiling", {}).get("currency", "")).upper()
    if amount < (0.0000001 if requires_cloud else 0) or currency not in ("RUB", "EUR", "USD"):
        raise ValueError("Некорректный предел стоимости")
    if requires_cloud:
        if request.get("cloud_consent") is not True or not settings.get("gigachat_cloud_ack"):
            raise ValueError("Для повтора облачного задания требуется текущее согласие")
        credentials = gigachat_credentials()
        if not credentials.get("client_id") or not credentials.get("client_secret"):
            raise ValueError("Учётные данные облачного помощника больше не настроены")
    elif request.get("privacy_scope") != "local":
        raise ValueError("Для повтора подтвердите локальную обработку")
    approval = {"consent": True, "privacy_scope": "cloud" if requires_cloud else "local",
                "cloud_consent": bool(request.get("cloud_consent", False)),
                "cost_ceiling": {"amount": amount, "currency": currency},
                "input_fingerprint": fingerprint, "confirmed_at": time.time(),
                "expires_at": time.time() + 3600}
    return retry_job(project_id, job_id, input_fingerprint=fingerprint, approval=approval)
