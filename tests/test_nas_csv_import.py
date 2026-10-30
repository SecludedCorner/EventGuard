"""Candidate exchange integration only; no actual DSM CSV or transport receipt."""
import itertools
import json
import unittest

from eventguard.events.nas_csv import PROFILE
from eventguard.events.nas_csv_import import inspect_fixture_csv
from test_nas_csv import context, encoded, row
from test_nas_coverage import snapshot


class NasCsvImportTests(unittest.TestCase):
    def inspect(self, rows, coverage=None):
        return inspect_fixture_csv(encoded(rows), context(), profile=PROFILE,
            now='2026-10-30T00:01:10Z', max_age_seconds=120, coverage=coverage)

    def test_successful_parse_never_invents_transport_health(self):
        result = self.inspect([row()])
        self.assertEqual(result['parser_status'], 'ok')
        self.assertEqual(result['status'], 'unknown')
        for key in ('heartbeat_at', 'last_success_at', 'dropped', 'parse_errors'):
            self.assertIsNone(result['transport_coverage'][key])
        self.assertEqual(result['incident_conclusion'], 'not_assessed')
        self.assertEqual(result['allowed_actions'], [])

    def test_errors_and_duplicates_preserve_good_records_without_echoing_input(self):
        result = self.inspect([row(), row(), row(subject_ref='PRIVATE; execute shell')], snapshot())
        self.assertEqual((len(result['events']), result['duplicate_rows']), (1, 1))
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['parser_errors'], {'record_invalid': 1})
        self.assertEqual(result['transport_coverage']['parse_errors'], 0)  # Independent supplied snapshot.
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_conflicting_identity_excludes_entire_group_in_any_order(self):
        rows = [row(), row(outcome='success'), row(record_ref='2'*64)]
        expected = self.inspect(rows, snapshot())
        self.assertEqual([event['record_ref'] for event in expected['events']], ['2'*64])
        self.assertEqual(expected['parser_errors'], {'identity_conflict_rows': 2})
        for permutation in itertools.permutations(rows):
            self.assertEqual(self.inspect(list(permutation), snapshot()), expected)

    def test_partial_event_and_failed_transport_cannot_become_ok(self):
        self.assertEqual(self.inspect([row(event_time='')], snapshot())['status'], 'partial')
        self.assertEqual(self.inspect([row()], snapshot(storage_error='disk_full'))['status'], 'partial')
        self.assertEqual(self.inspect([row()], snapshot(heartbeat_at=None))['status'], 'unknown')
        self.assertEqual(self.inspect([row()], snapshot(window_start='2026-10-30T00:00:30Z'))['status'], 'unknown')
        other = snapshot(); other['source']['device_ref'] = '3'*64
        with self.assertRaisesRegex(ValueError, 'source_mismatch'):
            self.inspect([row()], other)

    def test_truncated_batch_retains_prefix_but_has_unknown_overall_coverage(self):
        result = inspect_fixture_csv(encoded([row()])+b'"unterminated', context(), profile=PROFILE,
            now='2026-10-30T00:01:10Z', max_age_seconds=120, coverage=snapshot())
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['status'], 'unknown')
        self.assertFalse(result['input_complete'])
        self.assertEqual(result['parser_errors'], {'csv_syntax_invalid': 1})
