from __future__ import annotations

import base64
import io
import json
import mimetypes
import re
import time
import uuid
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import (ROOT, artifact_state, create_project, get_project_revision, get_studio_document,
                   list_projects, load_project, project_dir, project_revisions, restore_project_revision,
                   save_project, validate_spec)
from .assets import register_asset_bytes
from .drafts import commit_project_draft, get_project_draft, save_project_draft
from .migrations import apply_v1_migration, migration_plan
from .pipeline import get_job, plan, run
from .actions import action_views, get_action, verify_action_log
from .action_service import (apply_action, confirm_action, get_candidate, propose_script_draft,
                             reject_action, retry_action_job)
from .jobs import cancel_job, list_jobs, recover_jobs
from .providers import ProviderError, test_connection, check_gigachat_connection
from .settings import SETTINGS_PATH, gigachat_credentials, load_settings, save_settings
from .voice import check_piper_settings
from .visuals import (create_visual_variant, deselect_visual_variant, list_visual_variants,
                      reject_visual_variant, review_visual_variant, select_visual_variant,
                      update_visual_prompt)

WEB = Path(__file__).resolve().parent / "web"

def _legacy_job_state(job):
    if not job:
        return job
    mapped = dict(job)
    mapped["state"] = {"completed": "done", "failed": "error", "cancelled": "error"}.get(job.get("state"), job.get("state"))
    return mapped

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
        if path.startswith("/api/settings/voice/samples/"):
            sample = path.removeprefix("/api/settings/voice/samples/")
            if sample not in ("h1.wav", "h2.wav"):
                return self.send_error(404)
            sample_dir = (SETTINGS_PATH.parent / "voice-tests").resolve()
            candidate = (sample_dir / sample).resolve()
            if sample_dir not in candidate.parents:
                return self.send_error(404)
            return self._file(candidate)
        if path == "/api/settings":
            return self._json(200, load_settings())
        if path == "/api/projects":
            return self._json(200, {"projects": list_projects()})
        if path.startswith("/api/projects/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[3] == "visual-variants":
                try:
                    scene_id = urllib.parse.parse_qs(parsed.query).get("scene_id", [None])[0]
                    return self._json(200, list_visual_variants(parts[2], scene_id))
                except FileNotFoundError:
                    return self._error("Ролик или визуальный вариант не найден", 404)
                except ValueError as exc:
                    return self._error(exc, 409)
            if len(parts) == 4 and parts[3] == "studio":
                try:
                    return self._json(200, get_studio_document(parts[2]))
                except FileNotFoundError:
                    return self._error("Ролик не найден", 404)
                except ValueError as exc:
                    return self._error(exc, 409)
            if len(parts) == 4 and parts[3] == "fingerprints":
                try:
                    state = artifact_state(load_project(parts[2]), force_asset_hash=True)
                    return self._json(200, {"fingerprint_version": state["fingerprint_version"],
                                            "fingerprints": state["fingerprints"],
                                            "artifact_details": state["artifact_details"],
                                            "stale_reasons": state["stale_reasons"]})
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
                    job = get_job(job_id, project_id) if job_id else None
                    return self._json(200, {"artifacts": artifact_state(p), "job": _legacy_job_state(job)})
                except FileNotFoundError:
                    return self._error("Ролик не найден", 404)
                except ValueError as exc:
                    return self._error(exc, 503)
            if len(parts) == 4 and parts[3] == "artifacts":
                try:
                    return self._json(200, artifact_state(load_project(parts[2])))
                except FileNotFoundError:
                    return self._error("Ролик не найден", 404)
            if len(parts) == 4 and parts[3] == "jobs":
                job_id = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
                if not job_id:
                    return self._json(200, {"jobs": list_jobs(parts[2])})
                try:
                    job = get_job(job_id, parts[2])
                    return self._json(200, _legacy_job_state(job) or {"state": "missing"})
                except ValueError as exc:
                    return self._error(exc, 503)
            if len(parts) == 5 and parts[3] == "jobs":
                try:
                    job = get_job(parts[4], parts[2])
                    return self._json(200, job or {"state": "missing"})
                except ValueError as exc:
                    return self._error(exc, 503)
            if len(parts) == 4 and parts[3] == "actions":
                try:
                    journal = verify_action_log(parts[2])
                    return self._json(200, {"valid": journal["valid"], "event_count": journal["event_count"],
                                            "latest_event_hash": journal["latest_event_hash"],
                                            "events": journal["events"], "actions": action_views(parts[2])})
                except ValueError as exc:
                    return self._error(exc, 409)
            if len(parts) == 5 and parts[3] == "actions":
                try:
                    action = get_action(parts[2], parts[4])
                    if action.get("status") in ("candidate_ready", "apply_pending"):
                        candidate = get_candidate(parts[2], parts[4])
                        action["candidate_spec"] = candidate["spec"]
                        action["base_spec"] = candidate["base_spec"]
                    return self._json(200, action)
                except FileNotFoundError:
                    return self._error("Действие не найдено", 404)
                except ValueError as exc:
                    return self._error(exc, 409)
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
            parts = path.strip("/").split("/")
            if path == "/api/settings/voice/test":
                settings = load_settings()
                if settings.get("voice_provider") != "piper":
                    return self._error("Сначала выберите Piper в настройках озвучки.")
                return self._json(200, check_piper_settings(settings, SETTINGS_PATH.parent / "voice-tests"))
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "visual-variants":
                scene_id = str(body.get("scene_id", ""))
                data_url = str(body.get("data_url", ""))
                match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", data_url)
                if not scene_id or not match:
                    return self._error("Укажите сцену и выберите изображение PNG, JPG или WebP")
                try:
                    image_bytes = base64.b64decode(match.group(2), validate=True)
                    if len(image_bytes) > 3_500_000:
                        return self._error("Вариант изображения слишком большой (максимум 3,5 МБ)")
                    from PIL import Image
                    with Image.open(io.BytesIO(image_bytes)) as image:
                        width, height = image.size
                        image_format = str(image.format or "").upper()
                        image.verify()
                    expected = {"png": ("PNG", ".png", "image/png"),
                                "jpeg": ("JPEG", ".jpg", "image/jpeg"),
                                "webp": ("WEBP", ".webp", "image/webp")}[match.group(1)]
                    if image_format != expected[0] or width <= 0 or height <= 0 or width > 8192 or height > 8192 or width * height > 40_000_000:
                        return self._error("Формат или размеры изображения не поддерживаются (максимум 8192×8192)")
                except Exception as exc:
                    return self._error(f"Не удалось проверить изображение: {exc}")
                result = create_visual_variant(parts[2], scene_id, image_bytes,
                                               expected_revision=int(body.get("expected_revision", -1)),
                                               mime=expected[2], extension=expected[1],
                                               prompt=body.get("prompt"))
                return self._json(201, result)
            if len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "visual-variants":
                asset_id, verb = parts[4], parts[5]
                if verb == "review":
                    return self._json(200, review_visual_variant(parts[2], asset_id))
                if verb == "select":
                    return self._json(200, select_visual_variant(parts[2], asset_id,
                                                                 int(body.get("expected_revision", -1))))
                if verb == "deselect":
                    return self._json(200, deselect_visual_variant(parts[2], asset_id,
                                                                   int(body.get("expected_revision", -1))))
                if verb == "reject":
                    return self._json(200, reject_visual_variant(parts[2], asset_id,
                                                                 int(body.get("expected_revision", -1))))
            if len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "actions":
                if body.get("kind", "script-draft") != "script-draft":
                    return self._error("Поддерживается только действие script-draft")
                return self._json(201, propose_script_draft(parts[2]))
            if len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "actions":
                action_id, verb = parts[4], parts[5]
                if verb == "confirm":
                    return self._json(202, confirm_action(parts[2], action_id, body))
                if verb == "apply":
                    return self._json(200, apply_action(parts[2], action_id, body))
                if verb == "reject":
                    return self._json(200, reject_action(parts[2], action_id))
            if len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "jobs":
                job_id, verb = parts[4], parts[5]
                if verb == "cancel":
                    return self._json(200, cancel_job(parts[2], job_id))
                if verb == "retry":
                    return self._json(202, retry_action_job(parts[2], job_id, body))
            if len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3:] == ["migration", "apply"]:
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
                    return self._json(200, check_gigachat_connection(gigachat_credentials()))
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
                if int(project.get("schema_version", 1)) >= 2:
                    encoded_image = io.BytesIO()
                    image.save(encoded_image, "JPEG", quality=90, optimize=True)
                    record = register_asset_bytes(project["id"], encoded_image.getvalue(),
                                                  asset_type="scene_image", target={"scene_id": scene_id},
                                                  extension=".jpg", mime="image/jpeg")
                    relative = Path(record["path"])
                else:
                    # Keep the legacy upload layout for v1 projects; do not migrate them implicitly.
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
                    return self._error("Непроверенный прямой draft отключён. Создайте предложение через /actions, подтвердите его, затем отдельно просмотрите и примените кандидат.", 409)
                if action in ("voice-plan", "frames-plan", "render-plan"):
                    stage = action.removesuffix("-plan").replace("-", "_")
                    if stage == "render":
                        validate_spec(project["spec"])
                    result = plan(project, stage, body.get("kind"))
                    return self._json(200, result)
                if action in ("voice-run", "frames-run", "render-run"):
                    stage = action.removesuffix("-run").replace("-", "_")
                    job = run(project, str(body.get("plan_id", "")), stage, body.get("kind"), body.get("confirmation"))
                    return self._json(202, job)
            return self.send_error(404)
        except FileNotFoundError:
            return self._error("Ролик не найден", 404)
        except ProviderError as exc:
            return self._error(exc, 400)
        except ValueError as exc:
            detail = str(exc).lower()
            status = 409 if any(word in detail for word in ("устар", "изменил", "журнал", "целост", "hash-chain", "отпечаток")) else 400
            return self._error(exc, status)
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
        if len(parts) == 5 and parts[:2] == ["api", "projects"] and parts[3] == "visuals":
            try:
                body = self._body()
                result = update_visual_prompt(parts[2], parts[4], body)
                return self._json(200, result)
            except FileNotFoundError:
                return self._error("Ролик не найден", 404)
            except ValueError as exc:
                detail = str(exc).lower()
                return self._error(exc, 409 if "изменил" in detail or "устар" in detail else 400)
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
    recovered = recover_jobs()
    if recovered["queued"] or recovered["interrupted"]:
        print(f"Восстановление очереди: повторно поставлено {recovered['queued']}, прервано перезапуском {recovered['interrupted']}")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"AI Video Factory открыта: http://localhost:{port} (слушает {host}:{port})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстанавливаю приложение…")
    finally:
        server.server_close()
