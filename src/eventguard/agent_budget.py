"""One fail-closed, installation-local admission authority for optional models.

This is an application guard, not an account limit or a same-user tamper boundary.
No normal entry point creates a ledger. Test code may construct an isolated path
and clock directly; production launchers use only the module's fixed authority.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid

from .acceptance_control import FileLease
from .local_paths import _guard

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PATH = ROOT / "data/agent-budget/authority.sqlite3"
KIND = "eventguard-agent-budget-v1"
DAY_ZONE = timezone(timedelta(hours=8))
DAILY_LIMIT = 5
EVENT_LIMIT = 3
TERMINAL_RESERVE = 8192
_TOKEN = re.compile(r"[0-9a-f]{32}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_KINDS = frozenset({"dispatch", "acceptance", "retry"})
_STATES = frozenset({"reserved", "launch_intent", "started", "completed", "not_started"})


class BudgetError(RuntimeError):
    """Only a bounded reason code crosses the operator boundary."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _LaunchPermit:
    """Short-lived proof that this controller has not called OS creation yet."""

    def __init__(self, authority):
        self.authority = authority
        self.thread_id = threading.get_ident()
        self.alive = True
        self.spawn_called = False
        self.aborted = False
        self.attempt_id = None

    def mark_spawn_called(self):
        self.authority._permit_check(self, self.attempt_id)
        self.spawn_called = True


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise BudgetError("budget_clock_uncertain")
    try:
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise BudgetError("budget_clock_uncertain") from None


def _stamp(value):
    return value.isoformat(timespec="microseconds")


def _parse(value):
    try:
        if not isinstance(value, str) or len(value) > 64:
            raise ValueError
        return _utc(datetime.fromisoformat(value))
    except (ValueError, TypeError, OverflowError):
        raise BudgetError("budget_unavailable") from None


def _token(value):
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise BudgetError("budget_invalid_input")


def _digest(value, *, optional=False):
    if value is None and optional:
        return
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise BudgetError("budget_invalid_input")


def _exit_errors(receipt, started, attempt_id, *, require_success=False):
    from .capture_receipt import validate_receipt
    return validate_receipt(receipt, started, attempt_id, require_success=require_success)


