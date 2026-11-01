"""Actual CLI pages and case detail over 101 synthetic saved advisories."""
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import unittest

import test_advisory_case_page as page_fixture
import test_command_status_retry as cli_fixture
from eventguard.intelligence.store import IntelligenceStore


class CommandAdvisoryCasesTests(unittest.TestCase):
    cli = cli_fixture.CommandStatusRetryTests.cli

    def setUp(self):
        fixture = page_fixture.AdvisoryCasePageTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        self.root = fixture.path.parent
        self.path = self.root / "data/advisories/intelligence.sqlite3"
        self.path.parent.mkdir(parents=True)
        shutil.copyfile(fixture.path, self.path)

    def cases(self, *arguments):
        return self.cli("advisories", "cases", *arguments)

    def test_pages_and_detail_reach_every_case_without_changing_database(self):
        before = self.path.read_bytes()
        code, first = self.cases()
        code2, last = self.cases("--offset", "100")
        self.assertEqual((code, code2, first["schema_version"], first["total"]), (0, 0, "1.0", 101))
        self.assertEqual((len(first["cases"]), len(last["cases"])), (100, 1))
        self.assertEqual((first["has_more"], last["has_more"]), (True, False))
        ids = [case["case_id"] for case in first["cases"] + last["cases"]]
        self.assertEqual(len(set(ids)), 101)
        code, detail = self.cases("--case-id", ids[-1])
        self.assertEqual((code, detail["case_id"], detail["case_status"]), (0, ids[-1], "unknown"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_bounds_or_selector_combinations_fail_before_access(self):
        before = self.path.read_bytes()
        for args in (("--limit", "101"), ("--limit", "0"), ("--offset", "-1"),
                     ("--offset", str(2**31)), ("--case-id", "case-missing", "--limit", "1")):
            code, result = self.cases(*args)
            self.assertEqual((code, result["status"]), (2, "invalid_request"))
        self.assertEqual(self.path.read_bytes(), before)
        code, result = self.cases("--case-id", "case-missing")
        self.assertEqual((code, result["state"]), (5, "unknown"))

    def test_absent_store_is_distinct_from_initialized_empty_store(self):
        self.root = self.root / "absent"
        code, result = self.cases("--limit", "1")
        self.assertEqual((code, result["state"], result["total"], result["has_more"]), (0, "not_started", None, None))
        self.assertFalse(self.root.exists())
        self.assertEqual(self.cases("--case-id", "case-missing")[0], 5)
        self.assertFalse(self.root.exists())
        IntelligenceStore(self.root / "data/advisories/intelligence.sqlite3")
        code, result = self.cases()
        self.assertEqual((code, result["state"], result["total"], result["has_more"]), (0, "available", 0, False))

    def test_corrupt_record_is_an_operation_failure_without_partial_result(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE cases SET record='{'")
            db.commit()
        before = self.path.read_bytes()
        code, result = self.cases()
        self.assertEqual((code, result["status"], result["raw_error_omitted"]), (4, "error", True))
        self.assertNotIn("cases", result)
        self.assertEqual(self.path.read_bytes(), before)
