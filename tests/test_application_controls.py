"""Application controls: mock contracts and one bounded Windows fixture flow.

No real collectors, provider, Codex, account initialization or model calls.
The Windows test uses the real application-owned Job and loopback HTTP path.
"""
from __future__ import annotations

import http.client
from contextlib import nullcontext
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from eventguard import background, processes
from eventguard.application import Application
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.operations import OperatorAPI
from eventguard.synthetic import make_synthetic

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "tests/fixtures/normal.json"


class ApplicationControlFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for relative in ("config/default.json", "config/rules.json", "playbooks/default.json", FIXTURE):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def application(self):
        app = Application(self.root, port=0, fixture=FIXTURE, max_cycles=100000, notifications=False)
        self.addCleanup(app.web.close)
        return app

    @staticmethod
    def request(app, method, route, data=None, *, csrf=True):
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers.update(Origin=app.web.url, **{"X-EventGuard-CSRF": app.web.token})
        connection = http.client.HTTPConnection("127.0.0.1", app.web.server.server_port, timeout=20)
        try:
            connection.request(method, route, json.dumps(data) if data is not None else None, headers)
            reply = connection.getresponse()
            return reply.status, json.loads(reply.read())
        finally:
            connection.close()


class MockApplicationControls(ApplicationControlFixture):
    """Fake ownership/control receipts; these do not prove a Windows stop."""
    def setUp(self):
        super().setUp()
        self.view = {"state": "not_started", "namespace": "test", "desired_enabled": False,
                     "host_liveness": "not_recorded"}
        self.starts = []
        self.closes = []

    def fake_start(self, root, **kwargs):
        self.assertEqual(root, self.root)
        self.assertEqual(kwargs["fixture"], FIXTURE)
        self.assertEqual(kwargs["max_cycles"], 100000)
        self.assertEqual(kwargs["lifetime_owner"], "application")
        if self.starts:
            self.assertEqual(kwargs["expected_control_generation"], self.view["control_generation"])
        index = len(self.starts) + 1
        generation, run_id = f"{index:032x}", f"{index+100:032x}"
        job_name = "Global\\EventGuard-" + f"{index+200:032x}"
        child = Mock(pid=index+1000, created_at="2026-10-24T00:00:00+00:00")
        child.job = Mock()
        child.job.name = job_name
        child._eventguard_background_scope = {"kind": "eventguard-background-owned-launch-v1",
            "run_id": run_id, "control_generation": generation, "job_name": job_name, "namespace": "test",
            "pid": child.pid, "created_at": child.created_at}
        kwargs["child_owner"](child)
        self.view = {"state": "running", "namespace": "test", "desired_enabled": True,
                     "host_liveness": "alive_verified", "run_id": run_id, "control_generation": generation,
                     "owner": dict(child._eventguard_background_scope)}
        self.starts.append(kwargs)
        return {**self.view, "state": "started", "lifetime_owner": "application", "lifetime_limited": True}

    def fake_close(self, owner, grace_seconds=5):
        self.closes.append(owner)
        owned = list(owner._background_children)
        owner._background_owner_closed.set()
        owner._background_children = []
        if owned:
            self.view.update(state="stopped", desired_enabled=False, host_liveness="exited_verified",
                             control_generation=f"{len(self.closes)+500:032x}")
        return {"state": "closed", "child_exited": True, "forcibly_terminated": False,
                "evidence_write_failed": False, "owned_monitors_remaining": 0}

    def run_mock(self, app, announce, *, start=None, close=None):
        with patch.object(background, "start", side_effect=start or self.fake_start), \
             patch.object(background, "status", side_effect=lambda _root: dict(self.view)), \
             patch.object(background, "stop", side_effect=AssertionError("Only the application's captured owner may stop")), \
             patch.object(OperatorAPI, "close_owned_monitor", autospec=True, side_effect=close or self.fake_close), \
             patch.object(app.web, "start"), patch.object(app.web, "close", return_value={"web_thread_exited": True}), \
             patch("eventguard.agent_service.start", side_effect=AssertionError("No agent provider allowed")), \
             patch("eventguard.agent_dispatch.spawn", side_effect=AssertionError("No model allowed")):
            return app.run(max_seconds=3, announce=announce)

    def test_invalid_action_cannot_start_stop_or_change_events(self):
        app = self.application()
        for action in ("start", "kill", "resume;command", "", None, [], {}):
            with self.subTest(kind=type(action).__name__), patch.object(background, "start") as start, \
                 patch.object(background, "stop") as stop:
                with self.assertRaisesRegex(ValueError, "^invalid_monitor_action$"):
                    app.monitor_control(action)
            start.assert_not_called()
            stop.assert_not_called()
        self.assertFalse((self.root / "data").exists())

    def test_pause_resume_preserve_same_fixture_event_and_handling_state(self):
        app = self.application()
        event = make_synthetic("listener")
        EventStore(self.root / "data/test").enqueue(event)
        catalog = EventCatalog(self.root, "test")
        def announce(_value):
            try:
                controls = app.status()["monitor_controls"]
                self.assertTrue(controls["available"])
                self.assertFalse(controls["paused"])
                self.assertEqual(app.monitor_control("pause")["state"], "paused")
                self.assertTrue(app.status()["monitor_controls"]["paused"])
                catalog.set_status(event["event_id"], "handled")
                self.assertEqual(app.monitor_control("resume")["state"], "running")
                self.assertFalse(app.status()["monitor_controls"]["paused"])
                self.assertEqual(catalog.detail(event["event_id"])["status"], "handled")
                self.assertEqual(catalog.detail(event["event_id"])["delivery_status"], "pending")
                self.assertEqual(len(self.starts), 2)
            finally:
                app.cancel.set()
        result = self.run_mock(app, announce)
        self.assertEqual(result["state"], "stopped")
        self.assertEqual(result["model_calls"], 0)

    def test_external_or_other_namespace_host_is_not_paused(self):
        for namespace in ("test", "live"):
            with self.subTest(namespace=namespace):
                app = self.application()
                self.closes.clear()
                self.view = {"state": "running", "namespace": namespace, "desired_enabled": True,
                    "host_liveness": "alive_verified", "run_id": "f"*32, "control_generation": "e"*32}
                def external(_root, **_kwargs):
                    return {**self.view, "state": "already_running"}  # No child_owner callback: not our child.
                def announce(_value):
                    try:
                        result = app.monitor_control("pause")
                        self.assertEqual(result["state"], "blocked")
                        self.assertEqual(result["reason"], "monitor_not_owned")
                        self.assertEqual(self.closes, [])
                        self.assertTrue(self.view["desired_enabled"])
                    finally:
                        app.cancel.set()
                self.run_mock(app, announce, start=external)
                self.assertTrue(self.view["desired_enabled"])

    def test_unknown_exit_or_failed_receipt_cannot_enable_resume(self):
        for fault in ({"child_exited": None}, {"evidence_write_failed": True}):
            with self.subTest(fault=fault):
                self.starts.clear()
                app = self.application()
                def close(owner, grace_seconds=5):
                    return {**self.fake_close(owner, grace_seconds), **fault}
                def announce(_value):
                    try:
                        result = app.monitor_control("pause")
                        self.assertEqual(result["state"], "shutdown_unconfirmed" if "child_exited" in fault else "blocked")
                        self.assertFalse(app.status()["monitor_controls"]["paused"])
                        self.assertEqual(app.monitor_control("resume")["state"], "blocked")
                        self.assertEqual(len(self.starts), 1)
                    finally:
                        app.cancel.set()
                self.run_mock(app, announce, close=close)

    def test_idempotent_controls_do_not_hide_changed_or_failed_saved_state(self):
        app = self.application()
        def announce(_value):
            try:
                self.view["state"] = "blocked"
                self.assertEqual(app.monitor_control("resume")["state"], "blocked")
                self.view["state"] = "running"
                self.assertEqual(app.monitor_control("pause")["state"], "paused")
                old_generation = self.view["control_generation"]
                self.view["control_generation"] = "f" * 32
                self.assertFalse(app.status()["monitor_controls"]["paused"])
                self.assertEqual(app.monitor_control("pause")["state"], "blocked")
                self.view["control_generation"] = old_generation
                self.view["host_liveness"] = "unknown"
                self.assertEqual(app.monitor_control("pause")["state"], "blocked")
                self.assertEqual(len(self.starts), 1)
            finally:
                app.cancel.set()
        self.run_mock(app, announce)

    def test_resume_rechecks_rules_before_launching_child(self):
        app = self.application()
        def announce(_value):
            try:
                self.assertEqual(app.monitor_control("pause")["state"], "paused")
                (self.root / "config/rules.json").write_text("invalid private instruction", encoding="utf-8")
                try:
                    result = app.monitor_control("resume")
                except ValueError:
                    result = {"state": "blocked"}
                self.assertEqual(result["state"], "blocked")
                self.assertNotIn("private instruction", str(result))
                self.assertEqual(len(self.starts), 1)
                self.assertTrue(app.status()["monitor_controls"]["paused"])
            finally:
                app.cancel.set()
        self.run_mock(app, announce)

    def test_stop_returns_before_cleanup_and_closed_application_cannot_resume(self):
        app = self.application()
        def announce(_value):
            result = app.monitor_control("stop")
            self.assertEqual(result["state"], "stop_requested")
            self.assertTrue(app.cancel.is_set())
            self.assertEqual(self.closes, [], "HTTP handler must not close its own server synchronously")
        self.run_mock(app, announce)
        self.assertEqual(len(self.closes), 1)
        with patch.object(background, "start") as start:
            result = app.monitor_control("resume")
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reason"], "monitor_application_closing")
        start.assert_not_called()

    def test_parallel_requests_allow_only_one_transition_and_expose_progress(self):
        app = self.application()
        entered, release = threading.Event(), threading.Event()
        results = []
        calls = []
        def close(owner, grace_seconds=5):
            if not calls:
                calls.append(True)
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("bounded mock barrier expired")
            return self.fake_close(owner, grace_seconds)
        def announce(_value):
            worker = threading.Thread(target=lambda: results.append(app.monitor_control("pause")), name="mock-app-pause")
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(app.status()["monitor_controls"]["transition"], "pause")
                self.assertEqual(app.monitor_control("pause")["state"], "busy")
                self.assertEqual(app.monitor_control("resume")["state"], "busy")
            finally:
                release.set()
                worker.join(timeout=3)
                app.cancel.set()
            self.assertFalse(worker.is_alive())
            self.assertEqual([value["state"] for value in results], ["paused"])
            self.assertIsNone(app.status()["monitor_controls"]["transition"])
            self.assertEqual(len(self.starts), 1)
        self.run_mock(app, announce, close=close)

    def test_resume_generation_guard_rejects_changed_scope_before_write_or_spawn(self):
        expected = "a"*32
        for changed in ({"generation": "b"*32, "namespace": "test", "enabled": False},
                        {"generation": expected, "namespace": "live", "enabled": False},
                        {"generation": expected, "namespace": "test", "enabled": True}):
            with self.subTest(changed=changed), \
                 patch.object(background, "_mutation", return_value=nullcontext()), \
                 patch.object(background, "_control", return_value=changed), \
                 patch.object(background, "status") as status, \
                 patch.object(background, "_write") as write, \
                 patch.object(processes, "identity", return_value={"state": "alive", "pid": 1234,
                              "created_at": "2026-10-24T00:00:00+00:00"}), \
                 patch.object(processes, "spawn_application_host") as spawn:
                result = background.start(self.root, fixture=FIXTURE, max_cycles=100000,
                    lifetime_owner="application", child_owner=lambda child: None,
                    expected_control_generation=expected)
            self.assertEqual(result["state"], "blocked")
            self.assertEqual(result["reason"], "background_control_generation_changed")
            status.assert_not_called()
            write.assert_not_called()
            spawn.assert_not_called()
        self.assertFalse((self.root / "data").exists())


