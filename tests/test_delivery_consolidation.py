"""QueueInbox/legacy equivalence and owned fake CLI; never real agent proof."""
import asyncio
import ast
from copy import deepcopy
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from eventguard import delivery_validation as validation
from eventguard.agent_dispatch import command, assess_delivery
from eventguard.events.store import EventStore
from eventguard.local_wait import LocalWait
from eventguard.queue_inbox import QueueInbox
from eventguard.processes import spawn, finish
from eventguard.synthetic import make_synthetic
from test_agent_dispatch import trace_fixture, RECORD
from budget_fixtures import isolated_launch

ROOT = Path(__file__).resolve().parents[1]
FAKE = '''import json,sys
sys.path.insert(0,sys.argv[4])
from eventguard.queue_inbox import QueueInbox
backend=QueueInbox(sys.argv[1],sys.argv[2],event_id=sys.argv[3])
def reply(tool,args,value):
 print(json.dumps({'type':'item.completed','item':{'id':'fake-'+tool,'type':'mcp_tool_call','server':'eventguard_inbox','tool':tool,'status':'completed','error':None,'arguments':args,'result':{'content':[{'type':'text','text':json.dumps(value)}]}}}),flush=True)
item=backend.receive_event(); identity=item['event_id']; reply('receive_event',{},item)
query=backend.query_evidence(identity); reply('query_evidence',{'event_id':identity},query)
if sys.argv[5]=='fail':
 print(json.dumps({'type':'turn.failed'}),flush=True); raise SystemExit(7)
if sys.argv[5]!='read':
 args={'event_id':identity,'query_id':query['query_id'],'decision':'reviewed_metadata'}
 reply('ack_event',args,backend.ack_event(**args))
print(json.dumps({'type':'turn.completed'}),flush=True)
'''


