"""Installed SDK four-tool path; no model and no native collection."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from eventguard.agent_dispatch import command
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class InvestigationMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.event = make_synthetic('listener')
        self.identity = self.event['event_id']
        EventStore(self.root/'source').enqueue(self.event)
        script = Path(__file__).resolve().parents[1]/'scripts/eventguard_inbox_mcp.py'
        spec = importlib.util.spec_from_file_location('investigation_mcp_test', script)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    async def test_sdk_report_is_saved_separately_and_errors_leave_pending(self):
        server = self.module.build_server(self.root/'source', self.root/'state', self.identity, investigation=True)
        self.assertEqual({t.name for t in await server.list_tools()},
                         {'receive_event', 'query_evidence', 'save_investigation', 'ack_event'})
        await server.call_tool('receive_event', {})
        await server.call_tool('query_evidence', {'event_id': self.identity})
        backend = server._inbox_backend
        observed = backend.evidence(self.identity)
        ack = dict(event_id=self.identity, query_id=observed['query_id'], decision='needs_more_evidence')
        with self.assertRaisesRegex(Exception, 'saved_investigation_required'):
            await server.call_tool('ack_event', ack)
        with self.assertRaisesRegex(ValueError, 'invalid_inbox_tool_arguments'):
            await server.call_tool('save_investigation', dict(event_id=self.identity, query_id=observed['query_id'], report='text'))
        value = dict(summary='Synthetic evidence needs follow-up; no host verdict.',
            finding='metadata_requires_followup', fact_keys=['coverage_status'],
            limitations=observed['saved_evidence']['limitations'], next_step='request_authorized_evidence')
        await server.call_tool('save_investigation', dict(event_id=self.identity, query_id=observed['query_id'], report=value))
        self.assertEqual(EventStore(self.root/'source').stats()['pending'], 1)
        await server.call_tool('ack_event', ack)
        self.assertTrue(backend.acknowledged(self.identity))

    async def test_explicit_profile_command_and_legacy_tool_set_do_not_mix(self):
        server = self.module.build_server(self.root/'source', self.root/'legacy', self.identity)
        self.assertEqual({t.name for t in await server.list_tools()}, {'receive_event', 'query_evidence', 'ack_event'})
        args = command('codex', 'python', self.root/'source', self.root/'state', self.identity,
                       self.root/'reports', investigation=True)
        config = next(x for x in args if x.startswith('mcp_servers.eventguard_inbox='))
        self.assertIn('--investigation', config)
        self.assertIn('save_investigation', config)
        self.assertIn('features.shell_tool=false', args)
        with self.assertRaises(ValueError):
            command('codex', 'python', 'source', 'state', self.identity, self.root, investigation=True, allow_live=True)
