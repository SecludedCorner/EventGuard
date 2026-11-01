"""Saved advisory pagination over synthetic SQLite; no network or model."""
from pathlib import Path
import tempfile
import unittest

from eventguard.intelligence.store import IntelligenceStore, IntelligenceError


class AdvisoryCasePageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "cases.sqlite3"
        self.store = IntelligenceStore(self.path)
        assessment = {"status": "unknown", "reason_codes": ["inventory_unknown"], "asset_refs": [],
                      "evidence": [], "conditions": {}, "fix_available": False}
        for index in range(101):
            record = {"ids": [f"CVE-2026-{10000+index}"], "component": "fixture", "ecosystem": "fixture",
                      "affected": [], "fixes": [], "conditions": {}, "evidence": [], "synthetic": True}
            self.store.ingest(record, assessment, "fixture", 1000)
        self.reader = IntelligenceStore(self.path, readonly=True)

    def test_all_101_cases_are_reachable_with_stable_pages_and_unchanged_assessments(self):
        before = self.path.read_bytes()
        first, last = self.reader.case_page(now=1001), self.reader.case_page(offset=100, now=1001)
        self.assertEqual((len(first["cases"]), len(last["cases"]), first["total"]), (100, 1, 101))
        self.assertTrue(first["has_more"])
        self.assertFalse(last["has_more"])
        cases = first["cases"] + last["cases"]
        self.assertEqual(cases, self.reader.cases(limit=10000, now=1001))
        self.assertEqual(len({c["case_id"] for c in cases}), 101)
        self.assertTrue(all(c["current_assessment"]["status"] == "unknown" for c in cases))
        self.assertEqual(self.path.read_bytes(), before)

    def test_bounds_and_page_beyond_total_do_not_write(self):
        before = self.path.read_bytes()
        for values in ({"limit": 0}, {"limit": 101}, {"limit": True}, {"offset": -1}, {"offset": 2**31}):
            with self.assertRaises(ValueError):
                self.reader.case_page(**values)
        page = self.reader.case_page(offset=101, now=1001)
        self.assertEqual((page["total"], page["cases"], page["has_more"]), (101, [], False))
        self.assertEqual(self.path.read_bytes(), before)

    def test_corrupt_stored_case_does_not_become_a_complete_partial_page(self):
        with self.store._connect() as db:
            db.execute("UPDATE cases SET record='{' WHERE case_id=(SELECT case_id FROM cases ORDER BY created,case_id LIMIT 1)")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(IntelligenceError, "case_page_unreadable"):
            self.reader.case_page(now=1001)
        self.assertEqual(self.path.read_bytes(), before)
