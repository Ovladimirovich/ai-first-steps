import unittest
from unittest.mock import patch

from factory.settings import agnes_image_runtime_config, load_settings


class AgnesImageRuntimeSettingsTests(unittest.TestCase):
    def test_runtime_is_disabled_by_default(self):
        with patch("factory.settings._local_env", return_value={}):
            config = agnes_image_runtime_config()
        self.assertFalse(config["agnes_image_runtime_enabled"])
        self.assertEqual(config["agnes_image_billing_mode"], "unknown")

    def test_runtime_requires_explicit_free_quota_and_opt_in(self):
        with patch("factory.settings._local_env", return_value={
                "AGNES_IMAGE_RUNTIME_ENABLED": "true",
                "AGNES_IMAGE_BILLING_MODE": "free_quota"}):
            config = agnes_image_runtime_config()
        self.assertTrue(config["agnes_image_runtime_enabled"])
        self.assertEqual(config["agnes_image_billing_mode"], "free_quota")

    def test_paid_or_unknown_mode_never_enables_runtime(self):
        for mode in ("unknown", "paid", "trial"):
            with self.subTest(mode=mode), patch("factory.settings._local_env", return_value={
                    "AGNES_IMAGE_RUNTIME_ENABLED": "true", "AGNES_IMAGE_BILLING_MODE": mode}):
                self.assertFalse(agnes_image_runtime_config()["agnes_image_runtime_enabled"])

    def test_runtime_status_is_exposed_read_only_in_settings(self):
        with patch("factory.settings._local_env", return_value={
                "AGNES_IMAGE_RUNTIME_ENABLED": "1", "AGNES_IMAGE_BILLING_MODE": "free_quota"}), \
             patch("factory.settings.SETTINGS_PATH") as settings_path:
            settings_path.read_text.side_effect = FileNotFoundError
            settings = load_settings()
        self.assertTrue(settings["agnes_image_runtime_enabled"])
        self.assertEqual(settings["agnes_image_billing_mode"], "free_quota")


if __name__ == "__main__":
    unittest.main()
