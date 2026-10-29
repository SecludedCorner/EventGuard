"""Synthetic collector wire envelopes and saved projections, no host queries."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from eventguard.collectors.contract import evidence, payload
from eventguard.collectors.windows import WindowsCollectors, coverage_metadata
from eventguard.diagnostics.api import DiagnosticAPI
from eventguard.runtime import Runtime


class Backend:
    def __init__(self, data):
        self.data = data

    def collect(self, source, cancel=None):
        return deepcopy(self.data)


class ErrorClassificationPropagationTests(unittest.TestCase):
    def sample(self):
        return payload([{'name': 'synthetic', 'status': 'ok'}],
                       [evidence('object', 'access_denied', status='denied')] * 80)

    def collect(self, data):
        return WindowsCollectors(native=Backend(data), backend='native').collect('services')

    def test_summary_survives_collector_attempt_and_saved_readback(self):
        data = self.sample()
        result = self.collect(data)
        expected = data['error_classifications']
        self.assertEqual(result['coverage']['error_classifications'], expected)
        self.assertEqual(result['coverage']['attempts'][0]['error_classifications'], expected)
        projected = coverage_metadata(result)
        self.assertEqual(projected['error_classifications'], expected)
        self.assertEqual(projected['attempts'][0]['error_classifications'], expected)
        with tempfile.TemporaryDirectory() as folder:
            runtime = Runtime(Path(folder))
            runtime.save_observation(result, 'test')
            saved = runtime.observation('services', 'test')
        self.assertEqual(saved['section']['coverage']['error_classifications'], expected)
        self.assertEqual(saved['section']['status'], 'partial')
        self.assertEqual(len(saved['section']['coverage']['errors']), 64)
        diagnostic = DiagnosticAPI(WindowsCollectors(native=Backend(data), backend='native')).query('query_persistence_diff', {'kind': 'services'})
        self.assertEqual(diagnostic['coverage']['error_classifications'], expected)

    def test_legacy_declared_failures_cannot_be_reported_as_success(self):
        data = dict(status='ok', rows=[], errors=[], error_count=80)
        result = self.collect(data)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['coverage']['error_count'], 80)
        self.assertIsNone(result['coverage']['error_classifications'])

    def test_missing_or_inconsistent_summary_stays_unknown_without_extrapolation(self):
        data = self.sample()
        summary = data['error_classifications']
        variants = [None, {}, dict(summary, total_count=True), dict(summary, total_count=79),
                    dict(summary, unclassified_count=-1), dict(summary, groups=summary['groups'] * 2),
                    dict(summary, groups=[{'stage': [], 'status': 'denied', 'count': 80}]),
                    dict(summary, groups=[{'stage': 'field', 'status': 'denied', 'count': 80}]),
                    dict(summary, groups=summary['groups'] * 61)]
        for value in variants:
            with self.subTest(value=value):
                data['error_classifications'] = value
                result = self.collect(data)
                self.assertEqual(result['status'], 'partial')
                self.assertEqual(result['coverage']['error_count'], 80)
                self.assertIsNone(coverage_metadata(result)['error_classifications'])

    def test_invalid_rows_update_counts_without_copying_extra_summary_fields(self):
        data = self.sample()
        data['rows'].append(None)
        data['error_classifications']['private'] = 'PRIVATE'
        data['error_classifications']['groups'][0]['path'] = 'PRIVATE'
        result = self.collect(data)
        summary = coverage_metadata(result)['error_classifications']
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(summary['total_count'], 81)
        self.assertEqual(summary['groups'], [
            {'stage': 'object', 'status': 'denied', 'count': 80},
            {'stage': 'object', 'status': 'error', 'count': 1}])
        self.assertNotIn('PRIVATE', json.dumps(summary))
