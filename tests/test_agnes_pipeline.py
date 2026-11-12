import struct
import sys
import tempfile
import zlib
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from factory import core
from factory.core import create_project, draft_script, load_project, save_project
from factory.visuals import list_visual_variants, update_visual_prompt


def _test_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x80")) + chunk(b"IEND", b""))


AGNES_SETTINGS = {"comfyui_image_profile": "agnes", "comfyui_agnes_quality": "1K",
                  "comfyui_agnes_aspect_ratio": "4:3", "comfyui_agnes_preprocess_prompt": True}


class AgnesPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_patch = patch.object(core, "DATA_ROOT", Path(self.tmp.name))
        self.data_patch.start()
        project = create_project({"theme": "Agnes-профиль", "duration": 30})
        project["spec"] = draft_script(project["spec"])
        project["revision"] += 1
        save_project(project)
        self.project = load_project(project["id"])
        self.scene_id = self.project["spec"]["script"]["scenes"][0]["id"]

    def tearDown(self):
        self.data_patch.stop()
        self.tmp.cleanup()

    def _plan_agnes(self):
        update_visual_prompt(self.project["id"], self.scene_id, {
            "expected_revision": self.project["revision"], "prompt": "Маша за компьютером",
            "negative_prompt": "", "description": "", "reference_asset_ids": []})
        current = load_project(self.project["id"])
        from factory.pipeline import plan
        with patch("factory.settings.load_settings", return_value=AGNES_SETTINGS):
            return current, plan(current, "image", self.scene_id)

    def test_agnes_plan_is_free_quota_cloud_provider(self):
        current, planned = self._plan_agnes()
        self.assertEqual(planned["provider"], "comfyui_agnes")
        self.assertEqual(planned["billing_mode"], "free_quota")
        self.assertEqual(planned["cost"], 0)
        self.assertEqual(planned["privacy_scope"], "cloud")
        self.assertEqual(planned["generation"]["profile_id"], "comfyui-agnes-t2i-v1")
        self.assertEqual(planned["generation"]["quality"], "1K")
        self.assertEqual(planned["generation"]["aspect_ratio"], "4:3")
        self.assertTrue(planned["generation"]["preprocess_prompt"])
        self.assertIn("бесплатная квота", planned["message"])
        self.assertIn("fallback", planned["message"])

    def test_run_agnes_rejects_local_and_nonzero_ceiling_confirmations(self):
        current, planned = self._plan_agnes()
        from factory.pipeline import run
        with patch("factory.settings.load_settings", return_value=AGNES_SETTINGS):
            with self.assertRaisesRegex(ValueError, "явное подтверждение"):
                run(current, planned["id"], "image", self.scene_id)
            with self.assertRaisesRegex(ValueError, "cloud_free"):
                run(current, planned["id"], "image", self.scene_id,
                    {"max_cost": 0, "currency": "EUR", "privacy_scope": "local", "consent": True})
            with self.assertRaisesRegex(ValueError, "0 EUR"):
                run(current, planned["id"], "image", self.scene_id,
                    {"max_cost": 10, "currency": "EUR", "privacy_scope": "cloud_free",
                     "consent": True, "cloud_consent": True})
            job = run(current, planned["id"], "image", self.scene_id,
                      {"max_cost": 0, "currency": "EUR", "privacy_scope": "cloud_free",
                       "consent": True, "cloud_consent": True})
            self.assertEqual(job["approval"]["privacy_scope"], "cloud_free")
            self.assertTrue(job["approval"]["cloud_consent"])
            self.assertEqual(job["approval"]["cost_ceiling"], {"amount": 0.0, "currency": "EUR"})

    def test_cloud_free_approval_requires_zero_ceiling_and_consent(self):
        from factory.jobs import _validate_approval
        good = {"consent": True, "input_fingerprint": "f1",
                "cost_ceiling": {"amount": 0.0, "currency": "EUR"},
                "privacy_scope": "cloud_free", "cloud_consent": True,
                "expires_at": 10_000_000_000.0}
        self.assertIsNotNone(_validate_approval(good, "f1"))
        with self.assertRaisesRegex(ValueError, "облачного согласия"):
            _validate_approval({**good, "cloud_consent": False}, "f1")
        with self.assertRaisesRegex(ValueError, "нулевой предел"):
            _validate_approval({**good, "cost_ceiling": {"amount": 5.0, "currency": "EUR"}}, "f1")

    def test_execute_job_dispatches_agnes_by_profile(self):
        current, planned = self._plan_agnes()
        from factory.jobs import _validate_approval
        from factory.pipeline import _execute_job
        approval = _validate_approval({"consent": True, "input_fingerprint": planned["input_fingerprint"],
                                       "cost_ceiling": {"amount": 0.0, "currency": "EUR"},
                                       "privacy_scope": "cloud_free", "cloud_consent": True,
                                       "expires_at": 10_000_000_000.0}, planned["input_fingerprint"])
        job = {"id": "test-agnes-exec", "project_id": current["id"], "action_id": planned["action_id"],
               "job_type": "pipeline", "state": "running", "progress": 0, "log": [],
               "payload": {"plan_id": planned["id"], "revision": current["revision"],
                           "spec_hash": planned["spec_hash"], "stage": "image",
                           "kind": self.scene_id, "generation": planned["generation"]},
               "input_fingerprint": planned["input_fingerprint"], "approval": approval,
               "checkpoint": {}, "cancel_requested": False}
        with patch("factory.settings.load_settings", return_value=AGNES_SETTINGS), \
             patch("factory.pipeline.is_cancel_requested", return_value=False), \
             patch("factory.pipeline._make_agnes_image_variant") as make_agnes, \
             patch("factory.pipeline._make_local_image_variant") as make_local:
            _execute_job(job)
            make_agnes.assert_called_once()
            make_local.assert_not_called()
        wrong_approval = dict(approval)
        wrong_approval["privacy_scope"] = "local"
        wrong_approval.pop("cloud_consent", None)
        bad_job = dict(job, approval=wrong_approval)
        with patch("factory.settings.load_settings", return_value=AGNES_SETTINGS), \
             patch("factory.pipeline.is_cancel_requested", return_value=False), \
             patch("factory.pipeline._make_agnes_image_variant") as make_agnes:
            with self.assertRaisesRegex(ValueError, "cloud_free"):
                _execute_job(bad_job)
            make_agnes.assert_not_called()

    def test_agnes_variant_registers_generated_candidate_without_fallback(self):
        update_visual_prompt(self.project["id"], self.scene_id, {
            "expected_revision": self.project["revision"], "prompt": "Маша за компьютером",
            "negative_prompt": "", "description": "", "reference_asset_ids": []})
        current = load_project(self.project["id"])
        png = _test_png()
        job = {"id": "test-agnes-image-job", "action_id": "test-agnes-image-action",
               "project_id": self.project["id"],
               "payload": {"revision": current["revision"], "generation": {
                   "profile_id": "comfyui-agnes-t2i-v1", "quality": "1K",
                   "aspect_ratio": "4:3", "preprocess_prompt": True, "seed": 42}},
               "checkpoint": {}, "input_fingerprint": "test-fingerprint", "progress": 0, "log": []}

        def fake_generate(_settings, **kwargs):
            kwargs["on_submitted"]("mock-agnes-prompt-1")
            return png, {"prompt_id": "mock-agnes-prompt-1", "profile_id": "comfyui-agnes-t2i-v1",
                         "quality": "1K", "aspect_ratio": "4:3", "preprocess_prompt": True,
                         "text_preset": "Prompt Enhance", "seed": 42}

        with patch("factory.settings.load_settings", return_value=AGNES_SETTINGS), \
             patch("factory.comfyui.generate_agnes_txt2img", side_effect=fake_generate) as generate, \
             patch("factory.pipeline.persist_job"), \
             patch("factory.pipeline.job_checkpoint", side_effect=lambda j, checkpoint: j.update(checkpoint=checkpoint)), \
             patch("factory.pipeline.is_cancel_requested", return_value=False):
            from factory.pipeline import _make_agnes_image_variant
            _make_agnes_image_variant(current, job, self.scene_id)
            _make_agnes_image_variant(current, job, self.scene_id)
            self.assertEqual(generate.call_count, 1, "recovery after asset registration must not regenerate")
        variants = list_visual_variants(self.project["id"], self.scene_id)["variants"]
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["state"], "created")
        self.assertEqual(variants[0]["provenance"], "comfyui_agnes_txt2img")
        self.assertEqual(job["checkpoint"]["stage"], "comfyui_prompt_submitted")

    def test_agnes_variant_rejects_settings_drift(self):
        update_visual_prompt(self.project["id"], self.scene_id, {
            "expected_revision": self.project["revision"], "prompt": "Маша за компьютером",
            "negative_prompt": "", "description": "", "reference_asset_ids": []})
        current = load_project(self.project["id"])
        job = {"id": "test-agnes-drift-job", "action_id": "test-agnes-drift-action",
               "project_id": self.project["id"],
               "payload": {"revision": current["revision"], "generation": {
                   "profile_id": "comfyui-agnes-t2i-v1", "quality": "1K",
                   "aspect_ratio": "4:3", "preprocess_prompt": True, "seed": 42}},
               "checkpoint": {}, "input_fingerprint": "test-fingerprint", "progress": 0, "log": []}
        drifted = dict(AGNES_SETTINGS, comfyui_agnes_quality="2K")
        with patch("factory.settings.load_settings", return_value=drifted), \
             patch("factory.comfyui.generate_agnes_txt2img") as generate, \
             patch("factory.pipeline.is_cancel_requested", return_value=False):
            from factory.pipeline import _make_agnes_image_variant
            with self.assertRaisesRegex(ValueError, "изменились"):
                _make_agnes_image_variant(current, job, self.scene_id)
        generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
