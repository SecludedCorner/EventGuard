"""Human budget operations on a labelled fixture installation, no model."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard import agent_budget
from eventguard.agent_budget import BudgetAuthority
from eventguard.cli import main
from eventguard.acceptance_control import write_json
from test_capture_receipt import fixture


class BudgetCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="budget-cli-", dir=agent_budget.ROOT/"reports")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.path=self.root/"installation/authority.sqlite3"
        self.enterContext(patch.object(agent_budget,"AUTHORITY_PATH",self.path))

    def call(self,*args):
        output=io.StringIO()
        with redirect_stdout(output):
            code=main(["budget",*args],root=self.root)
        return code,json.loads(output.getvalue())

    def test_status_missing_does_not_initialize_and_unknown_bootstrap_is_explicit(self):
        code,result=self.call("status")
        self.assertEqual(code,0)
        self.assertEqual(result["reason"],"budget_unavailable")
        self.assertFalse(self.path.parent.exists())
        code,result=self.call("initialize")
        self.assertEqual(code,0)
        self.assertFalse(result["usage_known"])
        self.assertEqual(result["remaining"],0)
        self.assertEqual(result["reason"],"budget_bootstrap_usage_unknown")

    def test_explicit_verified_baseline_cannot_be_reset(self):
        code,result=self.call("initialize","--known-used","3")
        self.assertEqual(code,0)
        self.assertEqual(result["used"],3)
        code,result=self.call("initialize","--known-used","0")
        self.assertEqual(code,4)
        self.assertEqual(result["reason"],"budget_already_initialized")
        self.assertEqual(self.call("status")[1]["used"],3)

    def test_reconcile_requires_matching_saved_started_identity_and_job_proof(self):
        self.call("initialize","--known-used","0")
        authority=BudgetAuthority.open_existing()
        receipt,started=fixture()
        token=started["attempt_id"]
        authority.reserve(token,"fixture-event","test","a"*64,"acceptance")
        authority.begin_launch(token)
        authority.record_started(token,started["codex_pid"],started["created_at"])
        directory=self.root/"attempt"; directory.mkdir()
        write_json(directory/"capture-start.json",started)
        receipt["process"]["remaining_owned_processes"]=1
        write_json(directory/"capture-exit.json",receipt)
        code,result=self.call("reconcile","--attempt-dir",str(directory))
        self.assertEqual(code,4)
        self.assertEqual(result["reason"],"budget_exit_unconfirmed")
        self.assertIsNotNone(authority.status()["active"])
        receipt["process"]["remaining_owned_processes"]=0
        write_json(directory/"capture-exit.json",receipt)
        code,result=self.call("reconcile","--attempt-dir",str(directory))
        self.assertEqual(code,0)
        self.assertEqual(result["state"],"completed")
        self.assertIsNone(authority.status()["active"])
        self.assertEqual(authority.status()["used"],1)

    def test_reconcile_rejects_outside_directory_before_reading(self):
        with patch("eventguard.acceptance_control.read_json") as read:
            code,result=self.call("reconcile","--attempt-dir",str(agent_budget.ROOT/"src"))
        self.assertEqual(code,2)
        read.assert_not_called()
