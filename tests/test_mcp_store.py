"""Synthetic-only persistence, concurrency and crash recovery; no native I/O."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from contrib.mcp_bridge.store import BridgeStore, BridgeError, BridgeCapacityError, subscription_id


def event(identity="evt-1", host="host-test", **changes):
    value = {"schema_version": "2.0", "event_id": identity, "host_id": host,
             "episode_id": "ep-test", "correlation_id": "ep-test", "sequence": 1,
             "event_type": "listener.changed", "transition": "new", "severity": "warning",
             "synthetic": True, "observed_at": "2026-01-01T00:00:00Z",
             "persisted_at": "2026-01-01T00:00:00Z", "evidence": {"port": 43210}}
    value.update(changes)
    return value


def snapshot(identity="evt-1", operation="query_listener", request_id="query-1"):
    return {"schema_version": "1.0", "event_id": identity, "operation": operation,
            "source": "eventguard_synthetic_evidence", "status": "ok", "request_id": request_id,
            "observed_at": "2026-01-01T00:00:00Z", "coverage_status": "partial",
            "synthetic": True, "snapshot_only": True, "system_query_executed": False,
            "rows": [{"protocol": "TCP", "port": 43210}], "truncated": False,
            "reason_code": "stored_synthetic_evidence"}


class Clock:
    def __init__(self):
        self.now = 10000.0
    def __call__(self):
        return self.now


class BridgeStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock()
        self.store = BridgeStore(self.temp.name, clock=self.clock)
        self.args = {"host_ref": "host-test", "event_types": []}
        self.url = "https://receiver.example.test/callback"
    def subscribe(self, owner="owner-a", **changes):
        values = dict(owner=owner, url=self.url, name="eventguard.security_change", arguments=self.args,
                      secret_ref="vault:opaque-ref", expires_at=self.clock.now + 10000,
                      verified_at=self.clock.now)
        values.update(changes)
        return self.store.upsert_subscription(**values)
    def accepted(self, identity="evt-1", owner="owner-a"):
        self.subscribe(owner)
        return self.store.enqueue_event(owner, event(identity))
    def assertCode(self, code, callable, *args, **kwargs):
        with self.assertRaises(BridgeError) as caught:
            callable(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_subscription_identity_is_principal_and_canonical_filter(self):
        args = {"host_ref": "host-test", "event_types": ["listener.changed", "coverage.degraded"]}
        other = {"host_ref": "host-test", "event_types": list(reversed(args["event_types"]))}
        self.assertEqual(subscription_id("a", self.url, "eventguard.security_change", args), subscription_id("a", self.url, "eventguard.security_change", other))
        self.assertNotEqual(subscription_id("a", self.url, "eventguard.security_change", args), subscription_id("b", self.url, "eventguard.security_change", args))

    def test_subscription_durable_rotation_expiry_and_safe_stats(self):
        old = self.subscribe()
        sub = self.subscribe(secret_ref="vault:new-ref", previous_secret_ref="vault:opaque-ref", previous_valid_until=self.clock.now+100)
        self.assertEqual(old["id"], sub["id"])
        reopened = BridgeStore(self.temp.name, clock=self.clock)
        self.assertEqual(reopened.find_subscription("owner-a", self.url, "eventguard.security_change", self.args), sub)
        self.assertEqual(len(reopened.active_subscriptions("owner-a")), 1)
        self.assertEqual(reopened.active_subscriptions("owner-b"), [])
        self.clock.now += 10001
        self.assertEqual(reopened.active_subscriptions(), [])
        text = json.dumps(reopened.stats())
        for private in (self.url, "vault:new-ref", "owner-a"):
            self.assertNotIn(private, text)

    def test_no_match_is_retryable_and_does_not_ack_or_store(self):
        self.assertCode("no_matching_subscription", self.store.enqueue_event, "owner-a", event())
        self.subscribe(arguments={"host_ref": "other-host", "event_types": []})
        self.assertCode("no_matching_subscription", self.store.enqueue_event, "owner-a", event())
        self.assertEqual(self.store.stats()["events"], 0)
        self.assertEqual(sum(self.store.stats()["deliveries"].values()), 0)

    def test_filter_and_owner_match(self):
        self.subscribe(arguments={"host_ref": "host-test", "event_types": ["coverage.degraded"]})
        self.assertCode("no_matching_subscription", self.store.enqueue_event, "owner-a", event())
        self.assertCode("no_matching_subscription", self.store.enqueue_event, "owner-b", event(event_type="coverage.degraded"))
        self.store.enqueue_event("owner-a", event(event_type="coverage.degraded"))
        self.assertEqual(self.store.stats()["events"], 1)

    def test_real_and_unknown_schema_and_type_rejected(self):
        self.subscribe()
        self.assertCode("synthetic_only", self.store.enqueue_event, "owner-a", event(synthetic=False))
        self.assertCode("invalid_event", self.store.enqueue_event, "owner-a", event(schema_version="9.0"))
        self.assertCode("unsupported_event_type", self.store.enqueue_event, "owner-a", event(event_type="arbitrary"))
        self.assertEqual(self.store.stats()["events"], 0)

    def test_idempotency_conflict_and_replay_after_unsubscribe(self):
        receipt = self.accepted()
        self.assertEqual(receipt["ack_type"], "receiver_persisted")
        self.assertFalse(receipt["real_agent_woken"])
        self.store.unsubscribe("owner-a", self.url, "eventguard.security_change", self.args)
        self.assertEqual(self.store.enqueue_event("owner-a", event()), receipt)
        self.assertCode("event_identity_conflict", self.store.enqueue_event, "owner-a", event(severity="high"))
        self.assertIsNone(self.store.claim_delivery())
        self.assertEqual(self.store.stats()["deliveries"]["revoked"], 1)

    def test_multiple_subscriptions_each_get_delivery_once(self):
        self.subscribe()
        self.subscribe(url="https://other.example.test/callback")
        self.store.enqueue_event("owner-a", event())
        ids = set()
        for _ in range(2):
            claim = self.store.claim_delivery()
            ids.add(claim["delivery_id"])
            self.store.complete_delivery(claim["delivery_id"], claim["lease_token"], "received", "callback_accepted", 202)
        self.assertEqual(len(ids), 2)
        self.assertIsNone(self.store.claim_delivery())
        self.assertEqual(self.store.stats()["deliveries"]["received"], 2)
        self.assertIsNone(self.store.get_case("owner-a", "evt-1"))

    def test_expiry_and_unsubscribe_cannot_resurrect_inflight(self):
        self.accepted()
        claim = self.store.claim_delivery()
        self.store.unsubscribe("owner-a", self.url, "eventguard.security_change", self.args)
        self.assertCode("stale_delivery_lease", self.store.complete_delivery, claim["delivery_id"], claim["lease_token"], "received", "ok", 200)
        self.assertIsNone(self.store.claim_delivery())
        self.assertEqual(self.store.unsubscribe("owner-a", self.url, "eventguard.security_change", self.args), {})

    def test_two_instances_lease_and_crash_recovery_at_least_once(self):
        self.accepted()
        other = BridgeStore(self.temp.name, clock=self.clock)
        first = self.store.claim_delivery()
        self.assertIsNone(other.claim_delivery())
        self.clock.now += 61
        second = other.claim_delivery()
        self.assertEqual(first["delivery_id"], second["delivery_id"])
        self.assertEqual(second["attempt"], 2)
        self.assertNotEqual(first["lease_token"], second["lease_token"])
        self.assertCode("stale_delivery_lease", self.store.complete_delivery, first["delivery_id"], first["lease_token"], "received", "ok", 200)
        other.complete_delivery(second["delivery_id"], second["lease_token"], "received", "ok", 200)
        self.assertIsNone(self.store.claim_delivery())

    def test_eighth_crashed_lease_becomes_failed_uncertain(self):
        self.accepted()
        for attempt in range(1, 9):
            store = BridgeStore(self.temp.name, clock=self.clock)
            self.assertEqual(store.claim_delivery()["attempt"], attempt)
            self.clock.now += 61
        self.assertIsNone(store.claim_delivery())
        self.assertEqual(store.stats()["deliveries"]["failed"], 1)
        self.assertIsNone(store.claim_delivery())

    def test_retry_backoff_is_bounded_and_max_attempts(self):
        self.accepted()
        for attempt in range(1, 9):
            claim = self.store.claim_delivery()
            outcome = self.store.complete_delivery(claim["delivery_id"], claim["lease_token"], "retry", "offline", 503)
            if attempt < 8:
                delay = outcome["next_retry_at"] - self.clock.now
                self.assertGreaterEqual(delay, min(3600, 30*2**(attempt-1))*0.8)
                self.assertLessEqual(delay, min(3600, 30*2**(attempt-1)*1.2))
                self.assertIsNone(self.store.claim_delivery())
                self.clock.now = outcome["next_retry_at"] + 0.01
            else:
                self.assertEqual(outcome["status"], "failed")
                self.assertIsNone(outcome["next_retry_at"])

    def test_success_needs_2xx_and_no_agent_case_claim(self):
        self.accepted()
        claim = self.store.claim_delivery()
        self.assertCode("received_requires_success_status", self.store.complete_delivery, claim["delivery_id"], claim["lease_token"], "received", "ok", 500)
        self.store.complete_delivery(claim["delivery_id"], claim["lease_token"], "received", "ok", 200)
        self.assertEqual(self.store.stats()["results"], 0)

    def test_owner_event_isolation_even_identical_ids(self):
        self.accepted()
        self.accepted(owner="owner-b")
        self.assertEqual(self.store.stats()["events"], 2)
        self.assertIsNone(self.store.get_event("owner-c", "evt-1"))
        self.assertEqual(self.store.list_queries("owner-c", "evt-1"), [])
        self.assertIsNone(self.store.get_case("owner-c", "evt-1"))

    def test_query_idempotency_restart_conflict_and_case_links(self):
        self.accepted()
        first = self.store.record_query("owner-a", "evt-1", "query-1", "query_listener", snapshot())
        reopened = BridgeStore(self.temp.name, clock=self.clock)
        self.assertEqual(reopened.record_query("owner-a", "evt-1", "query-1", "query_listener", snapshot()), first)
        changed = snapshot(); changed["status"] = "unknown"
        self.assertCode("query_identity_conflict", reopened.record_query, "owner-a", "evt-1", "query-1", "query_listener", changed)
        body = {"decision": "benign_change", "evidence_request_ids": ["query-1"], "reason_code": "synthetic_evidence_reviewed", "run_ref": "run-synthetic"}
        case = reopened.record_result("owner-a", "evt-1", body)
        self.assertEqual(reopened.record_result("owner-a", "evt-1", body), case)
        self.assertEqual(case["status"], "agent_result_recorded")
        self.assertFalse(case["platform_run_verified"])
        self.assertFalse(case["system_actions_performed"])
        changed = dict(body, decision="requires_user_approval")
        self.assertCode("result_identity_conflict", reopened.record_result, "owner-a", "evt-1", changed)
        self.assertEqual(len(reopened.list_queries("owner-a", "evt-1")), 1)
        self.assertEqual(reopened.get_case("owner-a", "evt-1"), case)

    def test_query_and_result_cross_owner_and_cross_event_references_rejected(self):
        self.accepted(); self.accepted("evt-2"); self.accepted(owner="owner-b")
        self.store.record_query("owner-a", "evt-1", "query-1", "query_listener", snapshot())
        body = {"decision": "needs_more_evidence", "evidence_request_ids": ["query-1"], "reason_code": "coverage_incomplete"}
        for owner, identity in (("owner-b", "evt-1"), ("owner-a", "evt-2")):
            self.assertCode("evidence_reference_not_found", self.store.record_result, owner, identity, body)
        self.assertCode("event_not_found", self.store.record_query, "owner-c", "evt-1", "query-1", "query_listener", snapshot())

    def test_result_cas_revisions_and_old_replay_do_not_roll_back_current(self):
        self.accepted()
        first_body = {"decision": "needs_more_evidence", "evidence_request_ids": [], "reason_code": "no_matching_evidence"}
        first = self.store.record_result("owner-a", "evt-1", first_body)
        self.store.record_query("owner-a", "evt-1", "query-1", "query_listener", snapshot())
        second_body = {"decision": "benign_change", "evidence_request_ids": ["query-1"], "reason_code": "synthetic_evidence_reviewed", "expected_result_id": first["result_id"]}
        second = self.store.record_result("owner-a", "evt-1", second_body)
        self.assertEqual((first["revision"], second["revision"]), (1, 2))
        self.assertEqual(self.store.record_result("owner-a", "evt-1", first_body), first)
        self.assertEqual(self.store.get_case("owner-a", "evt-1"), second)
        stale = dict(second_body, decision="requires_user_approval")
        self.assertCode("result_identity_conflict", self.store.record_result, "owner-a", "evt-1", stale)
        reopened = BridgeStore(self.temp.name, clock=self.clock)
        self.assertEqual(reopened.get_case("owner-a", "evt-1"), second)
        self.assertEqual(reopened.list_results("owner-a", "evt-1"), [first, second])
        self.assertEqual(reopened.list_results("owner-b", "evt-1"), [])

    def test_benign_result_requires_at_least_one_successful_query(self):
        self.accepted()
        body = {"decision": "benign_change", "evidence_request_ids": [], "reason_code": "synthetic_evidence_reviewed"}
        self.assertCode("benign_requires_successful_evidence", self.store.record_result, "owner-a", "evt-1", body)
        query = snapshot(); query["status"] = "partial"
        self.store.record_query("owner-a", "evt-1", "query-1", "query_listener", query)
        body["evidence_request_ids"] = ["query-1"]
        self.assertCode("benign_requires_successful_evidence", self.store.record_result, "owner-a", "evt-1", body)
        self.assertEqual(self.store.stats()["results"], 0)

    def test_result_revision_capacity_preserves_current(self):
        self.accepted()
        prior = None
        for index in range(10):
            body = {"decision": "needs_more_evidence", "evidence_request_ids": [], "reason_code": "coverage_incomplete", "run_ref": "synthetic-run-" + str(index)}
            if prior:
                body["expected_result_id"] = prior["result_id"]
            prior = self.store.record_result("owner-a", "evt-1", body)
        body["run_ref"] = "synthetic-run-over-capacity"
        body["expected_result_id"] = prior["result_id"]
        self.assertCode("result_revision_capacity", self.store.record_result, "owner-a", "evt-1", body)
        self.assertEqual(self.store.get_case("owner-a", "evt-1"), prior)
        self.assertEqual(len(self.store.list_results("owner-a", "evt-1")), 10)

    def test_query_minimization_rejects_untyped_and_private_content(self):
        self.accepted()
        bad = snapshot(); bad["command_line"] = "private"
        self.assertCode("invalid_query_snapshot", self.store.record_query, "owner-a", "evt-1", "query-1", "query_listener", bad)
        bad = snapshot(); bad["rows"] = [{"path": "private"}]
        self.assertCode("invalid_query_rows", self.store.record_query, "owner-a", "evt-1", "query-1", "query_listener", bad)
        bad = snapshot(); bad["system_query_executed"] = True
        self.assertCode("invalid_query_snapshot", self.store.record_query, "owner-a", "evt-1", "query-1", "query_listener", bad)
        body = {"decision": "benign_change", "evidence_request_ids": [], "reason_code": "no_matching_evidence", "summary": "arbitrary"}
        self.assertCode("invalid_result_fields", self.store.record_result, "owner-a", "evt-1", body)

    def test_capacity_never_drops_pending_or_half_commits(self):
        self.store = BridgeStore(self.temp.name, clock=self.clock, max_events=1, max_subscriptions=1)
        self.accepted()
        self.assertCode("event_capacity", self.store.enqueue_event, "owner-a", event("evt-2"))
        self.assertCode("subscription_capacity", self.subscribe, "owner-b")
        self.assertIsNotNone(self.store.get_event("owner-a", "evt-1"))
        self.assertIsNone(self.store.get_event("owner-a", "evt-2"))
        self.assertEqual(self.store.stats()["events"], 1)
        self.assertEqual(self.store.stats()["deliveries"]["pending"], 1)

    def test_query_count_bound_and_result_count_bound(self):
        self.accepted()
        for index in range(20):
            rid = "query-" + str(index)
            self.store.record_query("owner-a", "evt-1", rid, "query_listener", snapshot(request_id=rid))
        self.assertCode("query_capacity", self.store.record_query, "owner-a", "evt-1", "query-21", "query_listener", snapshot(request_id="query-21"))
        self.assertEqual(len(self.store.list_queries("owner-a", "evt-1")), 20)

    def test_sqlite_bytes_capacity_rolls_back_and_preserves_rows(self):
        self.store = BridgeStore(self.temp.name, clock=self.clock, max_bytes=131072)
        self.subscribe()
        accepted = []
        for index in range(100):
            identity = "large-" + str(index)
            try:
                self.store.enqueue_event("owner-a", event(identity, evidence={"summary": "s"*500, "previous": ["x"*500]*8}))
                accepted.append(identity)
            except BridgeCapacityError:
                break
        self.assertGreater(len(accepted), 0)
        self.assertLess(len(accepted), 100)
        self.assertLessEqual(Path(self.store.path).stat().st_size, 131072)
        self.assertEqual(self.store.stats()["events"], len(accepted))
        self.assertEqual(self.store.stats()["deliveries"]["pending"], len(accepted))
        claim = self.store.claim_delivery()
        self.store.complete_delivery(claim["delivery_id"], claim["lease_token"], "received", "ok", 200)

    def test_tampered_stored_event_is_not_published(self):
        self.accepted()
        db = sqlite3.connect(str(self.store.path))
        try:
            payload = json.loads(db.execute("SELECT payload FROM events").fetchone()[0])
            payload["synthetic"] = False
            db.execute("UPDATE events SET payload=?", (json.dumps(payload),))
            db.commit()
        finally:
            db.close()
        self.assertCode("stored_event_invalid", self.store.claim_delivery)
        self.assertEqual(self.store.stats()["deliveries"]["pending"], 1)


if __name__ == "__main__":
    unittest.main()
