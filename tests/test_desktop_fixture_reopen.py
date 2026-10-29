"""Same saved scope, no copying/reset/seeding; only synthetic data."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard.desktop_fixture import DesktopFixtureController
from eventguard.desktop_fixture_read import SavedFixtureStore


class DesktopFixtureReopenTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.name = 'desktop-ux-reopen'
        self.first = DesktopFixtureController(self.project, self.name)
        self.addCleanup(self.first.close)

    def test_same_database_preserves_status_case_marker_and_pending_without_seed(self):
        self.first.set_status('synthetic-ux-listener', 'handled', 'fixture-saved')
        self.first.investigate('synthetic-ux-listener')
        expected = self.first.inspect('synthetic-ux-listener')['investigation']['case']
        before = self.first.store.path.read_bytes()
        marker = (self.first.root/'fixture.json').read_bytes()
        self.first.close()
        with patch.object(DesktopFixtureController, '_prepare', side_effect=AssertionError('no reseed')):
            second = DesktopFixtureController(self.project, self.name, reopen=True)
        self.addCleanup(second.close)
        self.assertEqual(second.root, self.first.root)
        self.assertEqual(second.inspect('synthetic-ux-listener')['status'], 'handled')
        self.assertEqual(second.inspect('synthetic-ux-listener')['investigation']['case'], expected)
        self.assertEqual(second.store.path.read_bytes(), before)
        self.assertEqual((second.root/'fixture.json').read_bytes(), marker)
        self.assertEqual((second.store.stats()['pending'], second.store.stats()['receipt_count']), (4, 0))

    def test_active_owner_and_missing_scope_refused_without_data_changes(self):
        before = self.first.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_already_owned'):
            DesktopFixtureController(self.project, self.name, reopen=True)
        with self.assertRaisesRegex(ValueError, 'desktop_fixture_scope_invalid'):
            DesktopFixtureController(self.project, 'desktop-ux-missing', reopen=True)
        self.assertFalse((self.project/'reports/desktop-ux-missing').exists())
        self.assertEqual(self.first.store.path.read_bytes(), before)

    def test_revalidation_failure_releases_owner_without_repair(self):
        self.first.close()
        saved = SavedFixtureStore(self.first.root)
        with patch('eventguard.desktop_fixture.SavedFixtureStore', side_effect=[saved, ValueError('fixture changed')]):
            with self.assertRaisesRegex(ValueError, 'fixture changed'):
                DesktopFixtureController(self.project, self.name, reopen=True)
        second = DesktopFixtureController(self.project, self.name, reopen=True)
        self.addCleanup(second.close)
        self.assertTrue(second.snapshot()['synthetic_fixture'])
