from __future__ import annotations

import json
import os
import queue
import traceback
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from . import core
from .actions import _safe, append_action_event, verify_action_log
from .storage import atomic_write_json, project_lock

VALID_STATES = {"queued", "running", "completed", "failed", "cancelled"}
class JobCancelled(Exception):
    pass

_QUEUE: queue.Queue[tuple[str, str]] = queue.Queue()
_GUARD = threading.RLock()
_WORKER: threading.Thread | None = None
_EXECUTOR: Callable[[dict], None] | None = None
_ENQUEUED: set[tuple[str, str]] = set()

@contextmanager
def _interprocess_worker_lock():
    """A filesystem lock keeps separate app processes from running workers concurrently."""
    lock_path = core.DATA_ROOT.parent / ".factory-worker.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    if os.fstat(descriptor).st_size == 0:
        os.write(descriptor, b"\0")
    try:
        try:
            import fcntl
        except ImportError:
            fcntl = None
        if fcntl is not None:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        else:
            import msvcrt
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(descriptor)


@contextmanager
def _submission_lock(project_id: str):
    lock_path = core.project_dir(project_id) / "studio" / "jobs" / ".submission.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    if os.fstat(descriptor).st_size == 0:
        os.write(descriptor, b"\0")
    try:
        try:
            import fcntl
        except ImportError:
            fcntl = None
        if fcntl is not None:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        else:
            import msvcrt
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(descriptor)


def _jobs_dir(project_id: str) -> Path:
    return core.project_dir(project_id) / "studio" / "jobs"

def _job_path(project_id: str, job_id: str) -> Path:
    if not str(job_id).isalnum():
        raise FileNotFoundError(job_id)
    return _jobs_dir(project_id) / f"{job_id}.json"

def _read_job(project_id: str, job_id: str) -> dict:
    path = _job_path(project_id, job_id)
    # Serialize same-process readers with atomic job replacement, and tolerate brief
    # Windows file-sharing/antivirus locks while the worker replaces the JSON file.
    with project_lock(project_id):
        for attempt in range(5):
            try:
                raw = path.read_text(encoding="utf-8")
                break
            except FileNotFoundError:
                raise
            except PermissionError as exc:
                if attempt == 4:
                    raise ValueError("Файл задачи временно недоступен для чтения") from exc
                time.sleep(0.025 * (attempt + 1))
            except OSError as exc:
                raise ValueError("Не удалось прочитать файл задачи") from exc
        try:
            value = json.loads(raw)
        except ValueError as exc:
            raise ValueError("Запись задачи повреждена") from exc
    if (not isinstance(value, dict) or value.get("id") != str(job_id) or
            value.get("project_id") != str(project_id) or value.get("state") not in VALID_STATES):
        raise ValueError("Некорректная запись задачи")
    return value

def _write(job: dict) -> None:
    atomic_write_json(_job_path(job["project_id"], job["id"]), job)

def _enqueue(project_id: str, job_id: str) -> None:
    key = (str(project_id), str(job_id))
    with _GUARD:
        if key in _ENQUEUED:
            return
        _ENQUEUED.add(key)
        _QUEUE.put(key)
        _ensure_worker_locked()

def set_executor(executor: Callable[[dict], None]) -> None:
    global _EXECUTOR
    with _GUARD:
        _EXECUTOR = executor

def _ensure_worker_locked() -> None:
    global _WORKER
    if _WORKER is None or not _WORKER.is_alive():
        _WORKER = threading.Thread(target=_worker_loop, name="factory-single-worker", daemon=True)
        _WORKER.start()

def _validate_approval(approval: dict | None, input_fingerprint: str) -> dict:
    if not isinstance(approval, dict) or approval.get("consent") is not True:
        raise ValueError("Для очереди требуется явное подтверждение согласия")
    if approval.get("input_fingerprint") != str(input_fingerprint):
        raise ValueError("Подтверждение не совпадает с отпечатком задачи")
    try:
        ceiling = approval.get("cost_ceiling") or {}
        amount = float(ceiling.get("amount"))
        expires_at = float(approval.get("expires_at", 0))
    except (AttributeError, TypeError, ValueError):
        raise ValueError("Для очереди требуется действующий предел стоимости")
    currency = str(ceiling.get("currency", "")).upper()
    scope = approval.get("privacy_scope")
    if amount < 0 or currency not in ("RUB", "EUR", "USD") or expires_at <= time.time():
        raise ValueError("Предел стоимости или срок подтверждения недействителен")
    if scope == "cloud":
        if amount <= 0 or approval.get("cloud_consent") is not True:
            raise ValueError("Облачная задача требует положительного лимита и отдельного согласия")
    elif scope == "cloud_free":
        if approval.get("cloud_consent") is not True:
            raise ValueError("Облачная задача бесплатной квоты требует отдельного облачного согласия")
        if amount != 0:
            raise ValueError("Профиль бесплатной квоты (нет платного fallback) разрешает только нулевой предел стоимости")
    elif scope != "local":
        raise ValueError("Укажите локальный или облачный scope согласия")
    return approval

