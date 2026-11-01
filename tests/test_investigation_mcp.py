"""Installed SDK four-tool path; no model and no native collection."""
import importlib.util
import json
from copy import deepcopy
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

    async def test_sdk_carries_saved_classification_only_in_synthetic_investigation_evidence(self):
        from eventguard.rules.decisions import classify
        from eventguard.queue_inbox import QueueInboxError
        rule = dict(id='sdk-classifier', name='inert fixture', enabled=True, severity='critical',
                    conditions=[dict(field='event_type', op='eq', value=self.event['event_type'])])
        event = classify([self.event], [rule])[0]
        source = self.root / 'classified-source'
        EventStore(source).enqueue(event)
        legacy = self.module.build_server(source, self.root/'minimal', self.identity)
        received = json.loads((await legacy.call_tool('receive_event', {}))[0].text)
        self.assertEqual(set(received['snapshot']), {'event_id','event_type','transition','severity','synthetic','observed_at','coverage_status'})
        minimal = json.loads((await legacy.call_tool('query_evidence', {'event_id': self.identity}))[0].text)
        self.assertNotIn('saved_evidence', minimal)
        server = self.module.build_server(source, self.root/'classified-state', self.identity, investigation=True)
        await server.call_tool('receive_event', {})
        queried = json.loads((await server.call_tool('query_evidence', {'event_id': self.identity}))[0].text)
        observed = queried['saved_evidence']
        self.assertEqual(observed['facts']['classification'], event['classification'])
        value = dict(summary='Saved classification still needs evidence.', finding='metadata_requires_followup',
            fact_keys=['classification'], limitations=observed['limitations'], next_step='request_authorized_evidence')
        saved = json.loads((await server.call_tool('save_investigation', dict(event_id=self.identity,
            query_id=queried['query_id'], report=value)))[0].text)
        backend = server._inbox_backend
        record = backend.evidence(self.identity)['result']['investigation']
        self.assertEqual(record['observations']['classification'], event['classification'])
        forged = deepcopy(record)
        forged['observations']['classification']['matched'] = 1
        with self.assertRaisesRegex(QueueInboxError, 'inbox_investigation_invalid'):
            backend._investigation_report(forged, {'saved_evidence': observed, 'query_id': queried['query_id']})
        self.assertEqual(EventStore(source).stats()['pending'], 1)
        await server.call_tool('ack_event', dict(event_id=self.identity, query_id=queried['query_id'], decision='needs_more_evidence'))
        self.assertEqual(EventStore(source).stats()['pending'], 0)
