"""All operator read paths agree on contradictory saved synthetic success."""
from datetime import timedelta
import hashlib
import json
import unittest
from unittest.mock import patch

import test_operator_status as fixtures
from eventguard.presentation import render
from eventguard.source_status import source_status


class OperatorSuccessContradictionsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.OperatorStatusTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.api, self.runtime = self.fixture.api, self.fixture.runtime
        self.enterContext(patch('eventguard.source_status._now', return_value=fixtures.NOW))

    def test_health_and_cli_preserve_raw_success_without_claiming_current_success(self):
        for age in (0, 900):
            self.fixture.health(coverage={'listeners': dict(status='ok', errors=[], error_count=80,
                observed_at=(fixtures.NOW-timedelta(seconds=age)).isoformat())})
            path = self.runtime.path('data/health.json')
            before = path.read_bytes()
            result = self.api.status()
            row = result['source_coverage']['listeners']
            self.assertEqual(row['saved_status'], 'ok')
            self.assertEqual(row['status'], 'partial')
            self.assertEqual(row['current_coverage'], 'partial' if age == 0 else 'unknown')
            self.assertIn('部分可讀', render(result, command='status'))
            self.assertEqual(path.read_bytes(), before)

    def test_health_with_invalid_error_count_is_unknown(self):
        self.fixture.health(coverage={'listeners': dict(status='ok', error_count=True,
            observed_at=fixtures.NOW.isoformat())})
        row = self.api.overview('test')['source_coverage']['listeners']
        self.assertEqual(row['status'], 'unknown')
        self.assertEqual(row['current_coverage'], 'unknown')

    def test_saved_observation_and_cross_namespace_overview_use_the_same_effective_status(self):
        self.fixture.health(coverage={'listeners': dict(status='ok', observed_at=fixtures.NOW.isoformat())})
        self.runtime.save_observation(dict(id='listeners', status='ok', rows=[],
            observed_at=fixtures.NOW.isoformat(), coverage={'errors': [], 'error_count': 80}), 'live')
        path = self.runtime.path('data/live/observations/listeners.json')
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        for row in (self.api.observation('listeners', 'live'), self.api.overview('live')['source_coverage']['listeners']):
            self.assertEqual(row['saved_status'], 'ok')
            self.assertEqual(row['status'], 'partial')
            self.assertEqual(row['current_coverage'], 'partial')
        self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_malformed_declared_status_does_not_break_other_sources(self):
        self.runtime.save_observation(dict(id='listeners', status='ok', rows=[],
            observed_at=fixtures.NOW.isoformat(), coverage={'errors': []}), 'live')
        path = self.runtime.path('data/live/observations/listeners.json')
        value = json.loads(path.read_text())
        value['section']['status'] = []
        path.write_text(json.dumps(value), encoding='utf-8')
        self.assertEqual(self.api.observation('listeners', 'live')['status'], 'unknown')
        result = source_status(self.fixture.root, 'live')
        self.assertEqual(len(result['sources']), 7)
        self.assertEqual(result['sources'][1]['status'], 'unknown')
