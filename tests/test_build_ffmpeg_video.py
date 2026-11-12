import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

try:
    from PIL import Image
except ImportError:
    Image = None
from tools import build_ffmpeg_video


class MoviePyCompatibilityTests(unittest.TestCase):
    @unittest.skipIf(Image is None, "Pillow is optional in the system Python test environment")
    def test_approved_scene_image_is_rendered_full_bleed_not_as_old_center_template(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "scene.jpg"
            Image.new("RGB", (320, 180), (32, 112, 192)).save(source, quality=100)
            frame = build_ffmpeg_video.draw_full_bleed_scene(
                "A short clear caption", "b", "s1", source, W=320, H=180)
        self.assertEqual(frame.size, (320, 180))
        # Mid-frame remains the generated artwork's color; the legacy card renderer would replace it.
        center = frame.getpixel((160, 70))
        self.assertGreater(center[2], center[0] + 100)
        self.assertGreater(center[1], center[0] + 50)

    @unittest.skipIf(Image is None, "Pillow is optional in the system Python test environment")
    def test_static_scene_renderer_uses_each_selected_scene_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            Image.new("RGB", (320, 180), (32, 112, 192)).save(directory / "s2.jpg", quality=100)
            fallback = directory / "fallback.jpg"
            Image.new("RGB", (320, 180), (210, 36, 28)).save(fallback, quality=100)
            frame = build_ffmpeg_video.render_static_scene_frame(
                "A short clear caption", "m", "s2", scene_bg_dir=directory,
                fallback_bg=fallback, W=320, H=180)
        center = frame.getpixel((160, 70))
        self.assertGreater(center[2], center[0] + 100)
        self.assertGreater(center[1], center[0] + 50)

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
