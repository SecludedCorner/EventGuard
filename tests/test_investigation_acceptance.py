"""Finite production acceptance with an explicitly FAKE CLI, real SDK and SQLite."""
from datetime import datetime, timezone
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from budget_fixtures import isolated_launch
from eventguard import delivery_validation as validation, investigation_scope as scope
from eventguard.acceptance_control import read_json, write_json
from eventguard.events.store import EventStore
from eventguard.queue_inbox import QueueInbox

ROOT = Path(__file__).resolve().parents[1]


class InvestigationAcceptanceTests(unittest.TestCase):
    def test_failed_acceptance_after_ack_never_claims_source_still_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'run'
            manifest = validation.prepare(root, 'investigation')
            validation.enqueue(root, manifest, manifest['events'])
            identity = manifest['events'][0]['event_id']
            inbox = QueueInbox(root/'source', root/'inbox', identity, investigation=True)
            inbox.receive_event()
            query = inbox.query_evidence(identity)
            value = dict(summary='Synthetic metadata needs follow-up.', finding='metadata_requires_followup',
                fact_keys=['coverage_status'], limitations=query['saved_evidence']['limitations'], next_step='request_authorized_evidence')
            inbox.save_investigation(identity, query['query_id'], value)
            inbox.ack_event(identity, query['query_id'], 'needs_more_evidence')
            output = io.StringIO()
            with patch.object(validation, 'execute', side_effect=ValueError('fixture_late_exit_failure')), contextlib.redirect_stdout(output):
                code = validation.main(['investigation', '--root', str(root), '--execute'])
            result = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertIsNone(result['pending_preserved'])
            self.assertIs(result['outbox_acknowledged'], True)
            self.assertEqual(EventStore(root/'source').stats()['pending'], 0)

    @patch.object(scope, 'inventory', return_value={'fixture_only': 'FAKE CLI, no executable bundle'})
    @patch.object(scope, 'verified_preflight', return_value={'fixture_only': 'no native probes'})
    def test_finite_fake_cli_real_stdio_report_ack_and_held_handle_natural_exit(self, _preflight, _inventory):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base/'reports/run'
            manifest = validation.prepare(root, 'investigation')
            def fake_command(codex, python, source, state, identity, evidence, **kwargs):
                return [sys.executable, '-B', str(ROOT/'tests/fixtures/investigation_client.py'),
                        str(source), str(state), identity, str(evidence), str(base)]
            with patch.object(validation, 'command', side_effect=fake_command), patch.object(scope, 'command', side_effect=fake_command):
                bound = scope.prepare(root, manifest, sys.executable)
                with self.assertRaisesRegex(ValueError, 'human_approval_required'):
                    validation.execute(root, manifest, sys.executable)
                self.assertEqual(EventStore(root/'source').stats()['pending'], 0)
                write_json(root/'human-approval.json', dict(approved=True, scope_hash=bound['scope_hash'],
                    approved_at=datetime.now(timezone.utc).isoformat(), user_instruction='FIXTURE ONLY; NO MODEL/HUMAN AUTHORIZATION'))
                with isolated_launch(base/'gate'):
                    proof = validation.execute(root, manifest, sys.executable)
                self.assertTrue(proof['passed'], proof)
                self.assertTrue(proof['per_stage'][0]['mcp_server_exit']['mcp_natural_exit_verified'])
                self.assertEqual(EventStore(root/'source').stats()['pending'], 0)
                self.assertTrue(validation.verify(root, manifest)['passed'])
                with self.assertRaisesRegex(ValueError, 'existing_execution_refused'):
                    validation.execute(root, manifest, sys.executable)
                self.evidence = dict(scope='FAKE CLI, actual SDK/private Jobs/HANDLE, SQLite; model_calls=0',
                    proof=proof, process=read_json(root/'stage-1/capture-exit.json'))
