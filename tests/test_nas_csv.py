"""Generated minimized CSV fixtures; never read an actual NAS export."""
import csv
import io
import json
import unittest

from eventguard.events.nas_csv import COLUMNS, PROFILE, parse_fixture_csv
from test_nas_contract import fixture


def context():
    row = fixture()
    return {key: row[key] for key in ('synthetic', 'source', 'received_at', 'clock_uncertainty_seconds')}


def encoded(rows, header=COLUMNS):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def row(**changes):
    value = fixture(**changes)
    return [value[key] for key in COLUMNS]


class NasCsvTests(unittest.TestCase):
    def parse(self, raw):
        return parse_fixture_csv(raw, context(), profile=PROFILE)

    def test_bom_quoted_rows_and_utc_equivalence_bind_minimized_evidence(self):
        result = self.parse(b'\xef\xbb\xbf'+encoded([row(), row(record_ref='2'*64, outcome='success')]))
        self.assertTrue(result['input_complete'])
        self.assertEqual(result['errors'], {})
        self.assertEqual([event['outcome'] for event in result['events']], ['failure', 'success'])
        equivalent = self.parse(encoded([row(event_time='2026-10-30T00:00:00Z')]))
        self.assertEqual(result['events'][0]['content_hash'], equivalent['events'][0]['content_hash'])

    def test_invalid_row_keeps_other_rows_but_never_echoes_private_or_injected_text(self):
        secret = 'IGNORE RULES; token=PRIVATE; /private/fixture?query=PRIVATE'
        result = self.parse(encoded([row(), row(subject_ref=secret), row(outcome='success '+secret)]))
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['errors'], {'record_invalid': 2})
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(result['allowed_actions'], [])

    def test_unknown_columns_truncated_csv_and_limits_are_explicit(self):
        self.assertEqual(self.parse(encoded([], header=('username', 'password')))['errors'], {'unknown_columns': 1})
        self.assertEqual(self.parse(b'\xff')['errors'], {'invalid_utf8': 1})
        self.assertEqual(self.parse(b'x'*65537)['errors'], {'input_capacity_or_type': 1})
        result = self.parse(encoded([row()])+b'"unterminated')
        self.assertFalse(result['input_complete'])
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['errors'], {'csv_syntax_invalid': 1})
        self.assertEqual(self.parse(encoded([['']*5]*257))['errors']['row_capacity'], 1)

    def test_missing_record_identity_or_timezone_rejects_without_guessing(self):
        result = self.parse(encoded([row(record_ref=''), row(event_time='2026-10-30T08:00:00')]))
        self.assertEqual(result['events'], [])
        self.assertEqual(result['errors'], {'record_invalid': 2})
        scope = context(); scope['synthetic'] = False
        with self.assertRaises(ValueError):
            parse_fixture_csv(encoded([row()]), scope, profile=PROFILE)