def _approval_is_journaled(job: dict, events: list[dict] | None = None) -> bool:
    events = events if events is not None else verify_action_log(job["project_id"])["events"]
    latest = None
    latest_job_id = None
    for event in events:
        data = event.get("data", {})
        if event.get("event_type") == "action_confirmed" and data.get("action_id") == job.get("action_id"):
            latest = data.get("confirmation")
            latest_job_id = data.get("job_id")
    return latest == job.get("approval") and latest_job_id == job.get("id")


def create_job(project_id: str, *, action_id: str, job_type: str, payload: dict,
               input_fingerprint: str, stage: str | None = None, kind: str | None = None,
               approval: dict | None = None) -> dict:
    approval = _validate_approval(approval, input_fingerprint)
    with _GUARD:
        if _EXECUTOR is None:
            raise RuntimeError("Обработчик очереди ещё не зарегистрирован")
    with _submission_lock(project_id):
        for existing in list_jobs(project_id):
            if existing.get("action_id") == str(action_id):
                if (existing.get("input_fingerprint") != str(input_fingerprint) or
                        existing.get("job_type") != str(job_type)):
                    raise ValueError("Для этого действия уже существует задача с другим входным отпечатком")
                if existing.get("approval") != approval:
                    raise ValueError("Для действия уже сохранено другое подтверждение; используйте retry")
                if existing.get("state") == "queued":
                    _enqueue(project_id, existing["id"])
                return existing
        job_id = uuid.uuid4().hex
        now = time.time()
        job = {"id": job_id, "project_id": str(project_id), "action_id": str(action_id),
               "job_type": str(job_type), "stage": stage, "kind": kind, "payload": payload,
               "input_fingerprint": str(input_fingerprint), "state": "queued", "progress": 0,
               "message": "В очереди", "log": ["В очереди"], "checkpoint": None,
               "cancel_requested": False, "retry_count": 0, "recovery_count": 0, "created_at": now,
               "started_at": None, "updated_at": now, "finished_at": None,
               "error": None, "approval": approval}
        with project_lock(project_id):
            append_action_event(project_id, "action_confirmed", actor="user",
                                data={"action_id": action_id, "job_id": job_id, "confirmation": approval})
            _write(job)
            append_action_event(project_id, "job_queued", actor="system",
                                data={"action_id": action_id, "job_id": job_id, "state": "queued"})
        _enqueue(project_id, job_id)
        return job


def persist_job(job: dict) -> dict:
    with project_lock(job["project_id"]):
        current = _read_job(job["project_id"], job["id"])
        if current["state"] in ("completed", "failed", "cancelled"):
            return current
        if current.get("cancel_requested"):
            job["cancel_requested"] = True
        job["updated_at"] = time.time()
        _write(job)
        return job

def ensure_job_enqueued(project_id: str, job_id: str) -> dict | None:
    try:
        job = _read_job(project_id, job_id)
    except FileNotFoundError:
        return None
    if job.get("state") == "queued":
        events = verify_action_log(project_id)["events"]
        if not _approval_is_journaled(job, events):
            raise ValueError("Задача не подтверждена целостным актуальным событием журнала")
        _enqueue(project_id, job_id)
    return job


def get_job(job_id: str, project_id: str | None = None) -> dict | None:
    if project_id is not None:
        try:
            return _read_job(project_id, job_id)
        except FileNotFoundError:
            return None
    # Compatibility lookup for the legacy status endpoint.
    root = core.DATA_ROOT
    if root.exists():
        for path in root.glob(f"*/studio/jobs/{job_id}.json"):
            try:
                return _read_job(path.parents[2].name, job_id)
            except (FileNotFoundError, ValueError):
                continue
    return None

