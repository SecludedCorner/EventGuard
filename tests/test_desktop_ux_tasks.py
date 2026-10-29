"""Metric fixtures only: never create real participant success claims."""
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard.desktop_ux_tasks import prepare_tasks, record_task, task_plan
from scripts import desktop_ux_acceptance as launcher


class DesktopUXTaskTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        prepare_tasks(self.root)

    def test_blank_plan_and_exclusive_unverified_reports(self):
        self.assertEqual(len(task_plan()['tasks']), 6)
        self.assertTrue(all(t['reported_metrics'] is None for t in task_plan()['tasks']))
        value = record_task(self.root, 'U1', 3, 12.5, 1, 'unresolved')
        self.assertFalse(value['human_participation_verified'])
        path = self.root/'task-U1.json'
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            record_task(self.root, 'U1', 4, 15, 0, 'completed')
        self.assertEqual(path.read_bytes(), before)

    def test_missing_invalid_metrics_and_changed_plan_do_not_create_report(self):
        for metrics in ((None, None, None), (True, 1, 0), (1, float('nan'), 0), (1, 901, 0), (1, 1, -1)):
            with self.assertRaisesRegex(ValueError, 'desktop_task_metrics_invalid'):
                record_task(self.root, 'U2', *metrics, 'completed')
        (self.root/'tasks.json').write_text(json.dumps({}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'desktop_task_plan_invalid'):
            record_task(self.root, 'U2', 1, 1, 0, 'completed')
        self.assertFalse((self.root/'task-U2.json').exists())

    def test_cli_records_only_explicit_unverified_metrics_without_spawning(self):
        root = self.root/'reports/desktop-ux-record'
        root.mkdir(parents=True)
        prepare_tasks(root)
        with patch.object(launcher, 'ROOT', self.root), patch.object(launcher, 'spawn', side_effect=AssertionError('no launch')), redirect_stdout(io.StringIO()):
            code = launcher.main(['--name', 'desktop-ux-record', '--record-task', 'U3',
                '--steps', '3', '--elapsed-seconds', '12.5', '--errors', '0', '--outcome', 'unresolved'])
        self.assertEqual(code, 0)
        result = json.loads((root/'task-U3.json').read_bytes())
        self.assertEqual(result['elapsed_seconds'], 12.5)
        self.assertFalse(result['human_participation_verified'])
