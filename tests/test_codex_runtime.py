"""Fake PE bytes only; no executables, host, network or model is launched."""
from pathlib import Path
import tempfile
import unittest

from eventguard.codex_runtime import REQUIRED, inventory, snapshot


class CodexRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'installed'
        self.source.mkdir()
        for name in REQUIRED:
            (self.source/name).write_bytes(b'MZ-FAKE-NOT-EXECUTABLE-'+name.encode())

    def test_main_executable_alone_is_rejected_before_snapshot_creation(self):
        (self.source/'codex-code-mode-host.exe').unlink()
        with self.assertRaisesRegex(ValueError, 'bundle_incomplete'):
            snapshot(self.source/'codex.exe', self.root/'copy')
        self.assertFalse((self.root/'copy').exists())

    def test_whole_bundle_is_copied_without_modifying_source_or_overwriting(self):
        expected = inventory(self.source/'codex.exe')
        result = snapshot(self.source/'codex.exe', self.root/'copy')
        self.assertEqual(result, expected)
        self.assertEqual(inventory(self.source/'codex.exe'), expected)
        self.assertEqual(inventory(self.root/'copy/codex.exe'), expected)
        with self.assertRaises(FileExistsError):
            snapshot(self.source/'codex.exe', self.root/'copy')
        (self.root/'copy/codex-code-mode-host.exe').write_bytes(b'MZ-CHANGED')
        self.assertNotEqual(inventory(self.root/'copy/codex.exe'), expected)

    def test_empty_invalid_or_unrecognized_layout_fails_closed(self):
        for payload in (b'', b'not-PE'):
            (self.source/'codex-code-mode-host.exe').write_bytes(payload)
            with self.assertRaises(ValueError):
                inventory(self.source/'codex.exe')
        (self.source/'codex-code-mode-host.exe').write_bytes(b'MZ-FAKE')
        (self.source/'new-resource').mkdir()
        with self.assertRaisesRegex(ValueError, 'layout_unrecognized'):
            snapshot(self.source/'codex.exe', self.root/'copy')
        self.assertFalse((self.root/'copy').exists())