class ConsolidationTests(unittest.TestCase):
    def test_legacy_and_queue_have_equal_delivery_identity_and_ack_semantics(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            old = LocalWait(base / "legacy")
            store = EventStore(base / "source")
            for scenario in ("listener", "defender", "startup", "coverage"):
                event = make_synthetic(scenario)
                identity = event["event_id"]
                old.store.enqueue(event)
                store.enqueue(event)
                inbox = QueueInbox(base / "source", base / "inbox", event_id=identity)
                received = [asyncio.run(old.wait_for_event(1)), inbox.receive_event()]
                queried = [old.query_evidence(identity), inbox.query_evidence(identity)]
                self.assertEqual({r["event_id"] for r in received + queried}, {identity})
                for backend in (old, inbox):
                    query = backend.query_evidence(identity)
                    self.assertEqual(backend.query_evidence(identity)["query_id"], query["query_id"])
                # Both sources remain pending until ACK; data projections/decisions differ deliberately.
                self.assertEqual(old.store.get_event(identity)["delivery_status"], "pending")
                self.assertEqual(store.get_event(identity)["delivery_status"], "pending")
                old.ack_event(identity, queried[0]["query_id"], "reviewed_synthetic")
                inbox.ack_event(identity, queried[1]["query_id"], "reviewed_metadata")
                old.ack_event(identity, queried[0]["query_id"], "reviewed_synthetic")
                inbox.ack_event(identity, queried[1]["query_id"], "reviewed_metadata")
                self.assertEqual(old.store.get_event(identity)["delivery_status"], "ack")
                self.assertEqual(store.get_event(identity)["delivery_status"], "ack")
            for source in (old.directory / "outbox", base / "source"):
                with closing(sqlite3.connect((source / "eventguard.sqlite3").as_uri()+"?mode=ro", uri=True)) as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 4)

    def test_read_stage_omits_ack_and_rejects_trace_with_ack(self):
        args = command("codex.exe", "python.exe", Path("s"), Path("i"), "synthetic-id", Path("e"), allow_ack=False)
        config = tomllib.loads(next(v for v in args if v.startswith("mcp_servers.")))["mcp_servers"]["eventguard_inbox"]
        self.assertEqual(config["enabled_tools"], ["receive_event", "query_evidence"])
        self.assertIn("--read-only", config["args"])
        self.assertNotIn("ack_event", config["tools"])
        record = deepcopy(RECORD); record.pop("result")
        trace = trace_fixture(); read_trace = trace[:2] + trace[-1:]
        self.assertTrue(assess_delivery(read_trace, record, record["event_id"], 0, False, require_ack=False)["passed"])
        self.assertFalse(assess_delivery(trace, RECORD, record["event_id"], 0, True, require_ack=False)["passed"])

    def test_all_cases_use_real_sqlite_with_explicit_fake_cli_and_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); fake = base / "fake.py"; fake.write_text(FAKE, encoding="utf-8")
            def fake_command(codex, python, source, state, identity, evidence, *, allow_ack=True):
                return [sys.executable, "-B", str(fake), str(source), str(state), identity, str(ROOT / "src"), "ack" if allow_ack else "read"]
            cases = []
            with patch.object(validation, "command", side_effect=fake_command), patch.object(validation.shutil, "which", return_value=sys.executable), patch.object(validation.importlib.util, "find_spec", return_value=True):
                # These four cases use the finite stage/capture adapter. The
                # service case has separate service-driver mocks and raw proof
                # replay tests; a stage-only fake must never start its host.
                for case in ("single", "continuous", "batch", "recovery"):
                    root = base / case; manifest = validation.prepare(root, case)
                    with isolated_launch(base / ("launch-" + case)):
                        proof = validation.execute(root, manifest, sys.executable)
                    self.assertTrue(proof["passed"], proof)
                    self.assertEqual(proof["missing"], [])
                    self.assertEqual(proof["duplicates"], [])
                    self.assertTrue(all(r["child_exited"] and not r["forcibly_terminated"] for r in proof["per_stage"]))
                    self.assertEqual(validation.verify(root, manifest)["passed"], True)
                    if case == "recovery":
                        self.assertTrue(proof["recovered_same_event_and_query"])
                        pending = json.loads((root / "pending-proof.json").read_text())
                        self.assertEqual(pending["delivery_status"], "pending")
                    cases.append({"case": case, "event_count": len(proof["generated"]), "passed": True})
                self.evidence = {"scope": "fake CLI + actual local SQLite; no real agent", "cases": cases}

    def test_failed_cli_keeps_event_and_refuses_silent_rerun(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); root = base / "run"; fake = base / "fake.py"; fake.write_text(FAKE, encoding="utf-8")
            manifest = validation.prepare(root, "single")
            def fake_command(codex, python, source, state, identity, evidence, **kwargs):
                return [sys.executable, "-B", str(fake), str(source), str(state), identity, str(ROOT / "src"), "fail"]
            with isolated_launch(base / "launch"), patch.object(validation, "command", side_effect=fake_command), patch.object(validation.shutil, "which", return_value=sys.executable), patch.object(validation.importlib.util, "find_spec", return_value=True):
                with self.assertRaisesRegex(ValueError, "stage_failed"):
                    validation.execute(root, manifest, sys.executable)
                self.assertEqual(EventStore(root / "source").get_event(manifest["events"][0]["event_id"])["delivery_status"], "pending")
                with self.assertRaisesRegex(ValueError, "existing_execution_refused"):
                    validation.execute(root, manifest, sys.executable)

    def test_preparation_and_missing_verify_never_call_capture(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(validation, "capture") as capture:
            root = Path(temporary) / "run"
            self.assertEqual(validation.main(["single", "--root", str(root)]), 0)
            self.assertEqual(validation.main(["single", "--root", str(root / "absent"), "--verify-only"]), 2)
            self.assertFalse((root / "absent").exists())
            capture.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "optional installed MCP SDK")
    def test_readonly_sdk_profile_never_advertises_or_accepts_ack(self):
        spec = importlib.util.spec_from_file_location("phase5_stdio", ROOT / "scripts/eventguard_inbox_mcp.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); event = make_synthetic("listener")
            EventStore(base / "source").enqueue(event)
            server = module.build_server(base / "source", base / "state", event["event_id"], allow_ack=False)
            async def check():
                tools = await server.list_tools()
                self.assertEqual({tool.name for tool in tools}, {"receive_event", "query_evidence"})
                with self.assertRaises(ValueError):
                    await server.call_tool("ack_event", {})
            asyncio.run(check())

    def test_native_wrapper_and_missing_sdk_fail_before_enqueuing(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(validation, "capture") as capture:
            root = Path(temporary) / "run"; manifest = validation.prepare(root, "single")
            for executable in ("codex.cmd", "codex.bat", "codex.ps1"):
                with patch.object(validation.shutil, "which", return_value=executable), self.assertRaisesRegex(ValueError, "native_codex_required"):
                    validation.execute(root, manifest, executable)
            with patch.object(validation.shutil, "which", return_value=sys.executable), patch.object(validation.importlib.util, "find_spec", return_value=None), self.assertRaisesRegex(ValueError, "existing_mcp_sdk_required"):
                validation.execute(root, manifest, sys.executable)
            self.assertEqual(manifest["enqueued"], [])
            capture.assert_not_called()

    def test_core_imports_without_bridge_localwait_or_sdk(self):
        code = '''import sys
class Block:
 def find_spec(self,name,*args):
  if name=='mcp' or name.startswith(('mcp.','contrib.','eventguard.mcp','eventguard.local_wait')): raise ImportError('optional dependency blocked')
sys.meta_path.insert(0,Block())
from eventguard.operations import OperatorAPI
from eventguard.agent_dispatch import command
from eventguard.delivery_validation import prepare
print('core_imports_ok')
'''
        child = spawn([sys.executable, "-B", "-c", code], env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, stderr)
            self.assertIn(b"core_imports_ok", stdout)
        finally:
            self.assertFalse(finish(child, "test_teardown", grace=.1)["forcibly_terminated"])

    @unittest.skipUnless(os.name == "nt", "Windows command wrapper")
    def test_cmd_wrapper_checks_existing_python_without_starting_monitor(self):
        child = spawn([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "scripts\\run-python.cmd", "--version"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, stderr)
            self.assertIn(b"Python 3.13.", stdout)
        finally:
            self.assertFalse(finish(child, "test_teardown", grace=.1)["forcibly_terminated"])
