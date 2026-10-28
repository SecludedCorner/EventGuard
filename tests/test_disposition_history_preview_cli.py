"""Synthetic CLI backup identity preview; standard input only, no real user data."""
from contextlib import closing, redirect_stdout
from copy import deepcopy
from pathlib import Path
import io
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.cli import main
from eventguard.events.disposition_history_backup import snapshot
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class HistoryPreviewCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root / "data/test")
        event = make_synthetic("listener")
        event["event_id"] = "evt-preview-cli-fixture"
        self.store.enqueue(event)
        self.store.set_disposition(event["event_id"], "read", operation_id="op-preview-cli-fixture")
        with closing(sqlite3.connect(self.store.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            self.value = snapshot(db, namespace="test")

    def invoke(self, data, *, namespace="test", fmt="json"):
        output = io.StringIO()
        with patch("sys.stdin", io.StringIO(data)), redirect_stdout(output):
            code = main(["--format", fmt, "events", "preview-history", "--namespace", namespace], root=self.root)
        return code, output.getvalue()

    def test_preview_is_explicit_aggregate_and_read_only(self):
        before = self.store.path.read_bytes()
        code, output = self.invoke(json.dumps(self.value))
        self.assertEqual(code, 0)
        result = json.loads(output)
        self.assertEqual(result["counts"]["already_present"], 1)
        self.assertEqual(result["identity_conflicts"], 0)
        for field in ("provenance_status", "history_completeness", "capacity_status", "recoverability_status"):
            self.assertEqual(result[field], "unknown")
        self.assertFalse(result["restore_performed"])
        self.assertFalse(result["restore_authorized"])
        self.assertNotIn("evt-preview-cli-fixture", output)
        self.assertNotIn("op-preview-cli-fixture", output)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))
        code, output = self.invoke(json.dumps(self.value), fmt="text")
        self.assertEqual(code, 0)
        self.assertIn("目標為備份的完全前綴", output)
        self.assertIn("不驗證來源真實性、容量或可還原性", output)

    def test_duplicate_json_fields_are_rejected_even_if_hash_matches(self):
        before = self.store.path.read_bytes()
        encoded = json.dumps(self.value, separators=(",", ":"))
        duplicate_root = encoded.replace('{"data":', '{"bytes":0,"data":', 1)
        duplicate_nested = encoded.replace('"namespace":"test"', '"namespace":"live","namespace":"test"', 1)
        self.assertNotEqual(duplicate_root, encoded)
        self.assertNotEqual(duplicate_nested, encoded)
        self.assertNotEqual(self.invoke(duplicate_root)[0], 0)
        self.assertNotEqual(self.invoke(duplicate_nested)[0], 0)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))

    def test_interactive_stdin_is_rejected_without_waiting(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True
            def read(self, *_args):
                raise AssertionError("must not wait for interactive input")
        before = self.store.path.read_bytes()
        with patch("sys.stdin", Terminal()), redirect_stdout(io.StringIO()):
            self.assertNotEqual(main(["--format", "json", "events", "preview-history", "--namespace", "test"], root=self.root), 0)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_invalid_scope_tamper_and_oversize_fail_without_writes(self):
        before = self.store.path.read_bytes()
        self.assertNotEqual(self.invoke(json.dumps(self.value), namespace="live")[0], 0)
        altered = deepcopy(self.value)
        altered["sha256"] = "0" * 64
        self.assertNotEqual(self.invoke(json.dumps(altered))[0], 0)
        self.assertNotEqual(self.invoke("x" * (4 * 1024 * 1024 + 1025))[0], 0)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertFalse((self.root / "reports").exists())
