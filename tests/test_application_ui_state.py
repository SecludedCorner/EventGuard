"""Served UI contract and browser-ready pure-state vectors.

Uses Python standard library and real loopback HTTP. No monitor/model starts.
These tests inspect delivered assets and state metadata, not JavaScript runtime
behavior. ``mapping_cases`` and ``ordering_cases`` are shared with the separate
real-browser acceptance; static assertions must not be reported as race proof.
"""
import copy
from html.parser import HTMLParser
import http.client
import json
from pathlib import Path
import re
import tempfile
import unittest

from eventguard.web import LocalWeb


def application_snapshot(state="running", *, revision=8, instance="a" * 32):
    stopped, paused = state == "stopped", state == "paused"
    return {"instance_id": instance, "state_revision": revision, "monitor_state": state,
            "monitor_controls": {"available": True, "paused": paused, "stopped": stopped,
                "transition": None, "can_start": stopped, "can_pause": state == "running",
                "can_resume": paused, "can_stop": state in {"running", "paused"}, "can_shutdown": True},
            "last_action": {"action": "start", "source": "startup", "state": "succeeded",
                "result_code": "fixture_backend_confirmed", "operation_id": "fixture-startup",
                "at": "2026-10-24T00:00:00+00:00", "revision": revision}, "model_calls": 0}


def mapping_cases():
    """Inputs/expected outputs for EventGuardUI.deriveApplicationView in a browser."""
    cases = []
    for state, tone in (("running", "green"), ("paused", "amber"), ("stopped", "gray"),
                        ("closing", "blue"), ("blocked", "red"), ("unknown", "red")):
        cases.append({"name": state, "snapshot": application_snapshot(state),
                      "options": {"connected": True, "fresh": True}, "key": state, "tone": tone})
    processing = application_snapshot()
    processing["monitor_controls"]["transition"] = "pausing"
    processing["last_action"]["state"] = "processing"
    cases.append({"name": "transition", "snapshot": processing, "options": {"connected": True, "fresh": True},
                  "key": "processing", "tone": "blue", "all_disabled": True})
    processing_without_transition = application_snapshot()
    processing_without_transition["last_action"]["state"] = "processing"
    cases.append({"name": "processing_action", "snapshot": processing_without_transition,
                  "options": {"connected": True, "fresh": True}, "key": "processing", "tone": "blue", "all_disabled": True})
    for action_state, key in (("failed", "failed"), ("unknown", "unknown")):
        snapshot = application_snapshot()
        snapshot["last_action"]["state"] = action_state
        cases.append({"name": "action_" + action_state, "snapshot": snapshot,
                      "options": {"connected": True, "fresh": True}, "key": key, "tone": "red"})
    for label, options, expected in (("offline", {"connected": False, "fresh": False}, "offline"),
                                     ("stale", {"connected": True, "fresh": False}, "stale"),
                                     ("pending", {"connected": True, "fresh": True, "requestPending": True}, "processing")):
        cases.append({"name": label, "snapshot": application_snapshot(), "options": options,
                      "key": expected, "tone": "blue" if label == "pending" else "red", "all_disabled": True})
    blocked = application_snapshot("blocked")
    blocked["monitor_controls"].update(can_start=False, can_pause=False, can_resume=False, can_stop=False)
    cases.append({"name": "blocked_owned_shutdown", "snapshot": blocked, "options": {"connected": True, "fresh": True},
                  "key": "blocked", "tone": "red", "permissions": {"start": False, "pause": False,
                      "resume": False, "stop": False, "shutdown": True}})
    malformed = application_snapshot()
    del malformed["monitor_controls"]["can_shutdown"]
    cases.append({"name": "missing_capability", "snapshot": malformed, "options": {"connected": True, "fresh": True},
                  "key": "invalid", "tone": "red", "all_disabled": True})
    inconsistent = application_snapshot()
    inconsistent["monitor_controls"]["paused"] = True
    cases.append({"name": "inconsistent_running", "snapshot": inconsistent,
                  "options": {"connected": True, "fresh": True}, "key": "unknown", "tone": "red"})
    return cases


