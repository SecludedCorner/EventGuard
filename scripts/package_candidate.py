"""Build a reviewed commit into a source-only candidate; never publish or tag."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from eventguard.processes import spawn, finish
from eventguard.runtime import atomic_json, safe_child

MAX_ARCHIVE = 16 * 1024 * 1024
MAX_UNPACKED = 32 * 1024 * 1024
MAX_ENTRIES = 1024
FORBIDDEN = frozenset({".git", ".codex", ".claude", ".aws", ".codex-remote-attachments",
                       "reports", "data", "logs", "credentials", "secrets", "__pycache__", ".venv"})
REQUIRED = frozenset({"EventGuard.cmd", "scripts/eventguard.py", "src/eventguard/__init__.py",
                      "config/default.json", "playbooks/default.json", "README.md", "LICENSE"})


def audit_archive(path, revision):
    """Validate before extraction; retain only file names, sizes and digests."""
    path = Path(path)
    if not re.fullmatch(r"[a-f0-9]{40}", revision) or path.stat().st_size > MAX_ARCHIVE:
        raise ValueError("archive_input_invalid")
    files, seen, total, version_source = {}, set(), 0, None
    with zipfile.ZipFile(path) as archive:
        if archive.comment != revision.encode("ascii"):
            raise ValueError("archive_revision_mismatch")
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES:
            raise ValueError("archive_entry_limit")
        for item in entries:
            name = item.filename
            parts = PurePosixPath(name).parts
            if (not name.startswith("EventGuard/") or "\\" in name or ":" in name
                    or ".." in parts or name.startswith("/") or len(parts) < 1
                    or "/".join(parts) != name.rstrip("/")
                    or stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1):
                raise ValueError("archive_path_invalid")
            reserved = {"CON", "PRN", "AUX", "NUL", *("COM" + str(i) for i in range(1, 10)),
                        *("LPT" + str(i) for i in range(1, 10))}
            if any(part.rstrip(" .") != part or part.split(".")[0].upper() in reserved for part in parts):
                raise ValueError("archive_windows_alias")
            if any(part.casefold() in FORBIDDEN for part in parts[1:]):
                raise ValueError("archive_runtime_path")
            relative = "/".join(parts[1:])
            if any(part.casefold().startswith(".env") and part != ".env.example" for part in parts[1:]):
                raise ValueError("archive_private_settings")
            if relative.lower().endswith((".sqlite3", ".sqlite3-wal", ".sqlite3-shm", ".sqlite3-journal",
                                          ".db", ".key", ".pem", ".pfx", ".p12", ".kdbx", ".token", ".credential")):
                raise ValueError("archive_private_file")
            folded = name.rstrip("/").casefold()
            if folded in seen:
                raise ValueError("archive_duplicate_path")
            seen.add(folded)
            total += item.file_size
            if item.file_size < 0 or total > MAX_UNPACKED:
                raise ValueError("archive_unpacked_limit")
            if item.is_dir():
                continue
            data = archive.read(item)
            files[relative] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            if relative == "src/eventguard/__init__.py":
                version_source = data.decode("utf-8")
        if not REQUIRED.issubset(files):
            raise ValueError("archive_required_file_missing")
    version = None
    for node in ast.parse(version_source).body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__"
                                                for target in node.targets):
            version = ast.literal_eval(node.value)
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("archive_version_invalid")
    return {"revision": revision, "source_version": version, "file_count": len(files),
            "unpacked_bytes": total, "archive_bytes": path.stat().st_size,
            "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "files": dict(sorted(files.items()))}


def archive_commit(root, revision, filename):
    """Git runs inside our private Job before execution; save fixed receipts."""
    executable = shutil.which("git")
    if (not executable or not Path(executable).is_absolute() or not Path(executable).is_file()
            or Path(executable).suffix.lower() != ".exe"):
        raise ValueError("installed_native_git_required")
    child, receipt = None, None
    reason = "owner_exception"
    try:
        child = spawn([str(Path(executable).resolve()), "archive", "--format=zip", "--prefix=EventGuard/",
                       "--output=" + str(root / filename), revision], cwd=PROJECT,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            child.wait(timeout=30)
            reason = "descendants_remaining"
        except subprocess.TimeoutExpired:
            reason = "timeout"
    finally:
        if child is not None:
            receipt = finish(child, reason, grace=2)
            atomic_json(root / (filename + ".owned-exit.json"), receipt)
    if (reason == "timeout" or not isinstance(receipt, dict) or receipt.get("managed") is not True
            or receipt.get("child_exited") is not True or receipt.get("exit_code") != 0
            or receipt.get("remaining_owned_processes") != 0 or receipt.get("forcibly_terminated") is not False):
        raise ValueError("archive_owned_exit_unverified")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args(argv)
    root = None
    try:
        if os.name != "nt" or not re.fullmatch(r"[a-f0-9]{40}", args.commit):
            raise ValueError("windows_owned_builder_and_commit_required")
        requested = args.root.absolute()
        if not requested.is_relative_to(PROJECT / "reports") or not requested.name.startswith("release-prep-"):
            raise ValueError("dedicated_reports_root_required")
        root = safe_child(PROJECT, requested.relative_to(PROJECT))
        root.mkdir(exist_ok=False)
        first = archive_commit(root, args.commit, "candidate.zip")
        manifest = audit_archive(root / "candidate.zip", args.commit)
        second = archive_commit(root, args.commit, "reproducibility.zip")
        repeated = audit_archive(root / "reproducibility.zip", args.commit)
        if manifest != repeated:
            raise ValueError("candidate_not_reproducible")
        atomic_json(root / "release-manifest.json", manifest, 1024 * 1024)
        result = {"status": "candidate_built", "commit": args.commit, "candidate_only": True,
                  "published": False, "tag_created": False, "reproducible": True,
                  "archive_sha256": manifest["archive_sha256"], "file_count": manifest["file_count"],
                  "owned_archives": [first, second], "native_queries": 0, "model_calls": 0}
        atomic_json(root / "package-result.json", result)
        print(json.dumps({key: result[key] for key in ("status", "commit", "reproducible", "file_count", "archive_sha256")}))
        return 0
    except Exception:
        # Do not overwrite a previous build/result or serialize exception text.
        print(json.dumps({"status": "blocked", "reason": "candidate_build_failed", "raw_error_omitted": True}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
