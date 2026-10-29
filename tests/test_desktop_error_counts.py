"""Saved synthetic error counts on the actual seven-source Tk component."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from eventguard.collectors.contract import evidence, payload
from eventguard.collectors.windows import WindowsCollectors
from eventguard.desktop import DesktopController
from eventguard.gui import EventGuardWindow, view_snapshot
from eventguard.runtime import Runtime


class DesktopErrorCountsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root/'config').mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[1]/'config/default.json', self.root/'config/default.json')
        self.runtime = Runtime(self.root)
        self.controller = DesktopController(self.root)
        self.controller.api = Mock()
        self.controller.api.call.return_value = {}
        self.now = datetime(2026, 10, 30, tzinfo=timezone.utc)
        self.enterContext(patch('eventguard.source_status._now', return_value=self.now))
        self.enterContext(patch('eventguard.runtime.utc_now', return_value=self.now.isoformat()))
        self.enterContext(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')))

    def save(self, legacy=False):
        data = payload(errors=[evidence('object', 'access_denied', status='denied')] * 64
                       + [evidence('field', 'object_unavailable', status='unknown')] * 16)
        if legacy:
            data.pop('error_classifications')
        self.runtime.save_observation(dict(id='processes', status='partial', rows=[],
            observed_at=self.now.isoformat(), coverage=data), 'live')

    def hashes(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_saved_full_counts_differ_from_retained_error_sample(self):
        self.save()
        before = self.hashes()
        document = self.controller.snapshot()
        row = dict(view_snapshot(document)['sources'])['processes']
        self.assertEqual(row[1], '部分可讀')
        self.assertIn('錯誤 80', row[7])
        self.assertIn('保留明細 64', row[7])
        self.assertIn('欄位／未知 16', row[7])
        self.assertIn('物件／拒讀 64', row[7])
        self.assertEqual(before, self.hashes())

    def test_legacy_counts_do_not_extrapolate_unretained_classifications(self):
        self.save(legacy=True)
        row = dict(view_snapshot(self.controller.snapshot())['sources'])['processes']
        self.assertIn('全量分類未知', row[7])
        self.assertNotIn('拒讀 80', row[7])

    def test_inconsistent_display_counts_never_claim_verified_full_classification(self):
        from eventguard.gui_presenter import source_error_text
        for retained in (True, -1, 64, 'PRIVATE'):
            text = source_error_text(dict(error_count=0, retained_error_count=retained,
                error_classifications={'total_count': 0, 'unclassified_count': 0, 'groups': []}))
            self.assertIn('全量分類未知', text)
            self.assertNotIn('PRIVATE', text)

    def test_actual_source_widget_renders_counts_without_writing_or_acknowledging(self):
        import tkinter as tk
        from test_gui import FixtureController
        try:
            window = tk.Tk()
        except tk.TclError:
            self.skipTest('own Tk unavailable; native/human acceptance remains separate')
        window.withdraw()
        ui = EventGuardWindow(window, FixtureController())
        try:
            self.save()
            before = self.hashes()
            ui._apply_snapshot(self.controller.snapshot())
            window.update_idletasks()
            self.assertIn('錯誤 80', ui.sources.item('processes', 'values')[7])
            self.assertIn('非安全判定', ui.sources.heading('errors', 'text'))
            self.assertEqual(before, self.hashes())
        finally:
            ui.dispose()
            ui.worker.shutdown(wait=True)
            window.destroy()
