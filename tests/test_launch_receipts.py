"""Production dispatcher rejects contradictory saved fixture receipts, no child."""
from copy import deepcopy
from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
import sys
import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from eventguard.acceptance_control import write_json
from eventguard.agent_dispatch import KIND, _receipt, _complete
from eventguard.delivery_validation import verify_stage
from test_agent_dispatch import FakeInbox, trace_fixture, EVENT
from test_capture_receipt import fixture
from budget_fixtures import isolated_budget, reserve_capture
from eventguard.acceptance_process import capture


class LaunchReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = {"event_id": EVENT, "attempt_id": "a"*32, "run_id": "b"*32,
                       "run_dir": str(self.root), "state": "started"}
        marker = {"kind": KIND, "run_id": self.record["run_id"]}
        write_json(self.root/"dispatch.json", marker)
        write_json(self.root/"status.json", marker)
        self.directory = self.root/"attempts"/self.record["attempt_id"]
        self.directory.mkdir(parents=True)
        self.backend = FakeInbox(self.root/"state")

    def save(self, receipt, started):
        write_json(self.directory/"capture-start.json", started)
        write_json(self.directory/"capture-exit.json", receipt)
        (self.directory/"codex.jsonl").write_text(
            "\n".join(json.dumps(row) for row in trace_fixture()), encoding="utf-8")

    def test_dispatcher_never_promotes_contradictory_receipt_to_exit_or_pass(self):
        for mutation in (lambda r,s:r.update(child_exited=False),
                         lambda r,s:r["process"].update(remaining_owned_processes=7),
                         lambda r,s:r["process"].update(remaining_owned_processes=None),
                         lambda r,s:r["process"].update(created_at="2026-10-23T00:00:00+00:00"),
                         lambda r,s:s.update(codex_pid=99),
                         lambda r,s:r.pop("process")):
            receipt, started = fixture()
            mutation(receipt, started)
            with self.subTest(receipt=receipt):
                self.save(receipt, started)
                self.assertIsNone(_receipt(self.record))
                record = deepcopy(self.record)
                summary = _complete(record, self.backend, receipt)
                self.assertFalse(summary["passed"])
                self.assertFalse(summary["child_exited"])
                self.assertFalse(record["child_exited"])
                self.assertEqual(record["state"], "started")

    def test_known_forced_or_truncated_exit_is_never_natural_delivery(self):
        for key in ("forcibly_terminated", "stdout_truncated", "stderr_truncated"):
            receipt, started = fixture()
            receipt[key] = True
            self.save(receipt, started)
            self.assertIsNotNone(_receipt(self.record), "known exit remains distinct from success")
            summary = _complete(deepcopy(self.record), self.backend, receipt)
            self.assertTrue(summary["child_exited"])
            self.assertFalse(summary["passed"])

    def test_acceptance_uses_same_strict_policy_before_tool_or_store_assessment(self):
        receipt, started = fixture()
        directory = self.root/"stage-1"; directory.mkdir()
        row = {"name":"stage-1", "attempt_id":"a"*32, "event_id":EVENT, "read_only":False}
        for mutation in (lambda r:r.update(child_exited=False),
                         lambda r:r["process"].update(remaining_owned_processes=7),
                         lambda r:r.update(forcibly_terminated=True),
                         lambda r:r["process"].update(created_at="2026-10-23T00:00:00+00:00")):
            changed = deepcopy(receipt); mutation(changed)
            write_json(directory/"capture-start.json", started)
            write_json(directory/"capture-exit.json", changed)
            with self.assertRaisesRegex(ValueError, "complete_natural_cli_exit_required"):
                verify_stage(self.root, row)

    def test_stop_after_intent_before_os_create_is_owned_abort_without_refund(self):
        directory=self.root/"abort"; directory.mkdir()
        args=[sys.executable,"-B","-c","raise SystemExit(99)"]
        token="c"*32
        with isolated_budget(self.root/"budget") as authority:
            reserve_capture(authority,args,directory,token,"fixture")
            with patch("eventguard.acceptance_process.spawn") as spawn, \
                    patch("eventguard.acceptance_process.time.monotonic",return_value=1):
                gates=iter((True,False))
                self.assertEqual(capture(args,directory,token,"fixture",start_allowed=lambda:next(gates)),4)
                spawn.assert_not_called()
            self.assertEqual(authority.status()["used"],1)
            self.assertIsNone(authority.status()["active"])
            self.assertEqual(authority.admission(token)["state"],"not_started")
            self.assertFalse((directory/"capture-start.json").exists())
            self.assertFalse((directory/"capture-exit.json").exists())

    def test_midnight_before_launch_records_known_skip_and_next_day_can_reserve(self):
        directory=self.root/"midnight"; directory.mkdir()
        args=[sys.executable,"-B","-c","raise SystemExit(99)"]
        token="d"*32
        with isolated_budget(self.root/"budget") as authority:
            # Keep initialization real-time, then choose the same day's last
            # second; this is a labelled fake clock, never the system clock.
            current=datetime.now(timezone.utc)
            local=current.astimezone(timezone(timedelta(hours=8)))
            before=local.replace(hour=23,minute=59,second=59,microsecond=999999).astimezone(timezone.utc)
            authority.clock=lambda:before
            reserve_capture(authority,args,directory,token,"fixture")
            original=authority.begin_launch
            def crossing(*a,**kw):
                authority.clock=lambda:before+timedelta(seconds=2)
                return original(*a,**kw)
            with patch.object(authority,"begin_launch",side_effect=crossing), \
                    patch("eventguard.acceptance_process.spawn") as spawn:
                self.assertEqual(capture(args,directory,token,"fixture"),4)
                spawn.assert_not_called()
            self.assertEqual(authority.admission(token)["state"],"not_started")
            self.assertIsNone(authority.status()["active"])
            self.assertEqual(authority.status()["used"],0)
            with closing(sqlite3.connect(authority.path.as_uri()+"?mode=ro",uri=True)) as db:
                self.assertEqual(db.execute("SELECT charged_count FROM daily_usage WHERE day=?",
                    (local.date().isoformat(),)).fetchone()[0],1,"original day is not refunded")
            reserve_capture(authority,args,directory,"e"*32,"fixture")
            self.assertEqual(authority.status()["used"],1)
            self.assertFalse((directory/"capture-start.json").exists())
