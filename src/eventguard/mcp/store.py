"""Local durable synthetic MCP bridge state; this module performs no transport.

All timestamps are UTC Unix epoch floats. Subscription dictionaries contain
id, owner, url, name, arguments, secret_ref, expires_at, verified_at,
previous_secret_ref, previous_valid_until, revoked, created_at and updated_at.
Secrets themselves must live in the separate vault. A delivery ``received`` is
only callback acceptance, never proof of a model turn or a closed incident.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlsplit
import uuid

from ..events.schema import validate_event, redact_text, EventValidationError

EVENT_TYPES = frozenset({"protection.changed", "listener.changed", "persistence.changed", "coverage.degraded"})
MAX_BYTES = 8 * 1024 * 1024
MAX_ATTEMPTS = 8
LEASE_SECONDS = 60
MAX_QUERIES_PER_EVENT = 20
MAX_RESULT_REVISIONS = 10
OPERATIONS = frozenset({"health", "query_listener", "query_defender", "query_persistence"})
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")


class BridgeError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class BridgeCapacityError(BridgeError):
    pass


def _json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode("ascii")).hexdigest()


def _identity(value, code="invalid_identity"):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise BridgeError(code)
    return value


def _owner(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 256 or any(ord(c) < 32 for c in value):
        raise BridgeError("invalid_owner")
    return value


def _time(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise BridgeError("invalid_timestamp")
    return float(value)


def _arguments(value):
    if not isinstance(value, dict) or set(value) != {"host_ref", "event_types"}:
        raise BridgeError("invalid_subscription_arguments")
    host = _identity(value["host_ref"], "invalid_host_ref")
    kinds = value["event_types"]
    if not isinstance(kinds, list) or len(kinds) > 4 or any(not isinstance(k, str) or k not in EVENT_TYPES for k in kinds):
        raise BridgeError("invalid_event_types")
    return {"host_ref": host, "event_types": sorted(set(kinds))}


def _subscription_identity(owner, url, name, arguments):
    owner = _owner(owner)
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        raise BridgeError("invalid_callback_url")
    try:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
            raise ValueError()
        parts.port
    except ValueError:
        raise BridgeError("invalid_callback_url") from None
    _identity(name, "invalid_event_name")
    args = _arguments(arguments)
    return owner, url, name, args


def subscription_id(owner, url, name, args):
    """Identity includes authenticated principal; event type order is canonical."""
    return "sub-" + _hash(_subscription_identity(owner, url, name, args))[:48]


def _guard(path):
    path = Path(path).absolute()
    for part in [*reversed(path.parents), path]:
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise BridgeError("data_path_redirect_rejected")
    return path


def _query_payload(value, depth=0):
    """Last defensive bound; service remains responsible for typed query fields."""
    if depth > 6:
        raise BridgeError("query_payload_limit")
    if value is None or type(value) in (bool, int):
        if type(value) is int and abs(value) > 2**63 - 1:
            raise BridgeError("query_payload_limit")
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, str):
        if len(value) > 512:
            raise BridgeError("query_payload_limit")
        return redact_text(value)
    if isinstance(value, list) and len(value) <= 100:
        return [_query_payload(v, depth + 1) for v in value]
    if isinstance(value, dict) and len(value) <= 40:
        clean = {}
        for key, item in value.items():
            if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,63}", key):
                raise BridgeError("invalid_query_field")
            if any(p in key.casefold() for p in ("command", "message", "xml", "password", "token", "secret", "credential", "authorization", "username", "account", "stderr", "traceback")):
                raise BridgeError("forbidden_query_field")
            clean[key] = _query_payload(item, depth + 1)
        return clean
    raise BridgeError("invalid_query_payload")


class BridgeStore:
    def __init__(self, directory, clock=time.time, max_events=1000, max_subscriptions=20, max_bytes=MAX_BYTES):
        if type(max_events) is not int or not 1 <= max_events <= 1000:
            raise BridgeError("invalid_event_capacity")
        if type(max_subscriptions) is not int or not 1 <= max_subscriptions <= 20:
            raise BridgeError("invalid_subscription_capacity")
        if type(max_bytes) is not int or not 65536 <= max_bytes <= MAX_BYTES:
            raise BridgeError("invalid_storage_capacity")
        self.directory = _guard(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = _guard(self.directory / "mcp-bridge.sqlite3")
        self.clock, self.max_events, self.max_subscriptions, self.max_bytes = clock, max_events, max_subscriptions, max_bytes
        if self.path.exists() and self.path.stat().st_size > max_bytes:
            raise BridgeCapacityError("database_already_over_capacity")
        with self._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS subscriptions(
              id TEXT PRIMARY KEY, owner TEXT NOT NULL, url TEXT NOT NULL, name TEXT NOT NULL,
              arguments TEXT NOT NULL, secret_ref TEXT NOT NULL, expires_at REAL NOT NULL,
              verified_at REAL NOT NULL, previous_secret_ref TEXT, previous_valid_until REAL,
              revoked INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
              owner TEXT NOT NULL, event_id TEXT NOT NULL, payload TEXT NOT NULL, payload_hash TEXT NOT NULL,
              receipt_id TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(owner,event_id));
            CREATE TABLE IF NOT EXISTS deliveries(
              delivery_id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL, owner TEXT NOT NULL,
              event_id TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
              next_retry_at REAL, lease_token TEXT, lease_until REAL, reason_code TEXT NOT NULL DEFAULT '',
              http_status INTEGER, created_at REAL NOT NULL, updated_at REAL NOT NULL,
              UNIQUE(subscription_id,owner,event_id),
              FOREIGN KEY(subscription_id) REFERENCES subscriptions(id),
              FOREIGN KEY(owner,event_id) REFERENCES events(owner,event_id));
            CREATE INDEX IF NOT EXISTS deliveries_due ON deliveries(status,next_retry_at,lease_until);
            CREATE TABLE IF NOT EXISTS queries(
              owner TEXT NOT NULL, event_id TEXT NOT NULL, request_id TEXT NOT NULL, operation TEXT NOT NULL,
              payload TEXT NOT NULL, body_hash TEXT NOT NULL, recorded_at REAL NOT NULL,
              PRIMARY KEY(owner,request_id), FOREIGN KEY(owner,event_id) REFERENCES events(owner,event_id));
            CREATE TABLE IF NOT EXISTS cases(
              owner TEXT NOT NULL, event_id TEXT NOT NULL, result_id TEXT NOT NULL, payload TEXT NOT NULL,
              body_hash TEXT NOT NULL, recorded_at REAL NOT NULL, PRIMARY KEY(owner,event_id),
              FOREIGN KEY(owner,event_id) REFERENCES events(owner,event_id));
            CREATE TABLE IF NOT EXISTS result_revisions(
              owner TEXT NOT NULL, event_id TEXT NOT NULL, result_id TEXT NOT NULL, payload TEXT NOT NULL,
              body_hash TEXT NOT NULL, recorded_at REAL NOT NULL, revision INTEGER NOT NULL,
              PRIMARY KEY(owner,event_id,body_hash), UNIQUE(owner,event_id,revision),
              FOREIGN KEY(owner,event_id) REFERENCES events(owner,event_id));
            INSERT OR IGNORE INTO result_revisions(owner,event_id,result_id,payload,body_hash,recorded_at,revision)
              SELECT owner,event_id,result_id,payload,body_hash,recorded_at,1 FROM cases;
            """)

    def _now(self, value=None):
        return _time(self.clock() if value is None else value)

    @contextmanager
    def _db(self):
        _guard(self.path)
        db = None
        try:
            db = sqlite3.connect(str(self.path), timeout=3)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA busy_timeout=3000")
            page = db.execute("PRAGMA page_size").fetchone()[0]
            db.execute("PRAGMA max_page_count=" + str(self.max_bytes // page))
            with db:
                yield db
        except sqlite3.Error as exc:
            if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
                raise BridgeCapacityError("storage_capacity") from None
            raise BridgeError("storage_error") from None
        finally:
            if db is not None:
                db.close()

    def _room(self, db, extra):
        page = db.execute("PRAGMA page_size").fetchone()[0]
        used = (db.execute("PRAGMA page_count").fetchone()[0] - db.execute("PRAGMA freelist_count").fetchone()[0]) * page
        reserve = min(1024 * 1024, self.max_bytes // 4)
        if used + extra > self.max_bytes - reserve:
            raise BridgeCapacityError("storage_capacity")

    @staticmethod
    def _sub(row):
        if row is None:
            return None
        item = dict(row)
        item["arguments"] = json.loads(item["arguments"])
        item["revoked"] = bool(item["revoked"])
        return item

    def find_subscription(self, owner, url, name, arguments):
        sid = subscription_id(owner, url, name, arguments)
        with self._db() as db:
            return self._sub(db.execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone())

    def upsert_subscription(self, owner, url, name, arguments, secret_ref, expires_at, verified_at, previous_secret_ref=None, previous_valid_until=None):
        owner, url, name, args = _subscription_identity(owner, url, name, arguments)
        sid, now = subscription_id(owner, url, name, args), self._now()
        _identity(secret_ref, "invalid_secret_reference")
        expiry, verified = _time(expires_at), _time(verified_at)
        if expiry <= now or verified > now + 1:
            raise BridgeError("invalid_subscription_time")
        if (previous_secret_ref is None) != (previous_valid_until is None):
            raise BridgeError("invalid_previous_reference")
        if previous_secret_ref is not None:
            _identity(previous_secret_ref, "invalid_secret_reference")
            previous_valid_until = _time(previous_valid_until)
            if previous_secret_ref == secret_ref or previous_valid_until > expiry:
                raise BridgeError("invalid_previous_reference")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT created_at FROM subscriptions WHERE id=?", (sid,)).fetchone()
            if existing is None and db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0] >= self.max_subscriptions:
                raise BridgeCapacityError("subscription_capacity")
            self._room(db, 8192 if existing is None else 4096)
            db.execute("""INSERT INTO subscriptions VALUES(?,?,?,?,?,?,?,?,?,?,0,?,?)
            ON CONFLICT(id) DO UPDATE SET secret_ref=excluded.secret_ref,expires_at=excluded.expires_at,
            verified_at=excluded.verified_at,previous_secret_ref=excluded.previous_secret_ref,
            previous_valid_until=excluded.previous_valid_until,revoked=0,updated_at=excluded.updated_at""",
                       (sid, owner, url, name, _json(args), secret_ref, expiry, verified, previous_secret_ref,
                        previous_valid_until, now, now))
            return self._sub(db.execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone())

    def unsubscribe(self, owner, url, name, args):
        sid, now = subscription_id(owner, url, name, args), self._now()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE subscriptions SET revoked=1,updated_at=? WHERE id=?", (now, sid))
            db.execute("UPDATE deliveries SET status='revoked',lease_token=NULL,lease_until=NULL,next_retry_at=NULL,reason_code='subscription_revoked',updated_at=? WHERE subscription_id=? AND status IN('pending','retry','inflight')", (now, sid))
        return {}

    def active_subscriptions(self, owner=None, now=None):
        current = self._now(now)
        if owner is not None:
            _owner(owner)
        with self._db() as db:
            return [self._sub(row) for row in db.execute("SELECT * FROM subscriptions WHERE revoked=0 AND expires_at>? AND (? IS NULL OR owner=?) ORDER BY id", (current, owner, owner))]

    @staticmethod
    def _event(row):
        try:
            raw = json.loads(row["payload"])
            clean = validate_event(raw)
        except (ValueError, TypeError):
            raise BridgeError("stored_event_invalid") from None
        if _hash(clean) != row["payload_hash"] or clean != raw or clean["synthetic"] is not True or clean["event_type"] not in EVENT_TYPES:
            raise BridgeError("stored_event_invalid")
        return clean

    @staticmethod
    def _receipt(row):
        return {"ack_type": "receiver_persisted", "event_id": row["event_id"], "receiver_receipt_id": row["receipt_id"], "receiver_kind": "verified_receiver", "received_at_epoch": row["created_at"], "wake_state": "unknown", "real_agent_woken": False}

    def enqueue_event(self, owner, event):
        owner, now = _owner(owner), self._now()
        try:
            clean = validate_event(event)
        except EventValidationError:
            raise BridgeError("invalid_event") from None
        if clean["synthetic"] is not True:
            raise BridgeError("synthetic_only")
        if clean["event_type"] not in EVENT_TYPES:
            raise BridgeError("unsupported_event_type")
        payload, digest = _json(clean), _hash(clean)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM events WHERE owner=? AND event_id=?", (owner, clean["event_id"])).fetchone()
            if row:
                if row["payload_hash"] != digest:
                    raise BridgeError("event_identity_conflict")
                self._event(row)
                return self._receipt(row)
            subs = [self._sub(s) for s in db.execute("SELECT * FROM subscriptions WHERE owner=? AND revoked=0 AND expires_at>?", (owner, now))]
            subs = [s for s in subs if s["arguments"]["host_ref"] == clean["host_id"] and (not s["arguments"]["event_types"] or clean["event_type"] in s["arguments"]["event_types"])]
            if not subs:
                raise BridgeError("no_matching_subscription")
            if db.execute("SELECT COUNT(*) FROM events").fetchone()[0] >= self.max_events:
                raise BridgeCapacityError("event_capacity")
            self._room(db, len(payload.encode("ascii")) + 4096 * (len(subs) + 1))
            receipt_id = "rcpt-" + uuid.uuid4().hex
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)", (owner, clean["event_id"], payload, digest, receipt_id, now))
            for sub in subs:
                did = "del-" + _hash([sub["id"], owner, clean["event_id"]])[:48]
                db.execute("INSERT INTO deliveries(delivery_id,subscription_id,owner,event_id,status,next_retry_at,created_at,updated_at) VALUES(?,?,?,?,'pending',?,?,?)", (did, sub["id"], owner, clean["event_id"], now, now, now))
            return self._receipt(db.execute("SELECT * FROM events WHERE owner=? AND event_id=?", (owner, clean["event_id"])).fetchone())

    def claim_delivery(self, now=None):
        current = self._now(now)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""UPDATE deliveries SET status='revoked',reason_code='subscription_inactive',lease_token=NULL,lease_until=NULL,next_retry_at=NULL,updated_at=?
            WHERE status IN('pending','retry','inflight') AND subscription_id IN(SELECT id FROM subscriptions WHERE revoked=1 OR expires_at<=?)""", (current, current))
            db.execute("""UPDATE deliveries SET status='failed',reason_code='delivery_uncertain',lease_token=NULL,lease_until=NULL,next_retry_at=NULL,updated_at=?
            WHERE status='inflight' AND lease_until<=? AND attempts>=?""", (current, current, MAX_ATTEMPTS))
            row = db.execute("""SELECT * FROM deliveries WHERE (status IN('pending','retry') AND next_retry_at<=? AND attempts<?)
            OR (status='inflight' AND lease_until<=? AND attempts<?) ORDER BY created_at,delivery_id LIMIT 1""", (current, MAX_ATTEMPTS, current, MAX_ATTEMPTS)).fetchone()
            if row is None:
                return None
            lease, attempt = uuid.uuid4().hex, row["attempts"] + 1
            event_row = db.execute("SELECT * FROM events WHERE owner=? AND event_id=?", (row["owner"], row["event_id"])).fetchone()
            event = self._event(event_row)
            subscription = self._sub(db.execute("SELECT * FROM subscriptions WHERE id=?", (row["subscription_id"],)).fetchone())
            db.execute("UPDATE deliveries SET status='inflight',attempts=?,lease_token=?,lease_until=?,reason_code='delivery_uncertain',updated_at=? WHERE delivery_id=?", (attempt, lease, current + LEASE_SECONDS, current, row["delivery_id"]))
            return {"delivery_id": row["delivery_id"], "lease_token": lease, "event": event, "subscription": subscription, "attempt": attempt, "lease_until": current + LEASE_SECONDS}

    def complete_delivery(self, delivery_id, lease_token, outcome, reason_code, http_status=None, now=None):
        _identity(delivery_id)
        _identity(lease_token)
        _identity(reason_code, "invalid_reason_code")
        if outcome not in ("received", "retry", "failed"):
            raise BridgeError("invalid_delivery_outcome")
        if http_status is not None and (type(http_status) is not int or not 100 <= http_status <= 599):
            raise BridgeError("invalid_http_status")
        if outcome == "received" and (http_status is None or not 200 <= http_status <= 299):
            raise BridgeError("received_requires_success_status")
        current = self._now(now)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM deliveries WHERE delivery_id=?", (delivery_id,)).fetchone()
            if row is None or row["status"] != "inflight" or row["lease_token"] != lease_token or row["lease_until"] <= current:
                raise BridgeError("stale_delivery_lease")
            sub = db.execute("SELECT revoked,expires_at FROM subscriptions WHERE id=?", (row["subscription_id"],)).fetchone()
            if sub["revoked"] or sub["expires_at"] <= current:
                raise BridgeError("subscription_inactive")
            next_at = None
            if outcome == "retry":
                if row["attempts"] >= MAX_ATTEMPTS:
                    outcome = "failed"
                else:
                    base = min(3600, 30 * 2**(row["attempts"] - 1))
                    jitter = int(_hash([delivery_id, row["attempts"]])[:8], 16) / 0xffffffff
                    next_at = current + min(3600, base * (0.8 + 0.4 * jitter))
            db.execute("UPDATE deliveries SET status=?,next_retry_at=?,lease_token=NULL,lease_until=NULL,reason_code=?,http_status=?,updated_at=? WHERE delivery_id=?", (outcome, next_at, reason_code, http_status, current, delivery_id))
            return {"delivery_id": delivery_id, "status": outcome, "attempts": row["attempts"], "next_retry_at": next_at, "reason_code": reason_code, "http_status": http_status}

    def get_event(self, owner, event_id):
        _owner(owner)
        _identity(event_id)
        with self._db() as db:
            row = db.execute("SELECT * FROM events WHERE owner=? AND event_id=?", (owner, event_id)).fetchone()
            return self._event(row) if row else None

    def record_query(self, owner, event_id, request_id, operation, result):
        _owner(owner)
        _identity(event_id)
        _identity(request_id, "invalid_request_id")
        if not isinstance(operation, str) or operation not in OPERATIONS or not isinstance(result, dict):
            raise BridgeError("invalid_query_operation")
        fields = {"schema_version", "event_id", "request_id", "operation", "source", "status", "observed_at", "coverage_status", "synthetic", "snapshot_only", "system_query_executed", "rows", "truncated", "reason_code"}
        if set(result) - fields or result.get("synthetic") is not True or result.get("snapshot_only") is not True or result.get("system_query_executed") is not False:
            raise BridgeError("invalid_query_snapshot")
        if result.get("event_id") != event_id or result.get("operation") != operation:
            raise BridgeError("query_event_mismatch")
        rows = result.get("rows")
        row_fields = {"event_type", "transition", "severity", "coverage_status", "protocol", "port", "binding_scope", "source", "status", "current"}
        if not isinstance(rows, list) or len(rows) > 20 or any(not isinstance(row, dict) or set(row) - row_fields for row in rows):
            raise BridgeError("invalid_query_rows")
        clean = _query_payload(result)
        if clean.get("request_id", request_id) != request_id:
            raise BridgeError("query_request_mismatch")
        payload = _json(clean)
        if len(payload.encode("ascii")) > 16384:
            raise BridgeError("query_payload_limit")
        digest, now = _hash([event_id, operation, clean]), self._now()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM events WHERE owner=? AND event_id=?", (owner, event_id)).fetchone():
                raise BridgeError("event_not_found")
            existing = db.execute("SELECT * FROM queries WHERE owner=? AND request_id=?", (owner, request_id)).fetchone()
            if existing:
                if existing["body_hash"] != digest:
                    raise BridgeError("query_identity_conflict")
                return self._query(existing)
            if db.execute("SELECT COUNT(*) FROM queries WHERE owner=? AND event_id=?", (owner, event_id)).fetchone()[0] >= MAX_QUERIES_PER_EVENT:
                raise BridgeCapacityError("query_capacity")
            self._room(db, len(payload) + 4096)
            db.execute("INSERT INTO queries VALUES(?,?,?,?,?,?,?)", (owner, event_id, request_id, operation, payload, digest, now))
            return self._query(db.execute("SELECT * FROM queries WHERE owner=? AND request_id=?", (owner, request_id)).fetchone())

    @staticmethod
    def _query(row):
        return {"event_id": row["event_id"], "request_id": row["request_id"], "operation": row["operation"], "result": json.loads(row["payload"]), "recorded_at": row["recorded_at"]}

    def list_queries(self, owner, event_id):
        _owner(owner)
        _identity(event_id)
        with self._db() as db:
            return [self._query(row) for row in db.execute("SELECT * FROM queries WHERE owner=? AND event_id=? ORDER BY recorded_at,request_id", (owner, event_id))]

    def record_result(self, owner, event_id, result):
        _owner(owner)
        _identity(event_id)
        if not isinstance(result, dict) or set(result) - {"decision", "evidence_request_ids", "reason_code", "run_ref", "expected_result_id"} or not {"decision", "evidence_request_ids", "reason_code"} <= set(result):
            raise BridgeError("invalid_result_fields")
        if result["decision"] not in ("needs_more_evidence", "benign_change", "requires_user_approval") or result["reason_code"] not in ("synthetic_evidence_reviewed", "coverage_incomplete", "no_matching_evidence"):
            raise BridgeError("invalid_result_decision")
        refs = result["evidence_request_ids"]
        if not isinstance(refs, list) or len(refs) > 10:
            raise BridgeError("invalid_evidence_references")
        refs = sorted(set(_identity(ref, "invalid_request_id") for ref in refs))
        clean = {"decision": result["decision"], "reason_code": result["reason_code"], "evidence_request_ids": refs}
        if "run_ref" in result:
            clean["run_ref"] = _identity(result["run_ref"], "invalid_run_reference")
        expected = result.get("expected_result_id")
        if expected is not None:
            _identity(expected, "invalid_expected_result_id")
        digest, now = _hash(clean), self._now()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM events WHERE owner=? AND event_id=?", (owner, event_id)).fetchone():
                raise BridgeError("event_not_found")
            previous = db.execute("SELECT * FROM result_revisions WHERE owner=? AND event_id=? AND body_hash=?", (owner, event_id, digest)).fetchone()
            if previous:
                return self._case(previous)
            if clean["decision"] == "benign_change" and not refs:
                raise BridgeError("benign_requires_successful_evidence")
            for ref in refs:
                query = db.execute("SELECT payload FROM queries WHERE owner=? AND event_id=? AND request_id=?", (owner, event_id, ref)).fetchone()
                if not query:
                    raise BridgeError("evidence_reference_not_found")
                if clean["decision"] == "benign_change" and json.loads(query["payload"]).get("status") != "ok":
                    raise BridgeError("benign_requires_successful_evidence")
            existing = db.execute("SELECT * FROM cases WHERE owner=? AND event_id=?", (owner, event_id)).fetchone()
            if existing:
                if expected != existing["result_id"]:
                    raise BridgeError("result_identity_conflict")
            elif expected is not None:
                raise BridgeError("result_identity_conflict")
            revision = db.execute("SELECT COUNT(*) FROM result_revisions WHERE owner=? AND event_id=?", (owner, event_id)).fetchone()[0] + 1
            if revision > MAX_RESULT_REVISIONS:
                raise BridgeCapacityError("result_revision_capacity")
            self._room(db, 8192)
            values = (owner, event_id, "res-" + _hash([owner, event_id, clean])[:48], _json(clean), digest, now)
            db.execute("INSERT INTO result_revisions VALUES(?,?,?,?,?,?,?)", (*values, revision))
            db.execute("""INSERT INTO cases VALUES(?,?,?,?,?,?) ON CONFLICT(owner,event_id) DO UPDATE SET
            result_id=excluded.result_id,payload=excluded.payload,body_hash=excluded.body_hash,recorded_at=excluded.recorded_at""", values)
            return self._case(db.execute("SELECT * FROM result_revisions WHERE owner=? AND event_id=? AND body_hash=?", (owner, event_id, digest)).fetchone())

    @staticmethod
    def _case(row):
        return {"event_id": row["event_id"], "result_id": row["result_id"], "revision": row["revision"], "status": "agent_result_recorded", "result": json.loads(row["payload"]), "recorded_at": row["recorded_at"], "platform_run_verified": False, "system_actions_performed": False}

    def get_case(self, owner, event_id):
        _owner(owner)
        _identity(event_id)
        with self._db() as db:
            row = db.execute("SELECT r.* FROM result_revisions r JOIN cases c ON c.owner=r.owner AND c.event_id=r.event_id AND c.result_id=r.result_id WHERE c.owner=? AND c.event_id=?", (owner, event_id)).fetchone()
            return self._case(row) if row else None

    def list_results(self, owner, event_id):
        """Bounded immutable audit history; replay never changes current result."""
        _owner(owner)
        _identity(event_id)
        with self._db() as db:
            return [self._case(row) for row in db.execute("SELECT * FROM result_revisions WHERE owner=? AND event_id=? ORDER BY revision", (owner, event_id))]

    def stats(self):
        now = self._now()
        with self._db() as db:
            statuses = {row[0]: row[1] for row in db.execute("SELECT status,COUNT(*) FROM deliveries GROUP BY status")}
            return {"subscriptions": db.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0],
                    "active_subscriptions": db.execute("SELECT COUNT(*) FROM subscriptions WHERE revoked=0 AND expires_at>?", (now,)).fetchone()[0],
                    "events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                    "queries": db.execute("SELECT COUNT(*) FROM queries").fetchone()[0],
                    "results": db.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
                    "result_revisions": db.execute("SELECT COUNT(*) FROM result_revisions").fetchone()[0],
                    "deliveries": {key: statuses.get(key, 0) for key in ("pending", "retry", "inflight", "received", "failed", "revoked")},
                    "database_bytes": self.path.stat().st_size, "max_bytes": self.max_bytes,
                    "synthetic_only": True, "real_agent_woken": False}
