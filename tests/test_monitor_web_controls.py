"""Real loopback HTTP; fixture callbacks only, no collector, model or process."""
import hashlib
from html.parser import HTMLParser
import http.client
import json
from pathlib import Path
import tempfile
import unittest

from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic
from eventguard.web import LocalWeb


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.by_id = {}

    def handle_starttag(self, tag, attributes):
        fields = dict(attributes)
        if "id" in fields:
            self.by_id[fields["id"]] = {"tag": tag, **fields}


class MonitorWebControlTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.calls = []
        self.operation_ids = []
        self.monitor_state = "running"
        self.revision = 0
        self.last_action = None
        self.controls = {"available": True, "paused": False, "stopped": False, "transition": None,
                         "can_start": False, "can_pause": True, "can_resume": False,
                         "can_stop": True, "can_shutdown": True}
        self.web = LocalWeb(self.root, "test", port=0,
                            status_provider=self.status, monitor_control=self.control)
        self.web.start()
        self.addCleanup(self.close_web)

    def close_web(self):
        self.assertTrue(self.web.close()["web_thread_exited"])

    def status(self):
        return {"instance_id": "a" * 32, "state_revision": self.revision,
                "monitor_state": self.monitor_state, "last_action": self.last_action,
                "monitor_controls": dict(self.controls), "model_calls": 0}

    def control(self, action, operation_id=None):
        # This fixture changes only an in-memory flag. Actual monitor lifetime
        # belongs to Application integration tests, not this HTTP contract.
        self.calls.append(action)
        self.operation_ids.append(operation_id)
        self.revision += 1
        self.monitor_state = {"start": "running", "pause": "paused", "resume": "running",
                              "stop": "stopped", "shutdown": "closing"}[action]
        closing = action == "shutdown"
        paused, stopped = self.monitor_state == "paused", self.monitor_state == "stopped"
        self.controls = {"available": not closing, "paused": paused, "stopped": stopped,
                         "transition": "shutdown" if closing else None,
                         "can_start": stopped, "can_pause": self.monitor_state == "running",
                         "can_resume": paused, "can_stop": self.monitor_state in {"running", "paused"},
                         "can_shutdown": not closing}
        self.last_action = {"action": action, "source": "gui", "state": "succeeded",
                            "result_code": "fixture_monitor_" + action,
                            "operation_id": operation_id or "fixture-" + str(self.revision),
                            "at": "2026-10-24T00:00:00+00:00", "revision": self.revision}
        return {**self.status(), "state": "succeeded", "reason": "fixture_monitor_" + action,
                "operation_id": self.last_action["operation_id"], "model_calls": 0}

    def request(self, method, path, body=None, *, auth=False, headers=None):
        values = {"Content-Type": "application/json"}
        if auth:
            values.update({"Origin": self.web.url, "X-EventGuard-CSRF": self.web.token})
        values.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.web.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=values)
            reply = connection.getresponse()
            return reply.status, dict(reply.getheaders()), reply.read()
        finally:
            connection.close()

    def post(self, action, body="{}", **options):
        return self.request("POST", "/api/monitor/" + action, body, auth=True, **options)

    def files(self):
        return {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.root.rglob("*") if path.is_file()}

    def test_five_fixed_controls_call_only_injected_monitor_callback(self):
        for action, expected_state in (("start", "running"), ("pause", "paused"), ("resume", "running"),
                                       ("stop", "stopped"), ("start", "running"), ("shutdown", "closing")):
            with self.subTest(action=action):
                code, headers, raw = self.post(action)
                self.assertEqual(code, 200, raw)
                self.assertEqual(json.loads(raw)["reason"], "fixture_monitor_" + action)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(headers["Connection"], "close")
                code, _, raw = self.request("GET", "/api/status")
                self.assertEqual(code, 200, raw)
                status = json.loads(raw)
                self.assertEqual(status["monitor_state"], expected_state)
                self.assertEqual(status["monitor_controls"], self.controls)
                self.assertEqual(status["last_action"]["source"], "gui")
                self.assertEqual(status["state_revision"], self.revision)
        self.assertEqual(self.calls, ["start", "pause", "resume", "stop", "start", "shutdown"])
        self.assertFalse((self.root / "data").exists())
        self.evidence = {"scope": "real loopback HTTP with in-memory monitor callback fixture",
                         "actual_monitor_pause_verified": False, "model_calls": 0}

    def test_pause_keeps_page_and_saved_pending_event_available_without_ack(self):
        source = self.root / "data/test"
        store = EventStore(source)
        event = make_synthetic("listener")
        store.enqueue(event)
        before = self.files()
        self.assertEqual(self.post("pause")[0], 200)
        for route in ("/", "/app.js", "/api/events", "/api/status"):
            with self.subTest(route=route):
                code, _, raw = self.request("GET", route)
                self.assertEqual(code, 200, raw)
        code, _, raw = self.request("GET", "/api/events")
        self.assertEqual(json.loads(raw)["events"][0]["event_id"], event["event_id"])
        self.assertEqual(self.files(), before)
        self.assertEqual(store.stats()["pending"], 1)
        self.assertEqual(store.stats()["receipt_count"], 0)
        self.assertEqual(self.calls, ["pause"])

    def test_monitor_controls_have_separate_initially_disabled_buttons_and_explanation(self):
        code, _, raw = self.request("GET", "/")
        self.assertEqual(code, 200)
        page = raw.decode("utf-8")
        elements = Elements()
        elements.feed(page)
        for action in ("start", "pause", "resume", "stop", "shutdown"):
            self.assertEqual(elements.by_id["monitor-" + action]["tag"], "button")
            self.assertIn("disabled", elements.by_id["monitor-" + action])
        self.assertIn('id="agent-pause"', page)
        self.assertIn('id="agent-stop"', page)
        self.assertIn("這些操作不會啟動 agent", page)
        self.assertIn("停止採集後，網頁與 MCP 仍可使用", page)
        self.assertIn('id="monitor-result" role="status"', page)
        code, _, raw = self.request("GET", "/app.js")
        self.assertEqual(code, 200)
        script = raw.decode("utf-8")
        # Served-script contract only. This is not a browser execution test.
        self.assertIn("deriveApplicationView", script)
        self.assertIn("scheduleStatusPoll", script)
        self.assertIn("STATUS_POLL_MS=1000", script)
        self.assertNotIn("monitorStopped=true", script)
        self.assertNotIn("clearInterval(refreshTimer)", script)
        self.assertEqual(self.calls, [])

    def test_stop_keeps_status_endpoint_and_start_capability_available(self):
        self.assertEqual(self.post("stop")[0], 200)
        for _ in range(3):
            code, _, raw = self.request("GET", "/api/status")
            self.assertEqual(code, 200, raw)
            view = json.loads(raw)
            self.assertEqual(view["monitor_state"], "stopped")
            self.assertTrue(view["monitor_controls"]["can_start"])
            self.assertTrue(view["monitor_controls"]["can_shutdown"])
            self.assertFalse(view["monitor_controls"]["paused"])
        self.assertEqual(self.calls, ["stop"])
        self.assertEqual(self.post("start")[0], 200)
        self.assertEqual(self.calls, ["stop", "start"])

    def test_missing_callback_is_503_and_status_cannot_advertise_available(self):
        self.assertTrue(self.web.close()["web_thread_exited"])
        self.web = LocalWeb(self.root, "test", port=0, status_provider=self.status)
        self.web.start()
        for action in ("start", "pause", "resume", "stop", "shutdown"):
            with self.subTest(action=action):
                code, _, raw = self.post(action)
                self.assertEqual(code, 503, raw)
                self.assertEqual(json.loads(raw)["error_code"], "monitor_control_unavailable")
        code, _, raw = self.request("GET", "/api/status")
        self.assertEqual(code, 200)
        expected = {**self.controls, "available": False,
                    **{key: False for key in self.controls if key.startswith("can_")}}
        self.assertEqual(json.loads(raw)["monitor_controls"], expected)
        self.assertTrue(self.controls["available"])  # Provider data was not mutated.
        self.assertEqual(self.calls, [])

    def test_missing_or_malformed_control_status_is_disabled_and_transition_is_visible(self):
        invalid_values = [None, {}, {"available": True, "paused": False, "transition": None},
                          {**self.controls, "transition": []}, {**self.controls, "command": "run"}]
        invalid_values.extend({**self.controls, key: 1} for key in self.controls if key != "transition")
        disabled = {"available": False, "paused": False, "stopped": False, "transition": None,
                    "can_start": False, "can_pause": False, "can_resume": False,
                    "can_stop": False, "can_shutdown": False}
        for invalid in invalid_values:
            self.web.status_provider = lambda value=invalid: {"monitor_state": "unknown", "monitor_controls": value}
            with self.subTest(value=invalid):
                code, _, raw = self.request("GET", "/api/status")
                self.assertEqual(code, 200, raw)
                self.assertEqual(json.loads(raw)["monitor_controls"], disabled)
        self.web.status_provider = self.status
        self.controls["transition"] = "pausing"
        code, _, raw = self.request("GET", "/api/status")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)["monitor_controls"]["transition"], "pausing")
        self.assertEqual(self.calls, [])

    def test_foreign_host_origin_missing_or_wrong_csrf_never_calls_monitor(self):
        attempts = ({}, {"Origin": self.web.url}, {"Origin": "http://evil.invalid", "X-EventGuard-CSRF": self.web.token},
                    {"Origin": self.web.url, "X-EventGuard-CSRF": "wrong"},
                    {"Origin": self.web.url, "X-EventGuard-CSRF": self.web.token, "Host": "evil.invalid"})
        for headers in attempts:
            with self.subTest(headers=headers):
                code, _, raw = self.request("POST", "/api/monitor/resume", "{}", headers=headers)
                self.assertEqual(code, 403, raw)
                self.assertEqual(json.loads(raw)["error_code"], "same_origin_required")
        self.assertEqual(self.calls, [])

    def test_only_empty_or_operation_id_json_and_fixed_routes_are_accepted(self):
        for body in ("[]", "null", "true", '"{}"', '{"action":"resume"}', '{"command":"run"}', "{"):
            with self.subTest(body=body):
                code, _, raw = self.post("pause", body)
                self.assertEqual(code, 400, raw)
        for route in ("/api/monitor/restart", "/api/monitor/pause?command=run", "/api/monitor/pause/", "/api/monitor"):
            with self.subTest(route=route):
                code, _, raw = self.request("POST", route, "{}", auth=True)
                self.assertEqual(code, 404, raw)
        self.assertEqual(self.request("GET", "/api/monitor/resume")[0], 404)
        self.assertEqual(self.calls, [])

    def test_operation_id_is_forwarded_without_accepting_an_actor_override(self):
        identity = "aefcd303-411d-4de4-a306-f79fae7f6543"
        code, _, raw = self.post("pause", json.dumps({"operation_id": identity}))
        self.assertEqual(code, 200, raw)
        self.assertEqual(json.loads(raw)["operation_id"], identity)
        self.assertEqual(self.operation_ids, [identity])
        self.assertEqual(self.calls, ["pause"])
        self.assertEqual(json.loads(raw)["last_action"]["source"], "gui")
        for body in ({"operation_id": identity, "source": "mcp"}, {"operation_id": identity, "actor": "system"},
                     {"operation_id": identity, "unknown": True}):
            with self.subTest(body=body):
                code, _, raw = self.post("resume", json.dumps(body))
                self.assertEqual(code, 400, raw)
        self.assertEqual(self.calls, ["pause"])

    def test_duplicate_operation_keys_or_invalid_operation_ids_are_rejected_before_callback(self):
        bodies = ['{"operation_id":"one","operation_id":"two"}',
                  '{"operation_id":"same","operation_id":"same"}',
                  '{"operation_id":"one","unknown":1,"unknown":2}']
        bodies.extend(json.dumps({"operation_id": invalid}) for invalid in
                      (None, 1, [], {}, "", "x" * 129, "run command", "name\ncommand"))
        for body in bodies:
            with self.subTest(body=body):
                code, _, raw = self.post("start", body)
                self.assertEqual(code, 400, raw)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.operation_ids, [])

    def test_content_type_size_and_transfer_checks_precede_callback(self):
        for body, headers in (("{}", {"Content-Type": "text/plain"}), ("", {}), (" " * 257, {}),
                              ("{}", {"Content-Length": "invalid"}), ("{}", {"Transfer-Encoding": "chunked"})):
            with self.subTest(body_length=len(body), headers=headers):
                code, _, raw = self.post("resume", body, headers=headers)
                self.assertEqual(code, 400, raw)
        self.assertEqual(self.calls, [])

    def test_duplicate_origin_or_length_headers_are_rejected_before_callback(self):
        for duplicated in ("Origin", "Content-Length"):
            connection = http.client.HTTPConnection("127.0.0.1", self.web.server.server_port, timeout=5)
            try:
                connection.putrequest("POST", "/api/monitor/stop")
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Origin", self.web.url)
                connection.putheader("X-EventGuard-CSRF", self.web.token)
                connection.putheader("Content-Length", "2")
                connection.putheader(duplicated, self.web.url if duplicated == "Origin" else "2")
                connection.endheaders(b"{}")
                reply = connection.getresponse()
                raw = reply.read()
                self.assertEqual(reply.status, 403 if duplicated == "Origin" else 400, raw)
            finally:
                connection.close()
        self.assertEqual(self.calls, [])

    def test_callback_failure_or_bad_result_has_fixed_error_without_raw_exception(self):
        def fail(_action, **_options):
            raise RuntimeError("private secret path C:/private")
        self.web.monitor_control = fail
        code, _, raw = self.post("pause")
        self.assertEqual(code, 503)
        self.assertEqual(json.loads(raw)["error_code"], "monitor_control_failed")
        self.assertNotIn(b"private", raw)
        for result in ([], None, {"bad": object()}, {"bad": float("nan")}):
            self.web.monitor_control = lambda _action, value=result, **_options: value
            with self.subTest(result_type=type(result).__name__):
                code, _, raw = self.post("stop")
                self.assertEqual(code, 503, raw)
                self.assertEqual(json.loads(raw)["error_code"], "monitor_control_failed")

    def test_noncallable_callback_is_refused_before_binding_a_port(self):
        with self.assertRaisesRegex(ValueError, "invalid_monitor_control"):
            LocalWeb(self.root, "test", port=0, monitor_control="run command")


if __name__ == "__main__":
    unittest.main()
