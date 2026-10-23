"""Opt-in fixtures only: no model, native collection or installed executable."""
import json
from pathlib import Path
import tempfile
import unittest

from eventguard import agent_automation as settings


class AutomationSettingsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_default_read_creates_no_configuration(self):
        self.assertFalse(settings.status(self.root)["enabled"])
        self.assertFalse((self.root / "data").exists())

    def test_explicit_native_path_is_saved_but_never_executed(self):
        executable = self.root / "codex.exe"
        executable.write_bytes(b"inert fixture only")
        self.assertTrue(settings.set_enabled(self.root, True, str(executable))["enabled"])
        self.assertEqual(settings.status(self.root)["executable"], str(executable.resolve()))
        self.assertFalse(settings.set_enabled(self.root, False)["enabled"])
        self.assertEqual(settings.status(self.root)["executable"], str(executable.resolve()))

    def test_wrappers_missing_files_and_control_characters_are_refused(self):
        for name in ("codex.cmd", "codex.ps1", "codex.bat", "missing.exe", "codex\n.exe"):
            path = self.root / name
            if name not in {"missing.exe", "codex\n.exe"}:
                path.write_bytes(b"inert fixture only")
            with self.assertRaises(ValueError):
                settings.set_enabled(self.root, True, str(path))
        self.assertFalse(settings.status(self.root)["enabled"])

    def test_tampered_setting_never_enables_automation(self):
        path = self.root / settings.PATH
        path.parent.mkdir(parents=True)
        for value in ({"enabled": True}, {"kind": settings.KIND, "enabled": True,
            "executable": "codex.exe", "updated_at": "not a timestamp"}):
            path.write_text(json.dumps(value), encoding="utf-8")
            result = settings.status(self.root)
            self.assertFalse(result["enabled"])
            self.assertTrue(result["blocked"])

    def test_non_boolean_opt_in_cannot_be_coerced(self):
        with self.assertRaises(ValueError):
            settings.set_enabled(self.root, "true")
