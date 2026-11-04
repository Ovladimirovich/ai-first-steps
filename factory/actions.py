from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .core import project_dir
from .storage import project_lock

_ZERO_HASH = "0" * 64
_SECRET_FRAGMENTS = ("secret", "token", "password", "api_key", "apikey", "authorization", "credential")

def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def _safe(value: Any) -> Any:
    if isinstance(value, str):
        value = re.sub(r"(?i)(authorization|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret|api[_ -]?key|password)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+",
                       r"\1=[redacted]", value)
        value = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~-]+", "Bearer [redacted]", value)
        value = re.sub(r"(?i)\b(?:sk|gc|ghp|gho|xox[baprs])-([A-Za-z0-9_-]{12,})\b", "[redacted]", value)
        return value[:2000]
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()
                if not any(fragment in str(key).lower() for fragment in _SECRET_FRAGMENTS)}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    return value

def action_log_path(project_id: str) -> Path:
    return project_dir(project_id) / "studio" / "actions.jsonl"

@contextmanager
def _journal_file_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
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

def _read_and_verify(path: Path) -> tuple[list[dict], str]:
    if not path.exists():
        return [], _ZERO_HASH
    events: list[dict] = []
    previous = _ZERO_HASH
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError("Не удалось прочитать журнал действий") from exc
    for sequence, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except ValueError as exc:
            raise ValueError(f"Повреждён журнал действий: некорректный JSON в событии {sequence}") from exc
        expected_previous = event.pop("prev_event_hash", None)
        event_hash = event.pop("event_hash", None)
        if event.get("sequence") != len(events) + 1:
            raise ValueError(f"Нарушена последовательность журнала действий в событии {sequence}")
        if expected_previous != previous or not isinstance(event_hash, str):
            raise ValueError(f"Нарушена hash-chain журнала действий в событии {sequence}")
        calculated = hashlib.sha256(_canonical({**event, "prev_event_hash": previous})).hexdigest()
        if calculated != event_hash:
            raise ValueError(f"Нарушена целостность журнала действий в событии {sequence}")
        event["prev_event_hash"] = previous
        event["event_hash"] = event_hash
        events.append(event)
        previous = event_hash
    return events, previous

def verify_action_log(project_id: str) -> dict:
    path = action_log_path(project_id)
    if not path.exists():
        return {"valid": True, "event_count": 0, "latest_event_hash": _ZERO_HASH, "events": []}
    with project_lock(project_id), _journal_file_lock(path):
        events, latest = _read_and_verify(path)
    return {"valid": True, "event_count": len(events), "latest_event_hash": latest, "events": events}

def append_action_event(project_id: str, event_type: str, *, actor: str = "user",
                        data: dict | None = None) -> dict:
    path = action_log_path(project_id)
    with project_lock(project_id), _journal_file_lock(path):
        events, previous = _read_and_verify(path)
        event = {
            "sequence": len(events) + 1,
            "event_id": uuid.uuid4().hex,
            "project_id": str(project_id),
            "event_type": str(event_type),
            "actor": str(actor),
            "created_at": time.time(),
            "data": _safe(data or {}),
            "prev_event_hash": previous,
        }
        event["event_hash"] = hashlib.sha256(_canonical(event)).hexdigest()
        payload = _canonical(event) + b"\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("Не удалось дописать журнал действий")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
        return event

def action_views(project_id: str) -> list[dict]:
    events = verify_action_log(project_id)["events"]
    actions: dict[str, dict] = {}
    for event in events:
        data = event.get("data", {})
        action_id = data.get("action_id")
        if not action_id:
            continue
        item = actions.setdefault(str(action_id), {"action_id": str(action_id), "events": []})
        item["events"].append(event)
        if event["event_type"] == "action_proposed":
            item.update(data)
            item["status"] = "proposed"
        elif event["event_type"] == "action_confirmed":
            item["confirmation"] = data.get("confirmation", {})
            item["status"] = "confirmed"
        elif event["event_type"] in ("job_queued", "job_retry_queued", "job_recovered"):
            item["job_id"] = data.get("job_id", item.get("job_id"))
            item["status"] = "queued"
        elif event["event_type"] == "job_started":
            item["job_id"] = data.get("job_id", item.get("job_id"))
            item["status"] = "running"
        elif event["event_type"] == "job_checkpoint":
            item["checkpoint"] = data.get("checkpoint")
        elif event["event_type"] in ("action_candidate_ready",):
            item["candidate"] = data.get("candidate")
            item["status"] = "candidate_ready"
        elif event["event_type"] == "action_apply_requested":
            item["status"] = "apply_pending"
        elif event["event_type"] == "action_applied":
            item["applied_revision_id"] = data.get("revision_id")
            item["applied_project_revision"] = data.get("project_revision")
            item["candidate_spec_hash"] = data.get("candidate_spec_hash")
            item["status"] = "applied"
        elif event["event_type"] == "action_rejected":
            item["status"] = "rejected"
        elif event["event_type"] == "job_completed":
            item["job_id"] = data.get("job_id", item.get("job_id"))
            if item.get("kind") != "script-draft" or item.get("status") != "candidate_ready":
                item["status"] = "completed"
        elif event["event_type"] == "job_failed":
            item["job_id"] = data.get("job_id", item.get("job_id"))
            item["status"] = "failed"
            item["error"] = data.get("error")
        elif event["event_type"] == "job_cancelled":
            item["job_id"] = data.get("job_id", item.get("job_id"))
            item["status"] = "cancelled"
    return sorted(actions.values(), key=lambda item: item["events"][0]["sequence"])

def get_action(project_id: str, action_id: str) -> dict:
    action = next((item for item in action_views(project_id) if item["action_id"] == str(action_id)), None)
    if action is None:
        raise FileNotFoundError(action_id)
    return action
