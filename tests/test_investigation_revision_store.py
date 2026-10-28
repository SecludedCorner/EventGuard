"""Synthetic transaction tests for investigation revision storage."""
from contextlib import closing
from copy import deepcopy
import sqlite3
import unittest

from eventguard.events.investigation import build, project
from eventguard.events.investigation_revision import make_revision
from eventguard.events.investigation_revision_store import append_revision, RevisionCapacityError
from eventguard.synthetic import make_synthetic


class InvestigationRevisionStoreTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.event = make_synthetic("listener")
        self.event["event_id"] = "evt-revision-fixture"
        case = build(project(self.event, "listeners"), [], as_of=self.event["observed_at"])
        self.revision = make_revision(case, self.event, saved_at=1.25)

    def test_requires_caller_write_transaction_and_never_commits(self):
        with self.assertRaisesRegex(ValueError, "write_transaction_required"):
            append_revision(self.db, self.revision, self.event, available_bytes=1000000)
        self.db.execute("BEGIN IMMEDIATE")
        append_revision(self.db, self.revision, self.event, available_bytes=1000000)
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM investigation_revisions").fetchone()[0], 1)
        self.db.rollback()
        self.assertIsNone(self.db.execute("SELECT 1 FROM sqlite_master WHERE name='investigation_revisions'").fetchone())

    def test_saves_exact_fields_and_fails_on_untrusted_revision(self):
        self.db.execute("BEGIN IMMEDIATE")
        append_revision(self.db, self.revision, self.event, available_bytes=1000000)
        row = self.db.execute("SELECT event_id,payload_hash,case_hash,saved_at FROM investigation_revisions").fetchone()
        self.assertEqual(row, tuple(self.revision[k] for k in ("event_id", "payload_hash", "case_hash", "saved_at")))
        bad = deepcopy(self.revision)
        bad["case_hash"] = "0" * 64
        with self.assertRaises(ValueError):
            append_revision(self.db, bad, self.event, available_bytes=1000000)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM investigation_revisions").fetchone()[0], 1)

    def test_capacity_rejects_before_table_creation_or_extra_insert(self):
        self.db.execute("BEGIN IMMEDIATE")
        with self.assertRaisesRegex(RevisionCapacityError, "bytes_capacity"):
            append_revision(self.db, self.revision, self.event, available_bytes=0)
        self.assertIsNone(self.db.execute("SELECT 1 FROM sqlite_master WHERE name='investigation_revisions'").fetchone())
        for _ in range(16):
            append_revision(self.db, self.revision, self.event, available_bytes=1000000)
        with self.assertRaisesRegex(RevisionCapacityError, "count_capacity"):
            append_revision(self.db, self.revision, self.event, available_bytes=1000000)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM investigation_revisions").fetchone()[0], 16)
        self.db.rollback()

    def test_read_only_transaction_is_rejected(self):
        self.db.execute("PRAGMA query_only=ON")
        self.db.execute("BEGIN")
        with self.assertRaisesRegex(ValueError, "write_transaction_required"):
            append_revision(self.db, self.revision, self.event, available_bytes=1000000)
