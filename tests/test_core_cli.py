"""Headless lifecycle and CLI integration; synthetic fixtures only."""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/"src"))
from eventguard.cli import main,export_report
from eventguard.runtime import Runtime,InstanceLock,atomic_json,safe_child
from eventguard.monitor import Monitor
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for relative in ("config/default.json","playbooks/default.json","tests/fixtures/normal.json"):
            destination=self.root/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(BASE/relative,destination)

    def command(self,*args):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=main(list(args),root=self.root)
        return code,json.loads(output.getvalue())

    def test_readonly_capabilities_and_empty_status(self):
        code,value=self.command("capabilities")
        self.assertEqual(code,0)
        self.assertEqual(value["model_calls"],0)
        self.assertFalse(value["gui"])
        self.assertFalse((self.root/"data").exists())
        code,value=self.command("status")
        self.assertEqual(code,0)
        self.assertEqual(value["agent_ingress"],"not_configured")
        self.assertFalse((self.root/"data").exists())

    def test_normal_fixture_zero_events_no_live_data(self):
        monitor=Monitor(self.root)
        result=monitor.run(max_cycles=2,fixture="tests/fixtures/normal.json",fixture_interval=.05)
        self.assertEqual(result["cycles"],2)
        self.assertEqual(result["state"],"stopped")
        self.assertTrue(result["healthy"])
        self.assertFalse(result["monitoring"])
        self.assertEqual(result["outbox"]["total"],0)
        self.assertEqual(result["model_calls"],0)
        self.assertFalse((self.root/"data/live").exists())
        self.assertFalse((self.root/"data/monitor-owner.json").exists())

    def test_synthetic_receiver_ack_diagnosis_case_and_restart(self):
        code,event=self.command("synthetic","emit","--scenario","listener")
        self.assertEqual(code,0)
        event_id=event["event_id"]
        code,result=self.command("deliver","--adapter","mock")
        self.assertEqual(code,0)
        self.assertEqual(result["delivery"]["acknowledged"],1)
        self.assertFalse(result["real_agent_woken"])
        code,result=self.command("mock","process","--event-id",event_id)
        self.assertEqual(code,0)
        self.assertTrue(result["mock_processed"])
        self.assertFalse(result["agent_started"])
        self.assertFalse(result["agent_processed"])
        self.assertEqual(result["case_state"],"mock_closed")
        code,repeated=self.command("mock","process","--event-id",event_id)
        self.assertEqual(repeated["case_id"],result["case_id"])
        code,replay=self.command("deliver","--adapter","mock")
        self.assertEqual(replay["delivery"]["attempted"],0)
        code,rows=self.command("events","list","--namespace","test")
        self.assertEqual(rows["events"][0]["delivery_status"],"ack")
        code,plan=self.command("playbook","simulate","--event-id",event_id,"--namespace","test")
        self.assertEqual(code,0)
        self.assertEqual(plan["status"],"planned")
        self.assertFalse(plan["authorization_granted"])
        self.assertEqual(plan["actions_executed"],[])
        self.assertFalse((self.root/"data/live").exists())

    def test_mock_refuses_live_namespace(self):
        code,result=self.command("deliver","--adapter","mock","--namespace","live")
        self.assertEqual(code,2)
        self.assertFalse((self.root/"data").exists())

    def test_disabled_adapter_does_not_consume_attempts(self):
        self.command("synthetic","emit")
        code,result=self.command("deliver","--adapter","disabled","--namespace","test")
        self.assertEqual(code,0)
        self.assertEqual(result["delivery"]["attempted"],0)
        rows=EventStore(self.root/"data/test").list_events()
        self.assertEqual(rows[0]["attempts"],0)

    def test_singleton_stop_and_old_stop_is_ignored(self):
        runtime=Runtime(self.root)
        first,second=InstanceLock(runtime),InstanceLock(runtime)
        self.assertTrue(first.acquire())
        self.addCleanup(first.release)
        self.assertFalse(second.acquire())
        result=runtime.request_stop()
        self.assertEqual(result["instance_id"],first.instance_id)
        self.assertTrue(first.stop_requested())
        first.release()
        self.assertTrue(second.acquire())
        self.addCleanup(second.release)
        self.assertFalse(second.stop_requested())

    def test_cooperative_monitor_thread_stops_without_process_signals(self):
        monitor=Monitor(self.root)
        results=[]
        thread=threading.Thread(target=lambda:results.append(monitor.run(max_cycles=100,fixture="tests/fixtures/normal.json",fixture_interval=.05)))
        thread.start()
        try:
            deadline=time.monotonic()+3
            while not (self.root/"data/monitor-owner.json").exists() and time.monotonic()<deadline:
                time.sleep(.01)
            runtime=Runtime(self.root)
            self.assertEqual(runtime.request_stop()["status"],"stop_requested")
        finally:
            monitor.cancel.set()
            thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertFalse((self.root/"data/monitor-owner.json").exists())
        self.assertFalse(results[0]["monitoring"])

    def test_queue_full_does_not_advance_baseline(self):
        config=json.loads((self.root/"config/default.json").read_text(encoding="utf-8"))
        config["outbox"]["max_events"]=1
        atomic_json(self.root/"config/default.json",config)
        store=EventStore(self.root/"data/test",max_events=1)
        store.enqueue(make_synthetic())
        fixture=json.loads((self.root/"tests/fixtures/normal.json").read_text(encoding="utf-8"))
        fixture["sections"][0]["rows"][1]["value"]=False
        atomic_json(self.root/"tests/fixtures/failure.json",fixture)
        result=Monitor(self.root).run(max_cycles=1,fixture="tests/fixtures/failure.json")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["last_error"],"queue_capacity_or_storage_failure")
        self.assertIsNone(store.load_detector_state())
        self.assertEqual(store.stats()["pending"],1)

    def test_slow_coverage_failure_not_masked_by_fast_round(self):
        fixture=json.loads((self.root/"tests/fixtures/normal.json").read_text(encoding="utf-8"))
        fixture["sections"][5]["status"]="denied"
        fixture["sections"][5]["coverage"]={"status":"denied"}
        nextframe={"sections":fixture["sections"][:3]}
        atomic_json(self.root/"tests/fixtures/mixed.json",{"frames":[fixture,nextframe]})
        result=Monitor(self.root).run(max_cycles=2,fixture="tests/fixtures/mixed.json",fixture_interval=.05)
        self.assertFalse(result["healthy"])
        self.assertEqual(result["coverage"]["tasks"]["status"],"denied")
        self.assertIsNone(result["last_success"])

    def test_invalid_config_and_fixture_path_never_collect(self):
        with self.assertRaises(ValueError):
            Monitor(self.root).run(max_cycles=1,fixture="../private.json")
        with self.assertRaises(ValueError):
            Monitor(self.root).run(fixture="tests/fixtures/normal.json")
        with self.assertRaises(ValueError):
            safe_child(self.root,"../other")
        code,result=self.command("query","query_listener","--args",'{"command":"MUST_NOT_RUN"}')
        self.assertEqual(code,2)
        self.assertEqual(result["error_code"],"invalid_request")

    def test_owner_write_failure_releases_os_lock(self):
        runtime=Runtime(self.root)
        first=InstanceLock(runtime)
        with patch("eventguard.runtime.atomic_json",side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                first.acquire()
        self.assertIsNone(first.stream)
        second=InstanceLock(runtime)
        self.assertTrue(second.acquire())
        second.release()

    def test_health_write_failure_releases_singleton(self):
        monitor=Monitor(self.root)
        with patch.object(monitor.runtime,"save_health",side_effect=OSError("synthetic disk full")):
            with self.assertRaises(OSError):
                monitor.run(max_cycles=1,fixture="tests/fixtures/normal.json")
        lock=InstanceLock(Runtime(self.root))
        self.assertTrue(lock.acquire())
        lock.release()

    def test_round_budget_skip_retries_soon_not_six_hours(self):
        tick=[100.0]
        class Collectors:
            def collect(self,key,cancel=None):
                tick[0]+=50
                return {"id":key,"status":"ok","rows":[],"observed_at":"2026-10-22T00:00:00Z"}
        monitor=Monitor(self.root,collectors=Collectors(),clock=lambda:tick[0])
        result=monitor.run(max_cycles=1)
        self.assertNotIn("versions",monitor.last)
        self.assertEqual(monitor.not_before["versions"],180.0)
        self.assertEqual(result["coverage"]["versions"]["status"],"busy")

    def test_pending_query_keeps_singleton_until_natural_exit(self):
        class Runner:
            pending=False
        class Collectors:
            runner=Runner()
        collector=Collectors()
        monitor=Monitor(self.root,collectors=collector)
        results=[]
        thread=threading.Thread(target=lambda:results.append(monitor.run(max_cycles=1,fixture="tests/fixtures/normal.json",on_cycle=lambda _:setattr(collector.runner,"pending",True))))
        thread.start()
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                try:
                    if Runtime(self.root).health().get("state")=="stopping_pending_query":
                        break
                except (OSError,ValueError):
                    pass
                time.sleep(.01)
            second=InstanceLock(Runtime(self.root))
            self.assertFalse(second.acquire())
        finally:
            collector.runner.pending=False
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]["state"],"stopped")

    def test_duration_limit_stops_new_queries_and_commits_finished_observation(self):
        tick=[100.0]
        calls=[]
        class Collectors:
            def collect(self,key,cancel=None):
                calls.append(key)
                tick[0]+=2
                return {"id":key,"status":"denied","rows":[],"observed_at":"2026-10-22T00:00:00Z"}
        result=Monitor(self.root,collectors=Collectors(),clock=lambda:tick[0]).run(max_seconds=1)
        self.assertEqual(calls,["defender"])
        self.assertEqual(result["stop_reason"],"duration_limit")
        self.assertEqual(result["state"],"stopped")
        self.assertEqual(result["coverage"]["defender"]["status"],"denied")
        self.assertGreaterEqual(EventStore(self.root/"data/live").stats()["pending"],1)
        for invalid in (True,0,-1,float('nan'),float('inf'),3601):
            with self.assertRaisesRegex(ValueError,"invalid_max_seconds"):
                Monitor(self.root).run(max_seconds=invalid)

    def test_html_export_escapes_and_does_not_overwrite(self):
        event=make_synthetic()
        event["inference"]["summary"]="<script>alert('x')</script> &"
        EventStore(self.root/"data/test").enqueue(event)
        first=export_report(Runtime(self.root),"test")
        second=export_report(Runtime(self.root),"test")
        self.assertNotEqual(first["json"],second["json"])
        body=Path(first["html"]).read_text(encoding="utf-8")
        self.assertNotIn("<script>alert",body)
        self.assertIn("&lt;script&gt;",body)


if __name__=="__main__":
    unittest.main()
