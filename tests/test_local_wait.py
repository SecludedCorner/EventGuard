import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.store import StoreError
from eventguard.local_wait import LocalWait, LocalWaitError


def sample(identity="synthetic-local-one", synthetic=True):
    return {"schema_version": "2.0", "event_id": identity, "host_id": "synthetic-host",
            "episode_id": identity, "correlation_id": identity, "sequence": 1,
            "event_type": "listener.changed", "transition": "new", "severity": "warning",
            "synthetic": synthetic, "observed_at": "2026-10-22T00:00:00Z",
            "persisted_at": "2026-10-22T00:00:00Z",
            "evidence": {"protocol": "TCP", "port": 45454, "binding_scope": "all_interfaces",
                         "name": "untrusted text must not reach the model"},
            "coverage": {"status": "ok", "gaps": []}}


class LocalWaitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "dedicated"
        self.backend = LocalWait(self.directory)

    async def test_wait_returns_only_after_event_then_query_and_idempotent_ack(self):
        task = asyncio.create_task(self.backend.wait_for_event(2))
        await asyncio.sleep(0.1)
        self.assertFalse(task.done())
        self.backend.store.enqueue(sample())
        delivered = await task
        self.assertEqual(delivered["status"], "event_available")
        self.assertGreaterEqual(delivered["duration_seconds"], 0.1)
        self.assertNotIn("name", delivered["event"]["data"]["evidence"])
        query = self.backend.query_evidence(delivered["event_id"])
        result = self.backend.ack_event(query["event_id"], query["query_id"], "reviewed_synthetic")
        self.assertTrue(result["outbox_acknowledged"])
        self.assertEqual(self.backend.ack_event(query["event_id"], query["query_id"], "reviewed_synthetic"), result)
        restarted = LocalWait(self.directory)
        self.assertEqual(restarted.ack_event(query["event_id"], query["query_id"], "reviewed_synthetic"), result)
        self.assertEqual(restarted.store.get_event(query["event_id"])["delivery_status"], "ack")
        self.assertFalse(result["real_agent_wake_verified"])

    async def test_timeout_is_terminal_and_does_not_ack(self):
        self.backend.store.enqueue(sample(synthetic=False))
        result = await self.backend.wait_for_event(1)
        self.assertEqual(result["status"], "wait_expired")
        self.assertTrue(result["do_not_model_repoll"])
        self.assertEqual(self.backend.store.stats()["pending"], 1)

    async def test_cancellation_releases_waiter_and_preserves_pending(self):
        task = asyncio.create_task(self.backend.wait_for_event(3))
        await asyncio.sleep(0.1)
        busy = await self.backend.wait_for_event(1)
        self.assertEqual(busy["status"], "busy")
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        ledger = json.loads((self.directory / "local-wait-results.json").read_text())
        self.assertEqual(ledger["waits"][-1]["status"], "cancelled")
        self.backend.store.enqueue(sample())
        self.assertEqual((await self.backend.wait_for_event(1))["status"], "event_available")
        self.assertEqual(self.backend.store.stats()["pending"], 1)

    async def test_result_survives_ack_failure_and_retries_same_identity(self):
        self.backend.store.enqueue(sample())
        delivered = await self.backend.wait_for_event(1)
        query = self.backend.query_evidence(delivered["event_id"])
        with patch.object(self.backend.store, "acknowledge", side_effect=StoreError("synthetic_failure")):
            with self.assertRaisesRegex(LocalWaitError, "result_preserved"):
                self.backend.ack_event(query["event_id"], query["query_id"], "reviewed_synthetic")
        ledger = json.loads((self.directory / "local-wait-results.json").read_text())
        saved = ledger["events"][query["event_id"]]["result"]
        self.assertEqual(self.backend.store.stats()["pending"], 1)
        restarted = LocalWait(self.directory)
        retried = restarted.ack_event(query["event_id"], query["query_id"], "reviewed_synthetic")
        self.assertEqual(retried["result_id"], saved["result_id"])
        self.assertTrue(retried["outbox_acknowledged"])

    async def test_same_event_query_required_and_decision_is_typed(self):
        with self.assertRaises(LocalWaitError):
            self.backend.query_evidence("not-delivered")
        self.backend.store.enqueue(sample())
        await self.backend.wait_for_event(1)
        with self.assertRaises(LocalWaitError):
            self.backend.ack_event("synthetic-local-one", "query-unknown", "reviewed_synthetic")
        query = self.backend.query_evidence("synthetic-local-one")
        for decision in ("safe", "run shell", None):
            with self.assertRaises(LocalWaitError):
                self.backend.ack_event(query["event_id"], query["query_id"], decision)
        self.assertEqual(self.backend.store.stats()["pending"], 1)

    async def test_rejects_foreign_directory_and_invalid_timeout(self):
        foreign = Path(self.temp.name) / "foreign"
        foreign.mkdir()
        (foreign / "user-file.txt").write_text("preserve", encoding="utf-8")
        with self.assertRaises(LocalWaitError):
            LocalWait(foreign)
        self.assertEqual((foreign / "user-file.txt").read_text(), "preserve")
        for value in (0, 46, True, float("nan"), float("inf"), "30"):
            with self.assertRaises(LocalWaitError):
                await self.backend.wait_for_event(value)


if __name__ == "__main__":
    unittest.main()
