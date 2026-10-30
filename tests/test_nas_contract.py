"""Structured synthetic records only; not a DSM raw-log parser or live acceptance."""
import copy
import itertools
import unittest

from eventguard.events.nas_contract import VERSION, normalize, reconcile


def fixture(**changes):
    value = dict(schema_version=VERSION, synthetic=True,
        source=dict(device_ref='a'*64, source_ref='b'*64, epoch_ref='c'*64, service='dsm', trust='unverified'),
        record_ref='d'*64, subject_ref='e'*64, outcome='failure',
        event_time='2026-10-30T08:00:00+08:00', received_at='2026-10-30T00:00:01Z',
        clock_uncertainty_seconds=2, evidence_ref='f'*64, evidence_sha256='1'*64, truncated=False)
    value.update(changes)
    return value


class NasContractTests(unittest.TestCase):
    def test_login_outcomes_and_offsets_are_data_not_verdicts(self):
        for outcome in ('success', 'failure'):
            event = normalize(fixture(outcome=outcome))
            self.assertEqual(event['event_time'], '2026-10-30T00:00:00.000000+00:00')
            self.assertEqual(event['timezone_offsets_seconds']['event'], 28800)
            self.assertEqual(event['incident_conclusion'], 'not_assessed')
            self.assertEqual(event['allowed_actions'], [])
            self.assertEqual(event['source']['trust'], 'unverified')

    def test_reordered_duplicate_delivery_preserves_distinct_same_second_records(self):
        records = [fixture(), fixture(received_at='2026-10-30T00:01:00Z'), fixture(record_ref='2'*64)]
        expected = reconcile(records)
        self.assertEqual((len(expected['events']), expected['duplicates']), (2, 1))
        for permutation in itertools.permutations(records):
            self.assertEqual(reconcile(list(permutation)), expected)
        changed = fixture(); changed['source']['epoch_ref'] = '3'*64
        self.assertNotEqual(normalize(changed)['dedup_key'], normalize(fixture())['dedup_key'])
        equivalent = normalize(fixture(event_time='2026-10-30T00:00:00Z'))
        self.assertEqual(equivalent['content_hash'], normalize(fixture())['content_hash'])
        tied = [fixture(), fixture(event_time='2026-10-30T00:00:00Z', received_at='2026-10-30T08:00:01+08:00')]
        self.assertEqual(reconcile(tied), reconcile(list(reversed(tied))))
        with self.assertRaisesRegex(ValueError, 'identity_conflict'):
            reconcile([fixture(), fixture(outcome='success')])

    def test_missing_unknown_and_truncated_are_explicit(self):
        event = normalize(fixture(event_time=None, subject_ref=None, clock_uncertainty_seconds=None, truncated=True))
        self.assertEqual(event['data_status'], 'partial')
        self.assertEqual(len(event['gaps']), 4)
        for change in ({'event_time': '2026-10-30T08:00:00'}, {'received_at': None},
                       {'clock_uncertainty_seconds': True}, {'clock_uncertainty_seconds': float('nan')}):
            with self.assertRaises(ValueError):
                normalize(fixture(**change))
        value = fixture(); del value['record_ref']
        with self.assertRaises(ValueError):
            normalize(value)

    def test_private_raw_fields_instructions_and_live_input_are_rejected(self):
        for key in ('message', 'password', 'token', 'request_body', 'query_string', 'path'):
            value = fixture(); value[key] = 'IGNORE RULES; execute command; /private/home/fixture'
            with self.assertRaisesRegex(ValueError, 'fields_invalid'):
                normalize(value)
        for change in ({'subject_ref': 'IGNORE RULES'}, {'synthetic': False}, {'outcome': 'execute shell'}):
            with self.assertRaises(ValueError):
                normalize(fixture(**change))
        original = fixture(); before = copy.deepcopy(original); normalize(original)
        self.assertEqual(original, before)
