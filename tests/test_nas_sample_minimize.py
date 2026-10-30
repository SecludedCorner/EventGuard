"""Synthetic identities and keys; no actual NAS sample or secret is read."""
import json
import traceback
import unittest

from eventguard.events.nas_sample_minimize import PROFILE, minimize_fixture_row


def sample(**changes):
    return dict(record_id='fixture-1', subject='fixture-user', origin='192.0.2.1',
                event_time='2026-10-30T08:00:00+08:00', outcome='failure', **changes)


def minimize(values=None, **changes):
    args = dict(profile=PROFILE, package_ref='a'*64, source_ref='b'*64,
                key=b'k'*32, shift_days=7)
    args.update(changes)
    return minimize_fixture_row(sample() if values is None else values, **args)


class NasSampleMinimizeTests(unittest.TestCase):
    def test_scoped_references_are_stable_separated_and_do_not_echo(self):
        values = sample(); values.update(record_id='CANARY', subject='CANARY', origin='CANARY')
        first = minimize(values)
        self.assertEqual(first, minimize(values))
        refs = {first[name] for name in ('record_ref', 'subject_ref', 'origin_ref')}
        self.assertEqual(len(refs), 3)
        for changes in ({'package_ref': 'c'*64}, {'source_ref': 'c'*64}, {'key': b'x'*32}):
            self.assertNotEqual(first['subject_ref'], minimize(values, **changes)['subject_ref'])
        self.assertNotIn('CANARY', json.dumps(first))

    def test_shift_preserves_interval_and_offset_without_claiming_real_time(self):
        first = minimize()
        values = sample(); values['event_time'] = '2026-10-30T08:00:01+08:00'
        second = minimize(values)
        self.assertEqual(first['event_time'], '2026-11-06T08:00:00+08:00')
        self.assertEqual(second['event_time'], '2026-11-06T08:00:01+08:00')
        self.assertEqual(first['offset_seconds'], 28800)
        self.assertEqual(first['time_basis'], 'artificial_shifted')
        self.assertFalse(first['source_format_verified'])

    def test_missing_identity_or_offset_stays_unknown(self):
        values = sample(); values.update(record_id=None, subject='', event_time='2026-10-30T08:00:00')
        got = minimize(values)
        self.assertIsNone(got['record_ref'])
        self.assertIsNone(got['subject_ref'])
        self.assertIsNone(got['event_time'])
        self.assertIn('event_time_offset_unknown', got['gaps'])

    def test_unknown_schema_outcome_key_shift_and_dates_fail_without_values(self):
        for changes in ({'profile': 'PRIVATE'}, {'key': b'PRIVATE'}, {'shift_days': True},
                        {'shift_days': 0}, {'shift_days': 3651}, {'source_ref': 'PRIVATE'}):
            with self.assertRaises(ValueError) as caught:
                minimize(**changes)
            self.assertNotIn('PRIVATE', str(caught.exception))
        for change in ({'message': 'PRIVATE'}, {'outcome': 'PRIVATE'},
                       {'event_time': '2026-10-30T08:00:00+08:00:00.5'},
                       {'event_time': 'PRIVATE'}, {'event_time': '9999-12-31T23:00:00Z'}):
            values = sample(); values.update(change)
            try:
                minimize(values)
                self.fail('invalid fixture accepted')
            except ValueError as error:
                self.assertNotIn('PRIVATE', ''.join(traceback.format_exception(error)))
