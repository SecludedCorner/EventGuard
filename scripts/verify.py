"""Fixture suite in an owned Windows guardian job; no scan/model or installation."""
from __future__ import annotations
import argparse
import ast
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))  # Optional contrib tests; core never imports them.
from eventguard.processes import spawn, finish, cleanup_owned, current_job_members
from eventguard.runtime import safe_child, atomic_json


def sources():
    result = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "scripts", "tests", "config", "playbooks", "contrib")
            for p in sorted((ROOT / folder).rglob("*")) if p.is_file() and p.suffix in {".py", ".json", ".cmd"}}
    for p in [*ROOT.glob("*.cmd"), *(ROOT / ".github").rglob("*.yml")]:
        result[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


MOCK_MODULES = ("test_events_transport", "test_rules_playbooks", "test_mcp_protocol", "test_mcp_store")


def guardian_start(child, job_name):
    return {"kind": "eventguard-verification-worker-v1", "pid": child.pid,
            "created_at": getattr(child, "created_at", None), "job_name": job_name,
            "managed": job_name is not None, "started_at": datetime.now(timezone.utc).isoformat(), "model_calls": 0}


def guardian_exit(child, job_name, output, reason, grace=.5):
    if job_name is not None:
        return finish(child, reason, grace=grace)
    # Non-Windows mock CI owns this exact Popen child, not a Windows Job or an
    # observable process tree. Keep missing creation/tree evidence explicit.
    forced, cooperative, cleanup_confirmed = False, None, True
    if child.poll() is None:
        try:
            atomic_json(output / "guardian-stop.request", {"reason": reason})
            cooperative = True
        except (OSError, ValueError):
            cooperative = False
        try:
            child.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            forced = True
            try:
                child.terminate()
                try:
                    child.wait(timeout=max(.1, grace))
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=max(.1, grace))
            except (OSError, subprocess.TimeoutExpired):
                cleanup_confirmed = False
    code = child.poll()
    return {"managed": False, "pid": child.pid, "created_at": None, "job_name": None,
            "child_exited": code is not None, "exit_code": code, "forcibly_terminated": forced,
            "remaining_owned_processes": None, "process_tree_verified": False,
            "cleanup_confirmed": cleanup_confirmed, "cooperative_stop_requested": cooperative,
            "deadline_or_owner_failure": reason in {"timeout", "owner_exception"},
            "reason": "natural_worker_exit" if code is not None and not forced else "worker_timeout_or_unconfirmed",
            "scope": "non_windows_mock_single_worker_only"}


def guardian_succeeded(receipt, scope):
    if (not receipt or receipt.get("child_exited") is not True or receipt.get("exit_code") != 0
            or receipt.get("forcibly_terminated") is not False):
        return False
    if receipt.get("managed") is True:
        return receipt.get("remaining_owned_processes") == 0
    return (scope == "mock" and receipt.get("scope") == "non_windows_mock_single_worker_only"
            and receipt.get("cleanup_confirmed") is True and receipt.get("cooperative_stop_requested") is not False
            and receipt.get("deadline_or_owner_failure") is False)


def suite_completed(value):
    """A clean exit is insufficient when discovery was empty or stopped early."""
    expected, ran = value.get("expected_tests"), value.get("tests_run")
    return (type(expected) is int and expected > 0 and type(ran) is int and ran == expected
            and value.get("stopped_early") is False and value.get("stop_requested") is False)


