"""Synthetic receipt/exit fixtures only; no CLI, model or native collection.

These tests distinguish durable receipt from proof of successful agent delivery.
Saved process identities are fixture data; no corresponding process is started.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

from eventguard.acceptance_control import read_json, write_json
from eventguard.agent_dispatch import KIND, _complete, maintain_ledger
from eventguard.capture_receipt import validate_receipt
from eventguard.events.store import EventStore
from eventguard.queue_inbox import QueueInbox
from eventguard.synthetic import make_synthetic


class DispatchTakeoverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger_path = self.root / "dispatcher-attempts.json"
        self.policy = {"max_events": 1, "max_completed": 2, "max_bytes": 65536}
        self.event_id = "synthetic-takeover-event"

    def record(self, number=1, *, event_id=None, tree_verified=True):
        row = {
            "event_id": event_id or self.event_id,
            "attempt_id": f"{number:032x}",
            "run_id": f"{number + 16:032x}",
            "run_dir": str(self.root / f"run-{number}"),
            "state": "complete", "child_exited": True,
            "passed": False, "ack_verified": False,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        if tree_verified:
            row["tree_exit_verified"] = True
        return row

    def save_ledger(self, records):
        write_json(self.ledger_path, {
            "kind": KIND, "events": {records[0]["event_id"]: records},
        })

    def capture_fixture(self, record):
        run_dir = Path(record["run_dir"])
        attempt_dir = run_dir / "attempts" / record["attempt_id"]
        attempt_dir.mkdir(parents=True)
        write_json(run_dir / "dispatch.json", {"kind": KIND, "run_id": record["run_id"]})
        write_json(run_dir / "status.json", {"kind": KIND, "run_id": record["run_id"]})
        created = "2026-10-23T01:02:03.000000+00:00"
        started = {"attempt_id": record["attempt_id"], "codex_pid": 32000, "created_at": created}
        receipt = {
            "attempt_id": record["attempt_id"], "codex_pid": 32000,
            "child_exited": True, "codex_exit_code": 0,
            "capture_complete": True, "stdout_truncated": False,
            "stderr_truncated": False, "forcibly_terminated": False,
            "stop_reason": "descendants_remaining",
            "process": {
                "managed": True, "pid": 32000, "created_at": created,
                "child_exited": True, "remaining_owned_processes": 0,
                "exit_code": 0, "forcibly_terminated": False,
                "reason": "natural_exit",
                "shutdown_requested_reason": "descendants_remaining",
            },
        }
        write_json(attempt_dir / "capture-start.json", started)
        write_json(attempt_dir / "capture-exit.json", receipt)
        (attempt_dir / "codex.jsonl").write_bytes(b"")
        self.assertEqual(validate_receipt(receipt, started, record["attempt_id"]), [])
        return attempt_dir, receipt

    def test_capture_exit_does_not_override_unconfirmed_supervisor_tree(self):
        record = self.record()
        record.update(state="started", child_exited=False, tree_exit_verified=False)
        attempt_dir, receipt = self.capture_fixture(record)
        write_json(attempt_dir / "supervisor-exit.json", {
            "managed": True, "child_exited": False,
            "remaining_owned_processes": 1, "exit_code": 0,
        })
        inbox = SimpleNamespace(evidence=lambda _: None, acknowledged=lambda _: True)

        summary = _complete(record, inbox, receipt)

        self.assertIn("supervisor_tree_exit_unconfirmed", summary["evidence_errors"])
        self.assertFalse(summary["passed"])
        self.assertFalse(summary["child_exited"])
        self.assertEqual(record["state"], "started")
        self.assertFalse(record["child_exited"])
        self.assertFalse(record["tree_exit_verified"])
        self.save_ledger([record])
        active, archive, status = maintain_ledger(self.ledger_path, inbox, self.policy)
        self.assertEqual(set(active["events"]), {self.event_id})
        self.assertEqual(archive["events"], {})
        self.assertEqual(status["rotated_events"], 0)
        self.assertTrue((attempt_dir / "capture-exit.json").is_file())

    def test_failed_ack_without_tree_proof_stays_active(self):
        record = self.record(tree_verified=False)
        self.save_ledger([record])
        before = self.ledger_path.read_bytes()
        acknowledgments_checked = []

        def acknowledged(identity):
            acknowledgments_checked.append(identity)
            return True

        active, archive, status = maintain_ledger(
            self.ledger_path, SimpleNamespace(acknowledged=acknowledged), self.policy)

        self.assertEqual(active["events"][self.event_id], [record])
        self.assertEqual(archive["events"], {})
        self.assertEqual(status["rotated_events"], 0)
        self.assertEqual(self.ledger_path.read_bytes(), before)
        self.assertEqual(acknowledgments_checked, [], "Receipt cannot replace missing tree-exit proof")

    def test_received_failed_attempts_archive_as_not_agent_success_with_all_refs(self):
        records = [self.record(number) for number in (1, 2, 3)]
        expected_refs = [
            {key: row[key] for key in ("attempt_id", "run_id", "run_dir")}
            for row in records
        ]
        capture_paths = []
        for record in records:
            path = Path(record["run_dir"]) / "attempts" / record["attempt_id"] / "fixture-evidence.json"
            path.parent.mkdir(parents=True)
            write_json(path, {"scope": "synthetic_fixture_no_model", "attempt_id": record["attempt_id"]})
            capture_paths.append(path)
        self.save_ledger(deepcopy(records))
        inbox = SimpleNamespace(acknowledged=lambda identity: identity == self.event_id)

        active, archive, status = maintain_ledger(self.ledger_path, inbox, self.policy)

        self.assertEqual(active["events"], {})
        row = archive["events"][self.event_id]
        self.assertIs(row["passed"], False)
        self.assertIs(row["ack_verified"], True)
        self.assertIs(row["child_exited"], True)
        self.assertEqual(row["completion"], "received_without_agent_proof")
        self.assertEqual(row["attempts"], 3)
        self.assertEqual(row["attempt_refs"], expected_refs)
        self.assertEqual(status["rotated_events"], 1)
        self.assertTrue(all(path.is_file() for path in capture_paths))
        # Reading the compact proof again neither upgrades the failed trace nor
        # invents another attempt/receipt during idempotent maintenance.
        _, replayed, replay_status = maintain_ledger(self.ledger_path, inbox, self.policy)
        self.assertEqual(replayed, archive)
        self.assertEqual(replay_status["rotated_events"], 0)
        self.assertEqual(read_json(self.ledger_path)["events"], {})

    def test_rotated_receiver_proof_does_not_guess_receipt_or_remove_active_history(self):
        source = self.root / "synthetic-source"
        state = self.root / "synthetic-inbox"
        store = EventStore(source)
        event = make_synthetic("coverage")
        identity = event["event_id"]
        store.enqueue(event)
        inbox = QueueInbox(source, state, event_id=identity,
                           limits={"completed_retention_seconds": 1})
        inbox.receive_event()
        queried = inbox.query_evidence(identity)
        result = inbox.ack_event(identity, queried["query_id"], "needs_more_evidence")
        self.assertTrue(inbox.acknowledged(identity))
        retention = inbox.maintain(now=time.time() + 2)
        self.assertEqual(retention["completed_removed"], 1)
        self.assertIsNone(inbox.evidence(identity))
        self.assertFalse(inbox.acknowledged(identity))
        source_event = store.get_event(identity)
        self.assertEqual(source_event["delivery_status"], "ack")
        self.assertEqual(source_event["receipt"]["receiver_receipt_id"], result["result_id"])
        record = self.record(event_id=identity)
        self.save_ledger([record])
        before = self.ledger_path.read_bytes()

        active, archive, status = maintain_ledger(self.ledger_path, inbox, self.policy)

        self.assertEqual(active["events"][identity], [record])
        self.assertEqual(archive["events"], {})
        self.assertEqual(status["rotated_events"], 0)
        self.assertEqual(self.ledger_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
