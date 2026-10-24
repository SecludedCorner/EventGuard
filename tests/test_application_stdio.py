"""Real owned stdio transports and synthetic applications; never a model.

All children enter private Windows Jobs before execution. The existing CLI
entry is root-injected into temporary fixture roots. No MCP configuration,
account state, native collection, installation or formal monitor is touched.
"""
from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from eventguard import processes
from eventguard.application import Application
from eventguard.application_mcp import APPLICATION_TOOLS
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.runtime import read_json
from eventguard.synthetic import make_synthetic
from test_operator_clients import Client

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "tests/fixtures/normal.json"
SDK_AVAILABLE = all(importlib.util.find_spec(name) is not None for name in ("mcp", "uvicorn", "starlette"))


class ApplicationClient(Client):
    """Reuse the existing initialize/call grammar with a bounded CLI reader."""
    def __init__(self, root):
        arguments = ["mcp", "--fixture", FIXTURE, "--max-cycles", "100000", "--port", "0", "--max-seconds", "75"]
        entry = ("import sys;from pathlib import Path;sys.path.insert(0," + repr(str(ROOT / "src")) + ");"
                 "from eventguard.cli import main;raise SystemExit(main(" + repr(arguments)
                 + ",root=Path(" + repr(str(root)) + ")))" )
        self.child = processes.spawn([sys.executable, "-B", "-c", entry], cwd=str(ROOT),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.incoming, self.transcript, self.stderr = queue.Queue(maxsize=64), [], bytearray()
        self.request_id = 0
        self.receipt = None
        def incoming(value):
            try:
                self.incoming.put_nowait(value)
            except queue.Full:
                pass  # The bounded request will fail; no unbounded reader backlog.
        def read():
            try:
                while line := self.child.stdout.readline(2*1024*1024+1):
                    if len(line) > 2*1024*1024:
                        incoming({"protocol_error": "stdio_line_capacity"})
                        break
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeError):
                        incoming({"protocol_error": "stdio_invalid_json"})
                        break
                    incoming(value)
            finally:
                incoming({"eof": True})
        def errors():
            while chunk := self.child.stderr.read(4096):
                self.stderr.extend(chunk[:max(0, 16384-len(self.stderr))])
        self.readers = [threading.Thread(target=read, name="fixture-stdio-reader", daemon=True),
                        threading.Thread(target=errors, name="fixture-stdio-stderr", daemon=True)]
        for reader in self.readers:
            reader.start()

    def request(self, method, params):
        self.request_id += 1
        self.send({"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params})
        deadline = time.monotonic()+40
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise AssertionError("bounded_application_stdio_response_timeout")
            try:
                response = self.incoming.get(timeout=remaining)
            except queue.Empty:
                raise AssertionError("bounded_application_stdio_response_timeout") from None
            if not isinstance(response, dict) or response.get("eof") or response.get("protocol_error"):
                raise AssertionError({"reason": "application_stdio_response_missing_or_invalid",
                    "exit_code": self.child.poll(), "stderr_sha256": hashlib.sha256(self.stderr).hexdigest()})
            if "id" not in response:
                continue  # Protocol notifications do not satisfy a request.
            self.transcript.append({"response": response})
            if response.get("id") != self.request_id or "error" in response:
                raise AssertionError("application_stdio_response_id_or_error")
            return response["result"]

    def close(self):
        if self.receipt is not None:
            return self.receipt
        try:
            if self.child.stdin is not None and not self.child.stdin.closed:
                try:
                    self.child.stdin.close()  # Cooperation first, no process signal.
                except (OSError, ValueError):
                    pass
            try:
                self.child.wait(timeout=35)
            except subprocess.TimeoutExpired:
                pass  # The following own-Job receipt must expose any force.
        finally:
            self.receipt = processes.finish(self.child, "test_teardown", grace=2, request_stop=False)
            for reader in self.readers:
                reader.join(timeout=2)
            for stream, reader in zip((self.child.stdout, self.child.stderr), self.readers):
                if stream is not None and not reader.is_alive():
                    stream.close()
        return self.receipt


@unittest.skipUnless(os.name == "nt" and SDK_AVAILABLE,
                     "Real Windows private Jobs and existing optional MCP SDK dependencies required")
class ApplicationStdioTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for relative in ("config/default.json", "config/rules.json", "playbooks/default.json", FIXTURE):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        self.event = make_synthetic("listener")
        self.store = EventStore(self.root / "data/test")
        self.store.enqueue(self.event)

    def assert_natural(self, client):
        receipt = client.receipt
        self.assertEqual(receipt["exit_code"], 0, receipt)
        self.assertTrue(receipt["managed"], receipt)
        self.assertTrue(receipt["child_exited"], receipt)
        self.assertEqual(receipt["remaining_owned_processes"], 0, receipt)
        self.assertFalse(receipt["forcibly_terminated"], receipt)
        self.assertFalse(any(reader.is_alive() for reader in client.readers))

    def initialize_idle(self, client):
        tools = client.initialize()
        self.assertEqual({tool["name"] for tool in tools}, APPLICATION_TOOLS)
        self.assertEqual(len(tools), 9)
        self.assertNotIn("ack_event", {tool["name"] for tool in tools})
        value = client.call("status")
        self.assertEqual(value["namespace"], "test")
        self.assertRegex(value["instance_id"], r"^[a-f0-9]{32}$")
        self.assertEqual(value["monitor_state"], "stopped")
        self.assertTrue(value["monitor_controls"]["stopped"])
        self.assertEqual(value["model_calls"], 0)
        self.assertFalse((self.root / "data/background/control.json").exists(), "Initialize must not start collection")
        return value

    @staticmethod
    def http(app_url, method, route, data=None, *, token=None):
        target = urlsplit(app_url)
        if target.scheme != "http" or target.hostname != "127.0.0.1":
            raise AssertionError("fixture_loopback_url_required")
        connection = http.client.HTTPConnection("127.0.0.1", target.port, timeout=20)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers.update(Origin=app_url, **{"X-EventGuard-CSRF": token})
        try:
            connection.request(method, route, json.dumps(data) if data is not None else None, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_owned_idle_stdio_start_stop_read_and_eof_preserve_pending(self):
        client = ApplicationClient(self.root)
        initial = None
        try:
            initial = self.initialize_idle(client)
            self.assertEqual(client.call("list_events")["events"][0]["event_id"], self.event["event_id"])
            started = client.call("start_monitor", operation_id="stdio-start")
            self.assertEqual(started["state"], "running", started)
            stopped = client.call("stop_monitor", operation_id="stdio-stop")
            self.assertEqual(stopped["state"], "stopped", stopped)
            self.assertFalse(stopped.get("forcibly_terminated"), stopped)
            current = client.call("status")
            self.assertEqual(current["instance_id"], initial["instance_id"])
            self.assertEqual(current["monitor_state"], "stopped")
            self.assertTrue(current["monitor_controls"]["can_start"])
            detail = client.call("inspect_event", event_id=self.event["event_id"])
            self.assertEqual(detail["event_id"], self.event["event_id"])
            self.assertEqual(detail["delivery_status"], "pending")
        finally:
            client.close()
            self.evidence = {"scope": "real Windows owned stdio SDK/CLI and synthetic fixture; no agent/model/native sources",
                "case": "new_idle_owned_application", "instance_id": initial.get("instance_id") if initial else None,
                "event_id": self.event["event_id"], "stdio_process": client.receipt,
                "protocol": client.transcript, "model_calls": 0, "native_provider_queries": 0}
        self.assert_natural(client)
        exit_receipt = read_json(self.root / "data/application/stdio-exit.json")
        self.assertEqual(exit_receipt["instance_id"], initial["instance_id"])
        self.assertTrue(exit_receipt["owned_application"])
        self.assertTrue(exit_receipt["application_thread_exited"])
        self.assertEqual(exit_receipt["state"], "closed")
        monitor_stop = read_json(self.root / "data/background/operator-stop-receipt.json")
        self.assertFalse(monitor_stop["forcibly_terminated"], monitor_stop)
        self.assertTrue(monitor_stop["child_exited"], monitor_stop)
        self.assertEqual(len(monitor_stop["results"]), 1)
        process = monitor_stop["results"][0]["process"]
        self.assertEqual(process["exit_code"], 0, monitor_stop)
        self.assertEqual(process["remaining_owned_processes"], 0, monitor_stop)
        self.assertFalse(process["forcibly_terminated"], monitor_stop)
        self.assertEqual(self.store.get_event(self.event["event_id"])["delivery_status"], "pending")
        self.assertEqual(self.store.stats()["receipt_count"], 0)
        self.evidence.update(owned_application_exit=exit_receipt, monitor_stop=monitor_stop,
                             pending_retained=True, ack_count=0)

    def test_observer_stdio_attaches_same_gui_instance_and_eof_does_not_stop_it(self):
        app = Application(self.root, port=0, fixture=FIXTURE, max_cycles=100000,
                          notifications=False, auto_start=False, mcp_enabled=False)
        ready = threading.Event()
        outcomes, failures = [], []
        def run():
            try:
                outcomes.append(app.run(max_seconds=75, announce=lambda _value: ready.set()))
            except BaseException as error:
                failures.append(type(error).__name__)
                ready.set()
        worker = threading.Thread(target=run, name="fixture-existing-gui", daemon=True)
        client = None
        try:
            worker.start()
            self.assertTrue(ready.wait(20))
            self.assertEqual(failures, [])
            before = app.status()
            client = ApplicationClient(self.root)
            initial = self.initialize_idle(client)
            self.assertEqual(initial["instance_id"], app.instance_id)
            self.assertEqual(initial["namespace"], app.namespace)
            changed = client.call("set_event_status", event_id=self.event["event_id"], status="read",
                                  operation_id="observer-handling")
            self.assertFalse(changed["ack_performed"])
            self.assertEqual(app.event_detail(self.event["event_id"])["status"], "read")
            self.assertGreater(app.status()["state_revision"], before["state_revision"])
            client.close()
            self.assert_natural(client)
            self.assertTrue(worker.is_alive(), "Observer EOF must not close the GUI")
            self.assertFalse(app.cancel.is_set())
            code, after = self.http(app.web.url, "GET", "/api/status")
            self.assertEqual(code, 200, after)
            self.assertEqual(after["instance_id"], app.instance_id)
            self.assertEqual(after["monitor_state"], "stopped")
            self.assertFalse((self.root / "data/application/stdio-exit.json").exists(), "Observer must not claim owned application exit")
        finally:
            try:
                if client is not None:
                    client.close()
            finally:
                try:
                    app.monitor_control("shutdown", source="system", operation_id="observer-test-cleanup")
                finally:
                    app.cancel.set()
                    if worker.ident is not None:
                        worker.join(timeout=25)
                    self.evidence = {"scope": "real Windows observer stdio forwards to existing fixture GUI; no model/native sources",
                        "case": "observer_eof_keeps_gui", "instance_id": app.instance_id, "event_id": self.event["event_id"],
                        "stdio_process": client.receipt if client else None, "protocol": client.transcript if client else [],
                        "application": outcomes, "application_thread_exited": not worker.is_alive(),
                        "failures": failures, "model_calls": 0, "native_provider_queries": 0}
                    if worker.ident is None:
                        app.web.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["state"], "stopped", outcomes)
        self.assertEqual(self.store.get_event(self.event["event_id"])["delivery_status"], "pending")
        self.assertEqual(self.store.stats()["receipt_count"], 0)

    def test_two_observers_share_control_lock_busy_and_replay_one_real_monitor(self):
        app = Application(self.root, port=0, fixture=FIXTURE, max_cycles=100000,
                          notifications=False, auto_start=False, mcp_enabled=False)
        ready, entered, release = threading.Event(), threading.Event(), threading.Event()
        outcomes, failures, clients, children, receipts = [], [], [], [], []
        first_results, first_failures, busy_results, barrier_calls = [], [], [], []
        operation_id = "two-observers-first-start"
        original_start = app._start_monitor

        def gated_start(**options):
            # Only control timing. The original method still performs every
            # scope/rule check and the real application-owned native Job spawn.
            barrier_calls.append({"at": time.monotonic(), "spawn_completed": False})
            entered.set()
            if not release.wait(15):
                raise RuntimeError("controlled_start_barrier_timeout")
            try:
                result = original_start(**options)
                barrier_calls[-1]["spawn_completed"] = result.get("state") == "started"
                return result
            finally:
                with app.owner._background_owner_lock:
                    for record in app.owner._background_children:
                        if record["child"] not in children:
                            children.append(record["child"])

        def run():
            try:
                outcomes.append(app.run(max_seconds=75, announce=lambda _value: ready.set()))
            except BaseException as error:
                failures.append(type(error).__name__)
                ready.set()

        def first_start():
            try:
                first_results.append(clients[0].call("start_monitor", operation_id=operation_id))
            except BaseException as error:
                first_failures.append(type(error).__name__)

        worker = threading.Thread(target=run, name="fixture-two-observer-gui", daemon=True)
        starter = threading.Thread(target=first_start, name="fixture-first-stdio-start", daemon=True)
        stop_result, active, replay = None, None, None
        with patch.object(app, "_start_monitor", side_effect=gated_start):
            try:
                worker.start()
                self.assertTrue(ready.wait(20), "bounded existing GUI readiness")
                self.assertEqual(failures, [])
                for _ in range(2):
                    client = ApplicationClient(self.root)
                    clients.append(client)
                    initial = self.initialize_idle(client)
                    self.assertEqual(initial["instance_id"], app.instance_id)
                    self.assertEqual(initial["namespace"], app.namespace)
                starter.start()
                self.assertTrue(entered.wait(10), "first MCP call must enter the owned control operation")
                active = app.status()
                self.assertEqual(active["monitor_controls"]["transition"], "start")
                self.assertEqual(active["last_action"]["operation_id"], operation_id)
                self.assertEqual(active["last_action"]["source"], "mcp")
                self.assertEqual(active["last_action"]["state"], "processing")
                self.assertEqual(children, [], "barrier precedes the actual native spawn")
                self.assertFalse((self.root / "data/background/control.json").exists())
                # A separate operation, its retry, and the original operation
                # ID all observe busy while the same application owns the lock.
                for contender_id in ("two-observers-contender", "two-observers-contender", operation_id):
                    began = time.monotonic()
                    result = clients[1].call("start_monitor", operation_id=contender_id)
                    elapsed = time.monotonic() - began
                    busy_results.append({"operation_id": contender_id, "elapsed_seconds": elapsed, "result": result})
                    self.assertEqual(result["state"], "busy", result)
                    self.assertLess(elapsed, 3, "busy must not wait for the first native start")
                    self.assertFalse(result["replayed"])
                    self.assertEqual(result["instance_id"], app.instance_id)
                    self.assertEqual(result["last_action"], active["last_action"])
                    self.assertEqual(result["state_revision"], active["state_revision"])
                during = clients[1].call("status")
                self.assertEqual(during["last_action"], active["last_action"])
                self.assertEqual(during["monitor_controls"]["transition"], "start")
                release.set()
                starter.join(timeout=35)
                self.assertFalse(starter.is_alive(), "bounded first MCP start response")
                self.assertEqual(first_failures, [])
                self.assertEqual(len(first_results), 1)
                self.assertEqual(first_results[0]["state"], "running", first_results)
                self.assertEqual(len(children), 1, "only the admitted call may create an owned monitor")
                self.assertIsNone(children[0].poll(), "the real fixture host must be running")
                self.assertEqual(app.status()["monitor_state"], "running")
                replay = clients[1].call("start_monitor", operation_id=operation_id)
                self.assertEqual(replay["state"], "running", replay)
                self.assertTrue(replay["replayed"], replay)
                self.assertEqual(replay["original_revision"], first_results[0]["state_revision"])
                self.assertEqual(replay["last_action"], first_results[0]["last_action"])
                self.assertEqual(len(barrier_calls), 1, "a replay must not enter the launch method again")
                with app.owner._background_owner_lock:
                    self.assertEqual(len(app.owner._background_children), 1)
                    self.assertIs(app.owner._background_children[0]["child"], children[0])
                stop_result = clients[1].call("stop_monitor", operation_id="two-observers-stop")
                self.assertEqual(stop_result["state"], "stopped", stop_result)
                self.assertFalse(stop_result.get("forcibly_terminated"), stop_result)
                self.assertTrue(stop_result["child_exited"], stop_result)
                for client in clients:
                    detail = client.call("inspect_event", event_id=self.event["event_id"])
                    self.assertEqual(detail["event_id"], self.event["event_id"])
                    self.assertEqual(detail["delivery_status"], "pending")
                    client.close()
                    self.assert_natural(client)
                self.assertTrue(worker.is_alive(), "both observer EOFs must keep the GUI alive")
                self.assertFalse(app.cancel.is_set())
                self.assertEqual(self.http(app.web.url, "GET", "/api/status")[0], 200)
                self.assertFalse((self.root / "data/application/stdio-exit.json").exists())
            finally:
                release.set()
                if starter.ident is not None:
                    starter.join(timeout=40)
                try:
                    for client in clients:
                        client.close()
                finally:
                    try:
                        app.monitor_control("shutdown", source="system", operation_id="two-observers-cleanup")
                    finally:
                        app.cancel.set()
                        if worker.ident is not None:
                            worker.join(timeout=25)
                        else:
                            app.web.close()
                        for child in children:
                            receipts.append(processes.finish(child, "test_teardown", grace=1, request_stop=False))
                        self.evidence = {
                            "scope": "real Windows dual observer stdio and application-owned fixture Job; controlled timing barrier; no model/native sources",
                            "case": "two_observers_busy_then_replay", "instance_id": app.instance_id,
                            "namespace": app.namespace, "event_id": self.event["event_id"],
                            "timing_control": "Event barrier inside original _start_monitor wrapper before real backend spawn",
                            "barrier_calls": barrier_calls, "active_action": active,
                            "busy_responses": busy_results, "first_results": first_results, "replay": replay,
                            "stop": stop_result, "original_monitor_stop": app._pause_receipt,
                            "stdio_processes": [client.receipt for client in clients],
                            "protocols": [client.transcript for client in clients],
                            "monitor_processes": receipts, "application": outcomes,
                            "application_thread_exited": not worker.is_alive(),
                            "first_request_thread_exited": not starter.is_alive(),
                            "failures": failures, "first_request_failures": first_failures,
                            "model_calls": 0, "native_provider_queries": 0}
        self.assertFalse(worker.is_alive())
        self.assertFalse(starter.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(first_failures, [])
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["state"], "stopped", self.evidence)
        self.assertTrue(outcomes[0]["monitor"]["child_exited"], self.evidence)
        self.assertFalse(outcomes[0]["monitor"]["forcibly_terminated"], self.evidence)
        self.assertEqual(len(receipts), 1, self.evidence)
        for receipt in receipts:
            self.assertEqual(receipt["exit_code"], 0, self.evidence)
            self.assertTrue(receipt["child_exited"], self.evidence)
            self.assertEqual(receipt["remaining_owned_processes"], 0, self.evidence)
            self.assertFalse(receipt["forcibly_terminated"], self.evidence)
        self.assertEqual(self.store.get_event(self.event["event_id"])["delivery_status"], "pending")
        self.assertEqual(self.store.stats()["receipt_count"], 0)
        self.evidence.update(pending_retained=True, ack_count=0)

    def test_owned_gui_shutdown_exits_stdio_while_stdin_remains_open(self):
        client = ApplicationClient(self.root)
        initial = None
        stdin_open_exit_verified = False
        try:
            initial = self.initialize_idle(client)
            # This capability belongs only to the newly created synthetic app.
            # Never retain it in transcripts/evidence or read an account secret.
            descriptor = read_json(self.root / "data/application/connection.json")
            self.assertEqual(descriptor["instance_id"], initial["instance_id"])
            self.assertEqual(descriptor["namespace"], "test")
            code, result = self.http(descriptor["url"], "POST", "/api/monitor/shutdown", {},
                                     token=descriptor["control_token"])
            self.assertEqual(code, 200, result)
            self.assertEqual(result["state"], "shutdown_requested")
            self.assertFalse(client.child.stdin.closed)
            self.assertEqual(client.child.wait(timeout=20), 0, "Owner-exit watchdog must not wait for stdin EOF")
            self.assertFalse(client.child.stdin.closed)
            stdin_open_exit_verified = True
        finally:
            client.close()
            self.evidence = {"scope": "real Windows owned stdio and GUI shutdown with stdin held open; synthetic only",
                "case": "owner_shutdown_stdin_open", "instance_id": initial.get("instance_id") if initial else None,
                "stdin_open_exit_verified": stdin_open_exit_verified, "stdio_process": client.receipt,
                "protocol": client.transcript, "model_calls": 0, "native_provider_queries": 0}
        self.assert_natural(client)
        self.assertTrue(stdin_open_exit_verified)
        exit_receipt = read_json(self.root / "data/application/stdio-exit.json")
        self.assertEqual(exit_receipt["state"], "closed")
        self.assertTrue(exit_receipt["application_thread_exited"])
        self.assertFalse((self.root / "data/background/control.json").exists())
        self.assertEqual(EventCatalog(self.root, "test").detail(self.event["event_id"])["delivery_status"], "pending")
        self.evidence["owned_application_exit"] = exit_receipt


if __name__ == "__main__":
    unittest.main()