def list_jobs(project_id: str) -> list[dict]:
    directory = _jobs_dir(project_id)
    if not directory.exists():
        return []
    values = []
    for path in directory.glob("*.json"):
        try:
            values.append(_read_job(project_id, path.stem))
        except (FileNotFoundError, ValueError):
            continue
    return sorted(values, key=lambda item: item.get("created_at", 0), reverse=True)

def is_cancel_requested(project_id: str, job_id: str) -> bool:
    try:
        return bool(_read_job(project_id, job_id).get("cancel_requested"))
    except (FileNotFoundError, ValueError):
        return True

def cancel_job(project_id: str, job_id: str) -> dict:
    with project_lock(project_id):
        job = _read_job(project_id, job_id)
        if job["state"] in ("completed", "failed", "cancelled"):
            return job
        if job["state"] == "queued":
            job.update(state="cancelled", cancel_requested=True, finished_at=time.time(), updated_at=time.time(),
                       message="Отменено до запуска")
            _write(job)
            append_action_event(project_id, "job_cancelled", actor="user",
                                data={"action_id": job["action_id"], "job_id": job_id, "state": "cancelled"})
        else:
            job.update(cancel_requested=True, updated_at=time.time(), message="Запрошена отмена")
            _write(job)
            append_action_event(project_id, "job_cancel_requested", actor="user",
                                data={"action_id": job["action_id"], "job_id": job_id})
        return job

def retry_job(project_id: str, job_id: str, *, input_fingerprint: str,
              approval: dict | None = None) -> dict:
    with _submission_lock(project_id):
        with project_lock(project_id):
            job = _read_job(project_id, job_id)
            if job["state"] not in ("failed", "cancelled"):
                raise ValueError("Повторить можно только завершившуюся ошибкой или отменённую задачу")
            if str(input_fingerprint) != job.get("input_fingerprint"):
                raise ValueError("Входные данные изменились; требуется новая смета и подтверждение")
            fresh_approval = _validate_approval(approval, input_fingerprint)
            append_action_event(project_id, "action_confirmed", actor="user",
                                data={"action_id": job["action_id"], "job_id": job_id, "confirmation": fresh_approval})
            job["approval"] = fresh_approval
            job.update(state="queued", progress=0, message="Повтор поставлен в очередь", cancel_requested=False,
                       finished_at=None, started_at=None, error=None, retry_count=int(job.get("retry_count", 0)) + 1,
                       updated_at=time.time())
            job["log"] = (job.get("log", []) + [job["message"]])[-40:]
            _write(job)
            append_action_event(project_id, "job_retry_queued", actor="user",
                                data={"action_id": job["action_id"], "job_id": job_id,
                                      "retry_count": job["retry_count"], "state": "queued"})
        _enqueue(project_id, job_id)
        return job


def checkpoint(job: dict, value: dict) -> None:
    append_action_event(job["project_id"], "job_checkpoint", actor="system",
                        data={"action_id": job["action_id"], "job_id": job["id"], "checkpoint": value})
    job["checkpoint"] = value
    persist_job(job)

def _finish(job: dict, state: str, error: str | None = None) -> None:
    now = time.time()
    safe_error = _safe(str(error)) if error is not None else None
    job.update(state=state, updated_at=now, finished_at=now, error=safe_error)
    if state == "completed":
        job.update(progress=100, message="Готово")
    elif state == "failed":
        job["message"] = "Задача завершилась ошибкой"
    elif state == "cancelled":
        job["message"] = "Задача отменена"
    _write(job)
    event = {"completed": "job_completed", "failed": "job_failed", "cancelled": "job_cancelled"}[state]
    data = {"action_id": job["action_id"], "job_id": job["id"], "state": state}
    if error:
        data["error"] = error[:500]
    append_action_event(job["project_id"], event, actor="system", data=data)

def _failed_closed(project_id: str, job_id: str, error: str) -> None:
    """Persist a terminal local state if the action journal itself has become unverifiable."""
    try:
        latest = _read_job(project_id, job_id)
        latest.update(state="failed", finished_at=time.time(), updated_at=time.time(),
                      error=_safe(error), message="Задача остановлена: журнал действий не подтверждён")
        _write(latest)
    except (OSError, ValueError, FileNotFoundError):
        pass

