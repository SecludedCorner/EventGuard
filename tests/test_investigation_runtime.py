"""Fake PE bundle admission checks; no native CLI or model is executed."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard import delivery_validation as validation, investigation_scope as scope
from eventguard.acceptance_control import write_json
from eventguard.codex_runtime import REQUIRED
from eventguard import codex_preflight
from eventguard.events.store import EventStore
from preflight_fixtures import seed_preflight


class InvestigationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.runtime = base/'runtime'
        self.runtime.mkdir()
        for name in REQUIRED:
            (self.runtime/name).write_bytes(b'MZ-FAKE-NOT-EXECUTABLE-'+name.encode())
        self.cli = self.runtime/'codex.exe'
        self.root = base/'acceptance'
        self.manifest = validation.prepare(self.root, 'investigation')

    def approve_fixture(self):
        seed_preflight(self.cli)
        bound = scope.prepare(self.root, self.manifest, self.cli)
        write_json(self.root/'human-approval.json', dict(approved=True, scope_hash=bound['scope_hash'],
            approved_at=datetime.now(timezone.utc).isoformat(), user_instruction='FIXTURE ONLY; NOT AUTHORIZATION'))
        return bound

    def assert_rejected_before_delivery(self, reason):
        with patch.object(validation, 'enqueue') as enqueue, patch.object(validation, 'stage') as stage:
            with self.assertRaisesRegex((ValueError, OSError), reason):
                validation.execute(self.root, self.manifest, self.cli)
            enqueue.assert_not_called()
            stage.assert_not_called()
        self.assertEqual(EventStore(self.root/'source').stats()['pending'], 0)
        self.assertEqual(self.manifest['stages'], [])

    def test_missing_companions_reject_prepare_and_delivery_before_enqueue(self):
        for name in REQUIRED[1:]:
            with self.subTest(name=name):
                path = self.runtime/name
                original = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(ValueError, 'bundle_incomplete'):
                    scope.prepare(self.root, self.manifest, self.cli)
                self.assertFalse((self.root/'investigation-scope.json').exists())
                self.assert_rejected_before_delivery('bundle_incomplete')
                path.write_bytes(original)

    def test_approved_main_binary_does_not_approve_changed_companions(self):
        bound = self.approve_fixture()
        self.assertEqual(set(bound['runtime_bundle']['files']), set(REQUIRED))
        for name in REQUIRED[1:]:
            with self.subTest(name=name):
                path = self.runtime/name
                original = path.read_bytes()
                path.write_bytes(b'MZ-CHANGED-COMPANION')
                self.assert_rejected_before_delivery('preflight_bundle_changed')
                path.write_bytes(original)

    def test_missing_preflight_and_modified_bound_evidence_reject_delivery(self):
        self.assert_rejected_before_delivery('bundle-before.json')
        bound = self.approve_fixture()
        self.assertEqual(bound['runtime_preflight'], codex_preflight.verified(self.cli))
        path = self.runtime/'preflight/help/codex.jsonl'
        path.write_text(path.read_text()+'\nextra benign help text\n', encoding='utf-8')
        self.assert_rejected_before_delivery('preflight_evidence_changed')

    def test_unrecognized_runtime_resource_rejected_before_delivery(self):
        self.approve_fixture()
        (self.runtime/'unbound.dll').write_bytes(b'MZ-FAKE')
        self.assert_rejected_before_delivery('layout_unrecognized')
