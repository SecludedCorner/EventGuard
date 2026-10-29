"""Controlled clocks over real synthetic SQLite; no OS time changes."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from eventguard.events.catalog import EventCatalog
from eventguard.events.disposition_history_backup_file import read_known_backup
from eventguard.gui_presenter import history_preview_window
import test_desktop_history_backup as fixture


class HistoryPreviewWindowTests(unittest.TestCase):
    def test_aware_offsets_are_normalized_to_utc(self):
        text = history_preview_window({'read_started_at': '2026-10-26T08:00:00+08:00',
                                      'read_finished_at': '2026-10-26T00:00:01Z'})
        self.assertIn('2026-10-26T00:00:00+00:00 → 2026-10-26T00:00:01+00:00', text)

    def test_invalid_missing_naive_future_or_reversed_times_stay_unknown(self):
        for start, end in ((None, None), ('broken', 'broken'), ([], {}),
                           ('2026-10-26T00:00:00', '2026-10-26T00:00:01Z'),
                           ('2026-10-26T00:00:02Z', '2026-10-26T00:00:01Z'),
                           ('2999-10-26T00:00:00Z', '2999-10-26T00:00:01Z'),
                           ('2026-10-26T00:00:00Z\n', '2026-10-26T00:00:01Z')):
            with self.subTest(start=start, end=end):
                self.assertIn('區間：未知', history_preview_window({'read_started_at': start, 'read_finished_at': end}))


class DesktopPreviewClockTests(unittest.TestCase):
    setUp = fixture.DesktopHistoryBackupTests.setUp

    def test_interval_encloses_both_file_reads_and_database_snapshot(self):
        name = 'history-backup-clock.json'
        self.controller.backup_history(name)
        before = self.store.path.read_bytes()
        start, end = (datetime(2026, 10, 26, 0, 0, second, tzinfo=timezone.utc) for second in (0, 1))
        sequence, stamps = [], iter((start, end))
        def clock(*args):
            sequence.append('clock')
            return next(stamps)
        def read(*args):
            sequence.append('file')
            return read_known_backup(*args)
        original = self.catalog.preview_handling_history
        def snapshot(value):
            sequence.append('database')
            return original(value)
        with patch('eventguard.desktop.datetime') as fake_clock, patch(
            'eventguard.events.disposition_history_backup_file.read_known_backup', side_effect=read), patch.object(
                EventCatalog, 'preview_handling_history', side_effect=snapshot):
            fake_clock.now.side_effect = clock
            result = self.controller.preview_history_backup(name)
        self.assertEqual(sequence, ['clock', 'file', 'database', 'file', 'clock'])
        self.assertEqual(result['read_started_at'], start.isoformat(timespec='microseconds'))
        self.assertEqual(result['read_finished_at'], end.isoformat(timespec='microseconds'))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))