class BudgetAuthority:
    def __init__(self, path=None, *, clock=None, max_bytes=1048576,
                 max_admissions=1024, max_completed_days=366, receipt_validator=None):
        try:
            self.path = _guard(AUTHORITY_PATH if path is None else path)
        except (OSError, ValueError, RuntimeError):
            raise BudgetError("budget_unavailable") from None
        self.marker = self.path.with_name("installation.json")
        self.lock = self.path.with_name("authority.lock")
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.validator = receipt_validator or _exit_errors
        for value, minimum, maximum in ((max_bytes, 65536, 1048576),
                                        (max_admissions, 1, 1024),
                                        (max_completed_days, 1, 366)):
            if type(value) is not int or not minimum <= value <= maximum:
                raise BudgetError("budget_invalid_policy")
        self.max_bytes, self.max_admissions = max_bytes, max_admissions
        self.max_completed_days = max_completed_days
        self._launch_permit = None

    @classmethod
    def open_existing(cls, path=None, **kwargs):
        authority = cls(path, **kwargs)
        with authority._transaction():
            pass
        return authority

    def _canonical(self):
        return hashlib.sha256(os.path.normcase(str(self.path)).encode("utf-8")).hexdigest()

    @contextmanager
    def launch_lease(self):
        """Capture holds this across final gate, OS create and started receipt.

        Releasing a file lock proves nothing about prior children. The durable
        active admission remains authoritative after an owner crashes.
        """
        self._marker()
        lease, permit = None, None
        try:
            lease = FileLease(self.path.with_name("authority.launch.lock"))
            if not lease.acquire():
                raise BudgetError("budget_launch_busy")
            permit = _LaunchPermit(self)
            self._launch_permit = permit
            yield permit
        except BudgetError:
            raise
        except (OSError, ValueError, RuntimeError):
            raise BudgetError("budget_unavailable") from None
        finally:
            if permit is not None:
                permit.alive = False
                if self._launch_permit is permit:
                    self._launch_permit = None
            if lease is not None:
                lease.release()

    def _permit_check(self, permit, attempt_id):
        if (type(permit) is not _LaunchPermit or permit.authority is not self
                or self._launch_permit is not permit or not permit.alive
                or permit.thread_id != threading.get_ident() or permit.spawn_called
                or permit.aborted or attempt_id is None or permit.attempt_id != attempt_id):
            raise BudgetError("budget_launch_permit_invalid")

    def _marker(self):
        try:
            _guard(self.path)
            _guard(self.marker)
            _guard(self.lock)
            if (not self.path.is_file() or self.path.stat().st_size > self.max_bytes
                    or self.marker.stat().st_size > 2048):
                raise ValueError
            value = json.loads(self.marker.read_text(encoding="utf-8"))
            if (set(value) != {"kind", "installation_id", "canonical_authority"}
                    or value["kind"] != KIND or value["canonical_authority"] != self._canonical()
                    or not isinstance(value["installation_id"], str)
                    or not _TOKEN.fullmatch(value["installation_id"])):
                raise ValueError
            return value
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            raise BudgetError("budget_unavailable") from None

    @contextmanager
    def _transaction(self):
        marker = self._marker()  # Never connect with create permissions.
        lease, db = FileLease(self.lock), None
        try:
            if not lease.acquire():
                raise BudgetError("budget_unavailable")
            if marker != self._marker():
                raise BudgetError("budget_unavailable")
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=0)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            page_size = db.execute("PRAGMA page_size").fetchone()[0]
            if db.execute("PRAGMA max_page_count=" + str((self.max_bytes - 2048) // page_size)).fetchone()[0] * page_size > self.max_bytes:
                raise BudgetError("budget_unavailable")
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise BudgetError("budget_unavailable")
            db.execute("BEGIN IMMEDIATE")
            self._policy(db, marker)
            yield db
            db.commit()
        except BudgetError:
            if db is not None:
                db.rollback()
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError, RuntimeError):
            if db is not None:
                db.rollback()
            raise BudgetError("budget_unavailable") from None
        finally:
            if db is not None:
                db.close()
            lease.release()

    def _policy(self, db, marker=None):
        value = db.execute("SELECT * FROM policy WHERE singleton=1").fetchone()
        marker = marker or self._marker()
        if (value is None or value["kind"] != KIND or value["schema_version"] != 1
                or value["installation_id"] != marker["installation_id"]
                or value["canonical_authority"] != marker["canonical_authority"]
                or value["offset_minutes"] != 480 or value["daily_limit"] != DAILY_LIMIT
                or value["max_bytes"] != self.max_bytes
                or value["max_admissions"] != self.max_admissions
                or value["max_completed_days"] != self.max_completed_days
                or value["bootstrap_unknown"] not in (0, 1)):
            raise BudgetError("budget_unavailable")
        pending = db.execute("SELECT attempt_id FROM admissions WHERE state IN ('reserved','launch_intent','started')").fetchall()
        active = self._active(db)
        if len(pending) > 1 or bool(pending) != bool(active) or pending and pending[0][0] != active:
            raise BudgetError("budget_unavailable")
        return value

    def initialize(self, known_used=None):
        """Explicit bootstrap only; unknown previous usage blocks this local day."""
        if known_used is not None and (type(known_used) is not int or not 0 <= known_used <= DAILY_LIMIT):
            raise BudgetError("budget_invalid_input")
        if self.path.exists() or self.marker.exists():
            raise BudgetError("budget_already_initialized")
        now = _utc(self.clock())
        day = now.astimezone(DAY_ZONE).date().isoformat()
        identity = uuid.uuid4().hex
        marker = {"kind": KIND, "installation_id": identity, "canonical_authority": self._canonical()}
        db = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _guard(self.path)
            # A partial bootstrap remains visible and cannot silently reinitialize.
            with self.marker.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(marker, stream, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            db = sqlite3.connect(self.path, timeout=0)
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA max_page_count=" + str((self.max_bytes - 2048) // 4096))
            db.executescript("""
                CREATE TABLE policy(singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    kind TEXT NOT NULL, schema_version INTEGER NOT NULL,
                    installation_id TEXT NOT NULL, canonical_authority TEXT NOT NULL,
                    offset_minutes INTEGER NOT NULL, daily_limit INTEGER NOT NULL,
                    high_water_day TEXT NOT NULL, last_observed_utc TEXT NOT NULL,
                    bootstrap_day TEXT NOT NULL, bootstrap_unknown INTEGER NOT NULL,
                    max_bytes INTEGER NOT NULL, max_admissions INTEGER NOT NULL,
                    max_completed_days INTEGER NOT NULL);
                CREATE TABLE daily_usage(day TEXT PRIMARY KEY, charged_count INTEGER NOT NULL
                    CHECK(charged_count BETWEEN 0 AND 5));
                CREATE TABLE event_usage(namespace TEXT NOT NULL, event_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL, charged_attempts INTEGER NOT NULL
                    CHECK(charged_attempts BETWEEN 0 AND 3), PRIMARY KEY(namespace,event_id));
                CREATE TABLE admissions(attempt_id TEXT PRIMARY KEY, namespace TEXT NOT NULL,
                    event_id TEXT NOT NULL, payload_hash TEXT NOT NULL, kind TEXT NOT NULL,
                    day TEXT NOT NULL, state TEXT NOT NULL, charged_at TEXT NOT NULL,
                    launch_hash TEXT, launch_intent_at TEXT, pid INTEGER, created_at TEXT,
                    exit_evidence_hash TEXT, terminal_reason TEXT);
                CREATE TABLE global_active(singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    attempt_id TEXT NOT NULL UNIQUE REFERENCES admissions(attempt_id));
                CREATE TABLE retired_attempts(attempt_id TEXT PRIMARY KEY, retired_at_utc TEXT NOT NULL);
                """)
            db.execute("INSERT INTO policy VALUES(1,?,1,?,?,480,5,?,?,?,?,?,?,?)",
                       (KIND, identity, self._canonical(), day, _stamp(now), day,
                        int(known_used is None), self.max_bytes, self.max_admissions, self.max_completed_days))
            db.execute("INSERT INTO daily_usage VALUES(?,?)", (day, DAILY_LIMIT if known_used is None else known_used))
            db.commit()
        except (OSError, sqlite3.Error, ValueError, TypeError, RuntimeError):
            raise BudgetError("budget_unavailable") from None
        finally:
            if db is not None:
                db.close()
        return self.status()

    def _time(self, db):
        now = _utc(self.clock())
        policy = self._policy(db)
        previous = _parse(policy["last_observed_utc"])
        day = now.astimezone(DAY_ZONE).date().isoformat()
        if (now < previous or day < policy["high_water_day"]
                or (now - previous).total_seconds() > 36 * 3600):
            raise BudgetError("budget_clock_uncertain")
        db.execute("UPDATE policy SET high_water_day=?,last_observed_utc=? WHERE singleton=1",
                   (max(day, policy["high_water_day"]), _stamp(now)))
        return now, day

    @staticmethod
    def _admission(db, attempt_id):
        row = db.execute("SELECT * FROM admissions WHERE attempt_id=?", (attempt_id,)).fetchone()
        if row is None or row["state"] not in _STATES:
            raise BudgetError("budget_admission_missing")
        return dict(row)

    @staticmethod
    def _active(db):
        row = db.execute("SELECT attempt_id FROM global_active WHERE singleton=1").fetchone()
        return row[0] if row else None

    @staticmethod
    def _used(db, day):
        row = db.execute("SELECT charged_count FROM daily_usage WHERE day=?", (day,)).fetchone()
        return row[0] if row else 0

    def _capacity(self, db, *, reserve=False):
        page_size = db.execute("PRAGMA page_size").fetchone()[0]
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        free = db.execute("PRAGMA freelist_count").fetchone()[0]
        occupied = (pages - free) * page_size + self.marker.stat().st_size
        if occupied + (TERMINAL_RESERVE if reserve else 0) > self.max_bytes:
            raise BudgetError("budget_capacity")
        return {"database_bytes": self.path.stat().st_size,
                "occupied_bytes": occupied,
                "max_bytes": self.max_bytes,
                "admissions": db.execute("SELECT count(*) FROM admissions").fetchone()[0],
                "retired_attempts": db.execute("SELECT count(*) FROM retired_attempts").fetchone()[0],
                "retired_logical_bytes": db.execute("SELECT coalesce(sum(length(attempt_id)+length(retired_at_utc)),0) FROM retired_attempts").fetchone()[0],
                "daily_summaries": db.execute("SELECT count(*) FROM daily_usage").fetchone()[0],
                "event_summaries": db.execute("SELECT count(*) FROM event_usage").fetchone()[0]}

    def status(self):
        with self._transaction() as db:
            _, day = self._time(db)
            policy, used = self._policy(db), self._used(db, day)
            active_id = self._active(db)
            active = self._admission(db, active_id) if active_id else None
            reason = ("budget_child_exit_unconfirmed" if active and active["state"] != "reserved"
                      else "budget_active_attempt" if active else
                      "budget_bootstrap_usage_unknown" if policy["bootstrap_unknown"] and day == policy["bootstrap_day"]
                      else "budget_exhausted" if used >= DAILY_LIMIT else None)
            return {"state": "blocked" if reason else "ready", "reason": reason,
                    "kind": KIND, "day": day, "utc_offset_minutes": 480,
                    "daily_limit": DAILY_LIMIT, "used": used,
                    "usage_known": not (policy["bootstrap_unknown"] and day == policy["bootstrap_day"]),
                    "remaining": max(0, DAILY_LIMIT - used), "active": active,
                    "capacity": self._capacity(db), "account_limit_enforced": False}

    def admission(self, attempt_id):
        _token(attempt_id)
        with self._transaction() as db:
            return self._admission(db, attempt_id)

    def _maintain(self, db, day):
        count = db.execute("SELECT count(*) FROM admissions").fetchone()[0]
        if count >= self.max_admissions:
            remove = count - self.max_admissions + 1
            rows = db.execute("""SELECT attempt_id FROM admissions
                WHERE state IN ('completed','not_started')
                AND attempt_id NOT IN (SELECT attempt_id FROM global_active)
                ORDER BY charged_at,attempt_id LIMIT ?""", (remove,)).fetchall()
            for row in rows:
                db.execute("INSERT INTO retired_attempts VALUES(?,?)", (row[0], self._policy(db)["last_observed_utc"]))
                db.execute("DELETE FROM admissions WHERE attempt_id=?", (row[0],))
        if db.execute("SELECT count(*) FROM admissions").fetchone()[0] >= self.max_admissions:
            raise BudgetError("budget_capacity")
        days = db.execute("SELECT count(*) FROM daily_usage").fetchone()[0]
        if not db.execute("SELECT 1 FROM daily_usage WHERE day=?", (day,)).fetchone() and days >= self.max_completed_days:
            raise BudgetError("budget_capacity")
        self._capacity(db, reserve=True)

    def reserve(self, attempt_id, event_id, namespace, payload_hash, kind, existing_attempts=0, *, launch_hash=None):
        _token(attempt_id)
        _digest(payload_hash)
        _digest(launch_hash, optional=True)
        if (not isinstance(event_id, str) or not _IDENTIFIER.fullmatch(event_id)
                or type(namespace) is not str or namespace not in {"live", "test"}
                or type(kind) is not str or kind not in _KINDS
                or type(existing_attempts) is not int or not 0 <= existing_attempts <= EVENT_LIMIT):
            raise BudgetError("budget_invalid_input")
        with self._transaction() as db:
            now, day = self._time(db)
            old = db.execute("SELECT * FROM admissions WHERE attempt_id=?", (attempt_id,)).fetchone()
            if old is not None:
                if any(old[key] != value for key, value in (("event_id", event_id), ("namespace", namespace),
                                                           ("payload_hash", payload_hash), ("kind", kind),
                                                           ("launch_hash", launch_hash))):
                    raise BudgetError("budget_identity_conflict")
                return dict(old)
            if db.execute("SELECT 1 FROM retired_attempts WHERE attempt_id=?", (attempt_id,)).fetchone():
                raise BudgetError("budget_admission_retired")
            existing = db.execute("SELECT * FROM event_usage WHERE namespace=? AND event_id=?",
                                  (namespace, event_id)).fetchone()
            if existing and existing["payload_hash"] != payload_hash:
                raise BudgetError("budget_identity_conflict")
            attempts = max(existing["charged_attempts"] if existing else 0, existing_attempts)
            if attempts >= EVENT_LIMIT:
                raise BudgetError("budget_per_event_exhausted")
            if self._active(db):
                raise BudgetError("budget_child_exit_unconfirmed")
            policy = self._policy(db)
            if policy["bootstrap_unknown"] and day == policy["bootstrap_day"]:
                raise BudgetError("budget_bootstrap_usage_unknown")
            if self._used(db, day) >= DAILY_LIMIT:
                raise BudgetError("budget_exhausted")
            self._maintain(db, day)
            db.execute("INSERT INTO daily_usage VALUES(?,1) ON CONFLICT(day) DO UPDATE SET charged_count=charged_count+1", (day,))
            db.execute("""INSERT INTO event_usage VALUES(?,?,?,?)
                ON CONFLICT(namespace,event_id) DO UPDATE SET charged_attempts=excluded.charged_attempts""",
                       (namespace, event_id, payload_hash, attempts + 1))
            db.execute("""INSERT INTO admissions(attempt_id,namespace,event_id,payload_hash,kind,day,state,charged_at,launch_hash)
                VALUES(?,?,?,?,?,?,'reserved',?,?)""",
                       (attempt_id, namespace, event_id, payload_hash, kind, day, _stamp(now), launch_hash))
            db.execute("INSERT INTO global_active VALUES(1,?)", (attempt_id,))
            self._capacity(db, reserve=True)
            return self._admission(db, attempt_id)

    def begin_launch(self, attempt_id, *, launch_hash=None):
        _token(attempt_id)
        _digest(launch_hash, optional=True)
        with self._transaction() as db:
            now, day = self._time(db)
            row = self._admission(db, attempt_id)
            if row["launch_hash"] != launch_hash:
                raise BudgetError("budget_launch_mismatch")
            if self._active(db) != attempt_id or row["state"] != "reserved":
                raise BudgetError("budget_launch_replayed")
            if row["day"] != day:
                raise BudgetError("budget_day_changed")
            db.execute("UPDATE admissions SET state='launch_intent',launch_intent_at=? WHERE attempt_id=?",
                       (_stamp(now), attempt_id))
            permit = self._launch_permit
            if permit is not None:
                if (not permit.alive or permit.thread_id != threading.get_ident()
                        or permit.spawn_called or permit.aborted or permit.attempt_id is not None):
                    raise BudgetError("budget_launch_permit_invalid")
                permit.attempt_id = attempt_id
            return self._admission(db, attempt_id)

    def record_started(self, attempt_id, pid, created_at):
        _token(attempt_id)
        if type(pid) is not int or not 1 <= pid <= 2**32 - 1:
            raise BudgetError("budget_invalid_input")
        _parse(created_at)
        with self._transaction() as db:
            row = self._admission(db, attempt_id)
            if (self._active(db) != attempt_id or row["state"] not in {"launch_intent", "started"}
                    or row["pid"] is not None and (row["pid"] != pid or row["created_at"] != created_at)):
                raise BudgetError("budget_identity_conflict")
            db.execute("UPDATE admissions SET state='started',pid=?,created_at=? WHERE attempt_id=?",
                       (pid, created_at, attempt_id))
            return self._admission(db, attempt_id)

    def finalize(self, attempt_id, receipt, started):
        _token(attempt_id)
        try:
            errors = self.validator(receipt, started, attempt_id, require_success=False)
            if errors != []:
                raise BudgetError("budget_exit_unconfirmed")
            evidence_hash = hashlib.sha256(json.dumps({"receipt": receipt, "started": started},
                                                       sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        except BudgetError:
            raise
        except (TypeError, ValueError, KeyError, ImportError, RuntimeError):
            raise BudgetError("budget_exit_unconfirmed") from None
        with self._transaction() as db:
            row = self._admission(db, attempt_id)
            if row["state"] == "completed" and row["exit_evidence_hash"] == evidence_hash:
                return row
            if (self._active(db) != attempt_id or row["state"] != "started"
                    or not isinstance(started, dict) or started.get("codex_pid") != row["pid"]
                    or started.get("created_at") != row["created_at"]):
                raise BudgetError("budget_exit_unconfirmed")
            reason = "forcibly_terminated" if receipt.get("forcibly_terminated") is True else (
                "natural_exit" if receipt.get("codex_exit_code") == 0 else "nonzero_exit")
            db.execute("UPDATE admissions SET state='completed',exit_evidence_hash=?,terminal_reason=? WHERE attempt_id=?",
                       (evidence_hash, reason, attempt_id))
            db.execute("DELETE FROM global_active WHERE singleton=1 AND attempt_id=?", (attempt_id,))
            return self._admission(db, attempt_id)

    def record_not_started(self, attempt_id, proof):
        _token(attempt_id)
        expected = {"attempt_id": attempt_id, "launch_not_started": True, "capture_complete": False}
        if (type(proof) is not dict or proof != expected
                or proof.get("launch_not_started") is not True or proof.get("capture_complete") is not False):
            raise BudgetError("budget_not_started_unconfirmed")
        proof_hash = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
        with self._transaction() as db:
            row = self._admission(db, attempt_id)
            if row["state"] == "not_started" and row["exit_evidence_hash"] == proof_hash:
                return row
            if (self._active(db) != attempt_id or row["state"] != "reserved"
                    or row["pid"] is not None or row["created_at"] is not None):
                raise BudgetError("budget_not_started_unconfirmed")
            db.execute("UPDATE admissions SET state='not_started',exit_evidence_hash=?,terminal_reason='not_started' WHERE attempt_id=?",
                       (proof_hash, attempt_id))
            db.execute("DELETE FROM global_active WHERE singleton=1 AND attempt_id=?", (attempt_id,))
            return self._admission(db, attempt_id)

    def abort_before_spawn(self, attempt_id, proof, permit):
        """Only the live launch owner can attest its final gate skipped OS create.

        No capability survives a crash. Calling mark_spawn_called before entering
        spawn permanently disables this path, including when spawn raises.
        """
        _token(attempt_id)
        self._permit_check(permit, attempt_id)
        expected = {"attempt_id": attempt_id, "launch_not_started": True, "capture_complete": False}
        if (type(proof) is not dict or proof != expected
                or proof.get("launch_not_started") is not True or proof.get("capture_complete") is not False):
            raise BudgetError("budget_not_started_unconfirmed")
        proof_hash = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
        with self._transaction() as db:
            row = self._admission(db, attempt_id)
            if (self._active(db) != attempt_id or row["state"] != "launch_intent"
                    or row["pid"] is not None or row["created_at"] is not None):
                raise BudgetError("budget_not_started_unconfirmed")
            db.execute("UPDATE admissions SET state='not_started',exit_evidence_hash=?,terminal_reason='not_started' WHERE attempt_id=?",
                       (proof_hash, attempt_id))
            db.execute("DELETE FROM global_active WHERE singleton=1 AND attempt_id=?", (attempt_id,))
        permit.aborted = True
        return self.admission(attempt_id)


def public_status():
    """No initialization, discovery of other homes, or model calls."""
    try:
        return BudgetAuthority.open_existing().status()
    except BudgetError as error:
        return {"state": "blocked", "reason": error.code, "account_limit_enforced": False}
