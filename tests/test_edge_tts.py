import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory import tts_edge
from factory.core import create_project, draft_script, load_project, save_project
from factory.fingerprints import _dep_hashes, load_project_fingerprint_inputs, project_fingerprints
from factory.schema_v2 import v2_to_v1
from factory.pipeline import _make_voice
from factory.settings import save_settings
from factory.timing import timing_for
from factory.tts_edge import (check_edge_settings, edge_rate, edge_service_rate,
                              edge_signature, edge_voice, synthesize_edge_line)
from factory.voice import VoiceProviderError

FAKE_MP3 = b"ID3\x04\x00" + b"\x00" * 2048


def _install_fake_edge_tts(failures: int):
    """Install a fake edge_tts module that fails ``failures`` times per stream."""
    state = {"calls": 0}

    class FakeCommunicate:
        def __init__(self, text, voice, rate="+0%"):
            self.text = text
            self.voice = voice
            self.rate = rate
            state["last_rate"] = rate

        async def stream(self):
            state["calls"] += 1
            if state["calls"] <= failures:
                raise RuntimeError("NoAudioReceived (fake)")
            yield {"type": "audio", "data": FAKE_MP3}

    module = types.ModuleType("edge_tts")
    module.Communicate = FakeCommunicate
    sys.modules["edge_tts"] = module
    return state


class EdgeSynthTests(unittest.TestCase):
    def test_synthesize_edge_line_retries_until_success(self):
        state = _install_fake_edge_tts(failures=2)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(tts_edge.time, "sleep", lambda *_: None):
            out = Path(tmp) / "line.mp3"
            synthesize_edge_line({}, "h1", "Привет", out)
            self.assertEqual(out.read_bytes(), FAKE_MP3)
            self.assertEqual(state["calls"], 3)
            # Дефолтная «+0%» отправляется в edge-tts как «+1%» (сервис не
            # отвечает на точный ноль скорости).
            self.assertEqual(state["last_rate"], "+1%")

    def test_synthesize_edge_line_fails_after_all_retries(self):
        _install_fake_edge_tts(failures=99)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(tts_edge.time, "sleep", lambda *_: None):
            out = Path(tmp) / "line.mp3"
            with self.assertRaisesRegex(VoiceProviderError, "после 3 попыток"):
                synthesize_edge_line({}, "h1", "Привет", out, attempts=3)
            self.assertFalse(out.is_file())

    def test_synthesize_edge_line_polls_cancelled_during_backoff(self):
        _install_fake_edge_tts(failures=99)
        polls = {"count": 0}

        def cancelled():
            polls["count"] += 1
            if polls["count"] >= 5:
                raise RuntimeError("job cancelled")

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(tts_edge.time, "sleep", lambda *_: None):
            out = Path(tmp) / "line.mp3"
            with self.assertRaisesRegex(RuntimeError, "job cancelled"):
                synthesize_edge_line({}, "h1", "Hello", out, cancelled=cancelled, attempts=3)
            # ``cancelled`` must be polled during backoff chunks, not only at
            # attempt boundaries (old behaviour polled exactly 3 times).
            self.assertGreater(polls["count"], 3)
            self.assertFalse(out.is_file())

    def test_check_edge_settings_creates_samples(self):
        _install_fake_edge_tts(failures=0)
        with tempfile.TemporaryDirectory() as tmp:
            sample_dir = Path(tmp)
            result = check_edge_settings({}, sample_dir)
            self.assertEqual(result["provider"], "edge-tts")
            for hero in ("h1", "h2"):
                self.assertEqual(result["voices"][hero]["sample_url"],
                                 f"/api/settings/voice/samples/{hero}.mp3")
                self.assertEqual((sample_dir / f"{hero}.mp3").read_bytes(), FAKE_MP3)

    def test_voice_and_rate_helpers_use_defaults(self):
        self.assertEqual(edge_voice({}, "h1"), "ru-RU-DmitryNeural")
        self.assertEqual(edge_voice({}, "h2"), "ru-RU-SvetlanaNeural")
        self.assertEqual(edge_rate({}, "h1"), "+0%")
        self.assertEqual(edge_rate({}, "h2"), "-10%")
        # edge-tts требует явный знак: беззнаковые значения приводятся к «+N%».
        self.assertEqual(edge_rate({"edge_rate_h1": "5%"}, "h1"), "+5%")
        self.assertEqual(edge_rate({"edge_rate_h1": "+5%"}, "h1"), "+5%")
        self.assertEqual(edge_rate({"edge_rate_h2": "-3%"}, "h2"), "-3%")
        self.assertEqual(edge_service_rate(edge_rate({}, "h1")), "+1%")
        self.assertEqual(edge_service_rate("+5%"), "+5%")
        self.assertEqual(edge_service_rate("-10%"), "-10%")
        self.assertEqual(edge_voice({"edge_voice_h1": "ru-RU-Any"}, "h1"), "ru-RU-Any")


