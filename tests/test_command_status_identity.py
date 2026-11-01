"""CLI writes bound to a previously read synthetic payload, never an OS query."""
from pathlib import Path
import json
import tempfile
import unittest

import test_command_status_retry as status_fixture
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.synthetic import make_synthetic


class CommandStatusIdentityTests(unittest.TestCase):
    cli = status_fixture.CommandStatusRetryTests.cli

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root / "data/test")
        self.event = dict(make_synthetic("listener"), event_id="evt-command-bound-status")
        self.store.enqueue(self.event)

    def update(self, digest, operation="bound-status"):
        return self.cli("events", "set-status", "--namespace", "test", "--event-id", self.event["event_id"],
                        "--status", "read", "--operation-id", operation, "--expected-payload-hash", digest)

    def test_detail_hash_to_bound_write_and_retry_work_across_processes(self):
        code, detail = self.cli("events", "detail", "--namespace", "test", "--event-id", self.event["event_id"])
        self.assertEqual(code, 0)
        digest = detail["payload_hash"]
        code, result = self.update(digest)
        self.assertEqual((code, result["status"], result["changed"]), (0, "read", True))
        before = self.store.path.read_bytes()
        code, result = self.update(digest)
        self.assertEqual((code, result["history_replayed"]), (0, True))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))

    def test_mismatch_and_invalid_hash_have_fixed_codes_without_writes(self):
        before = self.store.path.read_bytes()
        for digest, status, error in (("0"*64, "conflict", "event_payload_conflict"),
                                       ("invalid", "invalid_request", "input_or_config_validation_failed")):
            code, result = self.update(digest)
            self.assertEqual((code, result["status"], result["error_code"]), (2, status, error))
            self.assertTrue(result["raw_error_omitted"])
            self.assertEqual(self.store.path.read_bytes(), before)

    def test_changed_valid_event_payload_cannot_receive_a_stale_decision(self):
        _, detail = self.cli("events", "detail", "--namespace", "test", "--event-id", self.event["event_id"])
        with self.store._connect() as db:
            payload = json.loads(db.execute("SELECT payload FROM events").fetchone()[0])
            payload["evidence"]["port"] = 18082
            db.execute("UPDATE events SET payload=?,payload_hash=?", (json.dumps(payload), event_payload_hash(payload)))
        before = self.store.path.read_bytes()
        code, result = self.update(detail["payload_hash"])
        self.assertEqual((code, result["error_code"]), (2, "event_payload_conflict"))
        self.assertEqual(self.store.path.read_bytes(), before)
