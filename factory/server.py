from __future__ import annotations

import base64
import io
import json
import mimetypes
import re
import threading
import time
import uuid
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import (ROOT, artifact_state, create_project, get_project_revision, get_studio_document,
                   list_projects, load_project, project_dir, project_revisions, restore_project_revision,
                   save_project, validate_spec)
from .drafts import commit_project_draft, get_project_draft, save_project_draft
from .migrations import apply_v1_migration, migration_plan
from .pipeline import get_job, plan, run
from .providers import ProviderError, draft_with_gigachat, draft_with_llama, test_connection, test_gigachat_connection
from .settings import gigachat_credentials, load_settings, save_settings

WEB = Path(__file__).resolve().parent / "web"
TEXT_PROVIDER_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "AIVideoFactory/0.1"

    def log_message(self, fmt, *args):
        message = fmt % args
        if "/jobs?" not in message:
            print("[factory] " + message)

    def _json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _file(self, path: Path):
        if not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            # Клиент мог закрыть видеоплеер или перейти на другой шаг.
            pass

    def _body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size > 5_000_000:
            raise ValueError("Слишком большой запрос")
        return json.loads(self.rfile.read(size) or b"{}")

    def _error(self, error, status=400):
        self._json(status, {"error": str(error)})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        if path == "/" or path == "/index.html":
            return self._file(WEB / "index.html")
        if path.startswith("/static/"):
            candidate = (WEB / path.removeprefix("/static/")).resolve()
            if WEB.resolve() not in candidate.parents:
                return self.send_error(404)
            return self._file(candidate)
        if path.startswith("/media/"):
            bits = path.split("/")
            if len(bits) < 4:
                return self.send_error(404)
            candidate = (project_dir(bits[2]) / Path(*bits[3:])).resolve()
            base = project_dir(bits[2]).resolve()
            if base not in candidate.parents:
                return self.send_error(404)
            return self._file(candidate)
        if path == "/api/settings":
            return self._json(200, load_settings())
        if path == "/api/projects":
            return self._json(200, {"projects": list_projects()})
        if path.startswith("/api/projects/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "studio":
                try:
                    return self._json(200, get_studio_document(parts[2]))
                except FileNotFoundError:
                    return self._error("Ролик не найден", 404)
                except ValueError as exc:
                    return self._error(exc, 409)
            if len(parts) == 5 and parts[3] == "drafts":
                try:
                    return self._json(200, get_project_draft(parts[2], parts[4]))
                except FileNotFoundError:
                    return self._error("Черновик не найден", 404)
                except ValueError as exc:
                    return self._error(exc, 409)
            if len(parts) == 4 and parts[3] == "revisions":
                try:
                    return self._json(200, {"revisions": project_revisions(parts[2])})
                except FileNotFoundError:
                    return self._error("Ролик не найден", 404)
            if len(parts) == 5 and parts[3] == "revisions":
                try:
                    return self._json(200, get_project_revision(parts[2], parts[4]))
                except FileNotFoundError:
                    return self._error("Ревизия или ролик не найдены", 404)
                except ValueError as exc:
                    return self._error(exc, 409)
            if len(parts) == 5 and parts[3:] == ["migration", "plan"]:
                try:
                    return self._json(200, migration_plan(parts[2]))
                except FileNotFoundError:
                    return self._error("Ролик не найден", 404)
                except (ValueError, json.JSONDecodeError) as exc:
                    return self._error(exc, 409)
            if len(parts) == 4 and parts[3] == "status":
                project_id = parts[2]
                try:
                    p = load_project(project_id)
                    job_id = urllib.parse.parse_qs(parsed.query).get("job", [""])[0]
                    job = get_job(job_id) if job_id else None
                    return self._json(200, {"artifacts": artifact_state(p), "job": job})
                except FileNotFoundError:
                    return self._error("Ролик не найден", 404)
            if len(parts) == 4 and parts[3] == "artifacts":
                try:
                    return self._json(200, artifact_state(load_project(parts[2])))
                except FileNotFoundError:
                    return self._error("Ролик не найден", 404)
            if len(parts) == 4 and parts[3] == "jobs":
                job_id = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
                job = get_job(job_id)
                return self._json(200, job or {"state": "missing"})
            if len(parts) == 3:
                try:
                    return self._json(200, load_project(parts[2]))
                except FileNotFoundError:
                    return self._error("Ролик не найден", 404)
        return self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)
        try:
            body = self._body()
            if path == "/api/projects":
                project = create_project(body)
                return self._json(201, project)
            if len(parts := path.strip("/").split("/")) == 5 and parts[:2] == ["api", "projects"] and parts[3:] == ["migration", "apply"]:
                result = apply_v1_migration(parts[2], int(body.get("expected_revision", 0)),
                                            str(body.get("source_fingerprint", "")))
                return self._json(200, result)
            if len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "revisions" and parts[5] == "restore":
                project = restore_project_revision(parts[2], parts[4], int(body.get("expected_revision", -1)))
                return self._json(200, project)
            if len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "drafts" and parts[5] == "commit":
                result = commit_project_draft(parts[2], parts[4], body)
                return self._json(200, result)
            if path == "/api/settings/test":
                settings = load_settings()
                if settings["text_provider"] == "gigachat":
                    return self._json(200, test_gigachat_connection(gigachat_credentials()))
                if settings["text_provider"] == "llama_cpp":
                    return self._json(200, test_connection(settings))
                return self._error("Сначала выберите помощника в настройках.")
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3:] == ["frames", "upload"]:
                project = load_project(parts[2])
                scene_id = str(body.get("scene_id", ""))
                scene = next((s for s in project["spec"].get("script", {}).get("scenes", []) if s.get("id") == scene_id), None)
                if not scene:
                    return self._error("Сцена не найдена")
                data_url = str(body.get("data_url", ""))
                match = re.fullmatch(r"data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", data_url)
                if not match:
                    return self._error("Выберите изображение PNG, JPG или WebP")
                try:
                    image_bytes = base64.b64decode(match.group(1), validate=True)
                    if len(image_bytes) > 3_500_000:
                        return self._error("Изображение слишком большое (максимум 3,5 МБ)")
                    from PIL import Image, ImageOps
                    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                    image = ImageOps.fit(image, (1920, 1080), method=Image.Resampling.LANCZOS)
                except Exception as exc:
                    return self._error(f"Не удалось прочитать картинку: {exc}")
                safe_scene = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(scene_id).name)
                relative = Path("scene-backgrounds") / f"{safe_scene}-{uuid.uuid4().hex[:10]}.jpg"
                target = project_dir(project["id"]) / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                image.save(target, "JPEG", quality=90, optimize=True)
                image.save(target.parent / f"{safe_scene}.jpg", "JPEG", quality=90, optimize=True)
                scene["image"] = {"mode": "upload", "path": relative.as_posix()}
                project["revision"] += 1
                project["updated_at"] = time.time()
                save_project(project)
                return self._json(200, project)
            if len(parts) == 4 and parts[:2] == ["api", "projects"]:
                project = load_project(parts[2])
                action = parts[3]
                if action == "script-draft":
                    spec = project["spec"]
                    if not spec.get("intent", {}).get("theme", "").strip():
                        return self._error("Введите тему ролика")
                    with TEXT_PROVIDER_LOCK:
                        settings = load_settings()
                        if settings["text_provider"] == "llama_cpp":
                            project["spec"] = draft_with_llama(spec, settings)
                        elif settings["text_provider"] == "gigachat":
                            if not settings.get("gigachat_cloud_ack"):
                                return self._error("Подтвердите в настройках, что сценарий отправляется в облачный GigaChat.")
                            project["spec"] = draft_with_gigachat(spec, settings, gigachat_credentials())
                        else:
                            from .core import draft_script
                            project["spec"] = draft_script(spec)
                    validate_spec(project["spec"])
                    project["revision"] += 1
                    project["updated_at"] = time.time()
                    save_project(project)
                    return self._json(200, project)
                if action in ("voice-plan", "frames-plan", "render-plan"):
                    stage = action.removesuffix("-plan").replace("-", "_")
                    if stage == "render":
                        validate_spec(project["spec"])
                    result = plan(project, stage, body.get("kind"))
                    return self._json(200, result)
                if action in ("voice-run", "frames-run", "render-run"):
                    stage = action.removesuffix("-run").replace("-", "_")
                    job = run(project, str(body.get("plan_id", "")), stage, body.get("kind"))
                    return self._json(202, job)
            return self.send_error(404)
        except FileNotFoundError:
            return self._error("Ролик не найден", 404)
        except ProviderError as exc:
            return self._error(exc, 400)
        except ValueError as exc:
            return self._error(exc, 409 if "устар" in str(exc).lower() or "изменил" in str(exc).lower() else 400)
        except Exception as exc:
            return self._error(exc, 500)

    def do_PUT(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        parts = path.strip("/").split("/")
        if len(parts) != 5 or parts[:2] != ["api", "projects"] or parts[3] != "drafts":
            return self.send_error(404)
        try:
            draft = save_project_draft(parts[2], parts[4], self._body())
            return self._json(200, draft)
        except FileNotFoundError:
            return self._error("Ролик не найден", 404)
        except ValueError as exc:
            return self._error(exc, 409)

    def do_PATCH(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if path == "/api/settings":
            try:
                return self._json(200, save_settings(self._body()))
            except (ValueError, TypeError) as exc:
                return self._error(exc)
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[:2] != ["api", "projects"]:
            return self.send_error(404)
        try:
            body = self._body()
            project = load_project(parts[2])
            if body.get("revision") != project["revision"]:
                return self._error("Ролик изменён в другой вкладке. Обновите страницу.", 409)
            spec = body.get("spec")
            validate_spec(spec) if spec.get("script", {}).get("scenes") else None
            project["spec"] = spec
            project["revision"] += 1
            project["updated_at"] = time.time()
            project["title"] = (spec.get("intent", {}).get("theme") or "Новый ролик")[:80]
            project["current_step"] = int(body.get("current_step", project.get("current_step", 0)))
            save_project(project)
            return self._json(200, project)
        except FileNotFoundError:
            return self._error("Ролик не найден", 404)
        except (ValueError, TypeError) as exc:
            return self._error(exc)


def serve(host="0.0.0.0", port=7860):
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"AI Video Factory открыта: http://localhost:{port} (слушает {host}:{port})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстанавливаю приложение…")
    finally:
        server.server_close()
