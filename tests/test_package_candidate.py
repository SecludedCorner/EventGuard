"""Synthetic ZIPs only: no Git child, native query, model or extraction."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_candidate", ROOT / "scripts/package_candidate.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)
REVISION = "a" * 40


class CandidateArchiveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "candidate.zip"

    def make_zip(self, extra=None, *, revision=REVISION, omit=None):
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.comment = revision.encode("ascii")
            for name in sorted(package.REQUIRED):
                if name != omit:
                    content = '__version__ = "0.1.0"\n' if name.endswith("__init__.py") else "synthetic file\n"
                    archive.writestr("EventGuard/" + name, content)
            for name, data in extra or []:
                archive.writestr(name, data)

    def test_manifest_binds_revision_version_bytes_and_all_required_files(self):
        self.make_zip()
        result = package.audit_archive(self.path, REVISION)
        self.assertEqual(result["source_version"], "0.1.0")
        self.assertEqual(result["revision"], REVISION)
        self.assertEqual(result["file_count"], len(package.REQUIRED))
        self.assertEqual(sum(item["bytes"] for item in result["files"].values()), result["unpacked_bytes"])
        self.assertEqual(result, package.audit_archive(self.path, REVISION))

    def test_runtime_private_and_path_escape_entries_are_rejected(self):
        for name in ("EventGuard/reports/private.json", "EventGuard/data/eventguard.sqlite3",
                     "EventGuard/.codex/auth.json", "EventGuard/.codex-remote-attachments/photo.jpg",
                     "EventGuard/.env", "EventGuard/../outside", "EventGuard/C:/private", "outside/file",
                     "EventGuard/private.p12", "EventGuard/private.kdbx", "EventGuard/private.sqlite3-wal"):
            with self.subTest(name=name):
                self.make_zip([(name, "PRIVATE_SYNTHETIC")])
                with self.assertRaises(ValueError):
                    package.audit_archive(self.path, REVISION)

    def test_case_collisions_and_symlinks_are_rejected_before_extraction(self):
        self.make_zip([("EventGuard/readme.md", "collision")])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            package.audit_archive(self.path, REVISION)
        self.make_zip()
        with zipfile.ZipFile(self.path, "a") as archive:
            link = zipfile.ZipInfo("EventGuard/link")
            link.create_system = 3
            link.external_attr = 0o120777 << 16
            archive.writestr(link, "../outside")
        with self.assertRaisesRegex(ValueError, "path_invalid"):
            package.audit_archive(self.path, REVISION)

    def test_noncanonical_paths_and_windows_aliases_are_rejected(self):
        for name in ("EventGuard/a/./file", "EventGuard/a//file", "EventGuard/file.",
                     "EventGuard/file ", "EventGuard/CON", "EventGuard/LPT1.txt"):
            with self.subTest(name=name):
                self.make_zip([(name, "synthetic")])
                with self.assertRaises(ValueError):
                    package.audit_archive(self.path, REVISION)

    def test_missing_required_files_and_wrong_commit_never_build(self):
        self.make_zip(omit="LICENSE")
        with self.assertRaisesRegex(ValueError, "required_file"):
            package.audit_archive(self.path, REVISION)
        self.make_zip(revision="b" * 40)
        with self.assertRaisesRegex(ValueError, "revision_mismatch"):
            package.audit_archive(self.path, REVISION)

    def test_size_limits_apply_before_reading_file_payloads(self):
        self.make_zip([("EventGuard/large.txt", "x" * 100)])
        old = package.MAX_UNPACKED
        try:
            package.MAX_UNPACKED = 50
            with self.assertRaisesRegex(ValueError, "unpacked_limit"):
                package.audit_archive(self.path, REVISION)
        finally:
            package.MAX_UNPACKED = old


    def test_git_launch_resolves_installed_executable_before_owned_creation(self):
        executable = Path(self.directory.name) / "git.exe"
        executable.write_text("synthetic; never executed", encoding="utf-8")
        receipt = {"managed": True, "child_exited": True, "exit_code": 0,
                   "remaining_owned_processes": 0, "forcibly_terminated": False}
        with patch.object(package.shutil, "which", return_value=str(executable)), \
                patch.object(package, "spawn", return_value=Mock()) as spawn, \
                patch.object(package, "finish", return_value=receipt):
            package.archive_commit(Path(self.directory.name), REVISION, "fixture.zip")
        self.assertEqual(spawn.call_args.args[0][0], str(executable.resolve()))

    def test_missing_or_wrapper_git_does_not_create_a_child(self):
        for executable in (None, "git", str(Path(self.directory.name) / "git.cmd")):
            with self.subTest(executable=executable), patch.object(package.shutil, "which", return_value=executable), \
                    patch.object(package, "spawn") as spawn:
                with self.assertRaisesRegex(ValueError, "installed_native_git"):
                    package.archive_commit(Path(self.directory.name), REVISION, "fixture.zip")
                spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
