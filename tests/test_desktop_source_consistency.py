"""Synthetic saved observations override stale overview source rows; no scan."""
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from eventguard.desktop import DesktopController
from eventguard.gui import view_snapshot
from eventguard.runtime import Runtime

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class DesktopSourceConsistencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root/'config').mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[1]/'config/default.json', self.root/'config/default.json')
        self.runtime = Runtime(self.root)
        self.controller = DesktopController(self.root)
        self.controller.api = Mock()
        self.controller.api.call.return_value = {'source_coverage': {'defender': {
            'status': 'ok', 'row_count': 99, 'observed_at': NOW.isoformat(), 'freshness': {'state': 'fresh'}}}}
        self.enterContext(patch('eventguard.source_status._now', return_value=NOW))
        self.enterContext(patch('eventguard.runtime.utc_now', return_value=NOW.isoformat(timespec='seconds')))
        self.enterContext(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')))

    def save(self, status, seconds, namespace='live'):
        at = (NOW+timedelta(seconds=seconds)).isoformat(timespec='seconds')
        self.runtime.save_observation({'id': 'defender', 'status': status, 'rows': [], 'observed_at': at,
            'coverage': {'status': status, 'errors': [] if status == 'ok' else [
                {'stage': 'provider', 'status': status, 'reason_code': 'access_denied'}]}}, namespace)
        return at

    def read(self):
        def hashes():
            return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.root.rglob('*') if p.is_file()}
        before = hashes()
        value = self.controller.snapshot()
        self.assertEqual(before, hashes())
        return value['sources'][0], dict(view_snapshot(value)['sources'])['defender']

    def test_new_denial_and_its_reason_replace_old_success_overview(self):
        success = self.save('ok', -50)
        denied = self.save('denied', -5)
        source, row = self.read()
        self.assertEqual((source['status'], source['row_count'], source['observed_at']), ('denied', 0, denied))
        self.assertEqual(source['last_success_at'], success)
        self.assertEqual(source['reason'], 'access_denied')
        self.assertEqual(source['stage'], 'provider')
        self.assertEqual(row[1:4], ('拒讀', '0', '新鮮'))

    def test_stale_denial_retains_history_without_claiming_current_coverage(self):
        success = self.save('ok', -1000)
        self.save('denied', -900)
        source, row = self.read()
        self.assertEqual(source['current_coverage'], 'unknown')
        self.assertEqual(row[1:4], ('拒讀', '0', '過期'))
        self.assertEqual(source['last_success_at'], success)

    def test_test_namespace_success_cannot_supply_live_source_state(self):
        self.save('ok', -5, 'test')
        source, row = self.read()
        self.assertEqual(source['status'], 'not_observed')
        self.assertEqual(source['last_success_state'], 'unknown')
        self.assertEqual(row[1], '尚無觀察')
        self.assertEqual(row[3], '狀態未知')

    def test_persistence_failure_is_not_replaced_by_saved_ok_result(self):
        success = self.save('ok', -50)
        self.runtime.save_health({'namespace': 'live', 'coverage': {'defender': {
            'status': 'ok', 'observed_at': (NOW-timedelta(seconds=5)).isoformat(), 'row_count': 0,
            'observation_error': 'observation_persistence_failed'}}})
        source, row = self.read()
        self.assertEqual(source['status'], 'error')
        self.assertEqual(source['last_success_at'], success)
        self.assertEqual(row[1], '讀取失敗')

    def test_corrupt_saved_observation_never_falls_back_to_old_overview_success(self):
        self.save('ok', -5)
        (self.root/'data/live/observations/defender.json').write_bytes(b'not-json')
        source, row = self.read()
        self.assertEqual(source['status'], 'unknown')
        self.assertEqual(source['row_count'], None)
        self.assertEqual(source['last_success_state'], 'unknown')
        self.assertEqual(row[1], '狀態未知')

    def test_real_widgets_render_new_denial_and_old_success_from_same_saved_source(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest('standard-library Tk unavailable')
        try:
            window = tk.Tk()
        except tk.TclError:
            self.skipTest('own Tk display unavailable; not desktop acceptance')
        from eventguard.gui import EventGuardWindow
        from test_gui import FixtureController
        window.withdraw()
        ui = EventGuardWindow(window, FixtureController())
        try:
            success = self.save('ok', -50)
            self.save('denied', -5)
            ui._apply_snapshot(self.controller.snapshot())
            window.update_idletasks()
            row = ui.sources.item('defender', 'values')
            self.assertEqual(row[1:4], ('拒讀', '0', '新鮮'))
            self.assertEqual(row[5], success)
            self.assertEqual(row[6], 'access_denied')
            self.assertIn('拒讀 1', ui.source_gaps.get())
        finally:
            ui.dispose()
            ui.worker.shutdown(wait=True)
            window.destroy()
