"""Fixed metadata truth through actual detector, durable store and policy."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.validate_detection import ROOT, run


class DetectionCorpusTests(unittest.TestCase):
    def test_corpus_reports_unobserved_separately_and_never_receives_or_launches(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'reports') as directory:
            root = Path(directory) / 'corpus'
            with patch('subprocess.Popen', side_effect=AssertionError('no child/model/scan')), \
                 patch('eventguard.queue_inbox.QueueInbox.receive_event', side_effect=AssertionError('no receive')), \
                 patch('eventguard.queue_inbox.QueueInbox.ack_event', side_effect=AssertionError('no ACK')):
                result = run(root)
            self.assertTrue(result['passed'])
            self.assertEqual(result['case_count'], 10)
            self.assertEqual(result['metrics'], {'tp': 7, 'fp': 0, 'fn': 0, 'tn': 2, 'passed': 10, 'unobserved': 1})
            cases = {row['id']: row for row in result['cases']}
            self.assertEqual({key for key, row in cases.items() if row['policy_eligible']},
                             {'protection-two-disabled', 'collection-timeout'})
            self.assertFalse(cases['scan-without-telemetry']['observable'])
            self.assertEqual(cases['wildcard-listener']['events'], [['listener.changed', 'warning']])
            self.assertTrue(all(row['receipt_count'] == 0 for row in cases.values()))
            summary = root / 'detection-summary.json'
            self.assertEqual(json.loads(summary.read_text(encoding='utf-8')), result)
            before = summary.read_bytes()
            with self.assertRaises(FileExistsError):
                run(root)
            self.assertEqual(summary.read_bytes(), before)

    def test_report_cannot_be_written_outside_project_reports(self):
        with self.assertRaisesRegex(ValueError, 'detection_report_root_required'):
            run(ROOT / 'not-a-report')