class PassingResult(unittest.TextTestResult):
    """Count successful parent callbacks, not failure/skip subtest records."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_tests = 0
        self._successful_case = None

    def startTest(self, test):
        self._successful_case = None
        super().startTest(test)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_tests += 1
        self._successful_case = test

    def _retract_success(self, test):
        if self._successful_case is test:
            self.passed_tests -= 1
            self._successful_case = None

    def addFailure(self, test, error):
        self._retract_success(test)
        super().addFailure(test, error)

    def addError(self, test, error):
        self._retract_success(test)
        super().addError(test, error)


def worker(output, guardian_name, scope="full", modules=()):
    evidence, residuals, syntax = [], [], []
    baseline = {}
    files = [p for folder in ("src", "scripts", "tests", "contrib") for p in (ROOT / folder).rglob("*.py")]
    for file in files:
        try:
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file.relative_to(ROOT)))
        except SyntaxError as error:
            syntax.append({"file": str(file.relative_to(ROOT)), "line": error.lineno})
    class Result(PassingResult):
        def addSuccess(self, test):
            if hasattr(test, "evidence"):
                evidence.append({"test": test.id(), **test.evidence})
            super().addSuccess(test)

        def stopTest(self, test):
            if (output / "guardian-stop.request").exists():
                self.stop()
            receipts = cleanup_owned(grace=.1)
            forced = [r for r in receipts if r.get("forcibly_terminated")]
            members = current_job_members(guardian_name) if os.name == "nt" else {}
            extra = {pid: stamp for pid, stamp in members.items() if baseline.get(pid) != stamp or stamp is None}
            until = time.monotonic()+1
            while extra and time.monotonic() < until:
                time.sleep(.01)
                members = current_job_members(guardian_name)
                extra = {pid: stamp for pid, stamp in members.items() if baseline.get(pid) != stamp or stamp is None}
            if forced or extra:
                residuals.append({"test": test.id(), "unexpected_job_members": extra, "cleanup_receipts": receipts})
                try:
                    raise AssertionError("owned test cleanup was required or descendants remain")
                except AssertionError:
                    self.addFailure(test, sys.exc_info())
                if extra:
                    self.stop()
            super().stopTest(test)
    tick = time.monotonic()
    with (output / "unit-tests.txt").open("x", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        if modules:
            sys.path.insert(0, str(ROOT / "tests"))
            suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
        elif scope == "mock":
            sys.path.insert(0, str(ROOT / "tests"))
            suite = unittest.defaultTestLoader.loadTestsFromNames(MOCK_MODULES)
        else:
            suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
        # Windows may attach a conhost to the test worker during SDK imports.
        # Account for the exact pre-test PID+creation identities, never a count.
        baseline = current_job_members(guardian_name) if os.name == "nt" else {}
        expected_tests = suite.countTestCases()
        result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Result).run(suite)
    value = {"verified_at_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
             "tests_run": result.testsRun, "expected_tests": expected_tests,
             "stopped_early": bool(result.shouldStop or result.testsRun != expected_tests),
             "stop_requested": (output / "guardian-stop.request").exists(),
             "passed": result.passed_tests,
             "failures": [test.id() for test, _ in result.failures], "errors": [test.id() for test, _ in result.errors],
             "skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
             "python_files": len(files), "syntax_errors": syntax, "duration_seconds": round(time.monotonic()-tick, 3),
             "per_test_residuals": residuals, "scope": "fixture/SDK/fake CLI plus labelled real Windows owned-job APIs; no inventory scan/model",
             "guardian_baseline_identities": baseline,
             "machine_scan_executed": False, "real_agent_woken": False, "model_calls": 0}
    value.update(verification_scope="targeted" if modules else scope, linux_native_support=False,
                 scope="fixture/pure rules/SQLite/mock only; no Linux native support" if scope == "mock" else value["scope"],
                 selected_modules=list(modules) if modules else list(MOCK_MODULES) if scope == "mock" else ["test_*.py"])
    atomic_json(output / "worker-summary.json", value, 2*1024*1024)
    atomic_json(output / "lifecycle-evidence.json", evidence, 4*1024*1024)
    return 0 if result.wasSuccessful() and suite_completed(value) and not syntax and not residuals else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument("--scope", choices=("full", "mock"), default="full")
    parser.add_argument("--module", action="append", default=[], help="只驗證指定 tests/test_*.py。可重複；仍使用原 guardian。")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--guardian-job-name", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.module and (args.scope != "full" or len(args.module) != len(set(args.module)) or
            any(not re.fullmatch(r"test_[A-Za-z0-9_]+", name) or not (ROOT / "tests" / (name+".py")).is_file()
                for name in args.module)):
        parser.error("modules must name unique existing test modules; cannot combine with mock scope")
    if not 1 <= args.timeout_seconds <= 1800:
        parser.error("test budget must be 1..1800 seconds")
    path = args.run_dir or Path("reports") / ("verify-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    absolute = path.absolute()
    if not absolute.is_relative_to(ROOT / "reports"):
        parser.error("verification output must be inside this project's reports")
    output = safe_child(ROOT, absolute.relative_to(ROOT))
    if args._worker:
        return worker(output, args.guardian_job_name, args.scope, args.module)
    output.mkdir(parents=True, exist_ok=False)
    before = sources()
    atomic_json(output / "source-manifest.json", before, 2*1024*1024)
    child, receipt = None, None
    try:
        with (output / "worker.stdout.txt").open("xb") as stdout, (output / "worker.stderr.txt").open("xb") as stderr:
            job_name = "Local\\EventGuard-" + uuid.uuid4().hex if os.name == "nt" else None
            selections = [item for name in args.module for item in ("--module", name)]
            job_args = ["--guardian-job-name", job_name] if job_name is not None else []
            child = spawn([sys.executable, "-B", str(Path(__file__).resolve()), "--_worker", "--scope", args.scope, "--run-dir", str(output), *job_args, *selections],
                          **({"job_name": job_name} if os.name == "nt" else {}), stdout=stdout, stderr=stderr)
            # Retain bounded ownership metadata even if the invoking terminal
            # disappears before the final receipt. This is not an exit proof.
            atomic_json(output / "guardian-start.json", guardian_start(child, job_name))
            deadline = time.monotonic()+args.timeout_seconds
            while child.poll() is None and time.monotonic() < deadline:
                time.sleep(.1)
            receipt = guardian_exit(child, job_name, output, "timeout" if child.poll() is None else "descendants_remaining")
    finally:
        if child is not None:
            if receipt is None:
                receipt = guardian_exit(child, job_name, output, "owner_exception", grace=.1)
            atomic_json(output / "guardian-exit.json", receipt)
    worker_path = output / "worker-summary.json"
    value = json.loads(worker_path.read_text(encoding="utf-8")) if worker_path.exists() else {"worker_summary_missing": True}
    value.update(source_unchanged=before == sources(), guardian=receipt,
                 command="python -B scripts/verify.py --scope " + args.scope + "".join(" --module "+name for name in args.module) + " --run-dir " + str(output.relative_to(ROOT)), output_dir=str(output.relative_to(ROOT)),
                 passed_checks=bool(guardian_succeeded(receipt, args.scope)
                     and before == sources() and not value.get("worker_summary_missing") and suite_completed(value)
                     and not value.get("failures") and not value.get("errors") and not value.get("per_test_residuals")))
    atomic_json(output / "verification-summary.json", value, 2*1024*1024)
    print(json.dumps(value, ensure_ascii=True))
    return 0 if value["passed_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
