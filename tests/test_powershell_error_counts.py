"""Execute only synthetic Add-Evidence/Write-Result in the existing interpreter."""
import json
import os
import unittest

from eventguard.collectors.runner import Runner
from eventguard.collectors.windows import COMMON


@unittest.skipUnless(os.name == 'nt', 'existing Windows PowerShell and owned Job required')
class PowerShellErrorCountsTests(unittest.TestCase):
    def run_script(self, body):
        result = Runner().run(COMMON + '\n' + body, timeout=5)
        self.assertEqual(result['status'], 'ok')
        process = result['process']
        self.assertTrue(process['managed'])
        self.assertTrue(process['child_exited'])
        self.assertEqual(process['exit_code'], 0)
        self.assertEqual(process['remaining_owned_processes'], 0)
        self.assertFalse(process['forcibly_terminated'])
        return result['data']

    def test_complete_error_counts_and_status_survive_retained_prefix(self):
        result = self.run_script('''
$rows=New-Object System.Collections.Generic.List[object]
1..64 | ForEach-Object {Add-Evidence 'object' 'access_denied' 'Synthetic' $null $null 'Fixture' 'denied'}
1..16 | ForEach-Object {Add-Evidence 'field' 'missing_metadata' 'Synthetic' $null $null 'Fixture' 'unknown'}
Write-Result $rows
''')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['error_count'], 80)
        self.assertEqual(len(result['errors']), 64)
        self.assertEqual(result['error_classifications'], {
            'total_count': 80, 'unclassified_count': 0,
            'groups': [{'stage': 'field', 'status': 'unknown', 'count': 16},
                       {'stage': 'object', 'status': 'denied', 'count': 64}]})

    def test_invalid_classification_is_unknown_and_successful_empty_has_zero_counts(self):
        result = self.run_script('''
$rows=New-Object System.Collections.Generic.List[object]
Add-Evidence @('PRIVATE') 'PRIVATE' 'Synthetic' $null $null 'Fixture' 'PRIVATE'
Add-Evidence 'object' 'PRIVATE' 'Synthetic' $null $null 'Fixture' 'ok'
Write-Result $rows
''')
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(result['error_classifications']['unclassified_count'], 2)
        self.assertNotIn('PRIVATE', json.dumps(result['error_classifications']))
        empty = self.run_script('''
$rows=New-Object System.Collections.Generic.List[object]
Write-Result $rows
''')
        self.assertEqual(empty['status'], 'ok')
        self.assertEqual(empty['error_classifications'], {
            'total_count': 0, 'unclassified_count': 0, 'groups': []})
