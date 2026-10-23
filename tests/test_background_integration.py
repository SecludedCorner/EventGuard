"""Finite background fixtures and shared human controls; no model or scheduler mutation."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from eventguard import background, processes
from eventguard.cli import main
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.events.schema import validate_event
from eventguard.monitor import Monitor
from eventguard.operations import OperatorAPI
from eventguard.runtime import Runtime, atomic_json
from eventguard.synthetic import make_synthetic

ROOT=Path(__file__).resolve().parents[1]


class BackgroundSharedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for relative in ('config/default.json','playbooks/default.json','tests/fixtures/normal.json'):
            path=self.root/relative; path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/relative,path)
        self.enterContext(patch('eventguard.operations._budget_status',return_value={'state':'blocked','reason':'fixture_not_initialized'}))

    def cli(self,*args):
        output=io.StringIO()
        with redirect_stdout(output):
            code=main(list(args),root=self.root)
        return code,json.loads(output.getvalue())

    def test_empty_background_status_is_readonly_and_needs_no_model(self):
        code,result=self.cli('background','status')
        self.assertEqual(code,0)
        self.assertFalse(result['desired_enabled'])
        self.assertEqual(result['model_calls'],0)
        self.assertFalse((self.root/'data').exists())

    def test_background_failure_states_are_nonzero_for_scheduler_recovery(self):
        for state in ('blocked','startup_failed','shutdown_unconfirmed','stop_not_persisted','unknown'):
            with self.subTest(state=state),patch('eventguard.background.serve',return_value={'state':state}):
                code,_=self.cli('background','serve')
            self.assertNotEqual(code,0)
        with patch('eventguard.background.serve',return_value={'state':'disabled'}):
            self.assertEqual(self.cli('background','serve')[0],0)

    def test_pythonw_serve_can_exit_without_console_streams(self):
        with patch('eventguard.cli.sys.stdout',None),patch('eventguard.background.serve',return_value={'state':'disabled'}):
            self.assertEqual(main(['background','serve'],root=self.root),0)

    def test_overview_does_not_call_backoff_or_enabled_intent_active_collection(self):
        api=OperatorAPI(self.root)
        for state in ('backoff','enabled_not_running','running'):
            with self.subTest(state=state),patch('eventguard.operations._background_status',return_value={
                    'namespace':'live','state':state,'desired_enabled':True}):
                value=api.overview('live')
            self.assertEqual(value['operator_summary']['state'],'background_'+state)
            self.assertNotEqual(value['current_monitor']['state'],'running_verified')
            self.assertEqual(value['operator_summary']['next_steps'][0]['operation'],'background_status')

    def test_generic_stop_durably_disables_matching_background_scope(self):
        path=self.root/'data/background/control.json'
        atomic_json(path,{'scope':'fixture_for_routing_only'})
        api=OperatorAPI(self.root)
        with patch('eventguard.operations._background_status',return_value={'namespace':'test'}), \
             patch('eventguard.background.stop',return_value={'state':'stopped','desired_enabled':False}) as stop, \
             patch.object(api.runtime,'request_stop',return_value={'status':'not_running'}):
            result=api.stop('test')
        stop.assert_called_once()
        self.assertFalse(result['desired_enabled'])
        with patch('eventguard.operations._background_status',return_value={'namespace':'live'}), \
             patch('eventguard.background.stop') as stop:
            api.stop('test')
        stop.assert_not_called()

    def test_full_queue_stops_further_collection_and_recovers_without_losing_pending(self):
        config=json.loads((self.root/'config/default.json').read_text(encoding='utf-8'))
        config['outbox']['max_events']=4
        atomic_json(self.root/'config/default.json',config)
        store=EventStore(self.root/'data/live',max_events=4)
        original=[make_synthetic('coverage') for _ in range(4)]
        for event in original:
            event['synthetic']=False
            store.enqueue(event)
        before={event['event_id']:event_payload_hash(validate_event(store.get_event(event['event_id']))) for event in original}
        frame=json.loads((self.root/'tests/fixtures/normal.json').read_text(encoding='utf-8'))
        frame['sections'][0]['rows'][1]['value']=False
        sections={item['id']:item for item in frame['sections']}
        calls=[]
        class Collector:
            def collect(self,source,cancel=None):
                calls.append(source)
                return sections[source]
        result=Monitor(self.root,collectors=Collector()).run(max_cycles=10)
        self.assertEqual(result['stop_reason'],'persistence_backpressure')
        self.assertEqual(calls,['defender'])
        self.assertEqual(store.stats()['pending'],4)
        self.assertIsNone(store.load_detector_state())
        for event in original[:2]:
            store.acknowledge(event['event_id'],{'event_id':event['event_id'],'ack_type':'receiver_persisted','receipt_id':'synthetic-human-receipt'})
        calls.clear()
        resumed=Monitor(self.root,collectors=Collector()).run(max_cycles=1)
        self.assertEqual(resumed['state'],'stopped')
        self.assertEqual(len(calls),7)
        self.assertIsNone(resumed['last_error'])
        for event in original[2:]:
            saved=store.get_event(event['event_id'])
            self.assertEqual(event_payload_hash(validate_event(saved)),before[event['event_id']])
            self.assertEqual(saved['delivery_status'],'pending')
        self.assertTrue(any(item['event_type']=='monitor_gap' for item in store.list_events()))

    def test_global_shutdown_gate_can_be_queried_across_session_changes(self):
        runtime=Runtime(self.root)
        with patch('eventguard.processes.process_session',return_value=1):
            runtime.block_monitor_shutdown({'namespace':'live','query_shutdown':{'managed':True,'job_name':'Global\\EventGuard-'+'a'*32}})
        with patch('eventguard.processes.process_session',return_value=7),patch('eventguard.processes.current_job_active',return_value=0):
            self.assertEqual(runtime.monitor_shutdown_gate(recover=True)['state'],'clear')
        with patch('eventguard.processes.process_session',return_value=1):
            runtime.block_monitor_shutdown({'namespace':'live','query_shutdown':{'managed':True,'job_name':'Local\\EventGuard-'+'b'*32}})
        with patch('eventguard.processes.process_session',return_value=7),patch('eventguard.processes.current_job_active') as query:
            self.assertEqual(runtime.monitor_shutdown_gate()['reason'],'previous_local_job_session_unverified')
        query.assert_not_called()


@unittest.skipUnless(os.name=='nt','Real Windows owned background host; bounded synthetic fixture')
class BackgroundReceiptIntegration(unittest.TestCase):
    setUp=BackgroundSharedTests.setUp
    def test_pending_query_survives_stop_resume_and_ack_closes_once(self):
        original_spawn=processes.spawn_persistent
        children=[]
        def bounded_spawn(argv,**kwargs):
            child=original_spawn(argv,allow_parent_job=True,**kwargs)
            children.append(child)
            return child
        # The verify guardian intentionally bounds these hosts. This test seam
        # is never exposed as a production CLI flag or independent uptime proof.
        try:
            with patch('eventguard.background.processes.spawn_persistent',side_effect=bounded_spawn):
                started=background.start(self.root,fixture='tests/fixtures/normal.json',max_cycles=100)
                self.assertEqual(started['state'],'started',started)
                self.assertTrue(started['handoff']['lifetime_limited'])
                event=make_synthetic('listener')
                EventStore(self.root/'data/test').enqueue(event)
                api=OperatorAPI(self.root)
                received=api.receive_event(event['event_id'],'test')
                query_id=received['query_id']
                self.assertFalse(received['outbox_acknowledged'])
                stopped=background.stop(self.root,grace_seconds=5)
                self.assertEqual(stopped['state'],'stopped',stopped)
                self.assertFalse(background.status(self.root)['desired_enabled'])
                self.assertEqual(background.serve(self.root)['state'],'disabled')
                restarted=background.start(self.root,fixture='tests/fixtures/normal.json',max_cycles=100)
                self.assertEqual(restarted['state'],'started',restarted)
                repeated=api.receive_event(event['event_id'],'test')
                self.assertEqual(repeated['query_id'],query_id)
                ack=api.ack_event(event['event_id'],query_id,namespace='test')
                self.assertTrue(ack['outbox_acknowledged'])
                self.assertEqual(api.ack_event(event['event_id'],query_id,namespace='test')['status'],'already_received')
                self.assertEqual(EventStore(self.root/'data/test').stats()['receipt_count'],1)
                self.evidence={'scope':'real_windows_background_jobs_synthetic_fixture_no_agent_no_reboot',
                    'event_id':event['event_id'],'query_id':query_id,'same_query_after_restart':True,
                    'receipt_count':1,'model_calls':0,'handoffs':[started['handoff'],restarted['handoff']]}
        finally:
            stopped=background.stop(self.root,grace_seconds=5)
            for child in children:
                child.wait(timeout=5)
            self.assertEqual(stopped['state'],'stopped',stopped)
            self.assertTrue(all(child.returncode==0 for child in children))
