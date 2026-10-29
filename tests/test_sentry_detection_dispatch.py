"""Actual detector/outbox/policy/receive/query/save/ACK, explicitly fake CLI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from budget_fixtures import isolated_launch
from eventguard.acceptance_control import read_json
from eventguard.agent_dispatch import ROOT, run, status
from eventguard.dispatch_policy import select_pending
from eventguard.events.store import EventStore
from eventguard.queue_inbox import QueueInbox
from eventguard.rules.configured import DEFAULT_RULES, apply_rules
from eventguard.rules.detector import evaluate
from test_agent_dispatch import FAKE_QUEUE
from test_rules_playbooks import defender, endpoint, section


class SentryDetectionDispatchTests(unittest.TestCase):
    def test_high_signal_crosses_real_pipeline_once_and_warning_stays_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EventStore(root / 'source')
            state_dir = root / 'inbox'
            script = root / 'explicit-fake-cli.py'
            script.write_text(FAKE_QUEUE, encoding='utf-8')
            children = []
            original = subprocess.Popen
            def launch(*args, **kwargs):
                child = original(*args, **kwargs)
                children.append(child)
                return child
            def command(codex, python, source, state, event_id, evidence, **kwargs):
                return [sys.executable, '-B', str(script), str(source), str(state), event_id,
                        'success', str(ROOT / 'src')]
            def dispatch(name, seconds=15):
                return run(root / name, store.directory, state_dir, max_tasks=1, max_seconds=seconds,
                           execute=True, poll_seconds=.01, select_event=select_pending)
            with isolated_launch(root), patch('eventguard.agent_dispatch.command', side_effect=command), \
                 patch('eventguard.agent_dispatch.shutil.which', return_value=sys.executable), \
                 patch('eventguard.agent_dispatch.importlib.util.find_spec', return_value=True), \
                 patch('eventguard.agent_dispatch.subprocess.Popen', side_effect=launch):
                now = time.time()
                state, events = evaluate([defender()], now=now, host_id='synthetic-sentry')
                self.assertEqual(events, [])
                store.commit_evaluation(state, events)
                self.assertEqual(dispatch('normal', .05), 0)
                self.assertEqual(children, [])
                state, events = evaluate([defender(False, False), section('listeners', [endpoint()])],
                                         state, now=now+1, host_id='synthetic-sentry')
                for event in events:
                    event['synthetic'] = True
                events = apply_rules(events, DEFAULT_RULES)
                store.commit_evaluation(state, events)
                high = next(event['event_id'] for event in events if event['severity'] == 'high')
                warning = next(event['event_id'] for event in events if event['severity'] == 'warning')
                self.assertEqual(dispatch('signal'), 0)
                saved = status(root / 'signal')
                self.assertEqual((saved['tasks_started'], saved['tasks_passed']), (1, 1))
                self.assertTrue(saved['child_exited'])
                attempt = root / 'signal/attempts' / saved['active_attempt_id']
                self.assertTrue(read_json(attempt / 'capture-exit.json')['capture_complete'])
                self.assertTrue(read_json(attempt / 'summary.json')['passed'])
                inbox = QueueInbox(store.directory, state_dir)
                evidence = inbox.evidence(high)
                self.assertEqual(evidence['snapshot']['event_id'], high)
                self.assertEqual(evidence['result']['query_id'], evidence['query_id'])
                self.assertTrue(inbox.acknowledged(high))
                self.assertFalse(inbox.acknowledged(warning))
                self.assertEqual(store.get_event(warning)['delivery_status'], 'pending')
                self.assertEqual(dispatch('warning-only', .05), 0)
                self.assertEqual(len(children), 1)
            self.assertTrue(all(child.wait(timeout=5) == 0 for child in children))
            self.assertEqual((store.stats()['pending'], store.stats()['ack'], store.stats()['receipt_count']), (1, 1, 1))
            self.evidence = {'scope': 'synthetic_detector_to_explicit_fake_cli_only',
                             'model_calls': 0, 'real_agent_woken': False, 'native_collection': False,
                             'normal_cli_launches': 0, 'signal_cli_tasks': 1, 'warning_cli_launches': 0,
                             'receive_query_saved_ack': True, 'pending_warning_preserved': True}
