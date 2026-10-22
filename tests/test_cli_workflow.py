"""Whole human CLI flow and inert presentation; written before unified testing."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from eventguard.cli import main
from eventguard.events.store import EventStore
from eventguard.operations import OperatorAPI
from eventguard.presentation import render, text, ProgressPrinter
from eventguard.runtime import Runtime
from eventguard.synthetic import make_synthetic

ROOT=Path(__file__).resolve().parents[1]


class CliWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for relative in ("config/default.json","playbooks/default.json","tests/fixtures/normal.json"):
            target=self.root/relative; target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/relative,target)
        self.enterContext(patch("eventguard.operations._budget_status",return_value={"state":"blocked","reason":"fixture_not_initialized"}))

    def call(self,*args):
        out,err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            code=main(list(args),root=self.root)
        return code,out.getvalue(),err.getvalue()

    def test_json_monitor_is_single_document_and_saved_sources_are_visible(self):
        code,out,err=self.call("monitor","--format","json","--fixture","tests/fixtures/normal.json","--max-cycles","1")
        self.assertEqual(code,0,out)
        health=json.loads(out)
        self.assertEqual(health["state"],"stopped")
        self.assertEqual(health["model_calls"],0)
        self.assertEqual(err,"")
        code,out,_=self.call("sources","show","--source-id","listeners","--namespace","test")
        self.assertEqual(code,0)
        source=json.loads(out)
        self.assertEqual(source["status"],"ok")
        self.assertEqual(source["row_count"],0)
        self.assertFalse(source["system_query_executed"])

    def test_text_monitor_reports_progress_and_reuses_saved_data(self):
        code,out,progress=self.call("--format","text","monitor","--fixture","tests/fixtures/normal.json","--max-cycles","1")
        self.assertEqual(code,0,out)
        self.assertIn("監看結果",out)
        self.assertIn("資料筆數",progress)
        self.assertIn("監聽端點",progress)
        code,out,_=self.call("sources","list","--namespace","test","--format=text")
        self.assertEqual(code,0)
        self.assertIn("保存來源",out)
        self.assertIn("test",out)

    def test_event_receive_explicit_ack_and_report_work_without_agent(self):
        event=make_synthetic("listener")
        store=EventStore(self.root/"data/test")
        store.enqueue(event)
        event_id=event["event_id"]
        code,out,_=self.call("events","inspect","--namespace","test","--event-id",event_id)
        self.assertEqual(code,0)
        inspected=json.loads(out)
        self.assertEqual(inspected["event"]["event_id"],event_id)
        self.assertIn("guidance",inspected)
        code,out,_=self.call("events","receive","--namespace","test","--event-id",event_id)
        self.assertEqual(code,0,out)
        received=json.loads(out)
        self.assertEqual(received["event_id"],event_id)
        self.assertEqual(store.get_event(event_id)["delivery_status"],"pending")
        query_id=received["query_id"]
        human=render(received,"events","receive")
        self.assertIn(query_id,human)
        self.assertIn("events ack",human)
        self.assertIn("--namespace test",human)
        code,out,_=self.call("events","ack","--namespace","test","--event-id",event_id,"--query-id",query_id)
        self.assertEqual(code,0,out)
        self.assertTrue(json.loads(out)["outbox_acknowledged"])
        self.assertEqual(store.get_event(event_id)["delivery_status"],"ack")
        code,out,_=self.call("report","export","--namespace","test")
        self.assertEqual(code,0,out)
        report=json.loads(out)
        self.assertEqual(report["total"],1)
        self.assertTrue(Path(report["html"]).is_file())
        self.assertFalse((self.root/"data/live").exists())

    def test_wrong_query_is_failure_not_success_and_pending_survives(self):
        event=make_synthetic("listener"); store=EventStore(self.root/"data/test"); store.enqueue(event)
        self.call("events","receive","--namespace","test","--event-id",event["event_id"])
        code,out,_=self.call("events","ack","--namespace","test","--event-id",event["event_id"],"--query-id","wrong-query")
        self.assertNotEqual(code,0)
        self.assertEqual(json.loads(out)["status"],"blocked")
        self.assertEqual(store.get_event(event["event_id"])["delivery_status"],"pending")

    def test_overview_text_and_json_are_two_views_of_one_api(self):
        api=OperatorAPI(self.root)
        code,out,_=self.call("overview","--namespace","test","--format","json")
        self.assertEqual(code,0,out)
        result=json.loads(out)
        self.assertEqual(result["namespace"],"test")
        self.assertEqual(result,api.overview("test"))
        code,human,_=self.call("overview","--namespace","test","--format","text")
        self.assertEqual(code,0)
        self.assertIn("操作總覽",human)
        self.assertFalse((self.root/"data").exists())

    def test_text_controls_and_bidi_never_become_terminal_instructions(self):
        hostile="name\x1b[2J\r\n\u202erun-command"
        shown=text(hostile)
        self.assertNotIn("\x1b",shown)
        self.assertNotIn("\r",shown)
        self.assertNotIn("\u202e",shown)
        self.assertIn("\\u001b",shown)
        output=render({"source_id":"tasks","status":"partial","row_count":1,"exported":1,
                       "rows":[{"display_name":hostile}],"truncated":False},"sources","show")
        self.assertNotIn("\x1b",output)
        self.assertNotIn("\u202e",output)

    def test_text_never_calls_other_namespace_or_stale_observation_current(self):
        output=render({"namespace":"live","monitor_namespace":"test",
                       "current_monitor":{"state":"running_verified","scope_matches":False},
                       "source_coverage":{},"event_list":{}},"overview")
        self.assertIn("另一空間",output)
        output=render({"source_id":"listeners","status":"ok","current_coverage":"unknown",
                       "freshness":{"state":"stale"},"rows":[]},"sources","show")
        self.assertIn("過期",output)
        self.assertIn("目前可見性：未知",output)

    def test_progress_waiting_is_rate_limited_without_hiding_source_completion(self):
        out=io.StringIO(); now=[0]
        printer=ProgressPrinter(out,clock=lambda:now[0])
        health={"progress":{"phase":"source_waiting","source_id":"tasks","cycle":1,"elapsed_ms":100},"coverage":{}}
        printer(health); printer(health)
        self.assertEqual(len(out.getvalue().splitlines()),1)
        now[0]=6; printer(health)
        health["progress"]["phase"]="source_completed"; printer(health)
        self.assertEqual(len(out.getvalue().splitlines()),3)
