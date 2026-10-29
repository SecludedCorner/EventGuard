"""An open real Tk owner rejects another process; no PID-based cleanup."""
from concurrent.futures import ThreadPoolExecutor
import os
import time
import unittest
import uuid

from scripts import desktop_ux_acceptance as launcher


@unittest.skipUnless(os.name == 'nt', 'real Windows owned Job required')
class DesktopFixtureConcurrentGuiTests(unittest.TestCase):
    def assert_natural(self, result, exit_code):
        receipt = result['guardian']
        self.assertTrue(receipt['managed'])
        self.assertTrue(receipt['child_exited'])
        self.assertEqual(receipt['exit_code'], exit_code)
        self.assertEqual(receipt['remaining_owned_processes'], 0)
        self.assertFalse(receipt['forcibly_terminated'])

    def test_second_gui_refused_while_first_is_open_then_reopen_after_exit(self):
        name = 'desktop-ux-concurrent-'+uuid.uuid4().hex
        root = launcher.scope_path(name)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(launcher.launch, name, 8)
            ready = root/'worker-ready.json'
            deadline = time.monotonic()+6
            while not ready.exists() and not future.done() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(ready.exists(), root)
            self.assertFalse(future.done(), 'first GUI must still own the scope')
            saved_ready = ready.read_bytes()
            # Use the validated read view to locate the actual store, never initialize one.
            from eventguard.desktop_fixture_read import SavedFixtureStore
            view = SavedFixtureStore(root/'reports/desktop-ux-session')
            db = view.path
            saved_db = db.read_bytes()
            refused = launcher.launch('desktop-ux-contender-'+uuid.uuid4().hex, 1, reopen_from=name)
            self.assertEqual(refused['status'], 'unconfirmed')
            self.assertEqual(refused['worker']['state'], 'blocked')
            self.assertEqual(refused['worker']['reason'], 'desktop_fixture_already_owned')
            self.assert_natural(refused, 2)
            self.assertFalse((launcher.ROOT/refused['root']/'worker-ready.json').exists())
            self.assertFalse(future.done(), 'refusal must occur during the first GUI session')
            self.assertEqual(ready.read_bytes(), saved_ready)
            self.assertEqual(db.read_bytes(), saved_db)
            first = future.result(timeout=15)
        self.assertEqual(first['status'], 'synthetic_session_closed')
        self.assert_natural(first, 0)
        original = {p: (root/p).read_bytes() for p in ('worker-ready.json', 'worker-exit.json', 'guardian-exit.json')}
        reopened = launcher.launch('desktop-ux-after-owner-'+uuid.uuid4().hex, 1, reopen_from=name)
        self.assertEqual(reopened['status'], 'synthetic_session_closed')
        self.assert_natural(reopened, 0)
        self.assertTrue(all((root/p).read_bytes() == data for p, data in original.items()))
        self.assertEqual(db.read_bytes(), saved_db)
        stats = view.stats()
        self.assertEqual((stats['pending'], stats['receipt_count']), (4, 0))
        self.assertIsNone(reopened['participant_results'])
