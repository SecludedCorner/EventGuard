"""Actual installed SDK and owned Windows child; synthetic client, model_calls=0."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest

from eventguard.acceptance_control import read_json
from eventguard.acceptance_evidence import _tool_result
from eventguard.events.store import EventStore
from eventguard.processes import spawn, finish
from eventguard.synthetic import make_synthetic


class InvestigationStdioTests(unittest.TestCase):
    def test_four_tools_save_before_ack_and_natural_exit_with_stdin_still_open(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = EventStore(root/'source')
            event = make_synthetic('listener')
            identity = event['event_id']
            store.enqueue(event)
            script = Path(__file__).resolve().parents[1]/'scripts/eventguard_inbox_mcp.py'
            directory = root/'reports/attempt'
            child = spawn([sys.executable, '-B', str(script), '--source-dir', str(root/'source'),
                '--state-dir', str(root/'inbox'), '--event-id', identity, '--project-root', str(root),
                '--startup-evidence-dir', str(directory), '--investigation', '--exit-after-ack'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            messages = queue.Queue()
            def read_output():
                try:
                    for line in child.stdout:
                        messages.put(json.loads(line))
                finally:
                    child.stdout.close()
            def drain_errors():
                try:
                    while child.stderr.read(4096): pass
                finally:
                    child.stderr.close()
            readers = [threading.Thread(target=read_output, daemon=True), threading.Thread(target=drain_errors, daemon=True)]
            for reader in readers: reader.start()
            def request(number, method, params):
                child.stdin.write(json.dumps(dict(jsonrpc='2.0', id=number, method=method, params=params)).encode()+b'\n')
                child.stdin.flush()
                reply = messages.get(timeout=20)
                self.assertEqual(reply.get('id'), number)
                self.assertNotIn('error', reply)
                return reply['result']
            def tool(number, name, arguments):
                raw = request(number, 'tools/call', dict(name=name, arguments=arguments))
                self.assertFalse(raw.get('isError', False))
                return _tool_result(dict(result=raw))
            try:
                request(1, 'initialize', dict(protocolVersion='2024-11-05', capabilities={},
                        clientInfo=dict(name='synthetic-investigation-fixture', version='1')))
                child.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                child.stdin.flush()
                listed = request(2, 'tools/list', {})
                self.assertEqual({t['name'] for t in listed['tools']},
                                 {'receive_event', 'query_evidence', 'save_investigation', 'ack_event'})
                tool(3, 'receive_event', {})
                observed = tool(4, 'query_evidence', dict(event_id=identity))
                value = dict(summary='Synthetic listener evidence needs authorized follow-up; host unverified.',
                    finding='metadata_requires_followup', fact_keys=list(observed['saved_evidence']['facts']),
                    limitations=observed['saved_evidence']['limitations'], next_step='request_authorized_evidence')
                saved = tool(5, 'save_investigation', dict(event_id=identity, query_id=observed['query_id'], report=value))
                self.assertFalse(saved['outbox_acknowledged'])
                self.assertEqual(store.stats()['pending'], 1)
                ack = tool(6, 'ack_event', dict(event_id=identity, query_id=observed['query_id'], decision='needs_more_evidence'))
                self.assertEqual(ack['investigation'], saved['investigation'])
                self.assertTrue(ack['outbox_acknowledged'])
                self.assertFalse(child.stdin.closed)
                self.assertEqual(child.wait(timeout=15), 0)
            finally:
                if not child.stdin.closed: child.stdin.close()
                receipt = finish(child, 'descendants_remaining', grace=2, request_stop=True)
                for reader in readers: reader.join(timeout=2)
            self.assertFalse(receipt['forcibly_terminated'])
            self.assertEqual(receipt['remaining_owned_processes'], 0)
            self.assertEqual(store.stats()['pending'], 0)
            ended = read_json(directory/'mcp-stdio-exit.json')
            self.assertTrue(ended['ack_response_flushed'])
            self.assertEqual(ended['return_code'], 0)
            self.evidence = dict(scope='actual SDK/private Job, synthetic client, no model',
                process=receipt, ack_response_flushed=True, model_calls=0)
