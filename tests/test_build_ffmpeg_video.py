import sys
import unittest
from unittest.mock import call, patch

from tools import build_ffmpeg_video


class MoviePyCompatibilityTests(unittest.TestCase):
    def test_legacy_renderer_pins_moviepy_1x_when_editor_api_is_missing(self):
        sentinel = object()
        imports = [ImportError("moviepy.editor is unavailable in MoviePy 2.x"), sentinel]
        with patch.object(build_ffmpeg_video, "import_module", side_effect=imports) as importer, \
             patch.object(build_ffmpeg_video.subprocess, "run") as installer:
            result = build_ffmpeg_video.load_moviepy_editor()

        self.assertIs(result, sentinel)
        self.assertEqual(importer.call_args_list, [call("moviepy.editor")] * 2)
        installer.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "-q", "moviepy==1.0.3"], check=True)

    def test_legacy_renderer_does_not_install_when_compatible_api_is_available(self):
        sentinel = object()
        with patch.object(build_ffmpeg_video, "import_module", return_value=sentinel) as importer, \
             patch.object(build_ffmpeg_video.subprocess, "run") as installer:
            result = build_ffmpeg_video.load_moviepy_editor()

        self.assertIs(result, sentinel)
        importer.assert_called_once_with("moviepy.editor")
        installer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
