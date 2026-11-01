"""Configure only a synthetic installation's receive gate through real CLI."""
from pathlib import Path
import tempfile
import unittest

import test_command_status_retry as status_fixture
from eventguard.agent_access import guard
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class CommandAgentAccessTests(unittest.TestCase):
    cli = status_fixture.CommandStatusRetryTests.cli

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def access(self, action):
        return self.cli("agent", "access", action)

    def test_status_is_inert_and_enable_disable_only_change_receive_setting(self):
        code, result = self.access("status")
        self.assertEqual((code, result["status"], result["enabled"]), (0, "disabled", False))
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(guard(self.root)["status"], "blocked")
        for action, enabled in (("enable", True), ("enable", True), ("disable", False)):
            code, result = self.access(action)
            self.assertEqual((code, result["enabled"], result["setting_saved"]), (0, enabled, True))
            self.assertFalse(result["receiver_verified"])
            self.assertEqual(result["receiver_state"], "not_verified")
            self.assertFalse(result["model_start_requested"])
            self.assertFalse(result["process_control_performed"])
            self.assertEqual(result["model_calls"], 0)
            self.assertEqual(guard(self.root) is None, enabled)
        self.assertEqual([p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()],
                         ["data/agent-delivery.json"])

    def test_corrupt_setting_is_blocked_and_explicit_disable_can_save_a_valid_setting(self):
        path = self.root / "data/agent-delivery.json"
        path.parent.mkdir()
        path.write_text('{"enabled":"untrusted"}', encoding="utf-8")
        before = path.read_bytes()
        code, result = self.access("status")
        self.assertEqual((code, result["status"], result["delivery_allowed"]), (2, "blocked", False))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.access("disable")[0], 0)
        self.assertEqual(self.access("status")[1]["status"], "disabled")

    def test_storage_failure_is_not_reported_as_a_saved_permission_or_an_ack(self):
        store = EventStore(self.root / "data/test")
        store.enqueue(make_synthetic("listener"))
        before = store.path.read_bytes()
        (self.root / "data/agent-delivery.json").mkdir()
        code, result = self.access("disable")
        self.assertEqual((code, result["status"], result["setting_saved"]), (4, "blocked", False))
        self.assertEqual(result["reason"], "agent_setting_write_failed")
        self.assertEqual(store.path.read_bytes(), before)
        self.assertEqual((store.stats()["pending"], store.stats()["receipt_count"]), (1, 0))
