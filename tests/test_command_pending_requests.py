"""Actual CLI discovery of synthetic unconfirmed requests, without mutation."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

from eventguard.events.store import EventStore, event_payload_hash
from eventguard.events.schema import validate_event
from eventguard.processes import spawn, finish
from eventguard.synthetic import make_synthetic

ROOT = Path(__file__).resolve().parents[1]


class CommandPendingRequestsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root / "data/test")
        self.events = [dict(make_synthetic("listener"), event_id=f"evt-pending-cli-{i:03}") for i in range(3)]
        self.store.commit_evaluation({"synthetic_fixture": True}, self.events)
        self.evidence = {"cli_exits": [], "model_calls": 0}

    def prepare(self, index):
        event = self.events[index]
        self.store._prepare_desktop_request({"namespace": "test", "event_id": event["event_id"],
            "status": "handled", "operation_id": f"pending-cli-{index}",
            "payload_hash": event_payload_hash(validate_event(event))}, namespace="test")

    def cli(self, *arguments, root=None, fmt="json", operation="pending-requests"):
        child = spawn([sys.executable, "-B", "-c",
            "import sys; from eventguard.cli import main; raise SystemExit(main(sys.argv[2:],root=sys.argv[1]))",
            str(root or self.root), "--format", fmt, "events", operation, "--namespace", "test", *arguments],
            env=dict(os.environ, PYTHONPATH=str(ROOT / "src")), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out, err = child.communicate(timeout=15)
        finally:
            receipt = finish(child, reason="test_teardown", grace=1)
            self.evidence["cli_exits"].append(receipt)
        self.assertTrue(receipt["child_exited"])
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.assertEqual(err, b"")
        return child.returncode, json.loads(out) if fmt == "json" else out.decode("utf-8")

    def test_pages_detail_pipeline_and_reads_preserve_journal_status_and_ack(self):
        self.prepare(2)
        self.prepare(0)
        before = self.store.path.read_bytes()
        code, first = self.cli("--limit", "1")
        code2, second = self.cli("--limit", "1", "--offset", "1")
        self.assertEqual((code, code2, first["state"], first["total"], first["request_total"]), (0, 0, "available", 2, 2))
        self.assertEqual([first["events"][0]["event_id"], second["events"][0]["event_id"]],
                         [self.events[i]["event_id"] for i in (0, 2)])
        self.assertTrue(first["has_more"])
        self.assertFalse(second["has_more"])
        code, detail = self.cli("--event-id", first["events"][0]["event_id"], operation="detail")
        self.assertEqual(code, 0)
        self.assertEqual(detail["pending_handling_requests"]["requests"][0]["operation_id"], "pending-cli-0")
        code, text = self.cli(fmt="text")
        self.assertEqual(code, 0)
        self.assertIn("待確認人工操作", text)
        self.assertIn(self.events[0]["event_id"], text)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (3, 0))

    def test_missing_is_unknown_but_verified_empty_is_available(self):
        missing = self.root / "missing"
        code, result = self.cli(root=missing)
        self.assertEqual((code, result["state"], result["total"], result["has_more"]), (5, "unknown", None, None))
        self.assertFalse(missing.exists())
        code, result = self.cli()
        self.assertEqual((code, result["state"], result["total"]), (0, "available", 0))

    def test_off_page_identity_failure_and_invalid_bounds_preserve_database(self):
        self.prepare(0)
        self.prepare(2)
        with self.store._connect() as db:
            db.execute("UPDATE desktop_status_requests SET payload_hash=? WHERE event_id=?", ("0"*64, self.events[2]["event_id"]))
        before = self.store.path.read_bytes()
        code, result = self.cli("--limit", "1")
        self.assertEqual((code, result["state"], result["events"], result["total"]), (5, "unknown", [], None))
        for arguments in (("--limit", "101"), ("--offset", "129"), ("--offset", "-1")):
            code, result = self.cli(*arguments)
            self.assertEqual((code, result["status"]), (2, "invalid_request"))
        self.assertEqual(self.store.path.read_bytes(), before)
