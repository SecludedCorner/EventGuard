"""Real CLI argument parsing over health only; no native collection or model."""
from pathlib import Path
import tempfile
import unittest

import test_command_status_retry as status_fixture


class CommandQueryJsonTests(unittest.TestCase):
    cli = status_fixture.CommandStatusRetryTests.cli

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_duplicate_request_fields_are_rejected_before_dispatch(self):
        for data in ('{"request_id":"first","request_id":"second"}',
                     '{"request_id":"first","request_\\u0069d":"second"}'):
            code, result = self.cli("query", "health", "--args", data)
            self.assertEqual((code, result["status"]), (2, "invalid_request"))
            self.assertEqual(result["error_code"], "query_input_duplicate_key")
            self.assertEqual(list(self.root.iterdir()), [])

    def test_depth_budget_malformed_and_oversized_inputs_do_not_create_runtime(self):
        for data, error in (('{"max_rows":' + '['*32 + '0' + ']'*32 + '}', "query_input_depth_exceeded"),
                            ('{"request_id":', "input_or_config_validation_failed"),
                            ('{"request_id":"' + 'x'*8192 + '"}', "input_or_config_validation_failed")):
            code, result = self.cli("query", "health", "--args", data)
            self.assertEqual((code, result["status"], result["error_code"]), (2, "invalid_request", error))
            self.assertEqual(list(self.root.iterdir()), [])

    def test_valid_health_input_retains_versioned_result_and_literal_escapes(self):
        code, result = self.cli("query", "health", "--args", '{"request_id":"query-\\u0031","max_rows":1}')
        self.assertEqual((code, result["status"], result["schema_version"], result["request_id"]), (0, "ok", "1.0", "query-1"))
        self.assertEqual(result["source"], "tool_capabilities")
        self.assertEqual(list(self.root.iterdir()), [])
