"""Tests for factory.storage.atomic_write_json.

Covers the Windows PermissionError fallback path: os.replace raises,
direct write succeeds, and no leftover .tmp file remains.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from factory.storage import atomic_write_json


class AtomicWriteJsonTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.target = self.tmpdir / "data.json"

    def tearDown(self):
        for p in self.tmpdir.iterdir():
            try:
                p.unlink()
            except OSError:
                pass
        try:
            self.tmpdir.rmdir()
        except OSError:
            pass

    def _count_tmp(self):
        return len([p for p in self.tmpdir.iterdir() if p.suffix == ".tmp"])

    def test_normal_write_is_atomic_and_no_tmp_left(self):
        atomic_write_json(self.target, {"key": "value"})
        self.assertTrue(self.target.is_file())
        self.assertEqual(json.loads(self.target.read_text(encoding="utf-8")), {"key": "value"})
        self.assertEqual(self._count_tmp(), 0)

    @unittest.skipIf(sys.platform != "win32", "Windows-only fallback path")
    @patch("factory.storage.os.replace")
    def test_permission_error_fallback_direct_write_and_no_tmp_left(self, mock_replace):
        """os.replace raises PermissionError -> direct write -> file OK, no .tmp leftover."""
        mock_replace.side_effect = PermissionError("locked")

        atomic_write_json(self.target, {"key": "value"})

        # File was written via direct-write fallback
        self.assertTrue(self.target.is_file())
        self.assertEqual(json.loads(self.target.read_text(encoding="utf-8")), {"key": "value"})
        # os.replace was actually called and raised
        mock_replace.assert_called_once()
        # No temporary file left behind
        self.assertEqual(self._count_tmp(), 0)

    @unittest.skipIf(sys.platform == "win32", "Non-Windows path: PermissionError should propagate")
    @patch("factory.storage.os.replace")
    def test_permission_error_on_non_windows_re_raises(self, mock_replace):
        """On non-Windows, PermissionError from os.replace should propagate."""
        mock_replace.side_effect = PermissionError("locked")
        with self.assertRaises(PermissionError):
            atomic_write_json(self.target, {"key": "value"})


if __name__ == "__main__":
    unittest.main()
