"""Verify a candidate against external pins; optionally smoke only its isolated synthetic CLI."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
sys.path.insert(0, str(PROJECT / "scripts"))
from package_candidate import audit_archive, MAX_ARCHIVE
from eventguard.processes import spawn, finish
from eventguard.runtime import atomic_json, safe_child

MAX_MANIFEST = 1024 * 1024
MAX_OUTPUT = 256 * 1024


class CandidateError(ValueError):
    """Only fixed reasons created by this verifier may appear in its receipt."""


def bounded_bytes(path, limit):
    path = Path(path)
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise CandidateError("regular_input_required")
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise CandidateError("input_size_limit")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CandidateError("duplicate_json_key")
        result[key] = value
    return result


def verify_inputs(archive, declared, expected_commit, expected_sha256):
    """Caller supplies trust pins; declared metadata is never the trust anchor."""
    if (not re.fullmatch(r"[a-f0-9]{40}", expected_commit)
            or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256)):
        raise CandidateError("external_pins_invalid")
    if hashlib.sha256(bounded_bytes(archive, MAX_ARCHIVE)).hexdigest() != expected_sha256:
        raise CandidateError("external_archive_hash_mismatch")
    try:
        manifest = json.loads(declared, object_pairs_hook=unique_object)
        actual = audit_archive(archive, expected_commit)
        # JSON comparison preserves numeric types (True/1 and 1.0/1 differ).
        if json.dumps(manifest, sort_keys=True, allow_nan=False) != json.dumps(actual, sort_keys=True):
            raise CandidateError("manifest_content_mismatch")
    except CandidateError:
        raise
    except Exception:
        raise CandidateError("archive_or_manifest_invalid") from None
    return actual


def extract_verified(archive, manifest, root):
    """Only our new directory is written; ZIP modes/links are never restored."""
    unpacked = root / "unpacked"
    unpacked.mkdir(exist_ok=False)
    copy = unpacked / "EventGuard"
    copy.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        for name, record in manifest["files"].items():
            target = safe_child(copy, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            data = bundle.read("EventGuard/" + name)
            if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise CandidateError("extracted_file_mismatch")
            with target.open("xb") as stream:
                stream.write(data)
    return copy


def natural_exit(receipt):
    return (isinstance(receipt, dict) and receipt.get("managed") is True
            and receipt.get("child_exited") is True and type(receipt.get("exit_code")) is int
            and receipt["exit_code"] == 0 and type(receipt.get("remaining_owned_processes")) is int
            and receipt["remaining_owned_processes"] == 0
            and receipt.get("forcibly_terminated") is False and receipt.get("reason") == "natural_exit")


def cli(copy, root, label, arguments, receipts):
    child, receipt = None, None
    reason = "owner_exception"
    output = root / (label + ".json")
    try:
        with output.open("xb") as stream:
            child = spawn([sys.executable, "-B", str(copy / "scripts/eventguard.py"),
                           "--format", "json", *arguments], cwd=copy,
                          stdout=stream, stderr=subprocess.DEVNULL)
            try:
                child.wait(timeout=15)
                reason = "descendants_remaining"
            except subprocess.TimeoutExpired:
                reason = "timeout"
    finally:
        if child is not None:
            receipt = finish(child, reason, grace=2)
            receipt = {**receipt, "step": label}
            atomic_json(root / (label + ".owned-exit.json"), receipt)
            receipts.append(receipt)
    if reason == "timeout" or not natural_exit(receipt):
        raise CandidateError("cli_timeout_or_exit_unverified")
    try:
        value = json.loads(bounded_bytes(output, MAX_OUTPUT), object_pairs_hook=unique_object)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except Exception:
        raise CandidateError("cli_output_invalid") from None


def smoke(copy, root, manifest, receipts):
    emitted = cli(copy, root, "01-emit", ["synthetic", "emit", "--scenario", "listener"], receipts)
    event_id = emitted.get("event_id")
    if not isinstance(event_id, str) or not re.fullmatch(r"evt-[a-f0-9]{32}", event_id):
        raise CandidateError("synthetic_event_id_invalid")
    listed = cli(copy, root, "02-list", ["events", "list", "--namespace", "test"], receipts)
    saved = cli(copy, root, "03-investigate", ["events", "investigate", "--namespace", "test",
                                               "--event-id", event_id], receipts)
    database_path = safe_child(copy, "data/test/eventguard.sqlite3")
    before_read = hashlib.sha256(bounded_bytes(database_path, 16 * 1024 * 1024)).hexdigest()
    detail = cli(copy, root, "04-detail", ["events", "detail", "--namespace", "test",
                                          "--event-id", event_id], receipts)
    checks = {
        "source_files_unchanged": all(hashlib.sha256(bounded_bytes(safe_child(copy, name), 32 * 1024 * 1024)).hexdigest()
                                      == record["sha256"] for name, record in manifest["files"].items()),
        "one_synthetic_event_emitted": emitted.get("inserted") is True and emitted.get("synthetic") is True,
        "no_real_agent_woken": emitted.get("real_agent_woken") is False,
        "one_matching_listed_event": listed.get("total") == 1 and len(listed.get("events", [])) == 1
                                     and listed["events"][0].get("event_id") == event_id,
        "saved_case_survives_reopen": saved["case"] == detail["investigation"]["case"]
                                      and saved["case"]["anchor_event_id"] == event_id,
        "no_ack_model_or_native_query": saved.get("ack_performed") is False and saved.get("model_calls") == 0
                                        and saved.get("native_queries") == 0,
        "detail_did_not_change_database": before_read == hashlib.sha256(bounded_bytes(database_path, 16 * 1024 * 1024)).hexdigest(),
        "all_four_owned_jobs_natural_exit": len(receipts) == 4 and all(natural_exit(r) for r in receipts),
        "no_live_namespace_created": not (copy / "data/live").exists(),
    }
    with closing(sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)) as database:
        database.execute("PRAGMA query_only=ON")
        checks.update(
            one_source_event=database.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1,
            source_still_pending=database.execute("SELECT delivery_status FROM events").fetchone()[0] == "pending",
            one_saved_case=database.execute("SELECT COUNT(*) FROM event_investigations").fetchone()[0] == 1,
            zero_ack_receipts=database.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0,
        )
    if not all(checks.values()):
        raise CandidateError("synthetic_smoke_checks_failed")
    return checks


def reports_path(value):
    path = Path(value).absolute()
    if not path.is_relative_to(PROJECT / "reports"):
        raise CandidateError("reports_path_required")
    return safe_child(PROJECT, path.relative_to(PROJECT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true", help="Execute the pinned package's synthetic CLI in Windows private Jobs")
    args = parser.parse_args(argv)
    root, receipts = None, []
    result = {"kind": "eventguard-candidate-verification-v1", "passed": False,
              "smoke_requested": args.smoke, "synthetic_only": True, "model_calls": 0,
              "native_queries": 0, "real_agent_retested": False, "published": False}
    try:
        requested = reports_path(args.root)
        if not requested.name.startswith("candidate-verify-"):
            raise CandidateError("dedicated_root_required")
        requested.mkdir(exist_ok=False)
        root = requested  # Never write a receipt into a pre-existing directory.
        if args.smoke and os.name != "nt":
            raise CandidateError("windows_private_job_required_for_smoke")
        raw = bounded_bytes(reports_path(args.archive), MAX_ARCHIVE)
        declared = bounded_bytes(reports_path(args.manifest), MAX_MANIFEST)
        snapshot = root / "verified-input.zip"
        with snapshot.open("xb") as stream:
            stream.write(raw)
        actual = verify_inputs(snapshot, declared, args.expected_commit, args.expected_sha256)
        result.update(candidate_commit=actual["revision"], archive_sha256=actual["archive_sha256"],
                      file_count=actual["file_count"], manifest_verified=True)
        atomic_json(root / "verified-manifest.json", actual, MAX_MANIFEST)
        if args.smoke:
            copy = extract_verified(snapshot, actual, root)
            result["smoke_checks"] = smoke(copy, root, actual, receipts)
        result.update(passed=True, reason="candidate_verified", smoke_executed=args.smoke)
    except CandidateError as error:
        result["reason"] = str(error)
    except Exception:
        result["reason"] = "candidate_verification_failed"
    result["owned_steps"] = receipts
    if root is not None:
        atomic_json(root / "verification-result.json", result)
    print(json.dumps({k: result[k] for k in ("passed", "reason", "smoke_requested")}))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
