"""Legacy saved success with contradictory coverage must not look complete."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from eventguard.collectors.contract import SECTION_IDS
from eventguard.desktop import DesktopController
from eventguard.gui import EventGuardWindow, view_snapshot
from eventguard.runtime import Runtime
from eventguard.source_status import source_status

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)


class SourceSuccessContradictionsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'config').mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[1]/'config/default.json', self.root/'config/default.json')
        self.runtime = Runtime(self.root)
        self.enterContext(patch('eventguard.source_status._now', return_value=NOW))
        self.enterContext(patch('eventguard.runtime.utc_now', return_value=NOW.isoformat()))
        self.enterContext(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')))

    def save(self, source='listeners', age=0, coverage=None):
        self.runtime.save_observation(dict(id=source, status='ok', rows=[],
            observed_at=(NOW-timedelta(seconds=age)).isoformat(),
            coverage=coverage if coverage is not None else {'errors': [], 'error_count': 0}), 'live')

    def rows(self):
        return {row['source_id']: row for row in source_status(self.root, 'live')['sources']}

    def test_nonzero_errors_preserve_original_status_and_history_but_remove_success(self):
        for source in SECTION_IDS:
            self.save(source, 30)
            self.save(source, coverage={'errors': [], 'error_count': 80})
        for row in self.rows().values():
            self.assertEqual(row['saved_status'], 'ok')
            self.assertEqual(row['status'], 'partial')
            self.assertIsNone(row['success'])
            self.assertEqual(row['last_success_at'], (NOW-timedelta(seconds=30)).isoformat(timespec='seconds'))

    def test_malformed_legacy_coverage_cannot_report_success_or_modify_saved_bytes(self):
        self.save()
        path = self.root/'data/live/observations/listeners.json'
        value = json.loads(path.read_text())
        for changes in ({'error_count': True}, {'error_count': -1}, {'errors': None},
                        {'errors_truncated': 'false'}, {'status': 'denied'}):
            with self.subTest(changes=changes):
                value['section']['coverage'] = changes
                path.write_text(json.dumps(value), encoding='utf-8')
                before = hashlib.sha256(path.read_bytes()).hexdigest()
                row = self.rows()['listeners']
                self.assertEqual(row['status'], 'unknown')
                self.assertIsNone(row['success'])
                self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_actual_tk_stale_legacy_errors_do_not_display_successful_collection(self):
        import tkinter as tk
        from test_gui import FixtureController
        try:
            window = tk.Tk()
        except tk.TclError:
            self.skipTest('own Tk unavailable; not native or human acceptance')
        window.withdraw()
        ui = EventGuardWindow(window, FixtureController())
        try:
            self.save(age=900, coverage={'errors': [], 'error_count': 80})
            controller = DesktopController(self.root)
            controller.api = Mock()
            controller.api.call.return_value = {}
            document = controller.snapshot()
            self.assertEqual(dict(view_snapshot(document)['sources'])['listeners'][1], '部分可讀')
            ui._apply_snapshot(document)
            window.update_idletasks()
            self.assertEqual(ui.sources.item('listeners', 'values')[1:4], ('部分可讀', '0', '過期'))
        finally:
            ui.dispose()
            ui.worker.shutdown(wait=True)
            window.destroy()
