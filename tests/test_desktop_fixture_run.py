"""Synthetic worker lifecycle; membership is explicitly mocked in these tests."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch

from eventguard.desktop_fixture_run import run_fixture


class DesktopFixtureRunTests(unittest.TestCase):
    def test_invalid_duration_or_missing_membership_never_opens_data_or_tk(self):
        with patch('eventguard.desktop_fixture_run.DesktopFixtureController') as create, patch(
                'eventguard.desktop_fixture_run.adopt_current_job', side_effect=RuntimeError('fixture membership denied')):
            for seconds in (True, 0, 901):
                with self.assertRaisesRegex(ValueError, 'desktop_fixture_duration_invalid'):
                    run_fixture('not-read', seconds, 'not-a-job')
            with self.assertRaisesRegex(RuntimeError, 'fixture membership denied'):
                run_fixture('not-read', 1, 'not-a-job')
            create.assert_not_called()

    def test_real_tk_session_cooperatively_exits_on_owner_cancel(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        cancel = threading.Event()
        cancel.set()
        keeper = SimpleNamespace(receipt=lambda: {'kind': 'eventguard-private-job-keeper-v1'})
        with patch('eventguard.desktop_fixture_run.adopt_current_job', return_value=keeper), patch(
            'eventguard.processes.spawn', side_effect=AssertionError('no child/model')), patch(
            'eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no inventory')):
            result = run_fixture(root, 1, 'mock-membership', cancel=cancel)
        if result['state'] == 'unavailable' and result['reason'] in ('TclError', 'ImportError'):
            self.skipTest('own Tk unavailable')
        self.assertEqual((result['state'], result['reason']), ('closed', 'owner_eof'))
        self.assertTrue(result['gui_worker_exited'])
        self.assertIsNone(result['participant_results'])
        self.assertTrue((root/'worker-exit.json').is_file())
