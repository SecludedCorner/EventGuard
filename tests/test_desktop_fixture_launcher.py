"""Labelled real Windows Job + synthetic Tk process; no participant simulated."""
import json
import os
import unittest
import uuid
from unittest.mock import patch

from scripts import desktop_ux_acceptance as launcher


class DesktopFixtureLauncherTests(unittest.TestCase):
    def test_invalid_parameters_never_spawn(self):
        with patch.object(launcher, 'spawn', side_effect=AssertionError('no process')):
            for name, seconds in (('../data/live', 1), ('desktop-ux-invalid', True), ('desktop-ux-invalid', 901)):
                with self.assertRaises(ValueError):
                    launcher.launch(name, seconds)

    @unittest.skipUnless(os.name == 'nt', 'real Windows owned Job required')
    def test_real_owned_job_natural_deadline_and_owner_eof(self):
        for seconds, cancel_after, reason in ((1, None, 'deadline'), (30, 1, 'owner_eof')):
            with self.subTest(reason=reason):
                name = 'desktop-ux-smoke-'+uuid.uuid4().hex
                result = launcher.launch(name, seconds, cancel_after=cancel_after)
                self.assertEqual(result['status'], 'synthetic_session_closed', result)
                self.assertEqual(result['worker']['reason'], reason)
                self.assertTrue(result['guardian']['managed'])
                self.assertTrue(result['guardian']['child_exited'])
                self.assertEqual(result['guardian']['remaining_owned_processes'], 0)
                self.assertFalse(result['guardian']['forcibly_terminated'])
                self.assertIsNone(result['participant_results'])
                root = launcher.ROOT/result['root']
                self.assertTrue(json.loads((root/'worker-ready.json').read_bytes())['membership_verified'])
                with self.assertRaises(FileExistsError):
                    launcher.launch(name, seconds)