def ordering_cases():
    """Inputs/expected decisions for the exported pure acceptStatusDecision."""
    current = {"instanceId": "a" * 32, "stateRevision": 8, "lastAppliedSeq": 20}
    return [
        {"name": "first_sample", "current": {"instanceId": None, "stateRevision": -1, "lastAppliedSeq": -1},
         "snapshot": application_snapshot(), "sequence": 1, "expectedInstance": None, "decision": "apply"},
        {"name": "older_revision_newer_request", "current": current,
         "snapshot": application_snapshot(revision=7), "sequence": 21, "expectedInstance": "a" * 32, "decision": "ignore"},
        {"name": "older_request_same_revision", "current": current,
         "snapshot": application_snapshot(), "sequence": 19, "expectedInstance": "a" * 32, "decision": "ignore"},
        {"name": "higher_revision_older_request", "current": current,
         "snapshot": application_snapshot(revision=9), "sequence": 19, "expectedInstance": "a" * 32, "decision": "apply"},
        {"name": "new_instance", "current": current,
         "snapshot": application_snapshot(revision=0, instance="b" * 32), "sequence": 21,
         "expectedInstance": "a" * 32, "decision": "reload"},
        {"name": "old_instance_late_reply", "current": current,
         "snapshot": application_snapshot(instance="b" * 32), "sequence": 19,
         "expectedInstance": "a" * 32, "decision": "ignore"},
        {"name": "request_from_previous_instance", "current": current,
         "snapshot": application_snapshot(instance="b" * 32), "sequence": 21,
         "expectedInstance": "c" * 32, "decision": "ignore"},
    ]


class PageElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = {}

    def handle_starttag(self, tag, attributes):
        fields = dict(attributes)
        if "id" in fields:
            self.elements[fields["id"]] = {"tag": tag, **fields}


class ApplicationUIContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.view = application_snapshot()
        self.calls = []
        self.web = LocalWeb(self.root, "test", port=0, status_provider=lambda: copy.deepcopy(self.view),
                            monitor_control=lambda *args, **kwargs: self.calls.append((args, kwargs)) or {})
        self.web.start()
        self.addCleanup(self.close_web)

    def close_web(self):
        self.assertTrue(self.web.close()["web_thread_exited"])

    def request(self, route):
        connection = http.client.HTTPConnection("127.0.0.1", self.web.server.server_port, timeout=5)
        try:
            connection.request("GET", route)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode("utf-8")
        finally:
            connection.close()

    def test_page_separates_collection_stop_from_application_shutdown(self):
        code, headers, page = self.request("/")
        self.assertEqual(code, 200)
        elements = PageElements()
        elements.feed(page)
        for action in ("start", "pause", "resume", "stop", "shutdown"):
            button = elements.elements["monitor-" + action]
            self.assertEqual(button["tag"], "button")
            self.assertIn("disabled", button)
        self.assertIn("停止採集", page)
        self.assertIn("關閉程式", page)
        self.assertIn("網頁與 MCP 仍可使用", page)
        self.assertIn("監看", page)
        self.assertIn("monitor-last-action", elements.elements)
        self.assertIn("monitor-result", elements.elements)
        self.assertEqual(elements.elements["run-state"]["role"], "status")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.calls, [])

    def test_http_status_preserves_identity_revision_actor_and_capabilities(self):
        for state in ("running", "paused", "stopped", "blocked", "unknown", "closing"):
            self.view = application_snapshot(state, revision=12)
            self.view["last_action"]["source"] = "mcp"
            with self.subTest(state=state):
                code, _, raw = self.request("/api/status")
                self.assertEqual(code, 200, raw)
                actual = json.loads(raw)
                for key in ("instance_id", "state_revision", "monitor_state", "last_action", "monitor_controls"):
                    self.assertEqual(actual[key], self.view[key])
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / "data").exists())

    def test_delivered_state_palette_uses_text_icons_and_explicit_failure_colors(self):
        code, headers, script = self.request("/app.js")
        self.assertEqual(code, 200)
        match = re.search(r"const APP_STATE_PRESENTATION = (\{[^\n]+\});", script)
        self.assertIsNotNone(match)
        table = json.loads(match.group(1))
        expected = {"running": "green", "paused": "amber", "stopped": "gray", "processing": "blue",
                    "closing": "blue", "blocked": "red", "unknown": "red", "failed": "red",
                    "offline": "red", "stale": "red", "invalid": "red", "reloading": "blue"}
        self.assertEqual({key: value["tone"] for key, value in table.items()}, expected)
        for value in table.values():
            self.assertTrue(value["icon"].strip())
            self.assertTrue(value["label"].strip())
        for key in ("unknown", "offline", "stale"):
            self.assertIn("未確認", table[key]["label"])
        self.assertIn("尚未確認", table["closing"]["label"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_source_cards_use_separate_history_freshness_and_current_status(self):
        code, _, page = self.request("/")
        self.assertEqual(code, 200)
        self.assertIn('id="source-cards"', page)
        code, _, script = self.request("/app.js")
        self.assertEqual(code, 200)
        match = re.search(r"async function sources\(\)\{([^\n]+)", script)
        self.assertIsNotNone(match)
        source_renderer = match.group(1)
        for required in ("$('source-cards')", "s.last_collected_at", "s.saved_status", "s.status",
                         "sourceSuccess(s)", "sourceFreshness(s)", "s.row_count", "s.reasons"):
            self.assertIn(required, source_renderer)
        self.assertNotIn("innerHTML", source_renderer)
        self.assertIn("s.last_success_state!=='known'", script)
        self.assertIn("time<=Date.now()", script)
        self.assertEqual(self.calls, [])

    def test_three_source_http_reads_preserve_synthetic_event_and_saved_files(self):
        from eventguard.events.store import EventStore
        from eventguard.runtime import Runtime
        from eventguard.synthetic import make_synthetic
        store = EventStore(self.root / "data" / "test")
        store.enqueue(make_synthetic("listener"))
        Runtime(self.root).save_observation({"id": "defender", "status": "ok", "rows": [],
            "observed_at": "2026-10-24T00:00:00+00:00", "coverage": {"status": "ok", "errors": []}}, "test")
        files = lambda: {p.relative_to(self.root): p.read_bytes() for p in
                         (self.root / "data").rglob("*") if p.is_file()}
        before_files, before_stats = files(), store.stats()
        for _ in range(3):
            code, _, raw = self.request("/api/sources")
            self.assertEqual(code, 200)
            self.assertEqual(len(json.loads(raw)["sources"]), 7)
        self.assertEqual(files(), before_files)
        self.assertEqual(store.stats(), before_stats)
        self.assertEqual(before_stats["pending"], 1)
        self.assertEqual(self.calls, [])

    def test_event_page_exposes_source_gap_summary_independently_of_event_rows(self):
        code, _, page = self.request("/")
        self.assertEqual(code, 200)
        event_section = page.split('<section id="events">', 1)[1].split('<section id="sources"', 1)[0]
        self.assertIn('id="source-gap-summary" role="status"', event_section)
        self.assertIn("不代表主機安全", event_section)
        code, _, script = self.request("/app.js")
        self.assertEqual(code, 200)
        renderer = script.split("async function sourceGap(){", 1)[1].split("async function events(){", 1)[0]
        for required in ("/api/sources", "SOURCE_IDS.length", "indexed.has(row.source_id)",
                         "status!=='ok'", "freshness!=='fresh'", "來源狀態無法確認"):
            self.assertIn(required, renderer)
        self.assertIn("sequence!==sourceGapSequence", renderer)
        self.assertIn("sequence===sourceGapSequence", renderer)
        self.assertIn("if(busy){refreshQueued=true;return;}", script)
        self.assertIn("queueMicrotask(refresh)", script)
        self.assertNotIn("event-rows", renderer)
        self.assertNotIn("innerHTML", renderer)
        self.assertEqual(self.calls, [])

    def test_served_script_exposes_pure_state_functions_and_bounded_timeouts(self):
        code, _, script = self.request("/app.js")
        self.assertEqual(code, 200)
        self.assertIn("window.EventGuardUI=Object.freeze", script)
        for name in ("deriveApplicationView", "acceptStatusDecision", "isStatusSnapshot"):
            self.assertIn("function " + name + "(", script)
        constants = {key: int(value) for key, value in re.findall(
            r"(STATUS_TIMEOUT_MS|CONTROL_TIMEOUT_MS|STATUS_POLL_MS|STATUS_STALE_MS)=(\d+)", script)}
        self.assertEqual(constants, {"STATUS_TIMEOUT_MS": 4000, "CONTROL_TIMEOUT_MS": 30000,
                                     "STATUS_POLL_MS": 1000, "STATUS_STALE_MS": 5000})
        self.assertIn("new AbortController()", script)
        self.assertIn("window.crypto.randomUUID()", script)
        self.assertIn("operation_id:request.operationId", script)
        self.assertIn("window.location.reload()", script)
        self.assertEqual(self.calls, [])
        self.evidence = {"scope": "real loopback served assets and declarative UI state contract",
                         "javascript_executed": False, "browser_race_verified": False,
                         "pure_mapping_vectors": len(mapping_cases()), "ordering_vectors": len(ordering_cases()),
                         "model_calls": 0}


if __name__ == "__main__":
    unittest.main()