def _worker_loop() -> None:
    while True:
        project_id, job_id = _QUEUE.get()
        try:
            with _GUARD:
                _ENQUEUED.discard((project_id, job_id))
                executor = _EXECUTOR
            if executor is None:
                continue
            with _interprocess_worker_lock():
                try:
                    with project_lock(project_id):
                        job = _read_job(project_id, job_id)
                        if job["state"] != "queued":
                            continue
                        if not _approval_is_journaled(job):
                            raise ValueError("Задача не имеет актуального подтверждения в журнале действий")
                        job.update(state="running", started_at=time.time(), updated_at=time.time(), message="Выполняется")
                        _write(job)
                        append_action_event(project_id, "job_started", actor="system",
                                            data={"action_id": job["action_id"], "job_id": job_id, "state": "running"})
                    executor(job)
                    with project_lock(project_id):
                        latest = _read_job(project_id, job_id)
                        if latest.get("cancel_requested"):
                            _finish(latest, "cancelled")
                        else:
                            _finish(latest, "completed")
                except JobCancelled:
                    try:
                        with project_lock(project_id):
                            _finish(_read_job(project_id, job_id), "cancelled")
                    except Exception as exc:
                        tb = traceback.format_exc()
                        error_msg = f"{str(exc)}\nTRACEBACK:\n{tb}"
                        print(f"\n[JOB CANCEL ERROR] project={project_id} job={job_id} error={error_msg}")
                        _failed_closed(project_id, job_id, error_msg)
                except Exception as exc:
                    tb = traceback.format_exc()
                    error_msg = f"{str(exc)}\nTRACEBACK:\n{tb}"
                    print(f"\n[JOB ERROR] project={project_id} job={job_id} error={error_msg}")
                    try:
                        with project_lock(project_id):
                            _finish(_read_job(project_id, job_id), "failed", error_msg)
                    except Exception as journal_error:
                        tb = traceback.format_exc()
                        error_msg = f"{str(journal_error)}\nTRACEBACK:\n{tb}"
                        print(f"\n[JOB JOURNAL ERROR] project={project_id} job={job_id} error={error_msg}")
                        _failed_closed(project_id, job_id, error_msg)
        finally:
            _QUEUE.task_done()

def recover_jobs() -> dict:
    """Requeue durable queued work and resume interrupted jobs from idempotent checkpoints."""
    recovered = {"queued": 0, "interrupted": 0}
    root = core.DATA_ROOT
    if not root.exists():
        return recovered
    with _interprocess_worker_lock():
        for project_path in root.iterdir():
            jobs_path = project_path / "studio" / "jobs"
            if not jobs_path.is_dir():
                continue
            project_id = project_path.name
            try:
                journal_events = verify_action_log(project_id)["events"]
            except ValueError:
                # Do not execute or mutate work when its authorization journal is unverifiable.
                continue
            journal_checkpoints = {}
            for event in journal_events:
                data = event.get("data", {})
                if event.get("event_type") == "job_checkpoint" and data.get("job_id"):
                    journal_checkpoints[str(data["job_id"])] = data.get("checkpoint")
            for path in jobs_path.glob("*.json"):
                try:
                    job = _read_job(project_id, path.stem)
                except (OSError, ValueError, FileNotFoundError):
                    continue
                if journal_checkpoints.get(job["id"]):
                    job["checkpoint"] = journal_checkpoints[job["id"]]
                    _write(job)
                if job.get("state") in ("queued", "running") and not _approval_is_journaled(job, journal_events):
                    continue
                if job.get("state") == "queued":
                    _enqueue(project_id, job["id"])
                    recovered["queued"] += 1
                elif job.get("state") == "running":
                    with project_lock(project_id):
                        job = _read_job(project_id, job["id"])
                        if job.get("state") != "running":
                            continue
                        job.update(state="queued", started_at=None, finished_at=None, cancel_requested=False,
                                   recovery_count=int(job.get("recovery_count", 0)) + 1,
                                   updated_at=time.time(), message="Возобновление после перезапуска сервера")
                        job["log"] = (job.get("log", []) + [job["message"]])[-40:]
                        _write(job)
                        append_action_event(project_id, "job_recovered", actor="system",
                                            data={"action_id": job["action_id"], "job_id": job["id"],
                                                  "state": "queued", "checkpoint": job.get("checkpoint")})
                    _enqueue(project_id, job["id"])
                    recovered["interrupted"] += 1
        return recovered
