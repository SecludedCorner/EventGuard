"""Saved advisory pagination over synthetic SQLite; no network or model."""
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

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

    def test_page_keeps_one_snapshot_while_another_writer_changes_a_later_case(self):
        target = self.reader.cases(limit=100, now=1001)[-1]["case_id"]
        ready, done = threading.Event(), threading.Event()
        failures = []
        def write():
            try:
                with self.store._connect() as db:
                    db.execute("UPDATE cases SET record=json_set(record,'$.title','concurrent fixture') WHERE case_id=?", (target,))
                    ready.set()
                done.set()
            except Exception as error:
                failures.append(type(error).__name__)
                ready.set()
        worker = threading.Thread(target=write)
        original = self.reader._advisory
        started = False
        def read(db, case_id, stamp):
            nonlocal started
            if not started:
                started = True
                worker.start()
                self.assertTrue(ready.wait(3))
                self.assertFalse(failures)
                self.assertFalse(done.wait(.1))  # Commit is held until this read snapshot ends.
            return original(db, case_id, stamp)
        try:
            with patch.object(self.reader, "_advisory", side_effect=read):
                page = self.reader.case_page(now=1001)
        finally:
            if started:
                worker.join(timeout=8)
                self.assertFalse(worker.is_alive())
        self.assertFalse(failures)
        self.assertTrue(done.is_set())
        self.assertEqual(page["cases"][-1]["case_id"], target)
        self.assertNotIn("title", page["cases"][-1]["record"])
        self.assertEqual(self.reader.advisory(target, now=1001)["record"]["title"], "concurrent fixture")
