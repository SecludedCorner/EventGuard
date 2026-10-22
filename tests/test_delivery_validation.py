"""Finite validation entry points; no model, network, CI or native collection."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("finite_delivery_validation", ROOT / "contrib/legacy_delivery_validation.py")
validation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validation)


class DeliveryValidationTests(unittest.TestCase):
    def test_checkout_root_and_finite_tool_whitelists(self):
        self.assertEqual(validation.ROOT, ROOT)
        with patch.object(validation.shutil, "which", return_value="C:/Codex/codex.exe") as lookup:
            single = validation.argv(Path("runtime"), Path("evidence"), 1, native_executable="C:/Codex/codex.exe")
            lookup.assert_called_once_with("C:/Codex/codex.exe")
            multiple = validation.argv(Path("runtime"), Path("evidence"), 3)
            read_only = validation.argv(Path("runtime"), Path("evidence"), 1, read_only=True)
        self.assertTrue(any('--single-wait' in value for value in single))
        self.assertFalse(any('--single-wait' in value for value in multiple))
        config = next(value for value in read_only if value.startswith('mcp_servers.'))
        self.assertIn('query_evidence', config)
        self.assertNotIn('ack_event', config)
        server = tomllib.loads(config)["mcp_servers"]["eventguard_local"]
        self.assertEqual(server["enabled_tools"], ["wait_for_event", "query_evidence"])
        self.assertEqual(server["tools"], {name: {"approval_mode": "approve"}
                                         for name in server["enabled_tools"]})
        self.assertNotIn("default_tools_approval_mode", server)
        self.assertIn('features.unbounded_connection_retries=false', multiple)

    def test_prepare_is_durable_finite_and_never_launches_model(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(validation, 'capture') as capture:
            for case, count in (("continuous", 2), ("batch", 3), ("recovery", 1)):
                root = Path(temp) / case
                manifest = validation.prepare(root, case)
                self.assertEqual(len(manifest['events']), count)
                self.assertEqual(len({event['event_id'] for event in manifest['events']}), count)
                self.assertTrue(all(event['synthetic'] for event in manifest['events']))
                self.assertEqual(manifest['attempts'], {})
                self.assertEqual(manifest['enqueued'], [])
                self.assertEqual(validation.prepare(root, case), manifest)
                self.assertEqual(json.loads((root / 'manifest.json').read_text()), manifest)
            capture.assert_not_called()

    def test_verify_only_missing_evidence_does_not_create_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'absent'
            args = ['validate_delivery.py', 'batch', '--verify-only', '--root', str(root)]
            with patch.object(validation.sys, 'argv', args), self.assertRaisesRegex(ValueError, 'evidence_required'):
                validation.main()
            self.assertFalse(root.exists())

    def test_native_cli_wrapper_is_refused_without_model(self):
        with patch.object(validation.shutil, 'which', return_value='C:/npm/codex.cmd'):
            with self.assertRaisesRegex(ValueError, 'native_codex_required'):
                validation.argv(Path('runtime'), Path('evidence'), 1)

    def test_legacy_cli_refuses_execution_without_creating_source_or_calling_model(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(validation, 'capture') as capture:
            root = Path(temp) / 'absent'
            args = ['legacy_delivery_validation.py', 'batch', '--root', str(root), '--execute']
            with patch.object(validation.sys, 'argv', args), self.assertRaisesRegex(ValueError, 'legacy_execution_retired'):
                validation.main()
            self.assertFalse(root.exists())
            capture.assert_not_called()

    def test_legacy_reader_does_not_rewrite_schema_policy_ledger_or_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'old'
            manifest = validation.prepare(root, 'batch')
            backend = validation.LocalWait(root / 'runtime')
            event = manifest['events'][0]
            backend.store.enqueue(event)
            runtime = root / 'runtime'
            def snapshot():
                return {p.relative_to(runtime).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in runtime.rglob('*') if p.is_file()}
            before = snapshot()
            reader = validation.EvidenceReader(runtime)
            self.assertEqual(reader.store.get_event(event['event_id'])['delivery_status'], 'pending')
            self.assertEqual(reader.store.stats()['pending'], 1)
            validation.prepare(root, 'batch')
            with self.assertRaisesRegex(validation.LocalWaitError, 'read_only'):
                reader._save(reader._load())
            self.assertEqual(snapshot(), before)
