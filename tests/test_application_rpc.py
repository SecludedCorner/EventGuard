"""Real loopback attachment boundary; fixture callback, no inventory/model."""
import http.client
import json
from pathlib import Path
import tempfile
import unittest

from eventguard.application_mcp import validate_application_tool
from eventguard.web import LocalWeb


class ApplicationRPCBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.calls = []
        self.instance = "a" * 32

        def call(name, arguments):
            validate_application_tool(name, arguments)
            self.calls.append((name, arguments))
            return {"instance_id": self.instance, "namespace": "test", "model_calls": 0}

        self.web = LocalWeb(Path(temporary.name), "test", port=0, operator_call=call,
                            status_provider=lambda: {"instance_id": self.instance})
        self.web.start()
        self.addCleanup(self.close)

    def close(self):
        self.assertTrue(self.web.close()["web_thread_exited"])

    def request(self, body=None, headers=None):
        body = body if body is not None else json.dumps({"instance_id": self.instance, "name": "status", "arguments": {}})
        values = {"Content-Type": "application/json", "Authorization": "Bearer " + self.web.token}
        values.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.web.server.server_port, timeout=5)
        try:
            connection.request("POST", "/api/operator", body, values)
            response = connection.getresponse()
            raw = response.read()
            self.assertNotIn(self.web.token.encode(), raw)
            return response.status, json.loads(raw)
        finally:
            connection.close()

    def test_same_instance_valid_bearer_calls_only_fixed_operation(self):
        for headers in ({}, {"Origin": self.web.url}):
            self.assertEqual(self.request(headers=headers)[0], 200)
        self.assertEqual(self.calls, [("status", {}), ("status", {})])

    def test_missing_wrong_non_ascii_token_host_and_origin_are_denied(self):
        for headers in ({"Authorization": ""}, {"Authorization": "Bearer wrong"},
                        {"Authorization": "Bearer \xff"}, {"Host": "other.invalid"},
                        {"Origin": "http://other.invalid"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(headers=headers)[0], 403)
        self.assertEqual(self.calls, [])

    def test_foreign_instance_never_reaches_callback(self):
        body = {"instance_id": "b" * 32, "name": "start_monitor", "arguments": {}}
        self.assertEqual(self.request(json.dumps(body))[0], 409)
        self.assertEqual(self.calls, [])

    def test_duplicate_nonfinite_oversized_or_unknown_arguments_do_not_execute(self):
        bodies = ("[]", "null", '{"instance_id":"a","instance_id":"b"}',
                  '{"instance_id":NaN,"name":"status","arguments":{}}', " " * 8193,
                  json.dumps({"instance_id": self.instance, "name": "start_monitor", "arguments": {"namespace": "live"}}),
                  json.dumps({"instance_id": self.instance, "name": "shell", "arguments": {}}),
                  json.dumps({"instance_id": self.instance, "name": "status", "arguments": {}, "command": "anything"}))
        for body in bodies:
            with self.subTest(body_length=len(body)):
                self.assertEqual(self.request(body)[0], 400)
        self.assertEqual(self.calls, [])

    def test_body_framing_and_content_type_are_checked_before_callback(self):
        for headers in ({"Content-Type": "text/plain"}, {"Content-Length": "invalid"},
                        {"Transfer-Encoding": "chunked"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(headers=headers)[0], 400)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
