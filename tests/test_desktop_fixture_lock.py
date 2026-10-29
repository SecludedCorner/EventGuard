"""Existing OS-backed instance lock on synthetic scopes, never PID termination."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard.desktop_fixture import DesktopFixtureController
from eventguard.runtime import InstanceLock, Runtime


class DesktopFixtureLockTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)

    def test_second_owner_rejected_until_controller_closes(self):
        fixture = DesktopFixtureController(self.project, 'desktop-ux-lock')
        self.addCleanup(fixture.close)
        lock = InstanceLock(Runtime(fixture.root))
        self.addCleanup(lock.release)
        before = fixture.store.path.read_bytes()
        self.assertFalse(lock.acquire())
        fixture.close()
        self.assertTrue(lock.acquire())
        self.assertEqual(fixture.store.path.read_bytes(), before)

    def test_preparation_failure_releases_only_own_lock(self):
        with patch.object(DesktopFixtureController, '_prepare', side_effect=ValueError('fixture prepare failed')):
            with self.assertRaisesRegex(ValueError, 'fixture prepare failed'):
                DesktopFixtureController(self.project, 'desktop-ux-partial')
        lock = InstanceLock(Runtime(self.project/'reports/desktop-ux-partial'))
        self.addCleanup(lock.release)
        self.assertTrue(lock.acquire())
