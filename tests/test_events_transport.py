import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from eventguard.events.schema import validate_event, EventValidationError, stable_event_id
from eventguard.events.store import EventStore, StoreError, CapacityError, MAX_STATE_BYTES
from eventguard.transport.adapters import DisabledAdapter, MockReceiverAdapter


def event(identity="evt-test-1",synthetic=True):
    return {"schema_version":"2.0","event_id":identity,"host_id":"host-test","episode_id":"ep-test",
            "correlation_id":"corr-test","sequence":1,"event_type":"listener.changed",
            "transition":"new","severity":"warning","synthetic":synthetic,
            "observed_at":"2026-10-22T00:00:00Z","persisted_at":"2026-10-22T00:00:01Z",
            "evidence":{"protocol":"TCP","port":18080,"scope":"all_interfaces"},
            "coverage":{"status":"ok","gaps":[]}}


class EventSchemaTests(unittest.TestCase):
    def test_identity_time_defaults_and_stability(self):
        clean=validate_event(event())
        self.assertEqual(clean,validate_event(clean))
        self.assertEqual(stable_event_id("x",1),stable_event_id("x",1))
        self.assertNotEqual(stable_event_id("x",1),stable_event_id("x",2))
        self.assertEqual(clean["privacy"],{"profile":"minimal-v1","redacted":True})

    def test_unknown_version_malformed_types_and_timestamps_rejected(self):
        for key,value in (("schema_version","1.0"),("synthetic","true"),("sequence",True),("severity","safe"),("observed_at","2026-10-22"),("event_id","bad id")):
            bad=event();bad[key]=value
            with self.assertRaises(EventValidationError,msg=key):validate_event(bad)

    def test_sensitive_and_unknown_fields_dropped_and_home_masked(self):
        raw=event();raw["command_line"]="secret";raw["evidence"].update(path=r"C:\Users\private\app.exe",command="secret",Message="private",password="secret",unknown="hidden")
        clean=validate_event(raw)
        serialized=json.dumps(clean)
        for value in ("command_line","Message","password","private","hidden","secret"):
            self.assertNotIn(value,serialized)
        self.assertEqual(clean["evidence"]["path"],r"%USER_HOME%\app.exe")

    def test_size_depth_and_nonfinite_limits(self):
        bad=event();bad["evidence"]={"current":["x"*512]*20}
        with self.assertRaises(EventValidationError):validate_event(bad)
        bad=event();bad["evidence"]={"current":{"current":{"current":{"current":1}}}}
        with self.assertRaises(EventValidationError):validate_event(bad)
        bad=event();bad["evidence"]={"value":float("nan")}
        with self.assertRaises(EventValidationError):validate_event(bad)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.directory=Path(self.temporary.name)

    def test_atomic_state_events_dedup_and_restart(self):
        store=EventStore(self.directory)
        first=store.commit_evaluation({"baseline":1},[event()])
        self.assertEqual(first,{"inserted":1,"duplicates":0,"state_saved":True})
        self.assertEqual(store.commit_evaluation({"baseline":2},[event()])["duplicates"],1)
        recovered=EventStore(self.directory)
        self.assertEqual(recovered.load_detector_state(),{"baseline":2})
        self.assertEqual(recovered.stats()["pending"],1)

    def test_full_queue_rolls_back_state_and_all_new_events(self):
        store=EventStore(self.directory,max_events=1)
        store.commit_evaluation({"baseline":1},[event()])
        with self.assertRaises(CapacityError):store.commit_evaluation({"baseline":2},[event("evt-two")])
        self.assertEqual(store.load_detector_state(),{"baseline":1})
        self.assertEqual([e["event_id"] for e in store.list_events()],["evt-test-1"])
        store2=EventStore(self.directory/"other",max_events=1)
        with self.assertRaises(CapacityError):store2.commit_evaluation({"baseline":2},[event(),event("evt-two")])
        self.assertIsNone(store2.load_detector_state());self.assertEqual(store2.list_events(),[])

    def test_invalid_event_does_not_commit_detector_state(self):
        store=EventStore(self.directory);bad=event();bad["sequence"]=0
        with self.assertRaises(EventValidationError):store.commit_evaluation({"changed":True},[bad])
        self.assertIsNone(store.load_detector_state())

    def test_same_identity_different_payload_is_not_silently_deduplicated(self):
        store=EventStore(self.directory,max_events=1);store.commit_evaluation({"old":1},[event()])
        conflict=event();conflict["synthetic"]=False
        with self.assertRaisesRegex(StoreError,"event_identity_conflict"):
            store.commit_evaluation({"old":2},[conflict])
        self.assertEqual(store.load_detector_state(),{"old":1})
        store.acknowledge("evt-test-1",{"event_id":"evt-test-1","ack_type":"receiver_persisted","receipt_id":"r1"})
        store.enqueue(event("evt-two"))
        with self.assertRaisesRegex(StoreError,"event_identity_conflict"):store.enqueue(conflict)

    def test_pump_reports_remaining_events_after_bounded_batch(self):
        store=EventStore(self.directory)
        store.commit_evaluation({},[event("evt-"+str(i)) for i in range(101)])
        class Receiver:
            connected=True
            def send(self,e):return {"event_id":e["event_id"],"ack_type":"receiver_persisted","receipt_id":"r-"+e["event_id"]}
        result=store.pump(Receiver())
        self.assertEqual(result["acknowledged"],100)
        self.assertEqual(result["pending"],1)
        self.assertEqual(result["remaining_pending"],1)

    def test_detector_state_limit_does_not_change_old_state(self):
        store=EventStore(self.directory);store.commit_evaluation({"old":1},[])
        with self.assertRaises(CapacityError):store.commit_evaluation({"large":"x"*MAX_STATE_BYTES},[])
        self.assertEqual(store.load_detector_state(),{"old":1})

    def test_sqlite_byte_capacity_preserves_pending_and_rotates_ack(self):
        store=EventStore(self.directory,max_bytes=65536)
        count=0
        for count in range(30):
            large=event("large-"+str(count));large["evidence"]={"current":["x"*500]*8}
            try:store.enqueue(large)
            except CapacityError:break
        else:self.fail("byte limit was not enforced")
        pending=store.stats()["pending"]
        self.assertEqual(pending,count)
        self.assertLessEqual(store.path.stat().st_size,65536)
        store.acknowledge("large-0",{"event_id":"large-0","ack_type":"receiver_persisted","receipt_id":"r0"})
        large=event("large-replacement");large["evidence"]={"current":["x"*500]*8}
        self.assertTrue(store.enqueue(large))
        self.assertEqual(store.stats()["rotated_ack"],1)
        self.assertEqual(store.stats()["pending"],pending)
        original=event("large-0");original["evidence"]={"current":["x"*500]*8}
        self.assertFalse(store.enqueue(original))

    def test_stored_payload_is_minimized_again_and_tamper_not_sent(self):
        store=EventStore(self.directory);store.enqueue(event())
        with store._connect() as db:
            raw=json.loads(db.execute("SELECT payload FROM events").fetchone()[0]);raw["command_line"]="private secret"
            db.execute("UPDATE events SET payload=?",(json.dumps(raw),))
        self.assertNotIn("private",json.dumps(store.get_event("evt-test-1")))
        with store._connect() as db:
            raw["evidence"]["port"]=9999
            db.execute("UPDATE events SET payload=?",(json.dumps(raw),))
        class Never:
            connected=True
            def send(self,event):raise AssertionError("tampered event must not be transmitted")
        result=store.pump(Never())
        self.assertEqual(result["attempted"],0)
        self.assertEqual(result["failed"],1)

    def test_unconfigured_receiver_never_attempts_or_claims_agent(self):
        store=EventStore(self.directory);store.enqueue(event())
        for _ in range(3):
            result=store.pump(DisabledAdapter())
            self.assertEqual(result["attempted"],0);self.assertFalse(result["real_agent_woken"])
        self.assertEqual(store.list_events()[0]["attempts"],0)
        self.assertEqual(store.list_events()[0]["delivery_status"],"pending")

    def test_receipt_validation_and_ack_is_not_agent_processing(self):
        store=EventStore(self.directory);store.enqueue(event())
        for receipt in ({"event_id":"evt-test-1","ack_type":"sent","receipt_id":"r1"},
                        {"event_id":"wrong","ack_type":"receiver_persisted","receipt_id":"r1"}):
            with self.assertRaises(StoreError):store.acknowledge("evt-test-1",receipt)
        self.assertEqual(store.stats()["pending"],1)
        self.assertTrue(store.acknowledge("evt-test-1",{"event_id":"evt-test-1","ack_type":"receiver_persisted","receipt_id":"r1"}))
        row=store.list_events()[0]
        self.assertEqual(row["delivery_status"],"ack");self.assertFalse(row["receipt"]["real_agent_woken"])
        self.assertEqual(store.pump(DisabledAdapter())["attempted"],0)

    def test_ack_rotates_and_receipt_still_deduplicates(self):
        store=EventStore(self.directory,max_events=1);store.enqueue(event())
        store.acknowledge("evt-test-1",{"event_id":"evt-test-1","ack_type":"receiver_persisted","receipt_id":"r1"})
        self.assertTrue(store.enqueue(event("evt-two")))
        self.assertFalse(store.enqueue(event()))
        self.assertEqual(store.stats()["rotated_ack"],1)
        self.assertEqual(store.stats()["pending"],1)

    def test_retry_backoff_then_ack_and_no_redelivery(self):
        store=EventStore(self.directory);store.enqueue(event());now=time.time()
        class Adapter:
            connected=True
            def __init__(self):self.calls=0
            def send(self,e):
                self.calls+=1
                if self.calls==1:raise OSError("private diagnostic must not be stored")
                return {"event_id":e["event_id"],"ack_type":"receiver_persisted","receipt_id":"receipt-test"}
        adapter=Adapter()
        self.assertEqual(store.pump(adapter,now)["retry"],1)
        due=store.list_events()[0]["next_retry_at"]
        self.assertGreaterEqual(due-now,24);self.assertLessEqual(due-now,36)
        self.assertEqual(store.pump(adapter,due-0.1)["attempted"],0)
        self.assertEqual(EventStore(self.directory).pump(adapter,due+1)["acknowledged"],1)
        self.assertEqual(store.pump(adapter,due+1000)["attempted"],0)
        self.assertEqual(adapter.calls,2)
        self.assertNotIn("private",json.dumps(store.list_events()))

    def test_eighth_crashed_attempt_becomes_uncertain_failed(self):
        store=EventStore(self.directory);store.enqueue(event());now=time.time()
        with store._connect() as db:
            db.execute("UPDATE events SET delivery_status='retry',attempts=8,lease_until=?,next_retry_at=?",(now-1,now-1))
        result=EventStore(self.directory).pump(DisabledAdapter(),now)
        self.assertEqual(result["failed"],1)
        row=store.list_events()[0]
        self.assertEqual(row["delivery_status"],"failed")
        self.assertEqual(row["delivery_reason"],"last_attempt_uncertain")

    def test_retry_limit_and_explicit_replay(self):
        store=EventStore(self.directory);store.enqueue(event());now=time.time()
        class Failing:
            connected=True
            def send(self,event):return {"ack":False,"retryable":True}
        for attempt in range(8):
            result=store.pump(Failing(),now)
            row=store.list_events()[0]
            if row["next_retry_at"]:now=row["next_retry_at"]+1
        self.assertEqual(row["attempts"],8);self.assertEqual(row["delivery_status"],"failed")
        self.assertTrue(store.retry_failed("evt-test-1"))
        self.assertEqual(store.list_events()[0]["attempts"],0)

    def test_expired_dedup_window_does_not_automatically_replay(self):
        store=EventStore(self.directory);store.enqueue(event());now=time.time()
        with store._connect() as db:db.execute("UPDATE events SET created_at=?",(now-31*86400,))
        class Never:
            connected=True
            def send(self,event):raise AssertionError("old event must not transmit")
        self.assertEqual(store.pump(Never(),now)["attempted"],0)
        self.assertEqual(store.list_events()[0]["delivery_reason"],"dedup_window_expired")
        with self.assertRaises(StoreError):store.retry_failed("evt-test-1")

    def test_cross_instance_lease_avoids_double_send(self):
        first=EventStore(self.directory);second=EventStore(self.directory);first.enqueue(event());calls=[]
        class Adapter:
            connected=True
            def send(self,e):
                calls.append(e["event_id"])
                self.result=second.pump(self)
                return {"ack_type":"receiver_persisted","event_id":e["event_id"],"receipt_id":"r1"}
        adapter=Adapter();first.pump(adapter)
        self.assertEqual(calls,["evt-test-1"]);self.assertEqual(adapter.result["attempted"],0)


class MockReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.directory=Path(self.temporary.name)

    def test_receiver_ack_then_mock_diagnostic_closure_only(self):
        store=EventStore(self.directory);receiver=MockReceiverAdapter(self.directory)
        store.enqueue(event());result=store.pump(receiver)
        self.assertEqual(result["acknowledged"],1);self.assertFalse(result["real_agent_woken"])
        self.assertEqual(receiver.status()["mock_processed"],0)
        calls=[]
        def diagnose(e):
            calls.append(e["event_id"])
            return {"status":"ok","mock":True,"rows":[{"port":18080,"command_line":"secret"}]}
        case=receiver.process_mock("evt-test-1",diagnose)
        self.assertEqual(case["case_state"],"mock_closed");self.assertTrue(case["mock_processed"])
        self.assertFalse(case["agent_started"]);self.assertFalse(case["agent_processed"])
        self.assertEqual(case["actions_executed"],[])
        self.assertNotIn("secret",json.dumps(case))
        recovered=MockReceiverAdapter(self.directory)
        self.assertEqual(recovered.process_mock("evt-test-1",diagnose),case)
        self.assertEqual(calls,["evt-test-1"])
        self.assertEqual(recovered.status()["mock_closed"],1)

    def test_real_event_rejected_not_acknowledged(self):
        receiver=MockReceiverAdapter(self.directory)
        self.assertFalse(receiver.send(event(synthetic=False))["ack"])
        self.assertEqual(receiver.status()["receiver_accepted"],0)
        with self.assertRaises(StoreError):receiver.process_mock("evt-test-1",lambda _: {"status":"ok"})

    def test_ack_loss_receiver_restart_and_duplicate_receipt(self):
        receiver=MockReceiverAdapter(self.directory);first=receiver.send(event())
        recovered=MockReceiverAdapter(self.directory)
        self.assertEqual(first,recovered.send(event()))
        self.assertEqual(recovered.status()["receiver_accepted"],1)
        self.assertFalse(first["real_agent_woken"])

    def test_mock_receiver_rejects_identity_payload_conflict(self):
        receiver=MockReceiverAdapter(self.directory);receiver.send(event())
        conflict=event();conflict["transition"]="resolved"
        with self.assertRaisesRegex(StoreError,"event_identity_conflict"):receiver.send(conflict)

    def test_diagnostic_error_remains_needs_evidence(self):
        receiver=MockReceiverAdapter(self.directory);receiver.send(event())
        def bad(_):raise OSError("private exception")
        result=receiver.process_mock("evt-test-1",bad)
        self.assertEqual(result["case_state"],"mock_needs_evidence")
        self.assertNotIn("private",json.dumps(result))

    def test_mock_receiver_capacity_keeps_existing_receipt(self):
        receiver=MockReceiverAdapter(self.directory,max_events=1);receipt=receiver.send(event())
        with self.assertRaises(CapacityError):receiver.send(event("evt-two"))
        self.assertEqual(receiver.get_receipt("evt-test-1"),receipt)


if __name__=="__main__":unittest.main()
