"""Launch-scope regression with a fake command and no model/process launch."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard import delivery_validation as validation, investigation_scope as scope
from eventguard.acceptance_control import write_json
from eventguard.acceptance_process import launch_hash
from eventguard.agent_investigation import PROMPT
from eventguard.events.store import EventStore


class InvestigationLaunchBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "run"
        self.manifest = validation.prepare(self.root, "investigation")
        self.native = Path(__file__).resolve().parents[1] / "fixture-native.exe"  # Does not exist or execute.
        self.enterContext(patch.object(scope, "inventory", return_value={"fixture_only": True}))
        self.enterContext(patch.object(scope, "verified_preflight", return_value={"fixture_only": True}))
        self.enterContext(patch.object(scope, "file_hash", return_value="a"*64))
        command = lambda codex, *_args, **_kw: [str(codex), "fixture-only-no-model"]
        self.enterContext(patch.object(scope, "command", side_effect=command))
        self.enterContext(patch.object(validation, "command", side_effect=command))
        self.enterContext(patch.object(validation.shutil, "which", return_value="fixture-native.exe"))
        self.capture = self.enterContext(patch.object(validation, "capture", return_value=0))
        self.enterContext(patch.object(validation, "verify_stage", return_value={"passed": True}))
        self.enterContext(patch.object(validation, "verify", return_value={"passed": True}))
        self.bound = scope.prepare(self.root, self.manifest, self.native)
        write_json(self.root / "human-approval.json", {"approved": True, "scope_hash": self.bound["scope_hash"],
            "approved_at": datetime.now(timezone.utc).isoformat(), "user_instruction": "FIXTURE ONLY; NO MODEL APPROVAL"})

    def test_relative_executable_executes_the_exact_canonical_approved_launch(self):
        validation.execute(self.root, self.manifest, "fixture-native.exe")
        argv, _directory, _token, prompt = self.capture.call_args.args
        self.assertEqual(argv[0], str(self.native))
        self.assertEqual(prompt, PROMPT)
        self.assertEqual(launch_hash(argv, prompt), self.bound["launch_hash"])

    def test_command_drift_is_blocked_before_capture_and_stage_commit(self):
        with patch.object(validation, "command", return_value=[str(self.native), "changed-unapproved-arguments"]):
            with self.assertRaisesRegex(ValueError, "investigation_launch_scope_mismatch"):
                validation.execute(self.root, self.manifest, "fixture-native.exe")
        self.capture.assert_not_called()
        self.assertEqual(self.manifest["stages"], [])
        self.assertFalse((self.root / "stage-1").exists())
        self.assertEqual((EventStore(self.root / "source").stats()["pending"], len(self.manifest["enqueued"])), (1, 1))
