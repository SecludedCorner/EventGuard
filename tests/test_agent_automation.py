"""Opt-in fixtures only: no model, native collection or installed executable."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
        for change in (settings.set_enabled, settings.configure):
            with self.assertRaises(ValueError):
                change(self.root, "true")

    def test_shared_configuration_requires_receive_gate_but_never_starts(self):
        from eventguard.agent_access import set_enabled
        self.assertEqual(settings.describe(self.root)["state"], "available")
        self.assertFalse((self.root / "data").exists())
        native = self.root / "fixture.exe"
        native.write_bytes(b"inert fixture, never execute")
        denied = settings.configure(self.root, True, str(native))
        self.assertEqual(denied["reason"], "agent_receive_permission_required")
        self.assertFalse(denied["setting_saved"])
        self.assertFalse((self.root / settings.PATH).exists())
        set_enabled(self.root, True)
        saved = settings.configure(self.root, True, str(native))
        self.assertTrue(saved["enabled"])
        self.assertTrue(saved["setting_saved"])
        self.assertEqual(saved["dispatcher_state"], "not_verified")
        self.assertIsNone(saved["child_exited"])
        self.assertEqual(saved["model_calls"], 0)
        self.assertFalse(settings.configure(self.root, False)["enabled"])
        self.assertEqual({p.name for p in (self.root / "data").iterdir()}, {"agent-delivery.json", "agent-automation.json"})

    def test_failed_disable_preserves_actual_setting_and_omits_raw_error(self):
        native = self.root / "fixture.exe"
        native.write_bytes(b"inert")
        settings.set_enabled(self.root, True, str(native))
        before = (self.root / settings.PATH).read_bytes()
        with patch.object(settings, "atomic_json", side_effect=OSError("SYNTHETIC_PRIVATE")):
            value = settings.configure(self.root, False)
        self.assertTrue(value["enabled"])
        self.assertFalse(value["setting_saved"])
        self.assertEqual(value["state"], "blocked")
        self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(value))
        self.assertEqual((self.root / settings.PATH).read_bytes(), before)
