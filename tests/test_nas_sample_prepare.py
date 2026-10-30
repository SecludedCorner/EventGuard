"""Generated batch and public demo tests; private derivatives never enter stdout."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from eventguard.events.nas_sample_minimize import PROFILE
from eventguard.events.nas_sample_prepare import COLUMNS, prepare_fixture_csv
from scripts.preview_nas_sample import main
from test_nas_csv import encoded


def prepare(rows, header=COLUMNS, **changes):
    args = dict(profile=PROFILE, package_ref='a'*64, source_ref='b'*64,
                key=b'k'*32, shift_days=7)
    args.update(changes)
    return prepare_fixture_csv(encoded(rows, header), **args)


ROW = ['fixture-1', 'PRIVATE_CANARY', '192.0.2.1', '2026-10-30T08:00:00Z', 'failure']


class NasSamplePrepareTests(unittest.TestCase):
    def test_full_batch_preserves_distinct_same_second_records_and_private_boundary(self):
        second = list(ROW); second[0] = 'fixture-2'; second[-1] = 'success'
        got = prepare([ROW, second])
        self.assertEqual(got.summary['status'], 'prepared')
        self.assertEqual(got.summary['transformed_rows'], 2)
        self.assertNotEqual(got.private_rows[0]['record_ref'], got.private_rows[1]['record_ref'])
        public = repr(got)+json.dumps(got.summary)
        for value in ('PRIVATE_CANARY', ROW[2], ROW[3], got.private_rows[0]['subject_ref']):
            self.assertNotIn(value, public)
        self.assertFalse(got.summary['collection_authorized'])

    def test_missing_classes_and_fields_are_partial(self):
        row = list(ROW); row[0] = ''; row[3] = ''
        got = prepare([row])
        self.assertEqual(got.summary['status'], 'partial')
        self.assertEqual(got.summary['field_gaps'], 2)
        self.assertEqual(got.summary['missing_outcomes'], ['success'])

    def test_failed_batch_releases_no_partial_private_rows_or_values(self):
        bad = list(ROW); bad[-1] = 'PRIVATE_CANARY'
        for got in (prepare([ROW, bad]), prepare([ROW], key=b'x'),
                    prepare([ROW], header=['PRIVATE_CANARY']*5), prepare([ROW]*11)):
            self.assertEqual(got.summary['status'], 'rejected')
            self.assertEqual(got.private_rows, [])
            self.assertEqual(got.summary['transformed_rows'], 0)
            self.assertNotIn('PRIVATE_CANARY', repr(got))

    def test_demo_prints_only_summary_and_refuses_paths(self):
        for args, expected in [(['--synthetic'], 0), (['PRIVATE_CANARY.csv'], 2)]:
            out = io.StringIO()
            with patch('builtins.open', side_effect=AssertionError('no file reads')):
                with contextlib.redirect_stdout(out):
                    self.assertEqual(main(args), expected)
            result = json.loads(out.getvalue())
            self.assertNotIn('PRIVATE_CANARY', out.getvalue())
            self.assertNotIn('private_rows', result)
            self.assertFalse(result['collection_authorized'])
