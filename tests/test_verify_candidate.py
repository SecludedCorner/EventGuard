"""Candidate tampering and lifecycle rejection; all ZIPs/children here are synthetic."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_candidate", ROOT / "scripts/verify_candidate.py")
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)
REVISION = "a" * 40
REQUIRED = {"EventGuard.cmd", "scripts/eventguard.py", "src/eventguard/__init__.py",
            "config/default.json", "playbooks/default.json", "README.md", "LICENSE"}


class CandidateVerificationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name)
        self.inputs = self.project / "reports/inputs"
        self.inputs.mkdir(parents=True)
        self.archive = self.inputs / "candidate.zip"
        self.manifest = self.inputs / "release-manifest.json"
        self.make_zip()
        self.declared = verify.audit_archive(self.archive, REVISION)
        self.manifest.write_text(json.dumps(self.declared), encoding="utf-8")
        self.digest = self.declared["archive_sha256"]
        project_patch = patch.object(verify, "PROJECT", self.project)
        project_patch.start()
        self.addCleanup(project_patch.stop)

    def make_zip(self, *, omit=None, extra=(), revision=REVISION):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.comment = revision.encode("ascii")
            for name in sorted(REQUIRED):
                if name != omit:
                    value = '__version__ = "0.1.0"\n' if name.endswith("__init__.py") else "synthetic-only\n"
                    archive.writestr("EventGuard/" + name, value)
            for name, value in extra:
                archive.writestr(name, value)

    def args(self, root="candidate-verify-one"):
        return ["--archive", str(self.archive), "--manifest", str(self.manifest),
                "--expected-commit", REVISION, "--expected-sha256", self.digest,
                "--root", str(self.project / "reports" / root)]

    def validate(self, *, declared=None, commit=REVISION, digest=None):
        return verify.verify_inputs(self.archive, json.dumps(self.declared if declared is None else declared),
                                    commit, self.digest if digest is None else digest)

    def test_external_pins_and_exact_per_file_manifest_are_verified(self):
        actual = self.validate()
        self.assertEqual(actual, self.declared)
        with patch.object(verify, "spawn") as spawn, redirect_stdout(io.StringIO()):
            self.assertEqual(verify.main(self.args()), 0)
        spawn.assert_not_called()
        result = json.loads((self.project / "reports/candidate-verify-one/verification-result.json").read_text())
        self.assertTrue(result["manifest_verified"])
        self.assertFalse(result["smoke_executed"])
        self.assertEqual(result["owned_steps"], [])
        self.assertFalse((self.project / "reports/candidate-verify-one/unpacked").exists())

    def test_modified_archive_and_self_consistent_manifest_cannot_replace_external_hash(self):
        self.make_zip(extra=[("EventGuard/changed.txt", "SYNTHETIC_TAMPER")])
        changed = verify.audit_archive(self.archive, REVISION)
        with self.assertRaisesRegex(verify.CandidateError, "external_archive_hash_mismatch"):
            self.validate(declared=changed)

    def test_missing_file_or_forged_file_digest_in_manifest_is_rejected(self):
        for mutation in ("missing", "hash", "size", "count", "version"):
            with self.subTest(mutation=mutation):
                declared = json.loads(json.dumps(self.declared))
                if mutation == "missing":
                    del declared["files"]["LICENSE"]
                elif mutation == "hash":
                    declared["files"]["LICENSE"]["sha256"] = "0" * 64
                elif mutation == "size":
                    declared["files"]["LICENSE"]["bytes"] += 1
                elif mutation == "count":
                    declared["file_count"] += 1
                else:
                    declared["source_version"] = "9.9.9"
                with self.assertRaisesRegex(verify.CandidateError, "manifest_content_mismatch"):
                    self.validate(declared=declared)

    def test_manifest_numeric_type_substitution_and_duplicate_keys_are_rejected(self):
        for value in (float(self.declared["file_count"]), True):
            declared = {**self.declared, "file_count": value}
            with self.assertRaisesRegex(verify.CandidateError, "manifest_content_mismatch"):
                self.validate(declared=declared)
        with self.assertRaisesRegex(verify.CandidateError, "duplicate_json_key"):
            verify.verify_inputs(self.archive, '{"revision":"a","revision":"b"}', REVISION, self.digest)

    def test_wrong_archive_revision_and_missing_required_archive_file_are_rejected(self):
        for options in ({"revision": "b" * 40}, {"omit": "LICENSE"}):
            with self.subTest(options=options):
                self.make_zip(**options)
                digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
                with self.assertRaisesRegex(verify.CandidateError, "archive_or_manifest_invalid"):
                    self.validate(digest=digest)

    def test_untrusted_paths_refused_before_extraction_or_any_child(self):
        for index, name in enumerate(("EventGuard/../escaped", "EventGuard/data/live/foreign.db",
                                      "EventGuard/.codex/auth.json", "EventGuard/LPT1.txt",
                                      "EventGuard/readme.md", "EventGuard/C:/outside")):
            with self.subTest(name=name):
                self.make_zip(extra=[(name, "SYNTHETIC_ONLY")])
                self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
                args = self.args("candidate-verify-reject-" + str(index)) + (["--smoke"] if os.name == "nt" else [])
                with patch.object(verify, "extract_verified") as extract, patch.object(verify, "spawn") as spawn, \
                        redirect_stdout(io.StringIO()):
                    self.assertEqual(verify.main(args), 2)
                extract.assert_not_called()
                spawn.assert_not_called()
                result = json.loads((self.project / "reports" / ("candidate-verify-reject-" + str(index))
                                     / "verification-result.json").read_text())
                self.assertEqual(result["reason"], "archive_or_manifest_invalid")
        self.assertFalse((self.project / "escaped").exists())

    def test_pins_are_required_and_existing_result_never_overwritten(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                verify.main(self.args()[:4])
        existing = self.project / "reports/candidate-verify-one"
        existing.mkdir()
        receipt = existing / "verification-result.json"
        receipt.write_text("SYNTHETIC_EXISTING", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(verify.main(self.args()), 2)
        self.assertEqual(receipt.read_text(), "SYNTHETIC_EXISTING")

    def test_input_limits_fail_before_archive_is_parsed(self):
        with patch.object(verify, "MAX_ARCHIVE", 10), patch.object(verify, "audit_archive") as audit:
            with self.assertRaisesRegex(verify.CandidateError, "input_size_limit"):
                self.validate()
        audit.assert_not_called()

    def test_new_extraction_has_exact_verified_files_and_no_runtime(self):
        destination = self.project / "reports/candidate-verify-extraction"
        destination.mkdir()
        copy = verify.extract_verified(self.archive, self.validate(), destination)
        self.assertEqual({p.relative_to(copy).as_posix() for p in copy.rglob("*") if p.is_file()}, REQUIRED)
        for name, record in self.declared["files"].items():
            self.assertEqual(hashlib.sha256((copy / name).read_bytes()).hexdigest(), record["sha256"])
        with self.assertRaises(FileExistsError):
            verify.extract_verified(self.archive, self.declared, destination)

    def test_output_root_escape_and_input_redirects_are_refused(self):
        with self.assertRaises((verify.CandidateError, ValueError)):
            verify.reports_path(self.project / "outside")
        with self.assertRaises(ValueError):
            verify.reports_path(self.project / "reports/../outside")
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaisesRegex(verify.CandidateError, "regular_input"):
                verify.bounded_bytes(self.archive, 1024)


class CandidateOwnedChildTests(unittest.TestCase):
    def test_forced_failed_unknown_remaining_or_unmanaged_exit_cannot_pass(self):
        clean = {"managed": True, "child_exited": True, "exit_code": 0, "remaining_owned_processes": 0,
                 "forcibly_terminated": False, "reason": "natural_exit"}
        self.assertTrue(verify.natural_exit(clean))
        for changed in ({"managed": False}, {"child_exited": None}, {"exit_code": 1}, {"exit_code": False},
                        {"remaining_owned_processes": None}, {"remaining_owned_processes": False},
                        {"remaining_owned_processes": 1},
                        {"forcibly_terminated": True}, {"reason": "unconfirmed"}):
            with self.subTest(changed=changed):
                self.assertFalse(verify.natural_exit({**clean, **changed}))

    def test_cli_timeout_saves_original_receipt_and_never_passes_clean_late_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = []
            child = Mock()
            child.wait.side_effect = subprocess.TimeoutExpired("SYNTHETIC", 15)
            receipt = {"managed": True, "child_exited": True, "exit_code": 0, "remaining_owned_processes": 0,
                       "forcibly_terminated": False, "reason": "natural_exit"}
            with patch.object(verify, "spawn", return_value=child) as spawn, \
                    patch.object(verify, "finish", return_value=receipt) as finish:
                with self.assertRaisesRegex(verify.CandidateError, "cli_timeout"):
                    verify.cli(root, root, "fixture-timeout", ["synthetic", "emit"], receipts)
            self.assertEqual(spawn.call_args.args[0][-2:], ["synthetic", "emit"])
            finish.assert_called_once_with(child, "timeout", grace=2)
            self.assertEqual(len(receipts), 1)
            self.assertTrue((root / "fixture-timeout.owned-exit.json").is_file())


if __name__ == "__main__":
    unittest.main()
