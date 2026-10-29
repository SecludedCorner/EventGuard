"""Two original Job handles and two real Tk processes over the same saved DB."""
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
class DesktopFixtureProcessReopenTests(unittest.TestCase):
    def run_probe(self, phase, source=None):
        name = 'desktop-ux-probe-'+uuid.uuid4().hex
        root = scope_path(name)
        root.mkdir()
        job = 'Local\\EventGuard-'+uuid.uuid4().hex
        args = [sys.executable, '-B', str(Path(__file__).with_name('desktop_fixture_process_probe.py')),
                '--name', name, '--job', job, '--phase', phase]
        if source:
            args.extend(['--reopen-from', source])
        child = spawn(args, job_name=job, stdin=subprocess.PIPE)
        try:
            child.wait(timeout=20)
        finally:
            receipt = finish(child, 'test_teardown', grace=5)
            atomic_json(root/'probe-guardian.json', receipt)
        self.assertEqual(receipt['exit_code'], 0, root)
        self.assertEqual(receipt['remaining_owned_processes'], 0)
        self.assertFalse(receipt['forcibly_terminated'])
        result = json.loads((root/'probe-result.json').read_bytes())
        self.assertTrue(result['passed'], result)
        self.assertTrue(json.loads((root/'worker-exit.json').read_bytes())['automated_fixture_actions'])
        return name, root, result

    def test_first_gui_saves_second_gui_reads_same_case_and_data_without_copy(self):
        name, first, saved = self.run_probe('save')
        old = {p: (first/p).read_bytes() for p in ('worker-ready.json', 'worker-exit.json', 'probe-guardian.json')}
        _, second, reopened = self.run_probe('read', source=name)
        self.assertEqual(reopened['case_id'], saved['case_id'])
        self.assertEqual(reopened['database_sha256'], saved['database_sha256'])
        self.assertTrue(all((first/p).read_bytes() == data for p, data in old.items()))
        self.assertFalse((second/'reports/desktop-ux-session').exists())
        self.assertEqual(json.loads((second/'worker-ready.json').read_bytes())['scope_parent'], name)
