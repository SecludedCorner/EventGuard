"""Actual CLI opt-in configuration in disposable roots; no model execution."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

import test_command_status_retry as status_fixture
from eventguard.agent_automation import describe, PATH
from eventguard.cli import main
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class CommandAgentAutomationTests(unittest.TestCase):
    cli = status_fixture.CommandStatusRetryTests.cli

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def automation(self, *arguments):
        return self.cli("agent", "automation", *arguments)

    def test_settings_roundtrip_never_launches_or_claims_dispatcher_liveness(self):
        code, value = self.automation("status")
        self.assertEqual((code, value["state"], value["enabled"]), (0, "available", False))
        self.assertEqual(list(self.root.iterdir()), [])
        native = self.root / "fixture.exe"
        native.write_bytes(b"inert fixture, never execute")
        code, denied = self.automation("enable", "--codex-executable", str(native))
        self.assertEqual((code, denied["reason"]), (2, "agent_receive_permission_required"))
        self.assertFalse((self.root / PATH).exists())
        self.assertEqual(self.cli("agent", "access", "enable")[0], 0)
        for arguments, enabled in ((["enable", "--codex-executable", str(native)], True), (["enable"], True), (["disable"], False)):
            code, value = self.automation(*arguments)
            self.assertEqual((code, value["enabled"], value["setting_saved"]), (0, enabled, True))
            self.assertEqual(value["dispatcher_state"], "not_verified")
            self.assertIsNone(value["child_exited"])
            self.assertFalse(value["model_start_requested"])
            self.assertFalse(value["process_control_performed"])
            self.assertEqual(value["model_calls"], 0)
            self.assertEqual(describe(self.root)["enabled"], enabled)
        self.assertEqual({p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()},
                         {"fixture.exe", "data/agent-delivery.json", "data/agent-automation.json"})

    def test_invalid_native_paths_and_irrelevant_override_do_not_write(self):
        self.cli("agent", "access", "enable")
        wrapper = self.root / "fixture.cmd"
        wrapper.write_bytes(b"inert wrapper")
        for name in (str(wrapper), str(self.root / "missing.exe")):
            code, value = self.automation("enable", "--codex-executable", name)
            self.assertEqual((code, value["failure_kind"], value["setting_saved"]), (2, "validation", False))
        for action in ("status", "disable"):
            self.assertEqual(self.automation(action, "--codex-executable", str(wrapper))[0], 2)
        self.assertFalse((self.root / PATH).exists())

    def test_corrupt_setting_is_blocked_and_explicit_disable_repairs(self):
        path = self.root / PATH
        path.parent.mkdir()
        path.write_bytes(b'{"enabled":"untrusted"}')
        before = path.read_bytes()
        code, value = self.automation("status")
        self.assertEqual((code, value["state"], value["enabled"]), (2, "blocked", False))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.automation("disable")[0], 0)
        self.assertFalse(describe(self.root)["enabled"])

    def test_write_failure_is_exit_four_and_never_acknowledges_events(self):
        store = EventStore(self.root / "data/test")
        store.enqueue(make_synthetic("listener"))
        before = store.path.read_bytes()
        (self.root / PATH).mkdir()
        code, value = self.automation("disable")
        self.assertEqual((code, value["failure_kind"], value["setting_saved"]), (4, "io", False))
        self.assertIsNone(value["child_exited"])
        self.assertEqual(store.path.read_bytes(), before)
        self.assertEqual((store.stats()["pending"], store.stats()["receipt_count"]), (1, 0))

    def test_text_status_distinguishes_configuration_from_invalid_request(self):
        for extra, code, expected in (([], 0, "已停用選項"), (["--codex-executable", "unused.exe"], 2, "無法完成操作")):
            output = io.StringIO()
            with redirect_stdout(output):
                actual = main(["--format", "text", "agent", "automation", "status", *extra], root=self.root)
            self.assertEqual(actual, code)
            self.assertIn(expected, output.getvalue())
        self.assertEqual(list(self.root.iterdir()), [])
