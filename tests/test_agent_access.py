"""Fixture-only tests for the live agent gate; no receiver or model is run."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard import agent_access
from eventguard.runtime import atomic_json, read_json


class AgentAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.setting = self.root / agent_access.SETTING_PATH

    def test_default_is_disabled_and_read_does_not_create_data(self):
        value = agent_access.status(self.root)
        self.assertEqual(value["status"], "disabled")
        self.assertFalse(value["enabled"])
        self.assertFalse(value["delivery_allowed"])
        self.assertFalse((self.root / "data").exists())

    def test_enable_persists_across_reads_without_receiver_or_model_claim(self):
        value = agent_access.set_enabled(self.root, True)
        self.assertTrue(value.pop("setting_saved"))
        self.assertEqual(value, agent_access.status(self.root))
        self.assertEqual(value["status"], "enabled_waiting_receiver")
        self.assertTrue(value["enabled"])
        self.assertTrue(value["delivery_allowed"])
        self.assertEqual(value["receiver_state"], "not_verified")
        self.assertFalse(value["receiver_verified"])
        self.assertIsNone(value["receiver_connected"])
        self.assertEqual(value["model_calls"], 0)
        saved = read_json(self.setting)
        self.assertEqual(set(saved), {"kind", "enabled", "updated_at"})
        self.assertEqual(saved["kind"], agent_access.KIND)
        self.assertTrue(saved["enabled"])

    def test_disable_retains_existing_pending_and_query_bytes(self):
        pending = self.root / "data/live/eventguard.sqlite3"
        receipt = self.root / "data/agent-delivery/queries.json"
        pending.parent.mkdir(parents=True)
        receipt.parent.mkdir(parents=True)
        # Fixture sentinel bytes, not a database or a true receiver receipt.
        pending.write_bytes(b"synthetic-pending-event-sentinel")
        receipt.write_bytes(b"synthetic-query-sentinel")
        agent_access.set_enabled(self.root, True)
        value = agent_access.set_enabled(self.root, False)
        self.assertEqual(value["status"], "disabled")
        self.assertEqual(value["pending_disposition"], "retained")
        self.assertEqual(pending.read_bytes(), b"synthetic-pending-event-sentinel")
        self.assertEqual(receipt.read_bytes(), b"synthetic-query-sentinel")

    def test_gate_rechecks_after_enabled_receive_and_later_disable(self):
        self.assertEqual(agent_access.guard(self.root)["reason"], "agent_delivery_disabled")
        agent_access.set_enabled(self.root, True)
        self.assertIsNone(agent_access.guard(self.root))
        agent_access.set_enabled(self.root, False)
        self.assertEqual(agent_access.guard(self.root)["reason"], "agent_delivery_disabled")

    def test_synthetic_test_scope_bypasses_live_control_without_writing(self):
        self.assertIsNone(agent_access.guard(self.root, "test"))
        self.assertFalse((self.root / "data").exists())
        self.assertEqual(agent_access.guard(self.root, "other")["reason"], "agent_namespace_invalid")

    def test_invalid_boolean_inputs_are_not_coerced(self):
        for value in (1, 0, "true", None, [], {}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "agent_setting_requires_boolean"):
                    agent_access.set_enabled(self.root, value)
        self.assertFalse(self.setting.exists())

    def test_malformed_or_enlarged_settings_fail_closed_without_echoing_data(self):
        self.setting.parent.mkdir(parents=True)
        secret = "PRIVATE-SYNTHETIC-CONTENT"
        for raw in (secret, "[]", json.dumps({"kind": agent_access.KIND, "enabled": True}),
                    json.dumps({"kind": agent_access.KIND, "enabled": True, "updated_at": secret}),
                    json.dumps({"kind": agent_access.KIND, "enabled": "true", "updated_at": "2026-10-23T00:00:00+00:00"}),
                    json.dumps({"kind": agent_access.KIND, "enabled": True, "updated_at": "2026-10-23T00:00:00+00:00", "extra": secret}),
                    "x" * (agent_access.MAX_SETTING_BYTES + 1)):
            with self.subTest(raw=raw[:100]):
                self.setting.write_text(raw, encoding="utf-8")
                value = agent_access.status(self.root)
                refusal = agent_access.guard(self.root)
                self.assertEqual(value["status"], "blocked")
                self.assertFalse(value["delivery_allowed"])
                self.assertEqual(refusal["status"], "blocked")
                self.assertFalse(refusal["data_disclosed"])
                self.assertNotIn(secret, json.dumps(value) + json.dumps(refusal))
                self.assertEqual(set(refusal), {"status", "reason", "agent_delivery_enabled", "data_disclosed", "model_calls"})

    def test_naive_timestamp_fails_closed(self):
        atomic_json(self.setting, {"kind": agent_access.KIND, "enabled": True, "updated_at": "2026-10-23T12:34:56"})
        self.assertFalse(agent_access.status(self.root)["enabled"])

    def test_unreadable_setting_is_unavailable_and_does_not_echo_exception(self):
        agent_access.set_enabled(self.root, True)
        with patch("eventguard.agent_access.read_json", side_effect=PermissionError("SYNTHETIC PRIVATE PATH")):
            value = agent_access.status(self.root)
            refusal = agent_access.guard(self.root)
        self.assertEqual(value["reason"], "agent_setting_unavailable")
        self.assertEqual(refusal["reason"], "agent_setting_unavailable")
        self.assertNotIn("PRIVATE", json.dumps(value) + json.dumps(refusal))

    def test_failed_atomic_write_reports_failure_and_preserves_prior_setting(self):
        agent_access.set_enabled(self.root, False)
        previous = self.setting.read_bytes()
        with patch("eventguard.agent_access.atomic_json", side_effect=OSError("synthetic storage full")):
            value = agent_access.set_enabled(self.root, True)
        self.assertEqual(value["status"], "blocked")
        self.assertEqual(value["reason"], "agent_setting_write_failed")
        self.assertFalse(value["setting_saved"])
        self.assertEqual(self.setting.read_bytes(), previous)
        self.assertFalse(agent_access.status(self.root)["enabled"])

    def test_failed_disable_reports_still_enabled_instead_of_claiming_success(self):
        agent_access.set_enabled(self.root, True)
        with patch("eventguard.agent_access.atomic_json", side_effect=OSError("synthetic storage full")):
            value = agent_access.set_enabled(self.root, False)
        self.assertEqual(value["status"], "blocked")
        self.assertFalse(value["setting_saved"])
        self.assertTrue(value["enabled"])
        self.assertTrue(value["delivery_allowed"])
        self.assertIsNone(agent_access.guard(self.root))

    def test_explicit_disable_can_repair_corrupt_setting_without_enabling_access(self):
        self.setting.parent.mkdir(parents=True)
        self.setting.write_text("malformed", encoding="utf-8")
        self.assertEqual(agent_access.set_enabled(self.root, False)["status"], "disabled")
        self.assertFalse(read_json(self.setting)["enabled"])

    def test_redirected_setting_path_is_rejected_before_read_or_write(self):
        with patch("eventguard.agent_access.Runtime.path", side_effect=ValueError("redirected_runtime_path")), \
             patch("eventguard.agent_access.read_json") as read, \
             patch("eventguard.agent_access.atomic_json") as write:
            self.assertEqual(agent_access.status(self.root)["status"], "blocked")
            self.assertEqual(agent_access.set_enabled(self.root, True)["status"], "blocked")
            self.assertEqual(agent_access.guard(self.root)["status"], "blocked")
        read.assert_not_called()
        write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
