"""CLI and independent App lifecycle. Synthetic fixtures; no model or native scan."""
from contextlib import redirect_stdout
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

from eventguard import processes
from eventguard.application import Application
from eventguard.application_host import RemoteApplication
from eventguard.cli import main
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "tests/fixtures/normal.json"


class ApplicationCLIFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def command(self, *arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--format", "json", "app", *arguments], root=self.root)
        return code, json.loads(output.getvalue())


class ApplicationCLITests(ApplicationCLIFixture):
    def test_all_commands_without_app_are_blocked_and_create_no_runtime(self):
        with patch("eventguard.application.Application", side_effect=AssertionError("observer cannot create an app")) as create, \
             patch("eventguard.processes.spawn", side_effect=AssertionError("observer cannot spawn")) as spawn:
            for action in ("status", "start", "pause", "resume", "stop", "shutdown"):
                for namespace in ("test", "live"):
                    with self.subTest(action=action, namespace=namespace):
                        code, value = self.command(action, "--namespace", namespace)
                        self.assertEqual(code, 2, value)
                        self.assertEqual(value["state"], "blocked")
                        self.assertEqual(value["reason"], "application_not_running")
                        self.assertEqual(value["namespace"], namespace)
                        self.assertEqual(value["instance_id"], "unbound")
                        self.assertEqual(value["model_calls"], 0)
                        self.assertFalse((self.root / "data").exists())
            create.assert_not_called()
            spawn.assert_not_called()

    def test_cli_control_uses_same_proxy_with_truthful_actor_and_operation(self):
        for action in ("start", "pause", "resume", "stop", "shutdown"):
            with self.subTest(action=action):
                proxy = Mock()
                proxy.monitor_control.return_value = {"state": "shutdown_requested" if action == "shutdown" else "stopped",
                    "instance_id": "a" * 32, "namespace": "test", "model_calls": 0}
                with patch("eventguard.application_host.RemoteApplication", return_value=proxy) as connect:
                    code, _ = self.command(action, "--namespace", "test", "--operation-id", "human-operation")
                self.assertEqual(code, 0)
                connect.assert_called_once_with(self.root, "test")
                proxy.monitor_control.assert_called_once_with(action, source="cli", operation_id="human-operation")
                proxy.status.assert_not_called()

    def test_cli_auto_operation_id_and_status_do_not_share_mutation_path(self):
        proxy = Mock()
        proxy.monitor_control.return_value = {"state": "running", "model_calls": 0}
        proxy.status.return_value = {"state": "ready", "model_calls": 0}
        with patch("eventguard.application_host.RemoteApplication", return_value=proxy):
            self.assertEqual(self.command("start")[0], 0)
            operation = proxy.monitor_control.call_args.kwargs["operation_id"]
            self.assertRegex(operation, r"^[a-f0-9]{32}$")
            self.assertEqual(self.command("status")[0], 0)
        proxy.monitor_control.assert_called_once()
        proxy.status.assert_called_once_with()
        self.assertFalse((self.root / "data").exists())

    def test_cli_does_not_report_failed_or_uncertain_control_as_exit_zero(self):
        for state, expected in (("blocked", 2), ("conflict", 2), ("busy", 3),
                                ("unknown", 5), ("shutdown_unconfirmed", 5)):
            with self.subTest(state=state):
                proxy = Mock()
                proxy.monitor_control.return_value = {"state": state, "reason": "synthetic_control_result", "model_calls": 0}
                with patch("eventguard.application_host.RemoteApplication", return_value=proxy):
                    code, value = self.command("stop", "--operation-id", "operation-one")
                self.assertEqual(code, expected, value)

    def test_invalid_operation_is_rejected_without_app_or_runtime(self):
        code, value = self.command("start", "--namespace", "test", "--operation-id", "untrusted\ncommand")
        self.assertEqual(code, 2)
        self.assertEqual(value["status"], "invalid_request")
        self.assertFalse((self.root / "data").exists())


@unittest.skipUnless(os.name == "nt", "real Windows application-owned Jobs; synthetic fixtures only")
class WindowsApplicationCLILifecycleTests(ApplicationCLIFixture):
    """One real fixture App, controlled by the same typed loopback RPC as MCP."""

    def web_status(self, application):
        target = urlsplit(application.web.url)
        self.assertEqual(target.hostname, "127.0.0.1")
        connection = http.client.HTTPConnection("127.0.0.1", target.port, timeout=10)
        try:
            connection.request("GET", "/api/status")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            return json.loads(response.read())
        finally:
            connection.close()

    def test_cli_start_pause_resume_stop_and_shutdown_share_one_app_and_keep_pending(self):
        for relative in ("config/default.json", "config/rules.json", "playbooks/default.json", FIXTURE):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        event = make_synthetic("listener")
        store = EventStore(self.root / "data/test")
        store.enqueue(event)
        app = Application(self.root, port=0, fixture=FIXTURE, max_cycles=100000,
                          notifications=False, auto_start=False, mcp_enabled=False)
        ready = threading.Event()
        outcomes, failures, children, receipts, actions = [], [], [], [], []
        original_spawn = processes.spawn_application_host
        def spawn(argv, **kwargs):
            child = original_spawn(argv, **kwargs)
            children.append(child)
            return child
        def run():
            try:
                outcomes.append(app.run(max_seconds=75, announce=lambda _value: ready.set()))
            except BaseException as error:
                failures.append(type(error).__name__)
                ready.set()
        worker = threading.Thread(target=run, name="fixture-cli-independent-app", daemon=True)
        try:
            with patch.object(processes, "spawn_application_host", side_effect=spawn), \
                 patch("eventguard.agent_service.start", side_effect=AssertionError("No model allowed")), \
                 patch("eventguard.agent_dispatch.spawn", side_effect=AssertionError("No model allowed")):
                worker.start()
                self.assertTrue(ready.wait(20))
                self.assertEqual(failures, [])
                code, status = self.command("status", "--namespace", "test")
                self.assertEqual(code, 0, status)
                self.assertEqual(status["instance_id"], app.instance_id)
                self.assertEqual(status["namespace"], "test")
                self.assertEqual(status["monitor_state"], "stopped")
                self.assertFalse((self.root / "data/background/control.json").exists())
                for index, (action, state) in enumerate((("start", "running"), ("pause", "paused"),
                        ("resume", "running"), ("stop", "stopped"), ("start", "running"))):
                    code, value = self.command(action, "--namespace", "test", "--operation-id", "cli-control-" + str(index))
                    actions.append(value)
                    self.assertEqual(code, 0, value)
                    self.assertEqual(value["state"], state, value)
                    self.assertEqual(value["instance_id"], app.instance_id)
                    self.assertEqual(value["last_action"]["source"], "cli")
                    self.assertEqual(value["model_calls"], 0)
                    web = self.web_status(app)
                    self.assertEqual(web["instance_id"], app.instance_id)
                    self.assertEqual(web["namespace"], "test")
                    self.assertEqual(web["last_action"]["operation_id"], "cli-control-" + str(index))
                    self.assertEqual(web["last_action"]["source"], "cli")
                    self.assertTrue(worker.is_alive(), "stop only ends collection; App and Web remain")
                    self.assertFalse(app.cancel.is_set())
                proxy = RemoteApplication(self.root, "test")
                self.assertEqual(proxy.event_detail(event["event_id"])["delivery_status"], "pending")
                code, shutdown = self.command("shutdown", "--namespace", "test", "--operation-id", "cli-shutdown")
                actions.append(shutdown)
                self.assertEqual(code, 0, shutdown)
                self.assertEqual(shutdown["state"], "shutdown_requested")
                self.assertEqual(shutdown["last_action"]["source"], "cli")
                worker.join(timeout=25)
                self.assertFalse(worker.is_alive())
        finally:
            app.cancel.set()
            if worker.ident is not None:
                worker.join(timeout=25)
            else:
                app.web.close()
            for child in children:
                receipts.append(processes.finish(child, "test_teardown", grace=1, request_stop=False))
            self.evidence = {"scope": "real Windows App-owned Jobs and typed CLI/Web RPC; synthetic fixture only",
                "instance_id": app.instance_id, "namespace": "test", "event_id": event["event_id"],
                "actions": actions, "application": outcomes, "processes": receipts,
                "failures": failures, "application_thread_exited": not worker.is_alive(),
                "model_calls": 0, "native_provider_queries": 0}
        self.assertFalse(worker.is_alive(), self.evidence)
        self.assertEqual(failures, [], self.evidence)
        self.assertEqual(len(outcomes), 1, self.evidence)
        self.assertEqual(outcomes[0]["state"], "stopped", self.evidence)
        self.assertEqual(len(children), 3, self.evidence)
        for receipt in receipts:
            self.assertEqual(receipt["exit_code"], 0, self.evidence)
            self.assertTrue(receipt["child_exited"], self.evidence)
            self.assertEqual(receipt["remaining_owned_processes"], 0, self.evidence)
            self.assertFalse(receipt["forcibly_terminated"], self.evidence)
        self.assertEqual(store.get_event(event["event_id"])["delivery_status"], "pending")
        self.assertEqual(store.stats()["receipt_count"], 0)
        self.evidence.update(pending_retained=True, ack_count=0)


if __name__ == "__main__":
    unittest.main()
