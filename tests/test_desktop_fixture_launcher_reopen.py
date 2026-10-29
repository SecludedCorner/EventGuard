"""Real Job/Tk reopen routing; saves between runs are explicitly controller calls."""
import os
import unittest
import uuid

from eventguard.desktop_fixture import DesktopFixtureController
from scripts import desktop_ux_acceptance as launcher


@unittest.skipUnless(os.name == 'nt', 'real Windows owned Job required')
class DesktopFixtureLauncherReopenTests(unittest.TestCase):
    def test_same_source_new_attempt_keeps_old_evidence_and_refuses_active_owner(self):
        first_name = 'desktop-ux-origin-'+uuid.uuid4().hex
        first = launcher.launch(first_name, 1)
        self.assertEqual(first['status'], 'synthetic_session_closed')
        source = launcher.ROOT/first['root']
        old = {p: (source/p).read_bytes() for p in ('guardian-exit.json', 'worker-exit.json', 'session-result.json')}
        controller = DesktopFixtureController(source, 'desktop-ux-session', reopen=True)
        self.addCleanup(controller.close)
        controller.set_status('synthetic-ux-listener', 'handled', 'fixture-launcher-save')
        controller.investigate('synthetic-ux-listener')
        before = controller.store.path.read_bytes()
        rejected = launcher.launch('desktop-ux-busy-'+uuid.uuid4().hex, 1, reopen_from=first_name)
        self.assertEqual(rejected['status'], 'unconfirmed')
        self.assertEqual(rejected['worker']['reason'], 'desktop_fixture_already_owned')
        self.assertEqual(controller.store.path.read_bytes(), before)
        controller.close()
        second = launcher.launch('desktop-ux-reopen-'+uuid.uuid4().hex, 1, reopen_from=first_name)
        self.assertEqual(second['status'], 'synthetic_session_closed', second)
        self.assertEqual(second['worker']['scope_parent'], first_name)
        self.assertTrue(second['worker']['reopened'])
        self.assertEqual(controller.store.path.read_bytes(), before)
        self.assertTrue(all((source/p).read_bytes() == value for p, value in old.items()))
        self.assertFalse((launcher.ROOT/second['root']/'reports/desktop-ux-session').exists())

    def test_invalid_or_missing_source_never_creates_a_substitute_database(self):
        name = 'desktop-ux-missing-'+uuid.uuid4().hex
        result = launcher.launch('desktop-ux-attempt-'+uuid.uuid4().hex, 1, reopen_from=name)
        self.assertEqual(result['status'], 'unconfirmed')
        self.assertEqual(result['worker']['reason'], 'desktop_fixture_scope_invalid')
        self.assertFalse((launcher.ROOT/'reports'/name).exists())
