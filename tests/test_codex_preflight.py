"""Synthetic receipts only; no CLI, host or model launched by these tests."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard import codex_preflight as preflight
from eventguard.acceptance_control import write_json
from eventguard.acceptance_process import launch_hash


class CodexPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.argv = [self.root/'codex-code-mode-host.exe', '--listen', 'stdio']
        self.token, self.stamp = 'a'*32, '2026-10-30T00:00:00+00:00'
        self.receipt = dict(attempt_id=self.token, codex_pid=42, capture_complete=True,
            codex_exit_code=0, stdout_truncated=False, stderr_truncated=False,
            forcibly_terminated=False, child_exited=True, stop_reason='descendants_remaining',
            process=dict(managed=True, pid=42, created_at=self.stamp, child_exited=True, exit_code=0,
                remaining_owned_processes=0, forcibly_terminated=False, reason='natural_exit',
                shutdown_requested_reason='descendants_remaining'))
        write_json(self.root/'capture-launch-intent.json', dict(kind='eventguard-capture-launch-intent-v1',
            attempt_id=self.token, launch_hash=launch_hash(self.argv, '')))
        write_json(self.root/'capture-start.json', dict(attempt_id=self.token, codex_pid=42, created_at=self.stamp))
        write_json(self.root/'capture-exit.json', self.receipt)
        for name in ('codex.jsonl', 'codex.stderr.txt'):
            (self.root/name).write_bytes(b'')

    def check(self):
        return preflight.checked_probe(self.root, 'host-stdio', self.argv)

    def test_successful_capture_is_not_successful_host_exit(self):
        self.assertEqual(set(self.check()[0]), set(preflight.ARTIFACTS))
        for field, value in [('codex_exit_code', 1), ('stdout_truncated', True),
                             ('forcibly_terminated', True), ('capture_complete', False)]:
            with self.subTest(field=field):
                receipt = copy.deepcopy(self.receipt)
                receipt[field] = value
                write_json(self.root/'capture-exit.json', receipt)
                with self.assertRaisesRegex(ValueError, 'process_not_verified'):
                    self.check()

    def test_wrong_command_and_host_output_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'process_not_verified'):
            preflight.checked_probe(self.root, 'host-stdio', [*self.argv, '--changed'])
        (self.root/'codex.stderr.txt').write_text('host failed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'output_not_verified'):
            self.check()

    def test_missing_bundle_never_creates_preflight_or_launches(self):
        with patch.object(preflight, 'capture') as capture:
            with self.assertRaises(ValueError):
                preflight.run(self.root/'codex.exe')
            capture.assert_not_called()
        self.assertFalse((self.root/'preflight').exists())
