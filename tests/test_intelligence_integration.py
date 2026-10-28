"""Offline advisory product acceptance. No model or real host inventory."""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock

from eventguard.intelligence import engine, service
from eventguard.intelligence.store import IntelligenceStore
from eventguard.events.store import EventStore, CapacityError, StoreError
from eventguard.events.catalog import EventCatalog
from eventguard.queue_inbox import QueueInbox, QueueInboxError
from eventguard.cli import main

NOW = "2026-10-23T12:00:00Z"


def record():
    return {"ids": ["RUSTSEC-2026-0381", "CVE-2026-111943"], "component": "webpki-roots",
            "ecosystem": "crates.io", "title": "SYNTHETIC: untrusted announcement",
            "published_at": NOW, "updated_at": NOW, "withdrawn": False,
            "affected": [{"ecosystem": "crates.io", "package": "webpki-roots", "ranges": [],
                          "versions": [], "patched": [">=1.0.10"], "unaffected": []}],
            "fixes": [{"stage": "released", "version": "1.0.10", "package": "webpki-roots"}],
            "conditions": {}, "evidence": [{"url": "https://rustsec.org/advisories/RUSTSEC-2026-0381.html", "stage": "published", "claim": "fixture", "confidence": "high"}],
            "exploitation": "unknown", "confidence": "high", "source_url": "https://rustsec.org/advisories/RUSTSEC-2026-0381.html"}


class IntelligenceIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.lock = self.root / "Cargo.lock"
        self.lock.write_text('version = 3\n[[package]]\nname = "webpki-roots"\nversion = "1.0.9"\n', encoding="utf-8")
        self.source = {"id": "rustsec-fixture", "adapter": "rustsec", "url": "https://rustsec.org/advisories/RUSTSEC-2026-0381.html",
                       "tracking_ids": ["RUSTSEC-2026-0381"], "interval_seconds": 3600, "stale_after_seconds": 86400}
        self.config = {"schema_version": 1, "namespace": "test", "sources": [self.source],
                       "inventory": {"paths": [str(self.lock)]}, "storage": {"cooldown_seconds": 0}}
        self.path = self.root / "config/advisories.json"
        self.path.write_text(json.dumps(self.config), encoding="utf-8")
        self.db = self.root / "data/advisories/intelligence.sqlite3"

    def fetch(self, source, previous, now=None):
        return {"status": "success", "records": [record()], "etag": '"fixture"', "last_modified": None,
                "retry_after_seconds": None, "content_hash": "a" * 64, "fetched_at": now, "error_code": None}

    def run_cycle(self, **options):
        return engine.cycle(self.root, fetcher=self.fetch, now=NOW, synthetic=True, **options)

    def test_end_to_end_offline_receive_query_result_ack_and_restart(self):
        with patch("subprocess.Popen", side_effect=AssertionError("no subprocess/model")):
            first = self.run_cycle()
            self.assertEqual(first["events_emitted"], 1)
            second = self.run_cycle()
            self.assertEqual(second["events_emitted"], 0)
        events = EventCatalog(self.root, "test").list(source="advisories")["events"]
        self.assertEqual(len(events), 1)
        identity = events[0]["event_id"]
        inbox = QueueInbox(self.root / "data/test", self.root / "data/intel-test-inbox", identity)
        received = inbox.receive_event()
        query = inbox.query_evidence(identity)
        self.assertEqual(received["snapshot"], query["snapshot"])
        self.assertEqual(len(query["snapshot"]), 7)
        self.assertEqual(query["snapshot"]["event_type"], "advisory.changed")
        for value in ("webpki", "Cargo.lock", "CVE-", "untrusted announcement", str(self.root)):
            self.assertNotIn(value, json.dumps(query))
        # Read then exit without ACK. A fresh receiver gets the same query ID.
        self.assertEqual(EventStore(self.root / "data/test").stats()["pending"], 1)
        recovered = QueueInbox(self.root / "data/test", self.root / "data/intel-test-inbox", identity)
        self.assertEqual(recovered.query_evidence(identity)["query_id"], query["query_id"])
        with patch.object(recovered.store, "acknowledge", side_effect=StoreError("fixture_save_failure")):
            with self.assertRaises(QueueInboxError):
                recovered.ack_event(identity, query["query_id"], "needs_more_evidence")
        self.assertIsNotNone(recovered.evidence(identity)["result"])
        result = recovered.ack_event(identity, query["query_id"], "needs_more_evidence")
        self.assertTrue(result["outbox_acknowledged"])
        self.assertEqual(result["incident_conclusion"], "not_assessed")
        self.assertEqual(EventStore(self.root / "data/test").stats()["ack"], 1)
        self.assertEqual(recovered.ack_event(identity, query["query_id"], "needs_more_evidence"), result)
        case = IntelligenceStore(self.db, readonly=True).event_case(identity)
        self.assertIn("CVE-2026-111943", case["aliases"])
        self.evidence = {"scope": "offline SQLite/backend tools; no real agent", "event_id": identity,
                         "same_query_recovered": True, "saved_result_before_ack": True, "model_calls": 0}

    def test_outbox_full_then_recovery_preserves_pending(self):
        outbox = EventStore(self.root / "data/test", max_events=1)
        blocker = engine.make_event({"change_id": "blocker", "reason": "fixture", "observed_at": NOW}, synthetic=True)
        outbox.enqueue(blocker)
        with self.assertRaises(CapacityError):
            self.run_cycle()
        store = IntelligenceStore(self.db)
        self.assertEqual(store.status(NOW)["pending_changes"], 1)
        pending = store.pending_changes(now=NOW)[0]
        event_id = engine.make_event(pending, synthetic=True)["event_id"]
        # Expand the explicit capacity policy; never remove the pending blocker.
        EventStore(self.root / "data/test", max_events=2)
        self.assertEqual(self.run_cycle()["events_emitted"], 1)
        self.assertEqual(outbox.get_event(blocker["event_id"])["delivery_status"], "pending")
        self.assertEqual(outbox.get_event(event_id)["delivery_status"], "pending")

    def test_crash_after_enqueue_before_mark_reuses_exact_payload(self):
        with patch.object(IntelligenceStore, "mark_emitted", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                self.run_cycle()
        outbox = EventStore(self.root / "data/test")
        saved = outbox.list_events()[0]
        self.assertEqual(self.run_cycle()["events_emitted"], 1)
        self.assertEqual(outbox.stats()["total"], 1)
        self.assertEqual(outbox.get_event(saved["event_id"])["event_id"], saved["event_id"])

    def test_status_has_no_daily_quota_and_does_not_drop_or_start(self):
        self.run_cycle()
        with patch("eventguard.agent_budget.public_status", side_effect=AssertionError("historical budget read")), \
                patch("subprocess.Popen", side_effect=AssertionError("no model")):
            value = engine.status(self.root)
        self.assertEqual(value["pending_events"], 1)
        self.assertNotIn("daily_remaining", value)
        self.assertNotIn("agent_budget", value)
        self.assertEqual(value["agent_blocked_reason"], "not_enabled_this_round")

    def test_failure_remains_visible_during_backoff_and_check_exit_is_partial(self):
        def failed(source,previous,now=None):
            return {"status":"failed","records":[],"error_code":"http_503","retry_after_seconds":None}
        first=engine.cycle(self.root,fetcher=failed,now=NOW,synthetic=True)
        self.assertEqual(first["state"],"partial")
        second=engine.cycle(self.root,fetcher=lambda *a,**k:self.fail("backoff must not fetch"),now=NOW,synthetic=True)
        self.assertEqual(second["errors"],first["errors"])
        with patch("eventguard.intelligence.engine.cycle",return_value=second),redirect_stdout(io.StringIO()):
            self.assertEqual(main(["advisories","check"],root=self.root),5)

    def test_scope_change_is_rejected_before_synthetic_can_enter_live(self):
        self.run_cycle()
        self.config["namespace"]="live"
        self.path.write_text(json.dumps(self.config),encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError,"namespace_binding_mismatch"):
            engine.cycle(self.root,fetcher=self.fetch,now=NOW)
        self.assertFalse((self.root/"data/live/eventguard.sqlite3").exists())

    def test_relative_inventory_path_uses_root_not_current_working_directory(self):
        self.config["inventory"]["paths"]=["Cargo.lock"]
        self.path.write_text(json.dumps(self.config),encoding="utf-8")
        self.assertEqual(self.run_cycle()["events_emitted"],1)

    def test_corrupt_host_control_is_not_reported_as_cooperative_stop(self):
        (self.root/"data/advisories").mkdir(parents=True)
        run_id="a"*32
        job="Global\\EventGuard-"+"b"*32
        control={"enabled":True,"run_id":run_id,"job_name":job,"config":"config/advisories.json"}
        held={"pid":123,"created_at":NOW,"session_id":1}
        keeper=Mock()
        keeper.receipt.return_value=held
        with patch.object(service,"_read",side_effect=[control,ValueError("synthetic corrupt control")]),patch.object(service.processes,"adopt_current_job",return_value=keeper),patch.object(service,"_KEEPERS",[]):
            with self.assertRaises(ValueError):
                service.serve(self.root,run_id,job)
        exit_record=json.loads((self.root/"data/advisories/exit.json").read_text(encoding="utf-8"))
        self.assertEqual(exit_record["reason"],"unexpected_host_failure")
        run=json.loads((self.root/"data/advisories/run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["state"],"failed")

    def test_shipped_facts_example_is_readable_but_cannot_be_live_evidence(self):
        from eventguard.intelligence.inventory import collect_inventory
        original=Path(__file__).resolve().parents[1]/"config/advisory-assets.example.json"
        # A managed checkout can live under .codex, which inventory must refuse.
        # Read the shipped fixture from a disposable test directory instead.
        sample=self.root/"advisory-assets.example.json"
        sample.write_bytes(original.read_bytes())
        config={"inventory":{"paths":[{"path":str(sample),"kind":"facts"}]}}
        observed=collect_inventory(config,now=NOW)
        self.assertEqual(observed["status"],"success")
        self.assertEqual(len(observed["assets"]),2)
        self.assertTrue(observed["synthetic"])
        with self.assertRaisesRegex(ValueError,"synthetic_inventory_requires_test_scope"):
            engine.cycle(self.root,inventory_reader=lambda *a,**k:observed,fetcher=self.fetch,now=NOW)

    def test_inventory_failure_is_visible_without_hiding_readable_assets(self):
        result=self.run_cycle(inventory_reader=lambda *a,**k:{"collected_at":NOW,"assets":[],"status":"unknown","coverage":[]})
        self.assertEqual(result["state"],"partial")
        self.assertEqual(result["errors"][0]["source_id"],"local_inventory")

    def test_start_metadata_failure_still_finishes_own_child(self):
        child=Mock()
        child.pid=123
        child.created_at=NOW
        child.detached=False
        def write(root,name,value):
            if name in {"owner.json","control.json"} and getattr(write,"launched",False):
                raise OSError("synthetic full disk")
            if name=="control.json":
                write.launched=True
        write.launched=False
        with patch.object(service,"_read",return_value=None),patch.object(service,"_write",side_effect=write),patch.object(service.processes,"spawn_persistent",return_value=child),patch.object(service.processes,"process_session",return_value=1),patch.object(service.processes,"finish",return_value={"child_exited":True}) as finish:
            with self.assertRaises(OSError):
                service.start(self.root)
        finish.assert_called_once()

    def test_status_before_start_does_not_initialize_and_cli_is_usable(self):
        output = io.StringIO()
        with patch("eventguard.agent_budget.public_status", side_effect=AssertionError("historical budget read")), \
                redirect_stdout(output):
            self.assertEqual(main(["advisories", "status", "--format", "json"], root=self.root), 0)
        self.assertFalse(self.db.exists())
        self.assertNotIn("daily_remaining", json.loads(output.getvalue()))
        self.assertFalse((self.root / "data/advisories/control.json").exists())

    @unittest.skipUnless(os.name == "nt", "Windows private Job lifecycle only")
    def test_bounded_synthetic_background_start_status_stop_no_network(self):
        # Prime a fresh empty cache. The child has no due network request.
        source = dict(self.source, interval_seconds=86400, stale_after_seconds=172800)
        self.config["sources"] = [source]
        self.config["inventory"] = {"paths": []}
        self.path.write_text(json.dumps(self.config), encoding="utf-8")
        store = IntelligenceStore(self.db)
        store.record_fetch(source, {"status": "success", "records": [], "content_hash": "b" * 64, "retry_after_seconds": None}, engine.stamp())
        try:
            started = service.start(self.root, _bounded_test=True)
            self.assertEqual(started["state"], "started")
            time.sleep(.2)
            with patch("eventguard.agent_budget.public_status", side_effect=AssertionError("historical budget read")):
                current = service.status(self.root)
            self.assertEqual(current["host_liveness"], "alive_verified")
            self.assertFalse(current["agent_enabled"])
        finally:
            stopped = service.stop(self.root, grace_seconds=5)
        self.assertEqual(stopped["state"], "stopped")
        self.assertFalse(stopped["process"]["forcibly_terminated"])
        self.assertEqual(stopped["process"]["remaining_owned_processes"], 0)
        self.evidence = {"scope": "Windows private Job; synthetic fresh cache; no network/model",
                         "start_status_stop": True, "process": stopped["process"]}
