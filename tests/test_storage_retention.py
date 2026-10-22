"""Real local SQLite/files, synthetic IDs; never a provider/model/agent test."""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from eventguard.events.store import EventStore, CapacityError, StoreError, event_payload_hash
from eventguard.events.schema import validate_event
from eventguard.queue_inbox import QueueInbox, QueueInboxError
from eventguard.storage_policy import limits
from eventguard.acceptance_control import FileLease, read_json, write_json
from eventguard.agent_dispatch import KIND, _ledger, _ledger_write, maintain_ledger, run


def event(identity):
    return {"schema_version": "2.0", "event_id": identity, "host_id": "synthetic-capacity-host",
            "episode_id": "synthetic-capacity", "correlation_id": "synthetic-capacity", "sequence": 1,
            "event_type": "listener.changed", "transition": "new", "severity": "warning", "synthetic": True,
            "observed_at": "2026-10-23T00:00:00Z", "persisted_at": "2026-10-23T00:00:00Z",
            "evidence": {"protocol": "TCP", "port": 18080}, "coverage": {"status": "unknown", "gaps": []}}


def ack(store, identity):
    return store.acknowledge(identity, {"ack_type": "receiver_persisted", "event_id": identity, "receipt_id": "receipt-"+identity})


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.state = self.root/"source", self.root/"state"

    def pending_hashes(self, store):
        return {e["event_id"]: event_payload_hash(validate_event(e)) for e in store.list_events(1000) if e["delivery_status"] != "ack"}

    def test_outbox_ttl_only_cleans_acked_including_review_and_preserves_failed(self):
        store = EventStore(self.source, max_events=4, acked_retention_seconds=10)
        for key in ("ack-old", "pending-old", "retry-old", "failed-old"):
            store.enqueue(event(key))
        ack(store, "ack-old")
        fingerprint = event_payload_hash(validate_event(event("ack-old")))
        store.save_review("ack-old", fingerprint, {"fixture": True, "payload_hash": fingerprint})
        with store._connect() as db:
            db.execute("UPDATE events SET updated_at=0")
            db.execute("UPDATE events SET delivery_status='retry' WHERE event_id='retry-old'")
            db.execute("UPDATE events SET delivery_status='failed' WHERE event_id='failed-old'")
        original = self.pending_hashes(store)
        result = store.maintain()
        self.assertIsNone(store.get_event("ack-old"))
        self.assertEqual(self.pending_hashes(store), original)
        with store._connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM event_reviews").fetchone()[0], 0)
        self.assertTrue(store.enqueue(event("after-cleanup")))
        self.assertEqual(result["receipt_count"], 1)
        self.evidence = {"scope": "synthetic_sqlite_not_agent", "case": "outbox_ttl", "preserved_unacked_ids": sorted(original), "stats": result}

    def test_count_full_rolls_back_then_ack_frees_one_slot_without_loss(self):
        store = EventStore(self.source, max_events=2)
        store.commit_evaluation({"baseline": 1}, [event("count-1"), event("count-2")])
        original = self.pending_hashes(store)
        with self.assertRaises(CapacityError):
            store.commit_evaluation({"baseline": 2}, [event("count-3")])
        self.assertEqual(self.pending_hashes(store), original)
        self.assertEqual(store.load_detector_state(), {"baseline": 1})
        ack(store, "count-1")
        self.assertTrue(store.enqueue(event("count-3")))
        self.assertEqual(set(self.pending_hashes(store)), {"count-2", "count-3"})
        self.assertFalse(store.enqueue(event("count-1")))
        self.evidence = {"scope": "synthetic_sqlite_not_agent", "case": "outbox_count_full_recovery", "before_ids": sorted(original), "acked_ids": ["count-1"], "after_ids": sorted(self.pending_hashes(store)), "missing": []}

    def test_byte_full_ack_and_receipt_pressure_recover_repeatedly(self):
        store = EventStore(self.source, max_bytes=65536, max_events=3)
        store.enqueue(event("preserve-pending"))
        held = self.pending_hashes(store)["preserve-pending"]
        for index in range(100):
            identity = "cycle-"+str(index)
            self.assertTrue(store.enqueue(event(identity)))
            ack(store, identity)
            self.assertEqual(self.pending_hashes(store)["preserve-pending"], held)
            self.assertLessEqual(store.path.stat().st_size, 65536)
        result = store.stats()
        self.assertGreater(int(result["receipt_rotation"].get("pressure_rotated_receipts", 0)), 0)
        self.assertTrue(store.enqueue(event("after-cycles")))
        self.evidence = {"scope": "synthetic_sqlite_not_24_hour_soak", "case": "receipt_pressure_100_cycles", "cycles": 100, "preserved_pending_id": "preserve-pending", "stats": result}

    def test_persisted_limits_apply_to_default_ack_opener(self):
        store = EventStore(self.source, max_events=1, max_bytes=65536, receipt_limit=2)
        store.enqueue(event("persisted-1"))
        inbox = QueueInbox(self.source, self.state, "persisted-1")
        inbox.receive_event()
        query = inbox.query_evidence("persisted-1")
        inbox.ack_event("persisted-1", query["query_id"], "reviewed_metadata")
        self.assertEqual(inbox.store.max_bytes, 65536)
        self.assertEqual(EventStore(self.source).policy, store.policy)
        store.enqueue(event("persisted-2"))
        with self.assertRaises(CapacityError):
            EventStore(self.source).enqueue(event("persisted-3"))

    def test_duplicate_ack_does_not_change_receipt_or_timestamp(self):
        store = EventStore(self.source)
        store.enqueue(event("once"))
        ack(store, "once")
        before = store.get_event("once")
        ack(store, "once")
        self.assertEqual(store.get_event("once"), before)
        with self.assertRaisesRegex(StoreError, "ack_receipt_identity_conflict"):
            store.acknowledge("once", {"ack_type": "receiver_persisted", "event_id": "once", "receipt_id": "different"})

    def test_receipt_count_and_age_are_bounded_and_recent_id_deduplicates(self):
        store = EventStore(self.source, receipt_limit=2, acked_retention_seconds=0, receipt_retention_seconds=20)
        for key in ("r1", "r2", "r3"):
            store.enqueue(event(key))
            ack(store, key)
        store.maintain()
        self.assertLessEqual(store.stats()["receipt_count"], 2)
        self.assertFalse(store.enqueue(event("r3")))
        store.maintain(now=time.time()+30)
        self.assertEqual(store.stats()["receipt_count"], 0)

    def inbox(self, identity=None, policy=None):
        return QueueInbox(self.source, self.state, identity, limits=policy)

    def test_inbox_count_full_then_ack_compacts_and_replays_same_query(self):
        store = EventStore(self.source)
        for key in ("i1", "i2"):
            store.enqueue(event(key))
        policy = {"max_events": 1, "max_completed": 1}
        first = self.inbox("i1", policy)
        first.receive_event()
        with self.assertRaisesRegex(QueueInboxError, "event_capacity_pending_preserved"):
            self.inbox("i2").receive_event()
        query = first.query_evidence("i1")
        result = first.ack_event("i1", query["query_id"], "reviewed_metadata")
        self.assertEqual(self.inbox("i1").query_evidence("i1"), query)
        with patch.object(first.store, "acknowledge", side_effect=AssertionError("duplicate ACK")):
            self.assertEqual(first.ack_event("i1", query["query_id"], "reviewed_metadata"), result)
        self.inbox("i2").receive_event()
        self.assertEqual(set(self.pending_hashes(store)), {"i2"})
        self.assertEqual(first.maintain()["active_events"], 1)
        self.evidence = {"scope": "synthetic_inbox_files_sqlite_not_agent", "case": "inbox_count_recovery", "same_query_id": query["query_id"], "acked_ids": ["i1"], "pending_ids": ["i2"], "missing": []}

    def test_inbox_byte_admission_reserves_query_result_and_ack_progress(self):
        store = EventStore(self.source)
        keys = ["byte-"+str(index) for index in range(16)]
        for key in keys:
            store.enqueue(event(key))
        policy = {"max_bytes": 65536}
        accepted = []
        for key in keys:
            try:
                self.inbox(key, policy).receive_event()
                accepted.append(key)
            except QueueInboxError as error:
                self.assertIn("capacity_pending_preserved", str(error))
                blocked = key
                break
        else:
            self.fail("byte admission did not fill")
        self.assertGreater(len(accepted), 0)
        original = self.pending_hashes(store)
        first = self.inbox(accepted[0])
        query = first.query_evidence(accepted[0])
        first.ack_event(accepted[0], query["query_id"], "reviewed_metadata")
        self.inbox(blocked).receive_event()
        remaining = self.pending_hashes(store)
        self.assertEqual(remaining, {key: value for key, value in original.items() if key != accepted[0]})
        self.assertLessEqual(first.maintain()["storage_bytes"], 65536)
        self.evidence = {"scope": "synthetic_inbox_files_sqlite_not_agent", "case": "inbox_byte_recovery", "accepted_before_full": accepted, "recovered_event_id": blocked, "pending_after": sorted(remaining), "missing": []}

    def test_completion_write_failure_preserves_legacy_triple_then_repairs_without_second_ack(self):
        store = EventStore(self.source)
        store.enqueue(event("repair"))
        inbox = self.inbox("repair")
        inbox.receive_event()
        query = inbox.query_evidence("repair")
        original = inbox._immutable
        def fail(path, value):
            if path.name.startswith("completed-"):
                raise QueueInboxError("synthetic_completion_write_failure")
            return original(path, value)
        with patch.object(inbox, "_immutable", side_effect=fail):
            with self.assertRaisesRegex(QueueInboxError, "synthetic_completion"):
                inbox.ack_event("repair", query["query_id"], "reviewed_metadata")
        self.assertTrue(inbox._path("snapshot", "repair").exists())
        self.assertTrue(inbox._path("result", "repair").exists())
        restarted = self.inbox("repair")
        restarted.maintain()
        with patch.object(restarted.store, "acknowledge", side_effect=AssertionError("must not ACK twice")):
            self.assertTrue(restarted.ack_event("repair", query["query_id"], "reviewed_metadata")["outbox_acknowledged"])
        self.assertFalse(inbox._path("snapshot", "repair").exists())

    def test_completed_files_count_ttl_and_source_receipt_expiry(self):
        store = EventStore(self.source, receipt_retention_seconds=0, acked_retention_seconds=0)
        for index in range(8):
            key = "completed-"+str(index)
            store.enqueue(event(key))
            inbox = self.inbox(key, {"max_completed": 2})
            inbox.receive_event()
            query = inbox.query_evidence(key)
            inbox.ack_event(key, query["query_id"], "reviewed_metadata")
            self.assertLessEqual(inbox.maintain()["completed_events"], 2)
            store.maintain()
        self.assertEqual(store.stats()["receipt_count"], 0)
        self.assertTrue(inbox.acknowledged(key), "Durable completion survives outbox retention")
        self.assertEqual(inbox.query_evidence(key), query)
        self.assertEqual(inbox.maintain(now=time.time()+2592001)["completed_events"], 0)

    def test_pending_source_cannot_be_hidden_by_a_completed_marker(self):
        store = EventStore(self.source)
        store.enqueue(event("reappeared"))
        inbox = self.inbox("reappeared")
        inbox.receive_event()
        query = inbox.query_evidence("reappeared")
        inbox.ack_event("reappeared", query["query_id"], "reviewed_metadata")
        with store._connect() as db:
            db.execute("UPDATE events SET delivery_status='pending',receipt=NULL")
        with self.assertRaisesRegex(QueueInboxError, "completed_event_reappeared"):
            inbox.maintain(now=time.time()+2592001)
        self.assertEqual(store.get_event("reappeared")["delivery_status"], "pending")

    def test_mutation_owner_busy_is_explicit_then_recovers(self):
        store = EventStore(self.source)
        store.enqueue(event("busy"))
        inbox = self.inbox("busy")
        lease = FileLease(self.state/"inbox-mutation.lock")
        self.assertTrue(lease.acquire())
        try:
            with self.assertRaisesRegex(QueueInboxError, "inbox_state_busy"):
                inbox.receive_event()
        finally:
            lease.release()
        self.assertEqual(inbox.receive_event()["event_id"], "busy")


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root/"dispatcher-attempts.json"
        self.policy = {"max_events": 1, "max_completed": 2, "max_bytes": 65536}

    def record(self, key, terminal=False):
        return {"event_id": key, "attempt_id": "a"*32, "run_id": "b"*32, "run_dir": str(self.root),
                "state": "complete" if terminal else "started", "child_exited": terminal,
                "passed": terminal, "ack_verified": terminal, "finished_at": datetime.now(timezone.utc).isoformat()}

    def backend(self):
        class Fixture:
            def acknowledged(self, identity):
                return False
        return Fixture()

    def test_full_active_ledger_preserves_uncertain_then_terminal_proof_recovers(self):
        ledger = {"kind": KIND, "events": {"l1": [self.record("l1")]}}
        _ledger_write(self.path, ledger, limits("dispatcher", self.policy))
        before = self.path.read_bytes()
        active, archive, status = maintain_ledger(self.path, self.backend(), self.policy)
        self.assertEqual(status["rotated_events"], 0)
        with self.assertRaisesRegex(Exception, "capacity_pending_preserved"):
            _ledger_write(self.path, {"kind": KIND, "events": {**active["events"], "l2": [self.record("l2")]}}, limits("dispatcher", self.policy))
        self.assertEqual(self.path.read_bytes(), before)
        ledger["events"]["l1"][0] = self.record("l1", True)
        _ledger_write(self.path, ledger, limits("dispatcher", self.policy))
        active, archive, status = maintain_ledger(self.path, self.backend(), self.policy)
        self.assertEqual(active["events"], {})
        self.assertEqual(set(archive["events"]), {"l1"})
        _ledger_write(self.path, {"kind": KIND, "events": {"l2": [self.record("l2")]}}, limits("dispatcher", self.policy))
        self.evidence = {"scope": "synthetic_ledger_terminal_proof_fixture_not_agent", "case": "ledger_count_full_recovery", "preserved_unconfirmed_id": "l1", "archived_ids": ["l1"], "new_active_ids": ["l2"], "missing": []}

    def test_archive_failure_never_deletes_active_and_crash_replay_is_idempotent(self):
        value = {"kind": KIND, "events": {"closed": [self.record("closed", True)]}}
        write_json(self.path, value)
        before = self.path.read_bytes()
        with patch("eventguard.agent_dispatch.write_json", side_effect=OSError("synthetic write")):
            with self.assertRaises(OSError):
                maintain_ledger(self.path, self.backend(), self.policy)
        self.assertEqual(self.path.read_bytes(), before)
        with patch("eventguard.agent_dispatch._ledger_write", side_effect=OSError("synthetic crash after archive")):
            with self.assertRaises(OSError):
                maintain_ledger(self.path, self.backend(), self.policy)
        self.assertEqual(self.path.read_bytes(), before)
        active, archive, status = maintain_ledger(self.path, self.backend(), self.policy)
        self.assertEqual(active["events"], {})
        self.assertEqual(set(archive["events"]), {"closed"})

    def test_human_receipt_after_failed_agent_frees_capacity_without_agent_success(self):
        from types import SimpleNamespace
        failed = dict(self.record("human-received", True), passed=False, ack_verified=False, tree_exit_verified=True)
        write_json(self.path, {"kind": KIND, "events": {"human-received": [failed]}})
        receiver = SimpleNamespace(acknowledged=lambda identity: identity == "human-received")
        active, archive, result = maintain_ledger(self.path, receiver, self.policy)
        self.assertEqual(active["events"], {})
        row = archive["events"]["human-received"]
        self.assertFalse(row["passed"])
        self.assertEqual(row["completion"], "received_without_agent_proof")
        self.assertEqual(row["attempts"], 1)
        self.assertEqual(result["rotated_events"], 1)
        # The retained receipt can be re-read; a new pending event fits.
        maintain_ledger(self.path, receiver, self.policy)
        _ledger_write(self.path, {"kind": KIND, "events": {"next": [self.record("next")]}}, limits("dispatcher", self.policy))

    def test_ack_never_archives_a_child_with_unconfirmed_exit(self):
        from types import SimpleNamespace
        write_json(self.path, {"kind": KIND, "events": {"unknown-exit": [self.record("unknown-exit")]}})
        active, archive, result = maintain_ledger(self.path, SimpleNamespace(acknowledged=lambda _: True), self.policy)
        self.assertEqual(set(active["events"]), {"unknown-exit"})
        self.assertEqual(archive["events"], {})
        self.assertEqual(result["rotated_events"], 0)

    def test_bytes_full_archive_rollover_and_ttl_keep_active_unchanged(self):
        policy = limits("dispatcher", {"max_completed": 2, "max_bytes": 65536})
        huge = {"kind": KIND, "events": {"pending": [{**self.record("pending"), "run_dir": "x"*33000}]}}
        with self.assertRaisesRegex(Exception, "capacity_pending_preserved"):
            _ledger_write(self.path, huge, policy)
        for index in range(10):
            key = "closed-"+str(index)
            write_json(self.path, {"kind": KIND, "events": {key: [self.record(key, True)], "pending": [self.record("pending")]}})
            active, archive, result = maintain_ledger(self.path, self.backend(), policy)
            self.assertEqual(set(active["events"]), {"pending"})
            self.assertLessEqual(result["completed_events"], 2)
            self.assertLessEqual(sum(p.stat().st_size for p in (self.path, self.path.with_name("dispatcher-completed.json"))), 65536)
        active, archive, status = maintain_ledger(self.path, self.backend(), policy, now=time.time()+2592001)
        self.assertEqual(archive["events"], {})
        self.assertEqual(set(active["events"]), {"pending"})

    def test_dispatch_capacity_blocks_before_any_child_or_command(self):
        from types import SimpleNamespace
        source = self.root/"source"
        EventStore(source).enqueue(event("new-pending"))
        state = self.root/"state"
        state.mkdir()
        old = self.record("failed")
        old.update(state="complete", passed=False, child_exited=True, tree_exit_verified=True)
        write_json(state/self.path.name, {"kind": KIND, "events": {"failed": [old]}})
        backend = SimpleNamespace(acknowledged=lambda _: False, pending_event_id=lambda: "new-pending")
        with patch("eventguard.agent_dispatch._inbox", return_value=backend), patch("eventguard.agent_dispatch.shutil.which", return_value=sys.executable), patch("eventguard.agent_dispatch.importlib.util.find_spec", return_value=True), patch("eventguard.agent_dispatch.command") as command, patch("eventguard.agent_dispatch.spawn") as spawn:
            code = run(self.root/"run", source, state, execute=True, storage_limits=self.policy)
        self.assertEqual(code, 2)
        command.assert_not_called()
        spawn.assert_not_called()
        self.assertEqual(EventStore(source).get_event("new-pending")["delivery_status"], "pending")

    def test_limits_reject_bool_unknown_or_unbounded_values(self):
        for section, values in (("outbox", {"receipt_limit": True}), ("inbox", {"max_bytes": 0}),
                                ("dispatcher", {"max_events": 129}), ("outbox", {"unknown": 1})):
            with self.subTest(section=section, values=values), self.assertRaises(ValueError):
                limits(section, values)


if __name__ == "__main__":
    unittest.main()
