"""Bounded local operation receipts shared by the GUI and agent adapter.

Records what EventGuard did, never prompts, raw parameters or tool contents.
This is application history, not an authenticated audit trail against the user.
"""
from __future__ import annotations

from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import re
import sqlite3
import time
import uuid

from .runtime import Runtime
from .processes import identity

APP_ID = 0x45564741
MAX_ROWS = 256
MAX_ACTIVE = 32
MAX_BYTES = 2 * 1024 * 1024
OPERATIONS = frozenset({"capabilities", "status", "overview", "observation", "stop", "monitor",
    "events", "inspect_event", "diagnose_event", "receive_event", "ack_event", "retry_event",
    "report", "background_start", "background_status", "background_stop", "gui_start", "gui_pause",
    "gui_inspect", "gui_investigate", "gui_receive_permission", "gui_automatic_agent"})
ACTORS = frozenset({"agent_mcp", "human_gui"})
CODE = re.compile(r"[a-z][a-z0-9_]{0,95}\Z")


class ActivityError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _code(value):
    return value if isinstance(value, str) and CODE.fullmatch(value) else None


def _owner():
    try:
        value = identity()
    except (OSError, ValueError, RuntimeError):
        raise ActivityError("activity_owner_unavailable") from None
    if value.get("state") != "alive" or type(value.get("pid")) is not int or not value.get("created_at"):
        raise ActivityError("activity_owner_unavailable")
    return value["pid"], value["created_at"]


def _gone(pid, stamp):
    try:
        current = identity(pid)
    except (OSError, ValueError, RuntimeError):
        return False  # Unknown ownership is never proof of completed work.
    return (current.get("state") in {"missing", "exited"}
            or current.get("state") == "alive" and isinstance(current.get("created_at"), str)
            and current["created_at"] != stamp)


def _path(root):
    return Runtime(root).path("data/activity.sqlite3")


