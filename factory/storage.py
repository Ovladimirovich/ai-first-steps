import json
import os
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def atomic_write_json(path: Path, value: Any) -> None:
    """Write one JSON file. Try atomic temp + os.replace everywhere;
    on Windows, fall back to direct write only on PermissionError (locked file).
    Temp file is cleaned up in both cases."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except PermissionError as exc:
        if sys.platform == "win32":
            # os.replace / rename fails with PermissionError when the target
            # file is locked (antivirus, indexer, or another reader).
            # Fall back to direct write — good enough for single-process factory.
            try:
                path.write_text(payload, encoding="utf-8", newline="\n")
            except Exception:
                # ensure temp is removed even if direct write also fails
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
                raise
        else:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        if default is not None:
            return default
        raise


@contextmanager
def project_lock(project_id: str) -> Iterator[None]:
    key = str(project_id)
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(key, threading.RLock())
    with lock:
        yield
