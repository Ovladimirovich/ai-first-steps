import json
import importlib.util
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.core import create_project, draft_script, load_project, project_dir, save_project
from factory.pipeline import _atempo_filter, _make_voice
from factory.settings import save_settings
from factory.voice import VoiceProviderError, check_piper_settings


FAKE_PIPER = r'''#!/usr/bin/env python3
import argparse, math, struct, sys, wave
parser = argparse.ArgumentParser()
parser.add_argument('--model', required=True)
parser.add_argument('--output_file', required=True)
args = parser.parse_args()
text = sys.stdin.read()
if not text.strip():
    sys.exit(3)
rate = 16000
frames = int(rate * 0.45)
with wave.open(args.output_file, 'wb') as audio:
    audio.setnchannels(1)
    audio.setsampwidth(2)
    audio.setframerate(rate)
    audio.writeframes(b''.join(struct.pack('<h', int(1800 * math.sin(2 * math.pi * 220 * i / rate))) for i in range(frames)))
'''


class PiperVoiceTests(unittest.TestCase):
    def _fake_models(self, root: Path):
        models = {}
        for hero in ("h1", "h2"):
            model = root / f"{hero}.onnx"
            model.write_bytes(b"test model placeholder")
            Path(str(model) + ".json").write_text("{}", encoding="utf-8")
            models[f"piper_model_{hero}"] = str(model)
        return models

    def _fake_executable(self, root: Path) -> Path:
        executable = root / "fake-piper"
        executable.write_text(FAKE_PIPER, encoding="utf-8")
        if os.name == "nt":
            # On Windows, wrap the Python script in a .bat launcher
            bat = root / "fake-piper.bat"
            bat.write_text(f'@echo off\n{sys.executable} "{executable}" %*\n', encoding="utf-8")
            executable = bat
        else:
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return executable

    def test_piper_settings_synthesize_local_samples_for_both_voices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            models = self._fake_models(root)
            result = check_piper_settings({"piper_executable": str(self._fake_executable(root)), **models})
        self.assertTrue(result["connected"])
        self.assertEqual(set(result["voices"]), {"h1", "h2"})
        self.assertGreater(result["voices"]["h1"]["sample_duration_s"], 0)

    def test_piper_settings_reject_missing_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "h1.onnx"
            model.write_bytes(b"model")
            with self.assertRaisesRegex(VoiceProviderError, "файл настроек"):
                check_piper_settings({"piper_executable": str(self._fake_executable(root)),
                                     "piper_model_h1": str(model), "piper_model_h2": str(model)})

    @unittest.skipUnless(importlib.util.find_spec("imageio_ffmpeg"), "optional renderer dependency imageio-ffmpeg is not installed")
    def test_piper_voice_stage_creates_speech_assets_and_mixed_track(self):
        with tempfile.TemporaryDirectory() as tmp, patch("factory.core.DATA_ROOT", Path(tmp)):
            root = Path(tmp)
            models = self._fake_models(root)
            executable = self._fake_executable(root)
            project = create_project({"theme": "Проверка локального голоса", "duration": 30})
            project["spec"] = draft_script(project["spec"])
            project["revision"] += 1
            save_project(project)
            project = load_project(project["id"])
            settings = {"voice_provider": "piper", "piper_executable": str(executable), **models}
            job = {"id": "voice-test-job", "project_id": project["id"], "log": []}
            with patch("factory.settings.load_settings", return_value=settings), \
                 patch("factory.pipeline.is_cancel_requested", return_value=False), \
                 patch("factory.pipeline.persist_job"), \
                 patch("factory.pipeline.job_checkpoint"):
                _make_voice(project, job)
            directory = project_dir(project["id"])
            meta = json.loads((directory / "voice.meta.json").read_text(encoding="utf-8"))
            cache = json.loads((directory / "voice-cache.json").read_text(encoding="utf-8"))
            timing = json.loads((directory / "timing.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["provider"], "piper")
            self.assertFalse(meta["demo"])
            self.assertTrue((directory / "audio" / "voice_track.mp3").is_file())
            self.assertTrue((directory / "subtitles.srt").is_file())
            self.assertTrue(all(item.get("source_duration_s", 0) > 0 for item in cache.values()))
            self.assertEqual(len(timing["lines"]), len(cache))
            self.assertTrue(any("Piper-озвучка готова" in line for line in job["log"]))

    def test_atempo_filter_supports_long_duration_corrections(self):
        self.assertEqual(_atempo_filter(1.0), "atempo=1.000000")
        self.assertEqual(_atempo_filter(4.0), "atempo=2.000000,atempo=2.000000")
        self.assertEqual(_atempo_filter(0.25), "atempo=0.500000,atempo=0.500000")

    def test_settings_persist_optional_piper_configuration(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("factory.settings.SETTINGS_PATH", Path(tmp) / "settings.json"), \
             patch("factory.settings.ENV_PATH", Path(tmp) / "missing.env"):
            saved = save_settings({"voice_provider": "piper", "piper_executable": "piper.exe",
                                   "piper_model_h1": "C:/voices/bit.onnx", "piper_model_h2": "C:/voices/masha.onnx"})
            self.assertEqual(saved["voice_provider"], "piper")
            self.assertEqual(saved["piper_model_h1"], "C:/voices/bit.onnx")
            persisted = json.loads((Path(tmp) / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["piper_model_h2"], "C:/voices/masha.onnx")


if __name__ == "__main__":
    unittest.main()
