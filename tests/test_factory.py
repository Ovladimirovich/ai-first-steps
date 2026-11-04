import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from factory.core import draft_script, new_spec
from factory.pipeline import _pending_scene_count, _segment_key, plan, run
from factory.providers import ProviderError, _base_url, draft_with_gigachat, draft_with_llama, test_gigachat_connection
from factory.timing import timing_for


class FactoryTimingTests(unittest.TestCase):
    def test_real_legacy_timing_parity(self):
        source = json.loads((ROOT / "script/lines_pixar_why_ai.json").read_text(encoding="utf-8"))
        reference = json.loads((ROOT / "remotion/public/timing-pixar.json").read_text(encoding="utf-8"))
        spec = new_spec("Проверка паритета")
        by_scene = {}
        durations = {}
        for row in source:
            by_scene.setdefault(row["scene"], []).append({
                "id": row["id"], "hero": "h1" if row["who"] == "b" else "h2",
                "text": row["text"], "pause_after_s": None,
            })
        spec["script"]["scenes"] = [
            {"id": scene_id, "order": index, "title": scene_id, "lines": lines}
            for index, (scene_id, lines) in enumerate(by_scene.items(), 1)
        ]
        durations = {row["id"]: row["dur"] for row in reference["lines"]}
        result = timing_for(spec, durations)
        self.assertEqual(len(result["lines"]), 57)
        self.assertEqual(result["total"], 379.0)
        for actual, expected in zip(result["lines"], reference["lines"]):
            self.assertEqual(actual["id"], expected["id"])
            self.assertEqual(actual["start"], expected["start"])
            self.assertEqual(actual["end"], expected["end"])
            self.assertEqual(actual["dur"], expected["dur"])

    def test_llama_cpp_draft_adapter_parses_local_openai_response(self):
        spec = new_spec("Почему небо голубое?", duration=30)
        response = {"choices": [{"message": {"content": json.dumps({"scenes": [
            {"title": "Вопрос", "purpose": "hook", "goal": "Зацепить", "visual_note": "Небо", "lines": [{"hero": "h2", "text": "Почему небо голубое?"}]},
            {"title": "Объяснение", "purpose": "point", "goal": "Понять", "visual_note": "Свет", "lines": [{"hero": "h1", "text": "Свет состоит из разных цветов."}]},
            {"title": "Вывод", "purpose": "payoff", "goal": "Запомнить", "visual_note": "Радуга", "lines": [{"hero": "h2", "text": "Теперь я знаю ответ!"}]},
        ]})}}]}
        with patch("factory.providers._request_json", side_effect=[{"data": [{"id": "Qwen-local"}]}, response]):
            result = draft_with_llama(spec, {"llama_cpp_base_url": "http://127.0.0.1:8081", "llama_cpp_model": ""})
        self.assertEqual(result["script"]["generator"]["provider"], "llama_cpp")
        self.assertEqual(len(result["script"]["scenes"]), 3)
        self.assertEqual(result["script"]["scenes"][0]["lines"][0]["id"], "l1")

    def test_gigachat_adapter_uses_chat_api_response(self):
        spec = new_spec("Почему появляется радуга?", duration=30)
        scenes = [{"title": title, "purpose": purpose, "lines": [{"hero": hero, "text": text}]}
                  for title, purpose, hero, text in [
                      ("Вопрос", "hook", "h2", "Откуда берётся радуга?"),
                      ("Свет", "point", "h1", "Солнечный свет состоит из цветов."),
                      ("Вывод", "payoff", "h2", "Теперь я знаю, как она появляется!")]]
        response = {"choices": [{"message": {"content": json.dumps({"scenes": scenes}, ensure_ascii=False)}}]}
        with patch("factory.providers._gigachat_api", side_effect=[{"data": [{"id": "GigaChat"}]}, response]) as call:
            result = draft_with_gigachat(spec, {"gigachat_model": ""}, {"client_id": "x", "client_secret": "y"})
        self.assertEqual(result["script"]["generator"]["provider"], "gigachat")
        self.assertEqual(call.call_args_list[0].args[0], "/models")
        self.assertEqual(call.call_args_list[1].args[0], "/chat/completions")

    def test_gigachat_requires_credentials(self):
        with self.assertRaisesRegex(ProviderError, "GIGACHAT_CLIENT_ID"):
            test_gigachat_connection({"client_id": "", "client_secret": ""})

    def test_llama_endpoint_is_local_and_normalized(self):
        self.assertEqual(_base_url("http://127.0.0.1:8081"), "http://127.0.0.1:8081/v1")
        with self.assertRaises(ProviderError):
            _base_url("https://example.com/v1")

    def test_expensive_stage_requires_current_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            spec = draft_script(new_spec("Тема для проверки"))
            project = {"id": "test-project", "title": "Тема", "revision": 1, "spec": spec}
            quote = plan(project, "voice")
            project["revision"] += 1
            project["spec"]["intent"]["theme"] = "Изменённая тема"
            with self.assertRaisesRegex(ValueError, "изменился"):
                run(project, quote["id"], "voice")
            with self.assertRaisesRegex(ValueError, "Смета не найдена"):
                run(project, "", "voice")

    def test_demo_script_tracks_requested_duration(self):
        expected_lines = {30: 4, 45: 6, 60: 8, 90: 12, 120: 16}
        for seconds, count in expected_lines.items():
            with self.subTest(seconds=seconds):
                spec = draft_script(new_spec("Почему мы чихаем?", duration=seconds))
                timeline = timing_for(spec)
                self.assertEqual(len(timeline["lines"]), count)
                self.assertLessEqual(abs(timeline["total"] - seconds), seconds * 0.18 + 2)

    def test_render_requires_reviewed_intermediate_steps(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = {"id": "gate-project", "title": "Тема", "revision": 1,
                       "spec": draft_script(new_spec("Проверка подтверждений"))}
            with self.assertRaisesRegex(ValueError, "обновите и проверьте"):
                plan(project, "render", "draft")

    def test_scene_cache_invalidates_only_edited_scene(self):
        from factory.core import project_dir
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            spec = draft_script(new_spec("Кэш сцен"))
            project = {"id": "cache-project", "spec": spec}
            root = project_dir(project["id"])
            root.mkdir(parents=True)
            entries = {}
            for scene in spec["script"]["scenes"]:
                key = _segment_key(scene, spec, "draft")
                relative = f"segments/{scene['id']}.mp4"
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"cached")
                entries[f"{scene['id']}:{key}"] = {"key": key, "file": relative}
            (root / "segment-cache.json").write_text(json.dumps(entries), encoding="utf-8")
            self.assertEqual(_pending_scene_count(project, "draft"), 0)
            spec["script"]["scenes"][0]["lines"][0]["text"] += " Новая фраза."
            self.assertEqual(_pending_scene_count(project, "draft"), 1)

    def test_renderer_has_optional_inputs(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/build_ffmpeg_video.py"), "--help"],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        for option in ("--timing", "--voice", "--scene-titles", "--scene-bg-dir"):
            self.assertIn(option, result.stdout)


if __name__ == "__main__":
    unittest.main()
