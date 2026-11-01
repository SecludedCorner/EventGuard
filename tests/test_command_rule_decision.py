"""Read saved classification through real CLI; no OS query, model or ACK."""
from contextlib import closing, redirect_stdout
import copy
import io
import json
import shutil
from pathlib import Path
import sqlite3
import tempfile
import unittest

import test_command_status_retry as status_fixture
from eventguard.cli import main
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.rules.decisions import classify
from eventguard.rules.detector import evaluate
from test_configured_rules import listener, source, single_rule, condition


class CommandRuleDecisionTests(unittest.TestCase):
    cli = status_fixture.CommandStatusRetryTests.cli

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root / "data/test")
        _, self.events = evaluate([listener()], now=1000)
        self.events[0]["synthetic"] = True
        rules = [single_rule([condition("event_type", "eq", "listener.changed")], "critical", "saved-winner")]
        self.event = classify(self.events, rules)[0]
        self.store.enqueue(self.event)

    def read(self, action, identity=None):
        return self.cli("events", action, "--namespace", "test", "--event-id", identity or self.event["event_id"])

    def test_detail_and_inspect_keep_original_snapshot_without_reading_current_rules(self):
        (self.root / "config").mkdir()
        (self.root / "config/rules.json").write_bytes(b"{inert invalid changed configuration")
        before = self.store.path.read_bytes()
        for action in ("detail", "inspect"):
            code, value = self.read(action)
            self.assertEqual(code, 0)
            self.assertEqual(value["event"]["classification"], self.event["classification"])
            self.assertEqual(value["event"]["severity"], "critical")
            self.assertEqual(value["model_calls"], 0)
            self.assertEqual(value["data_trust"], "untrusted_data")
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--format", "text", "events", "detail", "--namespace", "test", "--event-id", self.event["event_id"]], root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("保存的分類規則：saved-winner", output.getvalue())

    def test_legacy_is_distinct_from_a_recorded_unmatched_decision(self):
        legacy = copy.deepcopy(self.events[0])
        legacy["event_id"] += "-legacy"
        self.store.enqueue(legacy)
        self.assertNotIn("classification", self.read("detail", legacy["event_id"])[1]["event"])
        unmatched = classify(self.events, [single_rule([condition("evidence.port", "eq", 9999)])])[0]
        unmatched["event_id"] += "-unmatched"
        self.store.enqueue(unmatched)
        value = self.read("inspect", unmatched["event_id"])[1]
        self.assertFalse(value["event"]["classification"]["matched"])
        self.assertIsNone(value["event"]["classification"]["rule"])

    def test_tampered_snapshot_is_not_exposed_even_with_recomputed_payload_hash(self):
        event = copy.deepcopy(self.event)
        event["classification"]["rule_hash"] = "0" * 64
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE events SET payload=?,payload_hash=? WHERE event_id=?",
                       (json.dumps(event), event_payload_hash(event), event["event_id"]))
            db.commit()
        code, value = self.read("detail")
        self.assertEqual((code, value["status"]), (4, "error"))
        self.assertNotIn("event", value)

    def test_monitor_then_list_then_detail_reads_persisted_decision_through_cli(self):
        (self.root / "config").mkdir()
        shutil.copy2(status_fixture.ROOT / "config/default.json", self.root / "config/default.json")
        rules = [single_rule([condition("event_type", "eq", "listener.changed")], "high", "from-monitor")]
        (self.root / "config/rules.json").write_text(json.dumps({"schema_version": "1.0", "rules": rules}), encoding="utf-8")
        fixture = self.root / "tests/fixtures/rule-trace.json"
        fixture.parent.mkdir(parents=True)
        sections = [listener(18181), *[source(name) for name in ("defender", "processes", "startup", "services", "tasks", "versions")]]
        fixture.write_text(json.dumps({"frames": [{"sections": sections}]}), encoding="utf-8")
        code, monitored = self.cli("monitor", "--fixture", "tests/fixtures/rule-trace.json", "--max-cycles", "1")
        self.assertEqual((code, monitored["state"], monitored["model_calls"]), (0, "stopped", 0))
        code, listing = self.cli("events", "list", "--namespace", "test", "--limit", "100")
        self.assertEqual(code, 0)
        identity = next(event["event_id"] for event in listing["events"] if event["severity"] == "high")
        code, detail = self.read("detail", identity)
        self.assertEqual(code, 0)
        self.assertEqual(detail["event"]["facts"]["port"], 18181)
        self.assertEqual(detail["event"]["classification"]["rule"]["id"], "from-monitor")
        self.assertEqual(self.store.stats()["receipt_count"], 0)
