"""Real CLI against synthetic budget ledgers; never the installation ledger."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from eventguard.agent_budget import BudgetAuthority, DAILY_LIMIT
from eventguard.processes import spawn, finish

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''import sys
from pathlib import Path
from eventguard import agent_budget
agent_budget.AUTHORITY_PATH=Path(sys.argv[1])/"authority.sqlite3"
from eventguard.cli import main
raise SystemExit(main(["--format","json","budget",*sys.argv[2:]],root=sys.argv[1]))
'''


class CommandBudgetStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="command-budget-", dir=ROOT / "reports")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.authority = BudgetAuthority(self.root / "authority.sqlite3")

    def call(self, *arguments):
        child = spawn([sys.executable, "-B", "-c", PROGRAM, str(self.root), *arguments],
                      env=dict(os.environ, PYTHONPATH=str(ROOT / "src")),
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out, err = child.communicate(timeout=10)
        finally:
            receipt = finish(child, reason="test_teardown", grace=1)
        self.assertTrue(receipt["child_exited"])
        self.assertFalse(receipt["forcibly_terminated"])
        self.assertEqual(receipt["remaining_owned_processes"], 0)
        self.assertFalse(bool(err), "unexpected_stderr_omitted")
        return child.returncode, json.loads(out)

    def test_missing_budget_is_blocked_without_initializing_anything(self):
        code, value = self.call("status")
        self.assertEqual(value["state"], "blocked")
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(code, 2)

    def test_unknown_bootstrap_usage_is_not_success(self):
        self.authority.initialize()
        code, value = self.call("status")
        self.assertEqual(value["reason"], "budget_bootstrap_usage_unknown")
        self.assertEqual(code, 2)

    def test_active_reservation_is_blocked_without_launching_any_process(self):
        self.authority.initialize(known_used=0)
        self.authority.reserve("1" * 32, "evt-budget-cli-fixture", "test", "a" * 64, "acceptance")
        code, value = self.call("status")
        self.assertEqual((code, value["reason"], value["used"]), (2, "budget_active_attempt", 1))
        self.assertEqual(self.authority.status()["used"], 1)

    def test_corrupt_ledger_is_blocked_without_repair_or_reset(self):
        self.authority.initialize(known_used=0)
        self.authority.path.write_bytes(b"inert corrupt budget fixture")
        before = self.authority.path.read_bytes()
        code, value = self.call("status")
        self.assertEqual((code, value["state"]), (2, "blocked"))
        self.assertEqual(self.authority.path.read_bytes(), before)

    def test_exhausted_budget_is_non_success_and_usage_is_retained(self):
        self.authority.initialize(known_used=DAILY_LIMIT)
        code, value = self.call("status")
        self.assertEqual((value["state"], value["reason"], value["used"]), ("blocked", "budget_exhausted", DAILY_LIMIT))
        self.assertEqual(self.authority.status()["used"], DAILY_LIMIT)
        self.assertEqual(code, 2)

    def test_ready_read_preserves_usage_and_failed_initialize_stays_error(self):
        self.authority.initialize(known_used=0)
        code, value = self.call("status")
        self.assertEqual((code, value["state"], value["used"]), (0, "ready", 0))
        self.assertFalse(value["account_limit_enforced"])
        code, value = self.call("initialize", "--known-used", "0")
        self.assertEqual((code, value["status"], value["state"]), (4, "error", "blocked"))
        self.assertEqual(self.authority.status()["used"], 0)
