"""Only fixture approvals here; no model invocation or account inspection."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from eventguard import investigation_scope as scope
from eventguard.acceptance_control import read_json, write_json
from eventguard.synthetic import make_synthetic


class InvestigationScopeTests(unittest.TestCase):
    def test_scope_requires_current_explicit_single_use_approval_and_matching_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = dict(case='investigation', events=[make_synthetic('listener')], stages=[], enqueued=[])
            with patch.object(scope, 'file_hash', return_value='a'*64):
                bound = scope.prepare(root, manifest, sys.executable)
                self.assertFalse(read_json(root/'human-approval.json')['approved'])
                with self.assertRaisesRegex(ValueError, 'human_approval_required'):
                    scope.require_approval(root, manifest, sys.executable)
                write_json(root/'human-approval.json', dict(approved=True, scope_hash=bound['scope_hash'],
                    approved_at=datetime.now(timezone.utc).isoformat(), user_instruction='FIXTURE ONLY, NOT HUMAN AUTHORIZATION'))
                self.assertEqual(scope.require_approval(root, manifest, sys.executable), bound)
                manifest['stages'].append({'fixture': True})
                with self.assertRaisesRegex(ValueError, 'consumed'):
                    scope.require_approval(root, manifest, sys.executable)
                manifest['stages'].clear()
                with patch.object(scope, 'file_hash', return_value='b'*64):
                    with self.assertRaisesRegex(ValueError, 'human_approval_required'):
                        scope.require_approval(root, manifest, sys.executable)
