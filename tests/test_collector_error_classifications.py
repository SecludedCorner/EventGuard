"""Fixed error counts use the entire synthetic input, never host metadata."""
import json
import unittest
from unittest.mock import patch

from eventguard.collectors.contract import MAX_ERRORS, evidence, payload
from eventguard.collectors.native import NativeBackend


class CollectorErrorClassificationsTests(unittest.TestCase):
    def test_failure_after_retained_prefix_affects_status_and_counts(self):
        errors = [evidence('object', 'access_denied', status='denied')] * MAX_ERRORS
        errors += [evidence('field', 'object_unavailable', status='unknown')] * 16
        result = payload(errors=errors)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['errors']), MAX_ERRORS)
        self.assertEqual(result['error_count'], 80)
        self.assertTrue(result['errors_truncated'])
        self.assertEqual(result['error_classifications'], {
            'total_count': 80, 'unclassified_count': 0,
            'groups': [{'stage': 'field', 'status': 'unknown', 'count': 16},
                       {'stage': 'object', 'status': 'denied', 'count': 64}]})

    def test_invalid_errors_remain_unknown_without_copying_private_values(self):
        errors = [None, {'stage': ['PRIVATE'], 'status': {'PRIVATE': True}},
                  {'stage': 'PRIVATE', 'status': 'PRIVATE', 'path': 'PRIVATE'},
                  {'stage': 'object', 'status': 'ok'}]
        result = payload(errors=errors)
        summary = result['error_classifications']
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(summary['total_count'], 4)
        self.assertEqual(summary['unclassified_count'], 4)
        self.assertEqual(sum(group['count'] for group in summary['groups']), 4)
        self.assertNotIn('PRIVATE', json.dumps(summary))
        self.assertLessEqual(len(summary['groups']), 60)

    def test_malformed_error_is_not_successful_empty_collection(self):
        result = payload(errors=[None])
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['error_count'], 1)

    def test_successful_empty_collection_and_explicit_timeout_keep_their_scope(self):
        result = payload()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['error_classifications'], {
            'total_count': 0, 'unclassified_count': 0, 'groups': []})
        result = payload(errors=[evidence('object', 'access_denied', status='denied')], status='timeout')
        self.assertEqual(result['status'], 'timeout')
        self.assertEqual(result['error_classifications']['groups'][0]['status'], 'denied')

    def test_native_budget_adds_one_error_without_losing_counts_beyond_prefix(self):
        for policy_errors in (0, 2):
            errors = [evidence('object', 'access_denied', status='denied')] * 80
            errors += [evidence('policy', 'native_budget_exceeded', status='timeout')] * policy_errors
            backend = NativeBackend(timeout=1)
            with patch('eventguard.collectors.native.os.name', 'nt'), \
                 patch('eventguard.collectors.native.time.monotonic', side_effect=[0, 2]), \
                 patch.object(backend, '_services', return_value=payload(errors=errors)):
                result = backend.collect('services')
            summary = result['error_classifications']
            self.assertEqual(result['status'], 'timeout')
            self.assertEqual(summary['total_count'], 81 + policy_errors)
            self.assertEqual(sum(g['count'] for g in summary['groups']), result['error_count'])
            self.assertEqual(summary['groups'][-1], {
                'stage': 'policy', 'status': 'timeout', 'count': 1 + policy_errors})
            self.assertEqual(len(result['errors']), MAX_ERRORS)
