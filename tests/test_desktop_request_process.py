"""Two original private Job handles, real Tk, same DB, lost success receipt."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

from eventguard.processes import spawn, finish
from eventguard.runtime import atomic_json
from scripts.desktop_ux_acceptance import scope_path


@unittest.skipUnless(os.name == 'nt', 'real Windows owned Job required')
class DesktopRequestProcessTests(unittest.TestCase):
    def probe(self, phase, source=None):
        name = 'desktop-ux-request-'+uuid.uuid4().hex
        root = scope_path(name)
        root.mkdir()
        job = 'Local\\EventGuard-'+uuid.uuid4().hex
        args = [sys.executable, '-B', str(Path(__file__).with_name('desktop_request_process_probe.py')),
                '--name', name, '--job', job, '--phase', phase]
        if source:
            args.extend(['--reopen-from', source])
        child = spawn(args, job_name=job, stdin=subprocess.PIPE)
        try:
            child.wait(timeout=20)
        finally:
            receipt = finish(child, 'test_teardown', grace=5)
            atomic_json(root/'request-guardian.json', receipt)
        self.assertTrue(receipt['managed'])
        self.assertTrue(receipt['child_exited'])
        self.assertEqual(receipt['exit_code'], 0, root)
        self.assertEqual(receipt['remaining_owned_processes'], 0)
        self.assertFalse(receipt['forcibly_terminated'])
        proof = json.loads((root/'request-probe.json').read_bytes())
        self.assertTrue(proof['passed'], (root, proof))
        return name, root, proof

    def test_lost_success_then_new_process_recovers_same_key_and_keeps_later_decision(self):
        name, first, saved = self.probe('loss')
        old = {p: (first/p).read_bytes() for p in ('worker-ready.json', 'worker-exit.json', 'request-guardian.json')}
        _, second, recovered = self.probe('recover', source=name)
        self.assertEqual(saved['operation_id'], recovered['operation_id'])
        self.assertEqual(saved['final_db_sha256'], recovered['pre_replay_sha256'])
        self.assertEqual((saved['pending_requests'], recovered['pending_requests']), (1, 0))
        self.assertTrue(all((first/p).read_bytes() == data for p, data in old.items()))
        self.assertFalse((second/'reports/desktop-ux-session').exists())
        atomic_json(second/'cross-process-proof.json', {'first': first.name, 'second': second.name,
                    'same_key': True, 'read_before_replay_unchanged': True, 'synthetic': True, 'participant_results': None})
