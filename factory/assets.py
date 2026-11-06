from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import time
from pathlib import Path

from .core import _read_asset_manifest, project_dir
from .storage import atomic_write_json, project_lock


def _asset_version(manifest: dict, asset_type: str, target: dict) -> int:
    matches = [int(item.get("asset_version", 0)) for item in manifest.get("assets", [])
               if item.get("type") == asset_type and item.get("target", {}) == target]
    return max(matches, default=0) + 1


def _append_record(project_id: str, *, asset_type: str, target: dict, relative: Path,
                   sha256: str, size_bytes: int, mime: str, source: str,
                   provenance: str, input_fingerprint: str | None,
                   metadata: dict | None = None) -> dict:
    root = project_dir(project_id)
    manifest = _read_asset_manifest(root)
    version = _asset_version(manifest, asset_type, target)
    asset_id = "asset-" + hashlib.sha256(
        f"{asset_type}|{target}|{sha256}|{version}".encode("utf-8")).hexdigest()[:24]
    record = {
        "asset_id": asset_id,
        "type": asset_type,
        "target": target,
        "sequence": version,
        "asset_version": version,
        **({"render_version": version} if asset_type in ("preview", "final_render") else {}),
        "path": relative.as_posix(),
        "sha256": sha256,
        "mime": mime or mimetypes.guess_type(relative.name)[0] or "application/octet-stream",
        "size_bytes": int(size_bytes),
        "source": source,
        "provenance": provenance,
        "input_fingerprint": input_fingerprint,
        "created_at": time.time(),
    }
    allowed_metadata = {"prompt", "model", "parameters", "action_id", "created_by", "prompt_template_version"}
    for key, value in (metadata or {}).items():
        if key not in allowed_metadata:
            raise ValueError(f"Недопустимое provenance-поле ассета: {key}")
        record[key] = value
    manifest.setdefault("assets", []).append(record)
    atomic_write_json(root / "studio" / "assets.json", manifest)
    return record


def _blob_path(project_id: str, sha256: str, extension: str) -> tuple[Path, Path]:
    root = project_dir(project_id)
    relative = Path("assets") / "sha256" / sha256[:2] / f"{sha256}{extension.lower()}"
    return root / relative, relative


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _create_immutable_blob(data: bytes | None, source_path: Path | None,
                           blob: Path, expected_hash: str) -> None:
    blob.parent.mkdir(parents=True, exist_ok=True)
    if blob.exists():
        actual, _ = _hash_file(blob)
        if actual != expected_hash:
            raise ValueError("Обнаружено повреждение content-addressed ассета")
        return
    try:
        descriptor = os.open(blob, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        actual, _ = _hash_file(blob)
        if actual != expected_hash:
            raise ValueError("Обнаружено повреждение content-addressed ассета")
        return
    try:
        with os.fdopen(descriptor, "wb") as destination:
            if data is not None:
                destination.write(data)
            elif source_path is not None:
                with source_path.open("rb") as source:
                    shutil.copyfileobj(source, destination, 1024 * 1024)
            destination.flush()
            os.fsync(destination.fileno())
    except Exception:
        try:
            blob.unlink()
        except OSError:
            pass
        raise
    actual, _ = _hash_file(blob)
    if actual != expected_hash:
        blob.unlink(missing_ok=True)
        raise ValueError("Не удалось проверить записанный content-addressed ассет")


def register_asset_bytes(project_id: str, data: bytes, *, asset_type: str,
                         target: dict, extension: str, mime: str,
                         source: str = "uploaded", provenance: str = "user_upload",
                         input_fingerprint: str | None = None,
                         metadata: dict | None = None) -> dict:
    """Persist a content-addressed immutable blob and append its manifest record."""
    if not data:
        raise ValueError("Нельзя зарегистрировать пустой ассет")
    if not extension.startswith(".") or any(char not in ".abcdefghijklmnopqrstuvwxyz0123456789" for char in extension.lower()):
        raise ValueError("Некорректное расширение ассета")
    digest = hashlib.sha256(data).hexdigest()
    root = project_dir(project_id)
    blob, relative = _blob_path(project_id, digest, extension)
    with project_lock(project_id):
        _create_immutable_blob(data, None, blob, digest)
        return _append_record(project_id, asset_type=asset_type, target=target, relative=relative,
                              sha256=digest, size_bytes=len(data), mime=mime, source=source,
                              provenance=provenance, input_fingerprint=input_fingerprint,
                              metadata=metadata)


def register_asset_file(project_id: str, source_path: Path, *, asset_type: str,
                        target: dict, extension: str | None = None,
                        mime: str | None = None, source: str = "factory",
                        provenance: str = "generated", input_fingerprint: str | None = None) -> dict:
    """Copy a generated file to immutable content-addressed storage and append its record."""
    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    digest, size = _hash_file(source_path)
    suffix = extension or source_path.suffix or ".bin"
    if not suffix.startswith(".") or any(char not in ".abcdefghijklmnopqrstuvwxyz0123456789" for char in suffix.lower()):
        raise ValueError("Некорректное расширение ассета")
    root = project_dir(project_id)
    blob, relative = _blob_path(project_id, digest, suffix)
    with project_lock(project_id):
        _create_immutable_blob(None, source_path, blob, digest)
        return _append_record(project_id, asset_type=asset_type, target=target, relative=relative,
                              sha256=digest, size_bytes=size,
                              mime=mime or mimetypes.guess_type(blob.name)[0] or "application/octet-stream",
                              source=source, provenance=provenance, input_fingerprint=input_fingerprint)