@unittest.skipUnless(os.name == "nt", "Real Windows application-owned Job fixture")
class WindowsApplicationControls(ApplicationControlFixture):
    def test_real_fixture_http_run_pause_handle_resume_stop_preserves_pending(self):
        app = self.application()
        ready = threading.Event()
        outcomes, failures, children, receipts, requests = [], [], [], [], []
        original_spawn = processes.spawn_application_host
        def spawn(argv, **kwargs):
            child = original_spawn(argv, **kwargs)
            children.append(child)
            return child
        def run_application():
            try:
                outcomes.append(app.run(max_seconds=45, announce=lambda _value: ready.set()))
            except BaseException as error:
                failures.append(type(error).__name__)
                ready.set()
        worker = threading.Thread(target=run_application, name="fixture-product-application", daemon=True)
        event = make_synthetic("coverage")
        def request(method, route, data=None, *, csrf=True):
            code, value = self.request(app, method, route, data, csrf=csrf)
            requests.append({"method": method, "route": route, "http_status": code,
                             "state": value.get("state") if isinstance(value, dict) else None})
            return code, value
        try:
            with patch.object(processes, "spawn_application_host", side_effect=spawn), \
                 patch("eventguard.agent_service.start", side_effect=AssertionError("No provider allowed")), \
                 patch("eventguard.agent_dispatch.spawn", side_effect=AssertionError("No model allowed")):
                worker.start()
                self.assertTrue(ready.wait(20), "bounded application readiness")
                self.assertEqual(failures, [])
                self.assertEqual(request("GET", "/api/status")[0], 200)
                self.assertEqual(request("POST", "/api/monitor/pause", {}, csrf=False)[0], 403)
                code, paused = request("POST", "/api/monitor/pause", {})
                self.assertEqual(code, 200, paused)
                self.assertEqual(paused["state"], "paused", paused)
                code, saved = request("GET", "/api/status")
                self.assertEqual(code, 200)
                self.assertTrue(saved["monitor_controls"]["paused"])
                self.assertEqual(request("GET", "/api/sources")[0], 200, "Web must remain usable while paused")
                store = EventStore(self.root / "data/test")
                store.enqueue(event)
                route = "/api/events/" + event["event_id"]
                code, detail = request("GET", route)
                self.assertEqual(code, 200, detail)
                self.assertEqual(detail["event_id"], event["event_id"])
                self.assertEqual(detail["delivery_status"], "pending")
                code, handled = request("POST", route + "/status", {"status": "handled"})
                self.assertEqual(code, 200, handled)
                code, resumed = request("POST", "/api/monitor/resume", {})
                self.assertEqual(code, 200, resumed)
                self.assertEqual(resumed["state"], "running", resumed)
                code, detail = request("GET", route)
                self.assertEqual(code, 200, detail)
                self.assertEqual(detail["status"], "handled")
                self.assertEqual(detail["delivery_status"], "pending")
                code, stopping = request("POST", "/api/monitor/stop", {})
                self.assertEqual(code, 200, stopping)
                self.assertEqual(stopping["state"], "stop_requested")
                worker.join(timeout=15)
                self.assertFalse(worker.is_alive(), "application stops after sending HTTP receipt")
        finally:
            app.cancel.set()
            if worker.ident is not None:
                worker.join(timeout=15)
            for child in children:
                try:
                    receipt = processes.finish(child, "test_teardown", grace=1, request_stop=False)
                except (OSError, ValueError, RuntimeError):
                    receipt = {"child_exited": None, "remaining_owned_processes": None,
                               "reason": "test_owned_exit_unconfirmed"}
                receipts.append(receipt)
            if worker.ident is not None and worker.is_alive():
                worker.join(timeout=3)
            self.evidence = {"scope": "real Windows application-owned Jobs and loopback HTTP; synthetic fixture only",
                "launch_api": "spawn_application_host", "lifetime_limited": True,
                "event_id": event["event_id"], "http": requests, "application": outcomes,
                "child_receipts": receipts, "failures": failures, "provider_attempt_count": 0,
                "model_calls": 0, "native_inventory_executed": False,
                "application_thread_exited": not worker.is_alive()}
        self.assertEqual(failures, [])
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["state"], "stopped", outcomes)
        self.assertEqual(outcomes[0]["model_calls"], 0)
        self.assertTrue(outcomes[0]["web"]["web_thread_exited"])
        self.assertTrue(outcomes[0]["monitor"]["child_exited"])
        self.assertEqual(len(children), 2, "one initial host and one explicit same-scope resume")
        self.assertTrue(all(receipt["child_exited"] is True and receipt["exit_code"] == 0
                            and receipt["remaining_owned_processes"] == 0
                            and receipt["forcibly_terminated"] is False for receipt in receipts),
                        {"child_receipts": receipts, "application": outcomes, "http": requests,
                         "failures": failures})
        detail = EventCatalog(self.root, "test").detail(event["event_id"])
        self.assertEqual(detail["status"], "handled")
        self.assertEqual(detail["delivery_status"], "pending")
        self.assertEqual(detail["event_id"], event["event_id"])
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
