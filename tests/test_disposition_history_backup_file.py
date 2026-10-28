"""Synthetic no-overwrite local backup tests; never read user data."""
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.disposition_history_backup import snapshot, verify_snapshot
from eventguard.events.disposition_history_backup_file import write_backup
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class DispositionHistoryBackupFileTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = EventStore(self.root / "data" / "test")
        event = make_synthetic("listener")
        event["event_id"] = "evt-file-fixture"
        self.store.enqueue(event)
        self.store.set_disposition(event["event_id"], "read", source="gui", operation_id="op-file")
        with closing(sqlite3.connect(self.store.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            self.value = snapshot(db)

    def test_persists_verified_snapshot_without_touching_source(self):
        before = self.store.path.read_bytes()
        receipt = write_backup(self.root, "history-backup-fixture.json", self.value)
        path = self.root / receipt["path"]
        self.assertEqual(verify_snapshot(json.loads(path.read_bytes()))["sha256"], self.value["sha256"])
        self.assertTrue(receipt["file_fsynced"])
        self.assertEqual(receipt["directory_entry_durability"], "not_verified")
        self.assertFalse(receipt["source_history_removed"])
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))

    def test_existing_destination_is_never_overwritten(self):
        reports = self.root / "reports"
        reports.mkdir()
        destination = reports / "history-backup-fixture.json"
        destination.write_bytes(b"existing synthetic data")
        with self.assertRaises(FileExistsError):
            write_backup(self.root, destination.name, self.value)
        self.assertEqual(destination.read_bytes(), b"existing synthetic data")
        self.assertEqual([p.name for p in reports.iterdir()], [destination.name])

    def test_invalid_name_and_tampered_payload_do_not_create_backup(self):
        for filename in ("../outside.json", "other.json", "history-backup-.json"):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                write_backup(self.root, filename, self.value)
        bad = {**self.value, "sha256": "0" * 64}
        with self.assertRaises(ValueError):
            write_backup(self.root, "history-backup-invalid.json", bad)
        self.assertFalse((self.root / "reports").exists())

    def test_redirected_reports_path_is_rejected_before_writing(self):
        reports = self.root / "reports"
        reports.mkdir()
        original = Path.is_junction
        def is_redirect(path):
            return path == reports or original(path)
        with patch.object(Path, "is_junction", is_redirect):
            with self.assertRaisesRegex(ValueError, "redirected_runtime_path"):
                write_backup(self.root, "history-backup-fixture.json", self.value)
        self.assertEqual(list(reports.iterdir()), [])

    def test_link_failure_cleans_only_own_temp_and_preserves_database(self):
        before = self.store.path.read_bytes()
        with patch("eventguard.events.disposition_history_backup_file.os.link", side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):
                write_backup(self.root, "history-backup-failure.json", self.value)
        self.assertEqual(list((self.root / "reports").iterdir()), [])
        self.assertEqual(self.store.path.read_bytes(), before)
