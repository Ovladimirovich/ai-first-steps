import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.assets import register_asset_bytes, register_asset_file
from factory.core import _validate_asset_manifest_append_only, create_project, new_spec
from factory.fingerprints import fingerprint, project_fingerprints
from factory.schema_v2 import v1_to_v2


def fixture_inputs(root: Path):
    legacy = new_spec("Две сцены", duration=30)
    legacy["script"]["scenes"] = [
        {"id": "s1", "order": 1, "title": "Первая", "purpose": "hook", "goal": "Зацепить",
         "visual_note": "Солнце", "image": {"mode": "style", "path": None},
         "lines": [{"id": "l1", "hero": "h1", "text": "Первая реплика", "pause_after_s": None}]},
        {"id": "s2", "order": 2, "title": "Вторая", "purpose": "payoff", "goal": "Объяснить",
         "visual_note": "Луна", "image": {"mode": "style", "path": None},
         "lines": [{"id": "l2", "hero": "h2", "text": "Вторая реплика", "pause_after_s": None}]},
    ]
    story, production = v1_to_v2(legacy)
    production["hero_voices"]["h1"].update({
        "provider": "local-tts", "model": "voice-small", "model_version": "3.1",
        "prompt": "Тёпло и ясно", "parameters": {"temperature": 0.2, "rate": 1.0},
    })
    production["visuals"]["s1"]["prompt"] = {"text": "Тёплый рассвет", "negative": "мрачное"}
    project = {"id": "fp-project", "schema_version": 2, "spec": legacy, "revision": 1}
    manifest = {"manifest_version": 1, "assets": []}
    return project, story, production, manifest, root