@contextmanager
def _write(root):
    try:
        path = _path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_BYTES:
            raise ActivityError("activity_database_limit")
    except ActivityError:
        raise
    except (OSError, ValueError, RuntimeError):
        raise ActivityError("activity_storage_unavailable") from None
    try:
        with closing(sqlite3.connect(path, timeout=2)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA max_page_count=512")
            db.execute("BEGIN IMMEDIATE")
            app = db.execute("PRAGMA application_id").fetchone()[0]
            if app == 0 and not db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                db.execute("PRAGMA application_id=" + str(APP_ID))
                db.execute("""CREATE TABLE activity (
                    id TEXT PRIMARY KEY, actor TEXT NOT NULL, operation TEXT NOT NULL,
                    namespace TEXT NOT NULL, target_ref TEXT, started_at TEXT NOT NULL,
                    finished_at TEXT, state TEXT NOT NULL, result_code TEXT, reason_code TEXT,
                    owner_pid INTEGER NOT NULL, owner_created_at TEXT NOT NULL, elapsed_ms INTEGER)""")
            elif app != APP_ID:
                raise ActivityError("activity_database_identity_invalid")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
    except ActivityError:
        raise
    except (OSError, sqlite3.Error, ValueError):
        raise ActivityError("activity_storage_unavailable") from None


def begin(root, actor, operation, namespace, target=None):
    if actor not in ACTORS or operation not in OPERATIONS or namespace not in {"live", "test"}:
        raise ActivityError("activity_input_invalid")
    # Only an opaque hash of an identifier is retained, never free input.
    target_ref = hashlib.sha256(target.encode()).hexdigest()[:16] if isinstance(target, str) else None
    pid, stamp = _owner()
    token = uuid.uuid4().hex
    with _write(root) as db:
        active = db.execute("SELECT id,owner_pid,owner_created_at FROM activity WHERE state='running' LIMIT ?", (MAX_ACTIVE + 1,)).fetchall()
        for row in active:
            if _gone(row["owner_pid"], row["owner_created_at"]):
                db.execute("UPDATE activity SET state='interrupted',finished_at=?,reason_code='owner_exit_without_completion' WHERE id=?",
                           (_now(), row["id"]))
        count = db.execute("SELECT COUNT(*) FROM activity WHERE state='running'").fetchone()[0]
        if count >= MAX_ACTIVE:
            raise ActivityError("activity_active_capacity")
        total = db.execute("SELECT COUNT(*) FROM activity").fetchone()[0]
        if total >= MAX_ROWS:
            db.execute("DELETE FROM activity WHERE id IN (SELECT id FROM activity WHERE state!='running' ORDER BY started_at,id LIMIT ?)",
                       (total - MAX_ROWS + 1,))
        db.execute("INSERT INTO activity VALUES (?,?,?,?,?,?,NULL,'running',NULL,NULL,?,?,NULL)",
                   (token, actor, operation, namespace, target_ref, _now(), pid, stamp))
    return token


def complete(root, token, result, elapsed_ms, *, raised=False):
    value = result if isinstance(result, dict) else {}
    code = _code(value.get("state", value.get("status")))
    reason = _code(value.get("reason", value.get("error_code")))
    failed = raised or code in {"error", "invalid_request", "shutdown_unconfirmed", "stop_not_persisted", "startup_failed"}
    state = "failed" if failed else "blocked" if code in {"blocked", "denied", "busy"} else "completed"
    with _write(root) as db:
        count = db.execute("UPDATE activity SET finished_at=?,state=?,result_code=?,reason_code=?,elapsed_ms=? WHERE id=? AND state='running'",
                           (_now(), state, code, "operation_raised" if raised else reason,
                            max(0, min(int(elapsed_ms), 2**31-1)), token)).rowcount
        if count != 1:
            raise ActivityError("activity_completion_identity_invalid")


def call(root, actor, operation, namespace, function, target=None, *, allow_unrecorded_stop=False):
    """Persist intent before doing work; never retry an uncertain operation."""
    try:
        token = begin(root, actor, operation, namespace, target)
    except ActivityError as error:
        if operation in {"stop", "background_stop", "gui_pause"} or allow_unrecorded_stop:
            # Logging failure must never prevent a human from stopping work.
            result = function()
            return dict(result, activity_warning=str(error)) if isinstance(result, dict) else result
        return {"status": "blocked", "reason": str(error), "operation_started": False,
                "model_calls": 0}
    started = time.monotonic()
    try:
        result = function()
    except BaseException:
        try:
            complete(root, token, None, (time.monotonic()-started)*1000, raised=True)
        except ActivityError:
            pass  # Durable running intent remains; never invent completion.
        raise
    try:
        complete(root, token, result, (time.monotonic()-started)*1000)
    except ActivityError:
        return {"status": "error", "reason": "activity_completion_not_persisted", "activity_id": token,
                "operation_may_have_completed": True, "automatic_retry_allowed": False}
    return result


def snapshot(root, namespace="live", limit=100):
    if namespace not in {"live", "test"} or type(limit) is not int or not 1 <= limit <= MAX_ROWS:
        raise ValueError("activity_view_invalid")
    unavailable = {"state": "unavailable", "reason": "activity_history_unavailable", "entries": [],
                   "total": None, "active": None, "limit": limit, "retention_limit": MAX_ROWS, "truncated": None}
    try:
        path = _path(root)
        exists = path.exists()
    except (OSError, ValueError, RuntimeError):
        return unavailable
    if not exists:
        return {"state": "not_created", "entries": [], "total": 0, "active": 0,
                "limit": limit, "retention_limit": MAX_ROWS, "truncated": False}
    try:
        if path.stat().st_size > MAX_BYTES:
            raise ActivityError("activity_database_limit")
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
            db.row_factory = sqlite3.Row
            if db.execute("PRAGMA application_id").fetchone()[0] != APP_ID:
                raise ActivityError("activity_database_identity_invalid")
            total = db.execute("SELECT COUNT(*) FROM activity WHERE namespace=?", (namespace,)).fetchone()[0]
            active = db.execute("SELECT COUNT(*) FROM activity WHERE namespace=? AND state='running'", (namespace,)).fetchone()[0]
            rows = db.execute("SELECT * FROM activity WHERE namespace=? ORDER BY (state='running') DESC,started_at DESC,id DESC LIMIT ?", (namespace, limit)).fetchall()
        entries = []
        for row in rows:
            value = dict(row)
            if (value["actor"] not in ACTORS or value["operation"] not in OPERATIONS
                    or value["state"] not in {"running", "completed", "blocked", "failed", "interrupted"}
                    or not isinstance(value["id"], str) or not re.fullmatch(r"[0-9a-f]{32}", value["id"])
                    or type(value["owner_pid"]) is not int or not 1 <= value["owner_pid"] <= 2**32-1
                    or any(value[key] is not None and _code(value[key]) != value[key] for key in ("result_code", "reason_code"))
                    or value["target_ref"] is not None and (not isinstance(value["target_ref"], str)
                        or not re.fullmatch(r"[0-9a-f]{16}", value["target_ref"]))
                    or value["elapsed_ms"] is not None and (type(value["elapsed_ms"]) is not int or not 0 <= value["elapsed_ms"] <= 2**31-1)):
                raise ActivityError("activity_record_invalid")
            for key in ("started_at", "finished_at", "owner_created_at"):
                stamp = value[key]
                if key == "finished_at" and stamp is None:
                    continue
                if not isinstance(stamp, str) or len(stamp) > 80 or datetime.fromisoformat(stamp).utcoffset() is None:
                    raise ActivityError("activity_record_invalid")
            if value["state"] == "running" and _gone(value["owner_pid"], value["owner_created_at"]):
                value.update(state="interrupted", reason_code="owner_exit_without_completion")
                active -= 1
            entries.append({key: value[key] for key in ("id", "actor", "operation", "namespace", "target_ref",
                "started_at", "finished_at", "state", "result_code", "reason_code", "elapsed_ms")})
        return {"state": "available", "entries": entries, "total": total, "active": active,
                "limit": limit, "retention_limit": MAX_ROWS, "truncated": total > len(entries),
                "scope": "EventGuard entry points only; not chat thoughts, shell history or external actions"}
    except (ActivityError, OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        return unavailable
