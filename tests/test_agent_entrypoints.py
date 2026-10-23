"""Human entry points; synthetic SQLite/real loopback HTTP, never a model."""
from contextlib import redirect_stdout
import http.client
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from eventguard.cli import main
from eventguard.events.store import EventStore
from eventguard.queue_inbox import QueueInbox
from eventguard.synthetic import make_synthetic
from eventguard.web import LocalWeb

ROOT = Path(__file__).resolve().parents[1]


class AgentFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default.json", self.root / "config/default.json")

    def cli(self, args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--format", "json", "agent", *args], root=self.root)
        return code, json.loads(output.getvalue())


class AgentEntryTests(AgentFixture):
    def test_status_and_capabilities_do_not_initialize_or_launch(self):
        with patch("eventguard.agent_service.processes.spawn_persistent") as spawn:
            code, status = self.cli(["status"])
            self.assertEqual(code, 0)
            self.assertEqual(status["state"], "not_started")
            code, capabilities = self.cli(["capabilities"])
            self.assertEqual(code, 0)
            self.assertIsInstance(capabilities, dict)
            spawn.assert_not_called()
        self.assertFalse((self.root / "data").exists())

    def test_start_requires_explicit_execute_and_keeps_namespace(self):
        with patch("eventguard.agent_service.start", return_value={"state": "preflight_ready"}) as start:
            self.assertEqual(self.cli(["start", "--namespace", "test", "--codex-executable", "native.exe"])[0], 0)
            start.assert_called_once_with(self.root, codex_executable="native.exe", allow_live=False, execute=False)

    def test_resume_is_preflight_and_cli_controls_do_not_start(self):
        with patch("eventguard.agent_service.processes.spawn_persistent") as spawn:
            code, status = self.cli(["resume"])
            self.assertEqual(code, 0)
            self.assertTrue(status["execute_required"])
            self.assertEqual(self.cli(["pause"])[0], 0)
            self.assertEqual(self.cli(["stop"])[0], 0)
            spawn.assert_not_called()

    def test_missing_native_executable_is_a_blocked_exit(self):
        EventStore(self.root / "data/test")
        code, result = self.cli(["start", "--namespace", "test", "--codex-executable", "does-not-exist.exe"])
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "native_codex_executable_required")
        self.assertFalse((self.root / "data/agent-service/control.json").exists())

    def test_readonly_export_preserves_source_and_does_not_receive(self):
        event = make_synthetic("listener")
        source = self.root / "data/test"
        EventStore(source).enqueue(event)
        before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
        code, result = self.cli(["export", "--namespace", "test", "--event-id", event["event_id"],
                                "--producer-id", "urn:uuid:ec20e5d7-8410-4b70-9f6c-8a6727617397"])
        self.assertEqual(code, 0, result)
        envelope = result.get("envelope", result)
        self.assertEqual(envelope["data"]["event_id"], event["event_id"])
        self.assertEqual(len(envelope["data"]), 7)
        self.assertEqual(before, {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()})
        self.assertFalse((self.root / "data/agent-delivery-test").exists())

    def test_text_output_describes_unknown_cost_without_claiming_wake(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--format", "text", "agent", "status"], root=self.root), 0)
        self.assertIn("專用 agent 派送", output.getvalue())
        self.assertIn("未知", output.getvalue())

    def test_export_invalid_scope_returns_fixed_actionable_reason(self):
        code, result = self.cli(["export", "--namespace", "test", "--event-id", "evt-test",
                                 "--producer-id", "not-an-opaque-scope"])
        self.assertEqual(code, 2)
        self.assertEqual(result["error_code"], "ingress_invalid_producer_scope")


class AgentWebTests(AgentFixture):
    def setUp(self):
        super().setUp()
        self.web = LocalWeb(self.root, "test", port=0)
        self.web.start()
        self.addCleanup(self.close_web)

    def close_web(self):
        self.assertTrue(self.web.close()["web_thread_exited"])

    def request(self, method, route, body=None, *, csrf=False):
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers.update(Origin=self.web.url, **{"X-EventGuard-CSRF": self.web.token})
        connection = http.client.HTTPConnection("127.0.0.1", self.web.server.server_port, timeout=8)
        try:
            connection.request(method, route, body=body, headers=headers)
            reply = connection.getresponse()
            return reply.status, reply.read()
        finally:
            connection.close()

    def test_status_is_readonly_and_page_has_no_start_button(self):
        code, body = self.request("GET", "/api/agent")
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["state"], "not_started")
        self.assertFalse((self.root / "data").exists())
        code, body = self.request("GET", "/")
        self.assertIn('id="agent-pause"', body.decode())
        self.assertNotIn('id="agent-start"', body.decode())

    def test_controls_require_csrf_and_never_allow_start_or_resume(self):
        with patch("eventguard.agent_service.pause", return_value={"state": "pause_requested"}) as pause:
            self.assertEqual(self.request("POST", "/api/agent/pause", "{}")[0], 403)
            pause.assert_not_called()
            self.assertEqual(self.request("POST", "/api/agent/pause", "{}", csrf=True)[0], 200)
            pause.assert_called_once_with(self.root)
        with patch("eventguard.agent_service.start") as start, patch("eventguard.agent_service.resume") as resume:
            self.assertEqual(self.request("POST", "/api/agent/start", "{}", csrf=True)[0], 404)
            self.assertEqual(self.request("POST", "/api/agent/resume", "{}", csrf=True)[0], 404)
            start.assert_not_called()
            resume.assert_not_called()

    def test_saved_delivery_route_is_not_a_receiver(self):
        event = make_synthetic("coverage")
        source = self.root / "data/test"
        EventStore(source).enqueue(event)
        state = self.root / "data/agent-delivery-test"
        inbox = QueueInbox(source, state, event_id=event["event_id"])
        inbox.receive_event()
        before = {p.name: p.read_bytes() for p in state.iterdir() if p.is_file()}
        code, body = self.request("GET", "/api/events/"+event["event_id"]+"/delivery")
        self.assertEqual(code, 200, body)
        self.assertEqual(json.loads(body)["event_id"], event["event_id"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in state.iterdir() if p.is_file()})
        self.assertFalse(inbox.acknowledged(event["event_id"]))


@unittest.skipUnless(importlib.util.find_spec("mcp"), "optional installed MCP SDK unavailable")
class BoundRootTests(unittest.TestCase):
    def test_live_bound_server_cannot_switch_installation_root(self):
        spec = importlib.util.spec_from_file_location("entry_mcp", ROOT / "scripts/eventguard_inbox_mcp.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "live_project_root_not_authorized"):
                module.build_server(Path(temporary)/"source", Path(temporary)/"inbox", "evt-test",
                                    allow_live=True, root=temporary)
