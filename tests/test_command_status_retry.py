"""Real CLI retries against isolated synthetic SQLite; no collection/model."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from eventguard.events.store import EventStore
from eventguard.processes import spawn, finish
from eventguard.synthetic import make_synthetic

ROOT = Path(__file__).resolve().parents[1]


class CommandStatusRetryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root / "data/test")
        event = make_synthetic("listener")
        self.event_id = event["event_id"]
        self.store.enqueue(event)

    def cli(self, *arguments):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        child = spawn([sys.executable, "-B", "-c",
            "import sys; from eventguard.cli import main; raise SystemExit(main(sys.argv[2:],root=sys.argv[1]))",
            str(self.root), "--format", "json", *arguments],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = child.communicate(timeout=15)
        finally:
            receipt = finish(child, reason="test_teardown", grace=1)
        self.assertTrue(receipt["child_exited"], receipt)
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.assertFalse(receipt["forcibly_terminated"], receipt)
        self.assertEqual(stderr, b"")
        return child.returncode, json.loads(stdout)

    def status(self, status="handled", operation="op-command-retry"):
        return self.cli("events", "set-status", "--namespace", "test",
                        "--event-id", self.event_id, "--status", status, "--operation-id", operation)

    def test_lost_reply_retry_does_not_duplicate_or_undo_later_status(self):
        # The caller can lose the first result and retry in a fresh process.
        self.assertEqual(self.status()[0], 0)
        code, replay = self.status()
        self.assertEqual(code, 0)
        self.assertTrue(replay["history_replayed"])
        self.assertFalse(replay["changed"])
        self.assertFalse(replay["ack_performed"])
        self.assertEqual(self.status("ignored", "op-later")[0], 0)
        code, replay = self.status()
        self.assertEqual((code, replay["status"], replay["changed"]), (0, "ignored", False))
        code, detail = self.cli("events", "detail", "--namespace", "test", "--event-id", self.event_id)
        self.assertEqual(code, 0)
        self.assertEqual(len(detail["handling_history"]["entries"]), 2)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))
        self.assertFalse((self.root / "data/live").exists())

    def test_conflicting_or_invalid_operation_fails_without_writes(self):
        self.assertEqual(self.status()[0], 0)
        before = self.store.path.read_bytes()
        for status, operation in (("ignored", "op-command-retry"), ("handled", "bad key"), ("handled", "x" * 129)):
            code, result = self.status(status, operation)
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "invalid_request")
            self.assertEqual(result["error_code"], "operation_id_conflict" if operation == "op-command-retry" else "input_or_config_validation_failed")
            self.assertEqual(self.store.path.read_bytes(), before)
        with closing(sqlite3.connect(self.store.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM event_disposition_operations").fetchone()[0], 1)

    def test_operation_cannot_be_reused_for_another_event(self):
        self.assertEqual(self.status()[0], 0)
        event = make_synthetic("startup")
        self.store.enqueue(event)
        self.event_id = event["event_id"]
        before = self.store.path.read_bytes()
        code, result = self.status()
        self.assertEqual(code, 2)
        self.assertEqual(result["error_code"], "operation_id_conflict")
        self.assertEqual(self.store.path.read_bytes(), before)
        code, result = self.cli("events", "set-status", "--namespace", "test",
                               "--event-id", self.event_id, "--status", "read")
        self.assertEqual(code, 0)  # Omitted option retains the previous contract.
        self.assertFalse(result["history_replayed"])
