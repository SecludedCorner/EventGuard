"""Owned application Jobs and optional SDK gate, not a real model or reboot."""
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from eventguard import background, processes
from eventguard.agent_access import set_enabled
from eventguard.events.store import EventStore
from eventguard.operations import OperatorAPI
from eventguard.synthetic import make_synthetic

ROOT=Path(__file__).resolve().parents[1]


class FixtureRoot:
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for relative in ('config/default.json','playbooks/default.json','tests/fixtures/normal.json'):
            target=self.root/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/relative,target)


@unittest.skipUnless(os.name=='nt','Windows application-owned Job APIs')
class ApplicationHostTests(FixtureRoot,unittest.TestCase):
    def test_application_owns_same_private_job_until_pause(self):
        children=[]
        try:
            started=background.start(self.root,lifetime_owner='application',child_owner=children.append,
                fixture='tests/fixtures/normal.json',max_cycles=100)
            self.assertEqual(started['state'],'started',started)
            receipt=started['handoff']
            self.assertFalse(receipt['detached'])
            self.assertFalse(receipt['ownership_transferred'])
            self.assertIsNone(receipt['child_exited'])
            self.assertIsNotNone(children[0].job.handle)
            self.assertGreater(children[0].job.active(),0)
            stopped=background.stop(self.root,grace_seconds=5)
            self.assertEqual(stopped['state'],'stopped',stopped)
            self.assertEqual(children[0].wait(timeout=3),0)
            closed=processes.finish(children[0],'cancelled',grace=0,request_stop=False)
            self.assertFalse(closed['forcibly_terminated'])
            self.assertEqual(closed['remaining_owned_processes'],0)
            self.evidence={'scope':'real Windows application-owned finite fixture, no model',
                'retained_host':receipt,'stop':stopped,'handle_release':closed}
        finally:
            background.stop(self.root,grace_seconds=5)
            for child in children:
                processes.finish(child,'test_teardown',grace=1)

    def test_parent_exit_cooperatively_ends_owned_host_without_detach(self):
        entry=self.root/'application-parent.py'
        entry.write_text('import sys\nfrom pathlib import Path\n'
            + 'sys.path.insert(0,'+repr(str(ROOT/'src'))+')\n'
            + 'from eventguard.background import start\n'
            + 'from eventguard.runtime import atomic_json\n'
            + 'children=[]\nr=start(Path('+repr(str(self.root))+'),lifetime_owner="application",child_owner=children.append,'
            + 'fixture="tests/fixtures/normal.json",max_cycles=100000)\n'
            + 'atomic_json(Path('+repr(str(self.root/'started.json'))+'),r)\n'
            + 'raise SystemExit(0 if r["state"]=="started" else 2)\n',encoding='utf-8')
        child=processes.spawn([sys.executable,'-B',str(entry)],job_name='Global\\EventGuard-'+uuid.uuid4().hex,
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            self.assertEqual(child.wait(timeout=20),0)
            deadline=time.monotonic()+15
            while child.job.active() and time.monotonic()<deadline:
                time.sleep(.05)
            self.assertEqual(child.job.active(),0,'application host must observe its recorded parent exit')
            status=background.status(self.root)
            self.assertEqual(status['host_liveness'],'exited_verified',status)
            saved=json.loads((self.root/'data/background/run.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['reason'],'application_owner_exit_or_unverifiable')
            receipt=processes.finish(child,'descendants_remaining',grace=0)
            self.assertFalse(receipt['forcibly_terminated'])
            self.evidence={'scope':'real Windows finite parent exit, no OS reboot/model',
                'parent_and_tree_exit':receipt,'host_status':status,'last_report':saved}
        finally:
            background.stop(self.root,grace_seconds=5)
            processes.finish(child,'test_teardown',grace=1)


class AgentGateAdapterTests(FixtureRoot,unittest.IsolatedAsyncioTestCase):
    async def test_live_tools_recheck_switch_without_deleting_or_acknowledging_event(self):
        try:
            import mcp
        except ImportError:
            self.skipTest('optional existing SDK unavailable; no installation')
        spec=importlib.util.spec_from_file_location('gui_gate_adapter',ROOT/'scripts/eventguard_inbox_mcp.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        event=make_synthetic();event['synthetic']=False
        store=EventStore(self.root/'data/live');store.enqueue(event)
        server=module.build_operator_server(self.root,'live',allow_live=True)
        def unpack(result):
            return json.loads(next(item.text for item in getattr(result,'content',result) if item.type=='text'))
        blocked=unpack(await server.call_tool('receive_event',{'event_id':event['event_id']}))
        self.assertEqual(blocked['reason'],'agent_delivery_disabled')
        self.assertNotIn('event_id',blocked)
        set_enabled(self.root,True)
        received=unpack(await server.call_tool('receive_event',{'event_id':event['event_id']}))
        self.assertEqual(received['event_id'],event['event_id'])
        set_enabled(self.root,False)
        ack=unpack(await server.call_tool('ack_event',{'event_id':event['event_id'],'query_id':received['query_id']}))
        self.assertEqual(ack['status'],'blocked')
        self.assertEqual(store.get_event(event['event_id'])['delivery_status'],'pending')
        human=OperatorAPI(self.root).ack_event(event['event_id'],received['query_id'],namespace='live')
        self.assertTrue(human['outbox_acknowledged'])
        self.assertEqual(store.stats()['receipt_count'],1)
        self.evidence={'scope':'SDK tool functions with synthetic live-profile fixture; no actual agent/model',
            'disabled':blocked,'enabled_receive':received,'disabled_ack':ack,'human_ack':human}

    async def test_disabled_live_dispatch_never_checks_cli_or_launches_model(self):
        from eventguard import agent_dispatch
        with (patch.object(agent_dispatch,'ROOT',self.root),patch.object(agent_dispatch.shutil,'which') as which,
                patch.object(agent_dispatch,'spawn') as spawn):
            code=agent_dispatch.run(self.root/'dispatch',allow_live=True,execute=True)
        self.assertEqual(code,2)
        which.assert_not_called();spawn.assert_not_called()
