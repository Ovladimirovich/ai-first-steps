import base64
import copy
import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.core import (create_project, get_studio_document, load_project, new_spec, project_dir,
                          project_revisions, restore_project_revision, save_project)
from factory.drafts import commit_project_draft, get_project_draft, save_project_draft
from factory.migrations import apply_v1_migration, migration_plan
from factory.server import Handler


class StudioV2Tests(unittest.TestCase):
    def test_new_projects_store_v2_but_keep_legacy_runtime_view(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Радуга", "duration": 30})
            root = Path(tmp) / project["id"]
            disk_spec = json.loads((root / "spec.json").read_text(encoding="utf-8"))
            disk_production = json.loads((root / "production.json").read_text(encoding="utf-8"))
            self.assertEqual(project["schema_version"], 2)
            self.assertEqual(disk_spec["spec_version"], 2)
            self.assertEqual(disk_production["production_version"], 1)
            self.assertEqual(project["spec"]["spec_version"], 1)  # v1 adapter for current UI/pipeline
            self.assertEqual(project["spec_revision"], 1)
            self.assertEqual(project["production_revision"], 1)
            self.assertEqual(len(project_revisions(project["id"])), 1)

    def test_story_and_production_revisions_are_independent_and_restorable(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Исходная тема", "duration": 30})
            initial_revision = project["current_revision_id"]
            project["spec"]["look"]["palette"]["bg"] = "#112233"
            project["revision"] += 1
            save_project(project)
            after_production = load_project(project["id"])
            self.assertEqual(after_production["spec_revision"], 1)
            self.assertEqual(after_production["production_revision"], 2)

            after_production["spec"]["intent"]["theme"] = "Новая тема"
            after_production["revision"] += 1
            save_project(after_production)
            after_story = load_project(project["id"])
            self.assertEqual(after_story["spec_revision"], 2)
            self.assertEqual(after_story["production_revision"], 2)
            self.assertEqual(len(project_revisions(project["id"])), 3)

            restored = restore_project_revision(project["id"], initial_revision, after_story["revision"])
            self.assertEqual(restored["spec"]["intent"]["theme"], "Исходная тема")
            self.assertEqual(restored["title"], "Исходная тема")
            self.assertEqual(restored["spec"]["look"]["palette"]["bg"], "#FFF6E0")
            self.assertEqual(restored["revision"], after_story["revision"] + 1)
            self.assertEqual(restored["spec_revision"], 3)
            self.assertEqual(restored["production_revision"], 3)
            self.assertEqual(len(project_revisions(project["id"])), 4)

    def test_working_draft_does_not_change_canonical_state_until_commit(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Каноническая тема"})
            native = get_studio_document(project["id"])
            draft_spec = json.loads(json.dumps(native["spec"], ensure_ascii=False))
            draft_production = json.loads(json.dumps(native["production"], ensure_ascii=False))
            draft_spec["intent"]["theme"] = "Временная правка"
            draft_production["look"]["style_preset"] = "night_space"
            draft = save_project_draft(project["id"], "session_1", {
                "base_project_revision": native["project_revision"],
                "base_spec_revision": native["spec_revision"],
                "base_production_revision": native["production_revision"],
                "spec": draft_spec, "production": draft_production,
            })
            self.assertEqual(draft["status"], "draft")
            canonical = load_project(project["id"])
            self.assertEqual(canonical["spec"]["intent"]["theme"], "Каноническая тема")
            self.assertEqual(canonical["spec_revision"], 1)
            self.assertEqual(len(project_revisions(project["id"])), 1)

            result = commit_project_draft(project["id"], "session_1", {})
            self.assertFalse(result["already_committed"])
            committed = load_project(project["id"])
            self.assertEqual(committed["spec"]["intent"]["theme"], "Временная правка")
            self.assertEqual(committed["spec"]["look"]["style_preset"], "night_space")
            self.assertEqual(committed["spec_revision"], 2)
            self.assertEqual(committed["production_revision"], 2)
            self.assertEqual(get_project_draft(project["id"], "session_1")["status"], "committed")
            self.assertTrue(commit_project_draft(project["id"], "session_1", {})["already_committed"])

    def test_stale_draft_is_preserved_but_cannot_overwrite_new_revision(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Основа"})
            native = get_studio_document(project["id"])
            draft_spec = json.loads(json.dumps(native["spec"], ensure_ascii=False))
            draft_spec["intent"]["theme"] = "Черновик со старой основой"
            save_project_draft(project["id"], "stale_session", {
                "base_project_revision": native["project_revision"],
                "base_spec_revision": native["spec_revision"],
                "base_production_revision": native["production_revision"],
                "spec": draft_spec, "production": native["production"],
            })
            current = load_project(project["id"])
            current["spec"]["intent"]["theme"] = "Принятая новая версия"
            current["revision"] += 1
            save_project(current)
            self.assertTrue(get_project_draft(project["id"], "stale_session")["conflict"])
            with self.assertRaisesRegex(ValueError, "Ревизии проекта изменились"):
                commit_project_draft(project["id"], "stale_session", {})
            self.assertEqual(load_project(project["id"])["spec"]["intent"]["theme"], "Принятая новая версия")

    def test_stale_concurrent_save_cannot_overwrite_newer_revision(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Исходная"})
            first = load_project(project["id"])
            concurrent = copy.deepcopy(first)
            first["spec"]["intent"]["theme"] = "Первая правка"
            first["revision"] += 1
            save_project(first)
            concurrent["spec"]["intent"]["theme"] = "Устаревшая правка"
            concurrent["revision"] += 1
            with self.assertRaisesRegex(ValueError, "изменился в другой вкладке"):
                save_project(concurrent)
            self.assertEqual(load_project(project["id"])["spec"]["intent"]["theme"], "Первая правка")

    def test_revision_snapshot_integrity_is_checked_on_load(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Целостность"})
            snapshot = project_dir(project["id"]) / "revisions" / project["current_revision_id"] / "spec.json"
            snapshot.write_text(json.dumps({"spec_version": 2, "tampered": True}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "повреждён"):
                load_project(project["id"])

    def test_v1_load_and_migration_plan_are_read_only_until_apply(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project_id = "legacy-project"
            root = Path(tmp) / project_id
            root.mkdir()
            legacy_spec = new_spec("Старая тема", duration=30)
            legacy_spec["script"]["scenes"] = [{
                "id": "s1", "order": 1, "title": "Вопрос", "purpose": "hook", "goal": "Зацепить",
                "visual_note": "Светлый фон", "image": {"mode": "style", "path": None},
                "lines": [{"id": "l1", "hero": "h1", "text": "Старая реплика", "pause_after_s": None}],
            }]
            metadata = {"id": project_id, "title": "Старая тема", "revision": 7, "current_step": 1}
            spec_bytes = json.dumps(legacy_spec, ensure_ascii=False, indent=2).encode("utf-8")
            meta_bytes = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
            (root / "spec.json").write_bytes(spec_bytes)
            (root / "project.json").write_bytes(meta_bytes)

            loaded = load_project(project_id)
            report = migration_plan(project_id)
            self.assertEqual(loaded["spec"]["script"]["scenes"][0]["lines"][0]["text"], "Старая реплика")
            self.assertTrue(report["can_migrate"])
            self.assertEqual((root / "spec.json").read_bytes(), spec_bytes)
            self.assertEqual((root / "project.json").read_bytes(), meta_bytes)

            result = apply_v1_migration(project_id, expected_revision=7,
                                         expected_source_fingerprint=report["source_fingerprint"])
            migrated = load_project(project_id)
            self.assertEqual(result["schema_version"], 2)
            self.assertEqual(migrated["spec"]["script"]["scenes"][0]["id"], "s1")
            self.assertEqual(migrated["spec"]["script"]["scenes"][0]["lines"][0]["text"], "Старая реплика")
            self.assertTrue((root / result["backup_path"] / "spec.json").is_file())
            native = json.loads((root / "spec.json").read_text(encoding="utf-8"))
            self.assertEqual(native["spec_version"], 2)
            self.assertEqual(len(project_revisions(project_id)), 1)

    def test_migration_preserves_uploaded_scene_asset_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project_id = "legacy-upload"
            root = Path(tmp) / project_id
            (root / "scene-backgrounds").mkdir(parents=True)
            image_path = root / "scene-backgrounds" / "s1.jpg"
            image_path.write_bytes(b"legacy-image-bytes")
            legacy_spec = new_spec("Фон", duration=30)
            legacy_spec["script"]["scenes"] = [{
                "id": "s1", "order": 1, "title": "Сцена", "purpose": "hook", "goal": "Зацепить",
                "visual_note": "Фон", "image": {"mode": "upload", "path": "scene-backgrounds/s1.jpg"},
                "lines": [{"id": "l1", "hero": "h1", "text": "Текст", "pause_after_s": None}],
            }]
            (root / "spec.json").write_text(json.dumps(legacy_spec, ensure_ascii=False), encoding="utf-8")
            (root / "project.json").write_text(json.dumps({"id": project_id, "revision": 2}), encoding="utf-8")
            before = image_path.read_bytes()

            report = migration_plan(project_id)
            result = apply_v1_migration(project_id, expected_revision=2,
                                         expected_source_fingerprint=report["source_fingerprint"])
            manifest = json.loads((root / "studio" / "assets.json").read_text(encoding="utf-8"))
            migrated = load_project(project_id)
            visual = json.loads((root / "production.json").read_text(encoding="utf-8"))["visuals"]["s1"]
            self.assertEqual(len(manifest["assets"]), 1)
            self.assertEqual(visual["selected_asset_id"], manifest["assets"][0]["asset_id"])
            self.assertEqual(migrated["spec"]["script"]["scenes"][0]["image"]["path"], "scene-backgrounds/s1.jpg")
            self.assertEqual(image_path.read_bytes(), before)
            self.assertEqual(result["assets_migrated"], 1)

    def test_unsafe_legacy_upload_path_blocks_migration_without_touching_v1(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project_id = "unsafe-legacy"
            root = Path(tmp) / project_id
            root.mkdir()
            legacy_spec = new_spec("Проверка пути", duration=30)
            legacy_spec["script"]["scenes"] = [{
                "id": "s1", "order": 1, "title": "Сцена", "purpose": "hook", "goal": "Зацепить",
                "visual_note": "", "image": {"mode": "upload", "path": "../../outside.jpg"},
                "lines": [{"id": "l1", "hero": "h1", "text": "Текст", "pause_after_s": None}],
            }]
            (root / "spec.json").write_text(json.dumps(legacy_spec, ensure_ascii=False), encoding="utf-8")
            (root / "project.json").write_text(json.dumps({"id": project_id, "revision": 3}), encoding="utf-8")
            before_spec = (root / "spec.json").read_bytes()
            before_meta = (root / "project.json").read_bytes()
            report = migration_plan(project_id)
            self.assertFalse(report["can_migrate"])
            with self.assertRaisesRegex(ValueError, "выходит за каталог"):
                apply_v1_migration(project_id, expected_revision=3,
                                    expected_source_fingerprint=report["source_fingerprint"])
            self.assertEqual((root / "spec.json").read_bytes(), before_spec)
            self.assertEqual((root / "project.json").read_bytes(), before_meta)
            self.assertFalse((root / "backups").exists())

    def test_migration_plan_fingerprint_detects_manual_spec_change(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project_id = "migration-content-race"
            root = Path(tmp) / project_id
            root.mkdir()
            spec = new_spec("До правки", duration=30)
            (root / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            (root / "project.json").write_text(json.dumps({"id": project_id, "revision": 2}), encoding="utf-8")
            report = migration_plan(project_id)
            spec["intent"]["theme"] = "Правка вне API"
            (root / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Данные проекта изменились"):
                apply_v1_migration(project_id, expected_revision=2,
                                    expected_source_fingerprint=report["source_fingerprint"])
            self.assertFalse((root / "backups").exists())

    def test_migration_plan_is_revision_bound_and_repeat_apply_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project_id = "migration-race"
            root = Path(tmp) / project_id
            root.mkdir()
            spec = new_spec("Ревизия", duration=30)
            (root / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
            (root / "project.json").write_text(json.dumps({"id": project_id, "revision": 4}), encoding="utf-8")
            report = migration_plan(project_id)
            with self.assertRaisesRegex(ValueError, "изменился"):
                apply_v1_migration(project_id, expected_revision=3,
                                    expected_source_fingerprint=report["source_fingerprint"])
            result = apply_v1_migration(project_id, expected_revision=4,
                                        expected_source_fingerprint=report["source_fingerprint"])
            self.assertEqual(result["schema_version"], 2)
            with self.assertRaisesRegex(ValueError, "уже использует"):
                apply_v1_migration(project_id, expected_revision=4,
                                    expected_source_fingerprint=report["source_fingerprint"])


class StudioV2ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_root_patch = patch("factory.core.DATA_ROOT", Path(self.temp.name))
        self.data_root_patch.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.data_root_patch.stop()
        self.temp.cleanup()

    def request(self, path, method="GET", body=None):
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=data,
                                         headers={"Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def make_v1_project(self, project_id="api-legacy"):
        root = Path(self.temp.name) / project_id
        root.mkdir()
        spec = new_spec("API миграция", duration=30)
        spec["script"]["scenes"] = [{
            "id": "s1", "order": 1, "title": "Вопрос", "purpose": "hook", "goal": "Зацепить",
            "visual_note": "Светлый фон", "image": {"mode": "style", "path": None},
            "lines": [{"id": "l1", "hero": "h1", "text": "Исходная строка", "pause_after_s": None}],
        }]
        (root / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        (root / "project.json").write_text(json.dumps({"id": project_id, "title": "API миграция", "revision": 5}), encoding="utf-8")

    def test_migration_revision_and_restore_routes(self):
        project_id = "api-legacy"
        self.make_v1_project(project_id)
        status, before = self.request(f"/api/projects/{project_id}/studio")
        self.assertEqual(status, 200)
        self.assertTrue(before["migration_required"])
        status, plan = self.request(f"/api/projects/{project_id}/migration/plan")
        self.assertEqual(status, 200)
        status, applied = self.request(f"/api/projects/{project_id}/migration/apply", "POST", {
            "expected_revision": plan["revision"], "source_fingerprint": plan["source_fingerprint"]})
        self.assertEqual(status, 200)
        self.assertEqual(applied["schema_version"], 2)

        status, studio = self.request(f"/api/projects/{project_id}/studio")
        self.assertEqual(status, 200)
        self.assertFalse(studio["migration_required"])
        status, revisions = self.request(f"/api/projects/{project_id}/revisions")
        self.assertEqual(status, 200)
        original_id = revisions["revisions"][0]["revision_id"]

        status, legacy_view = self.request(f"/api/projects/{project_id}")
        self.assertEqual(status, 200)
        edited = legacy_view["spec"]
        edited["intent"]["theme"] = "Принятая правка"
        status, saved = self.request(f"/api/projects/{project_id}", "PATCH", {
            "revision": legacy_view["revision"], "spec": edited, "current_step": 1})
        self.assertEqual(status, 200)
        self.assertEqual(saved["spec_revision"], 2)
        status, revisions = self.request(f"/api/projects/{project_id}/revisions")
        self.assertEqual(len(revisions["revisions"]), 2)

        status, restored = self.request(f"/api/projects/{project_id}/revisions/{original_id}/restore", "POST", {
            "expected_revision": saved["revision"]})
        self.assertEqual(status, 200)
        self.assertEqual(restored["spec"]["intent"]["theme"], "API миграция")
        self.assertEqual(restored["revision"], saved["revision"] + 1)

        status, studio = self.request(f"/api/projects/{project_id}/studio")
        draft_spec = json.loads(json.dumps(studio["spec"], ensure_ascii=False))
        draft_spec["intent"]["theme"] = "UI draft, not yet committed"
        status, draft = self.request(f"/api/projects/{project_id}/drafts/browser-session", "PUT", {
            "base_project_revision": studio["project_revision"],
            "base_spec_revision": studio["spec_revision"],
            "base_production_revision": studio["production_revision"],
            "spec": draft_spec, "production": studio["production"],
        })
        self.assertEqual(status, 200)
        status, still_canonical = self.request(f"/api/projects/{project_id}")
        self.assertEqual(still_canonical["spec"]["intent"]["theme"], "API миграция")
        status, committed = self.request(f"/api/projects/{project_id}/drafts/browser-session/commit", "POST", {})
        self.assertEqual(status, 200)
        self.assertEqual(committed["project"]["spec"]["intent"]["theme"], "UI draft, not yet committed")

    def test_v2_uploads_are_immutable_asset_versions_and_fingerprints_api_is_read_only(self):
        project = create_project({"theme": "Неизменяемые фоны", "duration": 30})
        project["spec"]["script"]["scenes"] = [{
            "id": "s1", "order": 1, "title": "Сцена", "purpose": "hook", "goal": "Зацепить",
            "visual_note": "Фон", "image": {"mode": "style", "path": None},
            "lines": [{"id": "l1", "hero": "h1", "text": "Текст", "pause_after_s": None}],
        }]
        project["revision"] += 1
        save_project(project)

        import types
        class FakeImage:
            def __init__(self, raw):
                self.raw = raw
            def convert(self, mode):
                return self
            def save(self, target, fmt, **kwargs):
                target.write(b"fake-jpeg:" + self.raw)
        image_module = types.ModuleType("PIL.Image")
        image_module.open = lambda stream: FakeImage(stream.getvalue())
        image_module.Resampling = types.SimpleNamespace(LANCZOS=1)
        ops_module = types.ModuleType("PIL.ImageOps")
        ops_module.fit = lambda image, size, method=None: image
        pil_module = types.ModuleType("PIL")
        pil_module.Image = image_module
        pil_module.ImageOps = ops_module

        def png_data(payload):
            return "data:image/png;base64," + base64.b64encode(payload).decode("ascii")

        with patch.dict(sys.modules, {"PIL": pil_module, "PIL.Image": image_module, "PIL.ImageOps": ops_module}):
            status, first = self.request(f"/api/projects/{project['id']}/frames/upload", "POST",
                                         {"scene_id": "s1", "data_url": png_data(b"first image bytes")})
            self.assertEqual(status, 200)
            first_path = first["spec"]["script"]["scenes"][0]["image"]["path"]
            first_file = Path(self.temp.name) / project["id"] / first_path
            first_bytes = first_file.read_bytes()
            self.assertTrue(first_path.startswith("assets/sha256/"))

            status, second = self.request(f"/api/projects/{project['id']}/frames/upload", "POST",
                                          {"scene_id": "s1", "data_url": png_data(b"second image bytes")})
            self.assertEqual(status, 200)
        second_path = second["spec"]["script"]["scenes"][0]["image"]["path"]
        self.assertNotEqual(first_path, second_path)
        self.assertEqual(first_file.read_bytes(), first_bytes)
        manifest = json.loads((Path(self.temp.name) / project["id"] / "studio" / "assets.json").read_text(encoding="utf-8"))
        self.assertEqual([item["asset_version"] for item in manifest["assets"]], [1, 2])

        metadata_path = Path(self.temp.name) / project["id"] / "project.json"
        metadata_before = metadata_path.read_bytes()
        status, report = self.request(f"/api/projects/{project['id']}/fingerprints")
        self.assertEqual(metadata_path.read_bytes(), metadata_before)
        self.assertEqual(status, 200)
        self.assertEqual(report["fingerprint_version"], 1)
        self.assertIn(manifest["assets"][-1]["asset_id"], report["fingerprints"]["assets"])
        self.assertTrue(report["fingerprints"]["assets"][manifest["assets"][-1]["asset_id"]]["integrity_ok"])


if __name__ == "__main__":
    unittest.main()
