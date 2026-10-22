"""Public synthetic IDs/fake clock only; never starts a CLI or a model."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.acceptance_control import FileLease
from eventguard.agent_budget import AUTHORITY_PATH, ROOT, BudgetAuthority, BudgetError, public_status


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 22, 4, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


def fake_exit_validator(receipt, started, attempt_id, *, require_success=False):
    # Deliberate fixture boundary: no actual child or OS exit is claimed.
    return [] if receipt.get("fixture_verified") is True else ["fixture_exit_missing"]


class AgentBudgetTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "reports").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="budget-unit-", dir=ROOT / "reports")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "authority.sqlite3"
        self.clock = Clock()
        self.authority = self.make()
        self.sequence = 0

    def make(self, **kwargs):
        return BudgetAuthority(self.path, clock=self.clock, receipt_validator=fake_exit_validator, **kwargs)

    def init(self, known_used=0):
        return self.authority.initialize(known_used=known_used)

    def token(self):
        self.sequence += 1
        return f"{self.sequence:032x}"

    def reserve(self, event=None, *, kind="dispatch", existing_attempts=0, launch_hash=None):
        token = self.token()
        event = event or f"fixture-{self.sequence}"
        self.authority.reserve(token, event, "test", "a" * 64, kind,
                               existing_attempts=existing_attempts, launch_hash=launch_hash)
        return token

    def skip(self, token):
        return self.authority.record_not_started(token, {
            "attempt_id": token, "launch_not_started": True, "capture_complete": False})

    def complete(self, token, *, forced=False, exit_code=0, launch_hash=None):
        self.authority.begin_launch(token, launch_hash=launch_hash)
        created = self.clock.now.isoformat(timespec="microseconds")
        self.authority.record_started(token, 4242, created)
        start = {"attempt_id": token, "codex_pid": 4242, "created_at": created}
        receipt = {"attempt_id": token, "fixture_verified": True,
                   "forcibly_terminated": forced, "codex_exit_code": exit_code}
        return self.authority.finalize(token, receipt, start), receipt, start

    def assertCode(self, expected, function, *args, **kwargs):
        with self.assertRaises(BudgetError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, expected)

    def test_default_path_is_installation_local_not_current_directory(self):
        self.assertEqual(AUTHORITY_PATH, ROOT / "data/agent-budget/authority.sqlite3")
        self.assertEqual(BudgetAuthority().path, AUTHORITY_PATH)

    def test_open_existing_never_creates_missing_ledger(self):
        self.assertCode("budget_unavailable", BudgetAuthority.open_existing, self.path)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.path.with_name("installation.json").exists())

    def test_unknown_bootstrap_blocks_only_its_local_day(self):
        status = self.authority.initialize()
        self.assertEqual((status["day"], status["used"], status["usage_known"]), ("2026-10-22", 5, False))
        self.assertCode("budget_bootstrap_usage_unknown", self.reserve)
        self.clock.now += timedelta(days=1)
        self.assertEqual(self.authority.status()["remaining"], 5)
        self.reserve()
        self.assertEqual(self.authority.status()["used"], 1)

    def test_initialize_is_explicit_and_cannot_reset_usage(self):
        self.init(4)
        self.assertCode("budget_already_initialized", self.authority.initialize, known_used=0)
        self.assertEqual(self.authority.status()["used"], 4)

    def test_daily_five_includes_acceptance_failures_and_not_started(self):
        self.init()
        kinds = ("acceptance", "dispatch", "retry", "acceptance", "dispatch")
        for i, kind in enumerate(kinds):
            token = self.reserve(kind=kind)
            if i == 0:
                self.skip(token)
            else:
                self.complete(token, forced=i == 1, exit_code=2 if i == 2 else 0)
        self.assertEqual((self.authority.status()["used"], self.authority.status()["remaining"]), (5, 0))
        self.assertCode("budget_exhausted", self.reserve)
        reopened = BudgetAuthority.open_existing(self.path, clock=self.clock, receipt_validator=fake_exit_validator)
        self.assertEqual(reopened.status()["used"], 5)

    def test_same_event_limit_survives_next_day_and_terminal_rotation(self):
        self.authority = self.make(max_admissions=1)
        self.init()
        for _ in range(3):
            self.skip(self.reserve("same-event"))
        self.clock.now += timedelta(days=1)
        self.assertCode("budget_per_event_exhausted", self.reserve, "same-event")
        self.assertEqual(self.authority.status()["used"], 0)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT charged_attempts FROM event_usage").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT charged_count FROM daily_usage ORDER BY day").fetchone()[0], 3)

    def test_existing_attempts_conservatively_seed_event_limit(self):
        self.init()
        self.skip(self.reserve("history-event", existing_attempts=2))
        self.assertCode("budget_per_event_exhausted", self.reserve, "history-event")
        self.assertCode("budget_per_event_exhausted", self.reserve, "already-three", existing_attempts=3)

    def test_reserve_is_idempotent_but_token_cannot_change_identity(self):
        self.init()
        token = self.reserve("same-event")
        result = self.authority.reserve(token, "same-event", "test", "a" * 64, "dispatch")
        self.assertEqual(result["attempt_id"], token)
        self.assertEqual(self.authority.status()["used"], 1)
        self.assertCode("budget_identity_conflict", self.authority.reserve,
                        token, "other-event", "test", "a" * 64, "dispatch")

    def test_same_event_with_different_payload_is_not_a_new_budget(self):
        self.init()
        self.skip(self.reserve("same-event"))
        self.assertCode("budget_identity_conflict", self.authority.reserve,
                        self.token(), "same-event", "test", "b" * 64, "dispatch")

    def test_global_active_survives_new_authority_instance_and_midnight(self):
        self.init()
        token = self.reserve()
        self.authority.begin_launch(token)
        self.clock.now += timedelta(days=1)
        other = self.make()
        self.assertCode("budget_child_exit_unconfirmed", other.reserve,
                        self.token(), "another-source-event", "live", "b" * 64, "acceptance")
        self.assertEqual(other.status()["active"]["attempt_id"], token)
        self.assertEqual(other.status()["used"], 0)

    def test_one_remaining_concurrent_admission_is_atomic(self):
        self.init(4)

        def compete(i):
            other = self.make()
            try:
                return other.reserve(f"{i:032x}", f"race-{i}", "test", "a" * 64, "acceptance")
            except BudgetError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(compete, range(1, 9)))
        self.assertEqual(sum(isinstance(value, dict) for value in results), 1)
        self.assertEqual(self.authority.status()["used"], 5)

    def test_launch_hash_binds_command_and_prompt_without_storing_them(self):
        self.init()
        digest = hashlib.sha256(b"public fixture argv and prompt").hexdigest()
        token = self.reserve(launch_hash=digest)
        self.assertCode("budget_launch_mismatch", self.authority.begin_launch, token)
        self.assertCode("budget_launch_mismatch", self.authority.begin_launch, token, launch_hash="b" * 64)
        self.authority.begin_launch(token, launch_hash=digest)
        self.assertCode("budget_launch_replayed", self.authority.begin_launch, token, launch_hash=digest)
        self.assertEqual(self.authority.status()["used"], 1)

    def test_midnight_recheck_keeps_prior_charge_and_requires_new_admission(self):
        self.clock.now = datetime(2026, 10, 22, 15, 59, 59, tzinfo=timezone.utc)
        self.init()
        token = self.reserve("midnight-event")
        self.clock.now += timedelta(seconds=2)
        self.assertCode("budget_day_changed", self.authority.begin_launch, token)
        self.skip(token)
        second = self.reserve("midnight-event")
        self.assertNotEqual(token, second)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT day,charged_count FROM daily_usage ORDER BY day").fetchall(),
                             [("2026-10-22", 1), ("2026-10-23", 1)])

    def test_clock_rollback_and_large_forward_jump_fail_closed(self):
        self.init()
        baseline = self.clock.now
        self.clock.now -= timedelta(seconds=1)
        self.assertCode("budget_clock_uncertain", self.reserve)
        self.clock.now = baseline + timedelta(hours=37)
        self.assertCode("budget_clock_uncertain", self.reserve)
        self.clock.now = baseline
        self.assertEqual(self.authority.status()["used"], 0)

    def test_naive_clock_and_invalid_inputs_are_fixed_reasons(self):
        self.clock.now = datetime(2026, 10, 22)
        self.assertCode("budget_clock_uncertain", self.authority.initialize)
        self.assertFalse(self.path.exists())
        self.clock.now = datetime(2026, 10, 22, tzinfo=timezone.utc)
        self.init()
        for bad in (True, -1, 6, "0"):
            self.assertCode("budget_invalid_input", self.authority.initialize, known_used=bad)
        self.assertCode("budget_invalid_input", self.authority.reserve,
                        self.token(), "fixture", [], "a" * 64, "dispatch")
        self.assertCode("budget_invalid_input", self.reserve, kind="mock")

    def test_missing_marker_or_db_after_initialization_never_resets(self):
        self.init(4)
        marker = self.path.with_name("installation.json")
        original = marker.read_bytes()
        marker.unlink()
        self.assertCode("budget_unavailable", self.authority.status)
        self.assertFalse(marker.exists())
        marker.write_bytes(original)
        self.path.unlink()
        self.assertCode("budget_unavailable", self.authority.status)
        self.assertFalse(self.path.exists())

    def test_corrupt_database_and_marker_are_not_reinitialized(self):
        self.init()
        self.path.write_bytes(b"public fixture corrupt sqlite")
        self.assertCode("budget_unavailable", self.authority.status)
        self.assertCode("budget_already_initialized", self.authority.initialize)

    def test_authority_copy_to_new_path_has_wrong_installation_binding(self):
        self.init()
        copied = Path(self.temp.name) / "copied"
        copied.mkdir()
        target = copied / "authority.sqlite3"
        target.write_bytes(self.path.read_bytes())
        (copied / "installation.json").write_bytes(self.path.with_name("installation.json").read_bytes())
        self.assertCode("budget_unavailable", BudgetAuthority.open_existing, target, clock=self.clock)

    def test_busy_sqlite_or_file_lease_does_not_spawn_or_reset(self):
        self.init(2)
        with closing(sqlite3.connect(self.path, timeout=0)) as db, db:
            db.execute("BEGIN EXCLUSIVE")
            self.assertCode("budget_unavailable", self.reserve)
            db.rollback()
        lease = FileLease(self.path.with_name("authority.lock"))
        self.assertTrue(lease.acquire())
        try:
            self.assertCode("budget_unavailable", self.reserve)
        finally:
            lease.release()
        self.assertEqual(self.authority.status()["used"], 2)

    def test_positive_reserved_skip_does_not_refund_or_allow_replay(self):
        self.init()
        token = self.reserve()
        self.skip(token)  # Owner's positive no-child proof, not missing files.
        self.skip(token)  # Receipt replay is idempotent, never another launch.
        self.assertEqual(self.authority.status()["used"], 1)
        self.assertCode("budget_launch_replayed", self.authority.begin_launch, token)

    def test_launch_intent_without_pid_cannot_be_cleared_as_not_started(self):
        self.init()
        token = self.reserve()
        with self.authority.launch_lease():
            self.authority.begin_launch(token)
            self.assertCode("budget_not_started_unconfirmed", self.skip, token)
        # A crashed owner's released lease is not a no-child receipt.
        other = self.make()
        self.assertCode("budget_not_started_unconfirmed", other.record_not_started, token,
                        {"attempt_id": token, "launch_not_started": True, "capture_complete": False})
        self.assertEqual(other.status()["active"]["state"], "launch_intent")
        self.assertEqual(other.status()["used"], 1)

    def test_launch_lease_is_exclusive_but_never_clears_active(self):
        self.init()
        token = self.reserve()
        with self.authority.launch_lease():
            with self.assertRaises(BudgetError) as raised:
                with self.make().launch_lease():
                    self.fail("a competing launcher acquired the lease")
            self.assertEqual(raised.exception.code, "budget_launch_busy")
        self.assertEqual(self.authority.status()["active"]["attempt_id"], token)

    def test_live_launch_owner_can_abort_before_os_create_without_refund(self):
        self.init()
        token = self.reserve()
        proof = {"attempt_id": token, "launch_not_started": True, "capture_complete": False}
        with self.authority.launch_lease() as permit:
            self.authority.begin_launch(token)
            self.authority.abort_before_spawn(token, proof, permit)
            self.assertCode("budget_launch_permit_invalid", permit.mark_spawn_called)
        self.assertEqual(self.authority.status()["used"], 1)
        self.assertIsNone(self.authority.status()["active"])
        self.assertEqual(self.authority.admission(token)["state"], "not_started")
        self.skip(token)  # Same stored proof is still an idempotent read.

    def test_spawn_called_permit_cannot_abort_even_without_pid_receipt(self):
        self.init()
        token = self.reserve()
        proof = {"attempt_id": token, "launch_not_started": True, "capture_complete": False}
        with self.authority.launch_lease() as permit:
            self.authority.begin_launch(token)
            permit.mark_spawn_called()  # Only a marker; deliberately no subprocess.
            self.assertCode("budget_launch_permit_invalid", self.authority.abort_before_spawn, token, proof, permit)
            self.assertCode("budget_launch_permit_invalid", permit.mark_spawn_called)
        self.assertEqual(self.authority.status()["active"]["state"], "launch_intent")
        self.assertEqual(self.authority.status()["used"], 1)

    def test_fake_foreign_or_expired_capability_cannot_clear_intent(self):
        self.init()
        token = self.reserve()
        proof = {"attempt_id": token, "launch_not_started": True, "capture_complete": False}
        with self.authority.launch_lease() as permit:
            self.authority.begin_launch(token)
            self.assertCode("budget_launch_permit_invalid", self.authority.abort_before_spawn, token, proof, object())
            self.assertCode("budget_launch_permit_invalid", self.make().abort_before_spawn, token, proof, permit)
            self.assertCode("budget_launch_permit_invalid", self.authority.abort_before_spawn, "f" * 32, proof, permit)
        self.assertCode("budget_launch_permit_invalid", self.authority.abort_before_spawn, token, proof, permit)
        self.assertCode("budget_launch_permit_invalid", permit.mark_spawn_called)
        self.assertCode("budget_not_started_unconfirmed", self.skip, token)
        self.assertEqual(self.authority.status()["active"]["state"], "launch_intent")

    def test_capability_is_bound_to_the_launching_thread(self):
        self.init()
        token = self.reserve()
        proof = {"attempt_id": token, "launch_not_started": True, "capture_complete": False}
        with self.authority.launch_lease() as permit:
            self.authority.begin_launch(token)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.authority.abort_before_spawn, token, proof, permit)
                self.assertCode("budget_launch_permit_invalid", future.result)
            self.authority.abort_before_spawn(token, proof, permit)
        self.assertIsNone(self.authority.status()["active"])

    def test_unmatched_not_started_proof_and_started_child_do_not_clear_gate(self):
        self.init()
        token = self.reserve()
        self.assertCode("budget_not_started_unconfirmed", self.authority.record_not_started,
                        token, {"attempt_id": token, "launch_not_started": 1, "capture_complete": False})
        self.assertCode("budget_not_started_unconfirmed", self.authority.record_not_started,
                        token, {"attempt_id": "f" * 32, "launch_not_started": True, "capture_complete": False})
        self.authority.begin_launch(token)
        self.authority.record_started(token, 4242, self.clock.now.isoformat())
        self.assertCode("budget_not_started_unconfirmed", self.skip, token)
        self.assertEqual(self.authority.status()["active"]["state"], "started")

    def test_finalize_requires_verified_receipt_and_persistent_child_identity(self):
        self.init()
        token = self.reserve()
        self.authority.begin_launch(token)
        stamp = self.clock.now.isoformat()
        self.authority.record_started(token, 4242, stamp)
        start = {"attempt_id": token, "codex_pid": 4242, "created_at": stamp}
        receipt = {"fixture_verified": True, "codex_exit_code": 0, "forcibly_terminated": False}
        self.assertCode("budget_exit_unconfirmed", self.authority.finalize, token, {}, start)
        self.assertCode("budget_exit_unconfirmed", self.authority.finalize,
                        token, receipt, {**start, "codex_pid": 4243})
        self.assertCode("budget_exit_unconfirmed", self.authority.finalize,
                        token, receipt, {**start, "created_at": "2026-10-22T00:00:00+00:00"})
        self.authority.finalize(token, receipt, start)
        self.authority.finalize(token, receipt, start)
        self.assertIsNone(self.authority.status()["active"])
        self.assertEqual(self.authority.status()["used"], 1)

    def test_forced_and_nonzero_exit_release_gate_but_never_refund(self):
        self.init()
        forced, _, _ = self.complete(self.reserve(), forced=True, exit_code=1460)
        failed, _, _ = self.complete(self.reserve(), exit_code=3)
        self.assertEqual(forced["terminal_reason"], "forcibly_terminated")
        self.assertEqual(failed["terminal_reason"], "nonzero_exit")
        self.assertEqual(self.authority.status()["used"], 2)

    def test_default_validator_accepts_actual_writer_schema(self):
        # Saved dictionaries only; no child/model was actually created.
        self.authority = BudgetAuthority(self.path, clock=self.clock)
        self.init()
        token = self.reserve()
        self.authority.begin_launch(token)
        stamp = self.clock.now.isoformat(timespec="microseconds")
        self.authority.record_started(token, 4242, stamp)
        start = {"attempt_id": token, "codex_pid": 4242, "created_at": stamp}
        receipt = {"attempt_id": token, "codex_pid": 4242, "codex_exit_code": 0,
                   "capture_complete": True, "child_exited": True, "forcibly_terminated": False,
                   "stdout_truncated": False, "stderr_truncated": False,
                   "stop_reason": "descendants_remaining",
                   "process": {"managed": True, "pid": 4242, "created_at": stamp,
                               "child_exited": True, "exit_code": 0,
                               "remaining_owned_processes": 0, "forcibly_terminated": False,
                               "reason": "natural_exit", "shutdown_requested_reason": "descendants_remaining"}}
        for invalid in ({**receipt, "child_exited": False},
                        {**receipt, "process": {**receipt["process"], "remaining_owned_processes": 1}},
                        {**receipt, "process": {**receipt["process"], "created_at": "2026-10-22T00:00:00+00:00"}},
                        {**receipt, "process": {**receipt["process"], "exit_code": 3}}):
            self.assertCode("budget_exit_unconfirmed", self.authority.finalize, token, invalid, start)
            self.assertEqual(self.authority.status()["active"]["attempt_id"], token)
        result = self.authority.finalize(token, receipt, start)
        self.assertEqual(result["terminal_reason"], "natural_exit")
        self.assertIsNone(self.authority.status()["active"])

    def test_default_validator_known_forced_exit_is_failed_but_not_unknown(self):
        self.authority = BudgetAuthority(self.path, clock=self.clock)
        self.init()
        token = self.reserve()
        self.authority.begin_launch(token)
        stamp = self.clock.now.isoformat(timespec="microseconds")
        self.authority.record_started(token, 4242, stamp)
        start = {"attempt_id": token, "codex_pid": 4242, "created_at": stamp}
        receipt = {"attempt_id": token, "codex_pid": 4242, "codex_exit_code": 1460,
                   "capture_complete": False, "child_exited": True, "forcibly_terminated": True,
                   "process": {"managed": True, "pid": 4242, "created_at": stamp,
                               "child_exited": True, "exit_code": 1460,
                               "remaining_owned_processes": 0, "forcibly_terminated": True}}
        result = self.authority.finalize(token, receipt, start)
        self.assertEqual(result["terminal_reason"], "forcibly_terminated")
        self.assertEqual(self.authority.status()["used"], 1)

    def test_record_started_cannot_swap_pid_or_creation_identity(self):
        self.init()
        token = self.reserve()
        self.authority.begin_launch(token)
        stamp = self.clock.now.isoformat()
        self.authority.record_started(token, 4242, stamp)
        self.authority.record_started(token, 4242, stamp)
        self.assertCode("budget_identity_conflict", self.authority.record_started, token, 4243, stamp)

    def test_terminal_rotation_preserves_daily_event_counts(self):
        self.authority = self.make(max_admissions=1)
        self.init()
        first = self.reserve("first")
        self.skip(first)
        self.skip(self.reserve("second"))
        self.assertCode("budget_admission_missing", self.authority.admission, first)
        self.assertCode("budget_admission_retired", self.authority.reserve,
                        first, "first", "test", "a" * 64, "dispatch")
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT count(*) FROM admissions").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT sum(charged_attempts) FROM event_usage").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT charged_count FROM daily_usage").fetchone()[0], 2)
            retired = db.execute("SELECT attempt_id,retired_at_utc FROM retired_attempts").fetchone()
            self.assertEqual(retired, (first, self.clock.now.isoformat(timespec="microseconds")))
        capacity = self.authority.status()["capacity"]
        self.assertEqual(capacity["retired_attempts"], 1)
        self.assertEqual(capacity["retired_logical_bytes"], 64)

    def test_unresolved_admission_cannot_be_pruned_to_make_capacity(self):
        self.authority = self.make(max_admissions=1)
        self.init()
        token = self.reserve()
        before = self.authority.admission(token)
        self.assertCode("budget_child_exit_unconfirmed", self.reserve)
        self.assertEqual(self.authority.admission(token), before)

    def test_daily_summary_capacity_is_bounded_without_resetting_history(self):
        self.authority = self.make(max_completed_days=1)
        self.init()
        self.skip(self.reserve())
        self.clock.now += timedelta(days=1)
        self.assertCode("budget_capacity", self.reserve)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT * FROM daily_usage").fetchall(), [("2026-10-22", 1)])

    def test_full_page_capacity_rolls_back_usage_and_event_state(self):
        self.authority = self.make(max_bytes=65536)
        self.init()
        # Public padding occupies free pages; no model or child is involved.
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE fixture_padding(payload BLOB)")
            db.execute("INSERT INTO fixture_padding VALUES(?)", (b"p" * 8192,))
        self.assertCode("budget_capacity", self.reserve)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute("SELECT charged_count FROM daily_usage").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM admissions").fetchone()[0], 0)
            db.execute("DELETE FROM fixture_padding")
        self.skip(self.reserve())
        self.assertEqual(self.authority.status()["used"], 1)

    def test_inconsistent_unresolved_rows_block_instead_of_resetting_active(self):
        self.init()
        self.reserve()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM global_active")
        self.assertCode("budget_unavailable", self.authority.status)

    def test_public_status_does_not_initialize(self):
        with patch("eventguard.agent_budget.BudgetAuthority.open_existing", side_effect=BudgetError("budget_unavailable")):
            self.assertEqual(public_status(), {"state": "blocked", "reason": "budget_unavailable",
                                               "account_limit_enforced": False})
        self.assertFalse(self.path.exists())

    def test_no_runtime_flag_or_unknown_kind_can_exempt_real_launches(self):
        self.init()
        with self.assertRaises(TypeError):
            self.authority.reserve(self.token(), "fixture", "test", "a" * 64, "dispatch", synthetic=True)
        self.assertCode("budget_invalid_input", self.reserve, kind="fake")
        self.assertEqual(self.authority.status()["used"], 0)


if __name__ == "__main__":
    unittest.main()