class FingerprintTests(unittest.TestCase):
    def test_line_edit_invalidates_only_its_voice_scene_and_dependent_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, story, production, manifest, root = fixture_inputs(Path(tmp))
            before = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            edited = json.loads(json.dumps(story, ensure_ascii=False))
            edited["script"]["scenes"][0]["lines"][0]["text"] += " Новое предложение."
            after = project_fingerprints(project, story=edited, production=production, manifest=manifest, root=root)

            self.assertNotEqual(before["voice_lines"]["l1"]["fingerprint"], after["voice_lines"]["l1"]["fingerprint"])
            self.assertEqual(before["voice_lines"]["l2"]["fingerprint"], after["voice_lines"]["l2"]["fingerprint"])
            self.assertNotEqual(before["image_generation"]["s1"]["fingerprint"], after["image_generation"]["s1"]["fingerprint"])
            self.assertEqual(before["image_generation"]["s2"]["fingerprint"], after["image_generation"]["s2"]["fingerprint"])
            self.assertNotEqual(before["frames"]["s1"]["fingerprint"], after["frames"]["s1"]["fingerprint"])
            self.assertEqual(before["frames"]["s2"]["fingerprint"], after["frames"]["s2"]["fingerprint"])
            self.assertNotEqual(before["segments"]["s1"]["draft"]["fingerprint"], after["segments"]["s1"]["draft"]["fingerprint"])
            # Scene two keeps its local timing and rendering inputs when only scene one's duration changes.
            self.assertEqual(before["segments"]["s2"]["draft"]["fingerprint"], after["segments"]["s2"]["draft"]["fingerprint"])
            self.assertNotEqual(before["renders"]["draft"]["fingerprint"], after["renders"]["draft"]["fingerprint"])

    def test_canonicalization_ignores_volatile_metadata_secrets_and_numeric_representation(self):
        self.assertEqual(fingerprint({"rate": 1}), fingerprint({"rate": 1.0}))
        with tempfile.TemporaryDirectory() as tmp:
            project, story, production, manifest, root = fixture_inputs(Path(tmp))
            before = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            story["action_id"] = "volatile-action"
            story["created_at"] = 123456
            production["ui_state"] = {"current_step": 4}
            production["hero_voices"]["h1"]["api_key"] = "must-not-be-hashed-or-returned"
            after = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            self.assertEqual(before["components"], after["components"])
            self.assertEqual(before["voice_lines"]["l1"]["fingerprint"], after["voice_lines"]["l1"]["fingerprint"])
            self.assertNotIn("must-not-be-hashed-or-returned", json.dumps(after, ensure_ascii=False))

    def test_voice_fingerprint_includes_model_version_prompt_and_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, story, production, manifest, root = fixture_inputs(Path(tmp))
            before = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            production["hero_voices"]["h1"]["model_version"] = "3.2"
            production["hero_voices"]["h1"]["prompt"] = "Чуть быстрее и веселее"
            production["hero_voices"]["h1"]["parameters"]["temperature"] = 0.7
            after = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            self.assertNotEqual(before["voice_lines"]["l1"]["fingerprint"], after["voice_lines"]["l1"]["fingerprint"])
            self.assertEqual(before["voice_lines"]["l2"]["fingerprint"], after["voice_lines"]["l2"]["fingerprint"])

    def test_visual_prompt_model_version_and_parameters_are_scene_local_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, story, production, manifest, root = fixture_inputs(Path(tmp))
            before = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            production["visuals"]["s1"].update({
                "model": {"provider": "local-image", "name": "illustrator", "version": "2.4"},
                "parameters": {"steps": 28, "guidance": 6.5, "seed": 123},
                "prompt_template_version": "scene-v3",
            })
            production["visuals"]["s1"]["prompt"]["text"] = "Солнечная поляна, вариант B"
            after = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            self.assertNotEqual(before["image_generation"]["s1"]["fingerprint"], after["image_generation"]["s1"]["fingerprint"])
            self.assertEqual(before["image_generation"]["s2"]["fingerprint"], after["image_generation"]["s2"]["fingerprint"])
            self.assertEqual(before["frames"]["s2"]["fingerprint"], after["frames"]["s2"]["fingerprint"])

    def test_codec_change_invalidates_only_final_render_not_story_or_media_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, story, production, manifest, root = fixture_inputs(Path(tmp))
            before = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            production["profiles"]["final"]["video_codec"] = "hevc"
            after = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            self.assertEqual(before["components"]["story"], after["components"]["story"])
            self.assertEqual(before["voice_lines"], after["voice_lines"])
            self.assertEqual(before["image_generation"], after["image_generation"])
            self.assertEqual(before["frames"], after["frames"])
            self.assertEqual(before["segments"]["s1"]["final"]["fingerprint"], after["segments"]["s1"]["final"]["fingerprint"])
            self.assertEqual(before["renders"]["draft"]["fingerprint"], after["renders"]["draft"]["fingerprint"])
            self.assertNotEqual(before["renders"]["final"]["fingerprint"], after["renders"]["final"]["fingerprint"])

    def test_asset_bytes_are_hashed_and_corruption_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, story, production, _, root = fixture_inputs(Path(tmp))
            image_dir = root / "legacy-assets"
            image_dir.mkdir()
            image = image_dir / "background.jpg"
            image.write_bytes(b"first pixels")
            sha = hashlib.sha256(image.read_bytes()).hexdigest()
            manifest = {"manifest_version": 1, "assets": [{
                "asset_id": "img-s1-v1", "type": "scene_image", "target": {"scene_id": "s1"},
                "asset_version": 1, "path": "legacy-assets/background.jpg", "sha256": sha,
            }]}
            production["visuals"]["s1"].update({"image_mode": "upload", "legacy_path": "legacy-assets/background.jpg",
                                                  "selected_asset_id": "img-s1-v1"})
            before = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            self.assertTrue(before["assets"]["img-s1-v1"]["integrity_ok"])
            image.write_bytes(b"changed pixels")
            after = project_fingerprints(project, story=story, production=production, manifest=manifest, root=root)
            self.assertFalse(after["assets"]["img-s1-v1"]["integrity_ok"])
            self.assertNotEqual(before["assets_by_scene"]["s1"]["fingerprint"], after["assets_by_scene"]["s1"]["fingerprint"])
            self.assertNotEqual(before["frames"]["s1"]["fingerprint"], after["frames"]["s1"]["fingerprint"])

    def test_codec_profile_change_does_not_increment_story_revision(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Технический профиль"})
            native = project["revision"]
            story_path = Path(tmp) / project["id"] / "revisions" / project["current_revision_id"] / "spec.json"
            original_story = story_path.read_bytes()
            loaded = json.loads((Path(tmp) / project["id"] / "production.json").read_text(encoding="utf-8"))
            loaded["profiles"]["final"]["video_codec"] = "hevc"
            project["_native_update"] = {"spec": json.loads(original_story), "production": loaded}
            project["revision"] = native + 1
            from factory.core import save_project
            save_project(project)
            self.assertEqual(project["spec_revision"], 1)
            self.assertEqual(project["production_revision"], 2)
            self.assertEqual(story_path.read_bytes(), original_story)

    def test_asset_registration_appends_versions_without_overwriting_blob(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Версии ассетов"})
            first = register_asset_bytes(project["id"], b"image one", asset_type="scene_image",
                                         target={"scene_id": "s1"}, extension=".jpg", mime="image/jpeg")
            second = register_asset_bytes(project["id"], b"image two", asset_type="scene_image",
                                          target={"scene_id": "s1"}, extension=".jpg", mime="image/jpeg")
            root = Path(tmp) / project["id"]
            first_path = root / first["path"]
            second_path = root / second["path"]
            self.assertEqual(first["asset_version"], 1)
            self.assertEqual(second["asset_version"], 2)
            self.assertNotEqual(first["path"], second["path"])
            self.assertEqual(first_path.read_bytes(), b"image one")
            self.assertEqual(second_path.read_bytes(), b"image two")
            manifest = json.loads((root / "studio" / "assets.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["assets"]), 2)
            _validate_asset_manifest_append_only(manifest, {**manifest, "assets": manifest["assets"] + [{
                **second, "asset_id": "asset-third-version", "asset_version": 3, "sequence": 3,
            }]})
            with self.assertRaisesRegex(ValueError, "изменена"):
                _validate_asset_manifest_append_only(manifest, {**manifest, "assets": [manifest["assets"][1]]})

    def test_generated_file_registration_is_content_addressed(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Файл"})
            root = Path(tmp) / project["id"]
            source = root / "working.mp3"
            source.write_bytes(b"temporary media bytes")
            record = register_asset_file(project["id"], source, asset_type="dialogue_audio",
                                         target={"line_id": "l1"}, extension=".mp3",
                                         input_fingerprint="f" * 64)
            immutable = root / record["path"]
            source.write_bytes(b"later mutation")
            self.assertEqual(immutable.read_bytes(), b"temporary media bytes")
            self.assertTrue(record["path"].startswith("assets/sha256/"))
            self.assertEqual(record["input_fingerprint"], "f" * 64)


if __name__ == "__main__":
    unittest.main()
