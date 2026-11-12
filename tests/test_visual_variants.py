import base64
import json
import struct
import zlib
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from factory import core
from factory.actions import verify_action_log
from factory.core import create_project, draft_script, load_project, save_project
from factory.fingerprints import project_fingerprints
from factory.server import Handler
from factory.visuals import (create_visual_variant, list_visual_variants, reject_visual_variant,
                             review_visual_variant, select_visual_variant, update_visual_prompt)


def _test_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x80")) + chunk(b"IEND", b""))


class VisualVariantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_patch = patch.object(core, "DATA_ROOT", Path(self.tmp.name))
        self.data_patch.start()
        project = create_project({"theme": "История визуальных вариантов", "duration": 30})
        project["spec"] = draft_script(project["spec"])
        project["revision"] += 1
        save_project(project)
        self.project = load_project(project["id"])
        self.scene_id = self.project["spec"]["script"]["scenes"][0]["id"]
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.data_patch.stop()
        self.tmp.cleanup()

    def request(self, path, method="GET", body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode())

    def test_prompt_edit_is_a_production_revision_and_stale_writes_fail(self):
        before = load_project(self.project["id"])
        before_fingerprint = project_fingerprints(before)["image_generation"][self.scene_id]["fingerprint"]
        result = update_visual_prompt(self.project["id"], self.scene_id, {
            "expected_revision": before["revision"],
            "description": "Тёплая мастерская и бумажный самолёт",
            "prompt": "Крупный план, мягкий свет, чистая композиция",
            "negative_prompt": "Надписи, логотипы, размытые лица",
            "reference_asset_ids": [],
        })
        after = result["project"]
        self.assertEqual(after["revision"], before["revision"] + 1)
        self.assertEqual(after["spec_revision"], before["spec_revision"])
        self.assertEqual(after["production_revision"], before["production_revision"] + 1)
        after_fingerprint = project_fingerprints(after)["image_generation"][self.scene_id]["fingerprint"]
        self.assertNotEqual(before_fingerprint, after_fingerprint)
        with self.assertRaisesRegex(ValueError, "изменился"):
            update_visual_prompt(self.project["id"], self.scene_id, {
                "expected_revision": before["revision"], "prompt": "устаревший prompt"})

    def test_local_image_plan_is_zero_cost_and_bound_to_selected_model(self):
        update_visual_prompt(self.project["id"], self.scene_id, {
            "expected_revision": self.project["revision"], "prompt": "Кораблик на пруду",
            "negative_prompt": "Текст", "description": "", "reference_asset_ids": [],
        })
        current = load_project(self.project["id"])
        with patch("factory.settings.load_settings", return_value={
                "comfyui_local_model": "cyberrealistic_v80.safetensors"}):
            from factory.pipeline import plan, run
            planned = plan(current, "image", self.scene_id)
            with self.assertRaisesRegex(ValueError, "явное подтверждение"):
                run(current, planned["id"], "image", self.scene_id)
        self.assertEqual(planned["provider"], "comfyui_local")
        self.assertEqual(planned["cost"], 0)
        self.assertEqual(planned["generation"]["model"], "cyberrealistic_v80.safetensors")
        self.assertEqual(planned["generation"]["scene_id"], self.scene_id)
        self.assertIn("нет облачного", planned["message"])

    def test_local_image_job_registers_generated_png_as_unselected_candidate(self):
        update_visual_prompt(self.project["id"], self.scene_id, {
            "expected_revision": self.project["revision"], "prompt": "Кораблик на пруду",
            "negative_prompt": "Текст", "description": "", "reference_asset_ids": [],
        })
        current = load_project(self.project["id"])
        png = _test_png()
        job = {"id": "test-local-image-job", "action_id": "test-local-image-action",
               "project_id": self.project["id"],
               "payload": {"revision": current["revision"], "generation": {
                   "model": "cyberrealistic_v80.safetensors", "seed": 42,
                   "width": 1, "height": 1, "steps": 20, "cfg": 7.0}},
               "checkpoint": {}, "input_fingerprint": "test-fingerprint", "progress": 0, "log": []}
        def fake_generate(_settings, **kwargs):
            kwargs["on_submitted"]("mock-prompt-1")
            return png, {"prompt_id": "mock-prompt-1", "seed": 42, "steps": 20, "cfg": 7.0,
                         "width": 1, "height": 1, "sampler": "euler", "scheduler": "normal"}
        with patch("factory.settings.load_settings", return_value={
                "comfyui_local_model": "cyberrealistic_v80.safetensors"}), \
             patch("factory.comfyui.generate_local_txt2img", side_effect=fake_generate) as generate, \
             patch("factory.pipeline.persist_job"), \
             patch("factory.pipeline.job_checkpoint", side_effect=lambda j, checkpoint: j.update(checkpoint=checkpoint)), \
             patch("factory.pipeline.is_cancel_requested", return_value=False):
            from factory.pipeline import _make_local_image_variant
            _make_local_image_variant(current, job, self.scene_id)
            _make_local_image_variant(current, job, self.scene_id)
            self.assertEqual(generate.call_count, 1, "recovery after asset registration must not regenerate")
        variants = list_visual_variants(self.project["id"], self.scene_id)["variants"]
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["state"], "created")
        self.assertEqual(variants[0]["source"], "generated")
        self.assertEqual(variants[0]["provenance"], "comfyui_local_txt2img")
        self.assertIsNone(variants[0].get("selected_at"))
        self.assertEqual(job["checkpoint"]["stage"], "comfyui_prompt_submitted")
        self.assertIn("(не выбран)", job["message"])

    def test_interrupted_unknown_comfy_submission_is_never_automatically_repeated(self):
        update_visual_prompt(self.project["id"], self.scene_id, {
            "expected_revision": self.project["revision"], "prompt": "Кораблик на пруду",
            "negative_prompt": "", "description": "", "reference_asset_ids": [],
        })
        current = load_project(self.project["id"])
        job = {"id": "interrupted-local-image-job", "project_id": self.project["id"],
               "payload": {"revision": current["revision"], "generation": {
                   "model": "cyberrealistic_v80.safetensors", "seed": 42,
                   "width": 512, "height": 512, "steps": 20, "cfg": 7.0}},
               "checkpoint": {"stage": "comfyui_submission_in_flight"}, "log": []}
        with patch("factory.settings.load_settings", return_value={
                "comfyui_local_model": "cyberrealistic_v80.safetensors"}), \
             patch("factory.comfyui.generate_local_txt2img") as generate, \
             patch("factory.pipeline.is_cancel_requested", return_value=False):
            from factory.pipeline import _make_local_image_variant
            with self.assertRaisesRegex(ValueError, "повторной отправки не будет"):
                _make_local_image_variant(current, job, self.scene_id)
        generate.assert_not_called()

    def test_variant_is_immutable_candidate_review_select_and_deselect(self):
        project = load_project(self.project["id"])
        prompt = {"text": "Сцена с бумажным самолётом", "negative": "Без текста"}
        created = create_visual_variant(self.project["id"], self.scene_id, b"immutable image bytes",
                                        expected_revision=project["revision"], mime="image/png",
                                        extension=".png", prompt=prompt)
        asset = created["variant"]
        self.assertEqual(created["state"], "created")
        self.assertEqual(load_project(self.project["id"])["revision"], project["revision"])
        self.assertEqual(asset["prompt"], prompt)
        self.assertEqual(list_visual_variants(self.project["id"], self.scene_id)["variants"][0]["state"], "created")
        with self.assertRaisesRegex(ValueError, "просмотрите"):
            select_visual_variant(self.project["id"], asset["asset_id"], project["revision"])

        review_visual_variant(self.project["id"], asset["asset_id"])
        self.assertEqual(list_visual_variants(self.project["id"], self.scene_id)["variants"][0]["state"], "reviewed")
        selected = select_visual_variant(self.project["id"], asset["asset_id"], project["revision"])
        self.assertEqual(selected["project"]["revision"], project["revision"] + 1)
        self.assertEqual(selected["project"]["spec_revision"], project["spec_revision"])
        self.assertEqual(selected["project"]["production_revision"], project["production_revision"] + 1)
        self.assertEqual(selected["project"]["spec"]["script"]["scenes"][0]["image"]["mode"], "upload")
        variants = list_visual_variants(self.project["id"], self.scene_id)["variants"]
        self.assertEqual(variants[0]["state"], "selected")
        from factory.core import get_studio_document
        immutable_record = next(item for item in get_studio_document(self.project["id"])["assets"]["assets"]
                                if item["asset_id"] == asset["asset_id"])
        self.assertEqual(immutable_record["prompt"], prompt)
        prompted_again = update_visual_prompt(self.project["id"], self.scene_id, {
            "expected_revision": selected["project"]["revision"], "prompt": "Изменённое описание свет и фон",
            "negative_prompt": "Без текста", "description": "Другая режиссура", "reference_asset_ids": [],
        })
        stale_variants = list_visual_variants(self.project["id"], self.scene_id)["variants"]
        self.assertTrue(stale_variants[0]["stale"])
        deselected = self.request(f"/api/projects/{self.project['id']}/visual-variants/{asset['asset_id']}/deselect",
                                  "POST", {"expected_revision": prompted_again["project"]["revision"]})
        self.assertEqual(deselected[0], 200)
        self.assertEqual(deselected[1]["project"]["spec"]["script"]["scenes"][0]["image"]["mode"], "style")
        self.assertEqual(list_visual_variants(self.project["id"], self.scene_id)["variants"][0]["state"], "reviewed")
        event_types = [event["event_type"] for event in verify_action_log(self.project["id"])["events"]]
        self.assertIn("visual_variant_created", event_types)
        self.assertIn("visual_variant_reviewed", event_types)
        self.assertIn("visual_variant_selected", event_types)
        self.assertIn("visual_variant_deselected", event_types)

    def test_upload_rejects_a_stale_revision_without_registering_an_asset(self):
        base_revision = self.project["revision"]
        update_visual_prompt(self.project["id"], self.scene_id, {
            "expected_revision": base_revision, "prompt": "New prompt before upload"})
        from factory.core import get_studio_document
        count_before = len(get_studio_document(self.project["id"])["assets"]["assets"])
        with self.assertRaisesRegex(ValueError, "изменился"):
            create_visual_variant(self.project["id"], self.scene_id, b"must not be registered",
                                  expected_revision=base_revision, mime="image/png", extension=".png",
                                  prompt={"text": "Old form prompt", "negative": ""})
        self.assertEqual(len(get_studio_document(self.project["id"])["assets"]["assets"]), count_before)

    def test_rejected_variant_stays_in_history_and_cannot_be_selected(self):
        created = create_visual_variant(self.project["id"], self.scene_id, b"another image",
                                        expected_revision=self.project["revision"], mime="image/jpeg",
                                        extension=".jpg", prompt={"text": "Old prompt", "negative": ""})
        rejected = reject_visual_variant(self.project["id"], created["variant"]["asset_id"], self.project["revision"])
        self.assertEqual(rejected["state"], "rejected")
        self.assertEqual(list_visual_variants(self.project["id"], self.scene_id)["variants"][0]["state"], "rejected")
        with self.assertRaisesRegex(ValueError, "Отклонённый"):
            select_visual_variant(self.project["id"], created["variant"]["asset_id"], self.project["revision"])
        self.assertEqual(load_project(self.project["id"])["revision"], self.project["revision"])

    def test_api_routes_validate_image_bytes_and_expose_prompt_history(self):
        project = load_project(self.project["id"])
        png_data = b"tiny test png"

        class FakeImage:
            size = (2, 2)
            format = "PNG"
            def __enter__(self): return self
            def __exit__(self, *_args): return None
            def verify(self): return None

        image_module = types.ModuleType("PIL.Image")
        image_module.open = lambda _stream: FakeImage()
        pil_module = types.ModuleType("PIL")
        pil_module.Image = image_module
        with patch.dict(sys.modules, {"PIL": pil_module, "PIL.Image": image_module}):
            status, result = self.request(f"/api/projects/{self.project['id']}/visual-variants", "POST", {
                "scene_id": self.scene_id, "expected_revision": project["revision"],
                "data_url": "data:image/png;base64," + base64.b64encode(png_data).decode(),
                "prompt": {"text": "Промпт версии 1", "negative": "Водяные знаки"},
            })
        self.assertEqual(status, 201, result)
        asset_id = result["variant"]["asset_id"]
        status, listing = self.request(f"/api/projects/{self.project['id']}/visual-variants?scene_id={self.scene_id}")
        self.assertEqual(status, 200)
        self.assertEqual(listing["variants"][0]["prompt"]["text"], "Промпт версии 1")
        status, updated = self.request(f"/api/projects/{self.project['id']}/visuals/{self.scene_id}", "PATCH", {
            "expected_revision": project["revision"], "description": "Кадр", "prompt": "Prompt 2",
            "negative_prompt": "No text", "reference_asset_ids": [asset_id],
        })
        self.assertEqual(status, 200, updated)
        self.assertEqual(updated["project"]["production_revision"], project["production_revision"] + 1)
        status, review = self.request(f"/api/projects/{self.project['id']}/visual-variants/{asset_id}/review", "POST", {})
        self.assertEqual(status, 200, review)
        status, stale = self.request(f"/api/projects/{self.project['id']}/visual-variants/{asset_id}/select", "POST", {
            "expected_revision": project["revision"],
        })
        self.assertEqual(status, 409)
        self.assertIn("изменился", stale["error"])

    def test_legacy_project_visual_prompt_edits_require_explicit_migration(self):
        legacy_id = "legacyvisual"
        legacy = core.new_spec("Legacy image prompt")
        directory = core.project_dir(legacy_id)
        directory.mkdir(parents=True, exist_ok=True)
        from factory.storage import atomic_write_json
        atomic_write_json(directory / "project.json", {"id": legacy_id, "title": "Legacy", "revision": 1})
        atomic_write_json(directory / "spec.json", legacy)
        with self.assertRaisesRegex(ValueError, "явная миграция"):
            list_visual_variants(legacy_id)
        self.assertEqual(json.loads((directory / "project.json").read_text())["revision"], 1)


if __name__ == "__main__":
    unittest.main()