class EdgeSettingsTests(unittest.TestCase):
    def test_save_settings_accepts_edge_provider_and_rates(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("factory.settings.SETTINGS_PATH", Path(tmp) / "settings.json"), \
                 patch("factory.settings.ENV_PATH", Path(tmp) / "missing.env"):
                saved = save_settings({"voice_provider": "edge", "edge_rate_h2": "-15%"})
                self.assertEqual(saved["voice_provider"], "edge")
                self.assertEqual(saved["edge_rate_h2"], "-15%")
                self.assertEqual(saved["edge_rate_h1"], "+0%")
                self.assertEqual(save_settings({"voice_provider": "edge", "edge_rate_h1": "7%"})["edge_rate_h1"], "+7%")
                with self.assertRaisesRegex(ValueError, "процентами"):
                    save_settings({"voice_provider": "edge", "edge_rate_h1": "быстро"})
                with self.assertRaisesRegex(ValueError, "Piper"):
                    save_settings({"voice_provider": "azure"})
                self.assertEqual(save_settings({"voice_provider": "piper"})["voice_provider"], "piper")


class EdgeFingerprintTests(unittest.TestCase):
    def test_voice_line_fingerprints_include_edge_runtime(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Edge fingerprint", "duration": 30})
            project["spec"] = draft_script(project["spec"])
            project["revision"] += 1
            save_project(project)
            project = load_project(project["id"])
            settings = {"voice_provider": "edge"}
            with patch("factory.settings.load_settings", return_value=settings):
                data = project_fingerprints(project)
            self.assertTrue(data["voice_lines"])

            # Dependency values are SHA-256 hashes of the exact inputs, so rebuild
            # the same inputs with the edge runtime signature and compare hashes.
            story, production, manifest, root = load_project_fingerprint_inputs(project)
            timing = timing_for(v2_to_v1(story, production, manifest))
            rows = {str(row.get("id", "")): row for row in timing.get("lines", [])}
            hero_voices = production.get("hero_voices", {})
            dialogue = production.get("dialogue", {})
            for scene in story.get("script", {}).get("scenes", []):
                for line in scene.get("lines", []):
                    line_id = str(line.get("id", ""))
                    self.assertIn(line_id, data["voice_lines"])
                    hero_id = str(line.get("hero", ""))
                    provider_generation = {
                        "voice_generation": production.get("voice_generation", production.get("tts", {})),
                        "models": production.get("models", {}),
                        "providers": production.get("providers", {}),
                        "voice_prompt_template": production.get("voice_prompt_template", ""),
                    }
                    runtime = edge_signature(settings, hero_id)
                    self.assertEqual(runtime["provider"], "edge-tts")
                    self.assertIn("version", runtime)
                    provider_generation["runtime_voice"] = runtime
                    expected = _dep_hashes(
                        line_content={"line_id": line_id, "text": line.get("text", ""), "hero_id": hero_id},
                        voice_selection=hero_voices.get(hero_id, {}),
                        line_delivery=dialogue.get(line_id, {}),
                        provider_model_and_generation=provider_generation,
                        duration_and_parameters={"duration_s": rows.get(line_id, {}).get("dur"),
                                                 "engine": "factory-edge-tts-v1"},
                    )
                    deps = data["voice_lines"][line_id]["dependencies"]
                    self.assertEqual(deps, expected)


class EdgePipelineTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("imageio_ffmpeg"),
                         "optional renderer dependency imageio-ffmpeg is not installed")
    def test_edge_voice_stage_creates_assets_and_mixed_track(self):
        import imageio_ffmpeg

        def write_silence_mp3(settings, hero_id, text, out_path, cancelled=None, attempts=None):
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            subprocess.run([exe, "-y", "-f", "lavfi", "-i",
                            "anullsrc=channel_layout=mono:sample_rate=44100", "-t", "4.0",
                            "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-q:a", "9",
                            str(out_path)], check=True, capture_output=True)

        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            project = create_project({"theme": "Edge voice stage", "duration": 30})
            project["spec"] = draft_script(project["spec"])
            project["revision"] += 1
            save_project(project)
            project = load_project(project["id"])
            settings = {"voice_provider": "edge"}
            job = {"id": "edge-voice-job", "project_id": project["id"], "log": []}
            with patch("factory.settings.load_settings", return_value=settings), \
                 patch("factory.pipeline.is_cancel_requested", return_value=False), \
                 patch("factory.pipeline.persist_job"), \
                 patch("factory.pipeline.job_checkpoint"), \
                 patch("factory.tts_edge.synthesize_edge_line", side_effect=write_silence_mp3):
                _make_voice(project, job)
            from factory.core import project_dir
            directory = project_dir(project["id"])
            meta = json.loads((directory / "voice.meta.json").read_text(encoding="utf-8"))
            cache = json.loads((directory / "voice-cache.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["provider"], "edge")
            self.assertFalse(meta["demo"])
            self.assertTrue((directory / "audio" / "voice_track.mp3").is_file())
            self.assertTrue(all(item.get("source_duration_s", 0) > 0 for item in cache.values()))
            self.assertTrue(any("Edge-озвучка готова" in line for line in job["log"]))


if __name__ == "__main__":
    unittest.main()
