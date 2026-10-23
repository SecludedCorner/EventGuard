"""Bounded, event-bound projection of an existing durable EventStore outbox.

The local dispatcher polls IDs without a model. Each MCP process can disclose
only its one configured event, with no names, paths, evidence text or native
queries. A durable immutable review record precedes the core receiver ACK.
Neither this receipt nor this backend proves agent execution or host safety.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time

from .events.schema import MAX_EVENT_BYTES, STATUS_VALUES, validate_event
from .events.store import EventStore, StoreError, event_payload_hash

KIND = "eventguard-bound-minimal-inbox-v1"
MAX_RECORD_BYTES = 16 * 1024
MAX_STATE_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 1000
STAGE_RESERVE = 4096
EVENT_TYPES = frozenset({"coverage.degraded", "listener.changed", "persistence.changed", "protection.changed", "monitor_gap"})
DECISIONS = frozenset({"reviewed_metadata", "needs_more_evidence"})
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_LOCKS = {}
_REGISTRY_LOCK = threading.Lock()
_UNSET = object()


class QueueInboxError(RuntimeError):
    """Fixed reason codes only; raw source values and exceptions stay private."""


def _guard(path):
    path = Path(path)
    if ".." in path.parts:
        raise QueueInboxError("inbox_parent_path_rejected")
    path = path.absolute()
    for part in [*reversed(path.parents), path]:
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise QueueInboxError("inbox_path_redirect_rejected")
    return path


def _identifier(value):
    if type(value) is not str or not _ID.fullmatch(value):
        raise QueueInboxError("invalid_inbox_identifier")
    return value


def _bytes(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _digest(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _timestamp(value):
    if type(value) is not str or len(value) > 64:
        raise QueueInboxError("inbox_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, OverflowError):
        raise QueueInboxError("inbox_timestamp_invalid") from None


def _projection(event):
    """Only fixed enums, immutable event ID and an ISO timestamp cross MCP."""
    return {"event_id": _identifier(event["event_id"]),
            "event_type": event["event_type"] if event["event_type"] in EVENT_TYPES else "unknown",
            "transition": event["transition"], "severity": event["severity"],
            "synthetic": event["synthetic"], "observed_at": _timestamp(event["observed_at"]),
            "coverage_status": event["coverage"]["status"]}


def _validate_snapshot(snapshot, identity):
    if (not isinstance(snapshot, dict)
            or set(snapshot) != {"event_id", "event_type", "transition", "severity", "synthetic", "observed_at", "coverage_status"}
            or snapshot.get("event_id") != identity
            or snapshot.get("event_type") not in EVENT_TYPES | {"unknown"}
            or snapshot.get("transition") not in {"new", "escalated", "resolved"}
            or snapshot.get("severity") not in {"info", "warning", "high", "critical"}
            or type(snapshot.get("synthetic")) is not bool
            or snapshot.get("coverage_status") not in STATUS_VALUES):
        raise QueueInboxError("inbox_snapshot_invalid")
    _timestamp(snapshot.get("observed_at"))


class QueueInbox:
    def __init__(self, source_dir, state_dir, event_id=None, allow_live=False, limits=None, *, read_only=False):
        if type(allow_live) is not bool:
            raise QueueInboxError("invalid_live_profile")
        if type(read_only) is not bool:
            raise QueueInboxError("invalid_inbox_read_only_profile")
        self._read_only = read_only
        self.source_dir = _guard(source_dir)
        self.source_path = _guard(self.source_dir / "eventguard.sqlite3")
        if not self.source_path.is_file():
            raise QueueInboxError("existing_eventstore_required")
        self.state_dir = _guard(state_dir)
        if self.state_dir == self.source_dir or self.source_dir in self.state_dir.parents:
            raise QueueInboxError("separate_inbox_state_required")
        self.event_id = _identifier(event_id) if event_id is not None else None
        self.allow_live = allow_live
        self._store = None
        if read_only:
            if not self.state_dir.is_dir():
                raise QueueInboxError("existing_inbox_state_required")
        else:
            self.state_dir.mkdir(parents=True, exist_ok=True)
        self.marker_path = _guard(self.state_dir / "inbox-state.json")
        self.policy_path = _guard(self.state_dir / "inbox-limits.json")
        marker = {"kind": KIND, "source_key": _digest(os.path.normcase(str(self.source_dir))),
                  "allow_live": allow_live, "projection": "fixed-minimal-v1"}
        with _REGISTRY_LOCK:
            self._lock = _LOCKS.setdefault(os.path.normcase(str(self.state_dir)), threading.RLock())
        if read_only:
            existing = self._read_json(self.marker_path)
            if existing is None:
                raise QueueInboxError("existing_inbox_state_required")
            if existing != marker:
                raise QueueInboxError("inbox_source_profile_conflict")
            previous = self._read_json(self.policy_path)
            if previous is None:
                raise QueueInboxError("existing_inbox_policy_required")
            from .storage_policy import limits as validated
            self.policy = validated("inbox", previous)
            return
        with self._mutation():
            existing = self._read_json(self.marker_path)
            if existing is None:
                if any(item.name not in {"inbox-owner.lock", "inbox-mutation.lock"} for item in self.state_dir.iterdir()):
                    raise QueueInboxError("dedicated_empty_inbox_state_required")
                from .runtime import atomic_json
                atomic_json(self.marker_path, marker, MAX_RECORD_BYTES)
            elif existing != marker:
                raise QueueInboxError("inbox_source_profile_conflict")
            from .storage_policy import limits as validated
            previous = self._read_json(self.policy_path)
            self.policy = validated("inbox", limits if limits is not None else previous)
            if previous != self.policy:
                from .runtime import atomic_json
                atomic_json(self.policy_path, self.policy, MAX_RECORD_BYTES)

    @classmethod
    def open_readonly(cls, source_dir, state_dir, event_id=None, allow_live=False):
        """Read retained receipt evidence without creating state or changing policy."""
        return cls(source_dir, state_dir, event_id, allow_live, read_only=True)

    @contextmanager
    def _mutation(self):
        if self._read_only:
            raise QueueInboxError("inbox_read_only")
        from .acceptance_control import FileLease
        with self._lock:
            lease = FileLease(self.state_dir / "inbox-mutation.lock")
            if not lease.acquire():
                raise QueueInboxError("inbox_state_busy")
            try:
                yield
            finally:
                lease.release()

    def _completed(self, identity):
        value = self._read_json(self._path("completed", identity))
        if value is None:
            return None
        if (set(value) != {"kind", "snapshot", "query", "result", "acked_at"}
                or value.get("kind") != "inbox-completed-v1"
                or any(not isinstance(value.get(k), dict) for k in ("snapshot", "query", "result"))
                or any(value[k].get("event_id") != identity for k in ("snapshot", "query", "result"))):
            raise QueueInboxError("inbox_completed_record_invalid")
        _timestamp(value["acked_at"])
        return value

    def _usage(self):
        return sum(_guard(p).stat().st_size for p in self.state_dir.iterdir() if p.is_file())

    def _reserve(self, replacing=None):
        total = 0
        for path in self.state_dir.glob("snapshot-*.json"):
            record = self._read_json(path)
            identity = _identifier(record.get("event_id"))
            if self._completed(identity) is not None:
                continue
            for stage in ("query", "result", "completed"):
                candidate = self._path(stage, identity)
                if candidate != replacing and not candidate.exists():
                    total += STAGE_RESERVE
        return total

    def _maintain(self, now=None, needed=0, reserve_extra=0, completed_slots=0, protect=None):
        now = time.time() if now is None else now
        candidates = []
        removed = 0
        # Upgrade legacy ACKed triples only with the original matching ACK.
        for path in self.state_dir.glob("snapshot-*.json"):
            snapshot = self._read_json(path)
            identity = _identifier(snapshot.get("event_id"))
            if self._completed(identity) is None:
                record, source = self._checked_record(identity)
                if source["delivery_status"] == "ack":
                    query, _ = self._query_record(identity, record)
                    result = self._result_record(identity, record, query)
                    if result is not None and self._ack_matches(source, result):
                        self._immutable(self._path("completed", identity), {"kind": "inbox-completed-v1",
                            "snapshot": record, "query": query, "result": result, "acked_at": result["recorded_at"]})
            if self._completed(identity) is not None:
                record, source = self._checked_record(identity)
                query, _ = self._query_record(identity, record)
                result = self._result_record(identity, record, query)
                if result is None or not self._ack_matches(source, result):
                    raise QueueInboxError("inbox_completed_ack_unconfirmed")
                for stage in ("snapshot", "query", "result"):
                    self._path(stage, identity).unlink(missing_ok=True)
        for path in self.state_dir.glob("completed-*.json"):
            raw = self._read_json(path)
            if not isinstance(raw.get("snapshot"), dict):
                raise QueueInboxError("inbox_completed_record_invalid")
            identity = _identifier(raw["snapshot"].get("event_id"))
            if path != self._path("completed", identity):
                raise QueueInboxError("inbox_completed_record_invalid")
            entry = self._completed(identity)
            candidates.append((_timestamp(entry["acked_at"]), identity, path))
        candidates.sort()
        usage, reserve = self._usage(), self._reserve()
        for stamp, identity, path in candidates:
            if identity == protect:
                continue
            expired = now-datetime.fromisoformat(stamp).timestamp() > self.policy["completed_retention_seconds"]
            pressure = usage+reserve+needed+reserve_extra > min(MAX_STATE_BYTES, self.policy["max_bytes"])
            if expired or len(candidates)-removed+completed_slots > self.policy["max_completed"] or pressure:
                record, source = self._checked_record(identity)
                query, _ = self._query_record(identity, record)
                result = self._result_record(identity, record, query)
                if result is None or not self._ack_matches(source, result):
                    raise QueueInboxError("inbox_completed_ack_unconfirmed")
                size = _guard(path).stat().st_size
                _guard(path).unlink()
                usage -= size
                removed += 1
        return {"completed_removed": removed, "storage_bytes": self._usage(), "reserved_bytes": self._reserve(),
                "active_events": len(list(self.state_dir.glob("snapshot-*.json"))),
                "completed_events": len(list(self.state_dir.glob("completed-*.json"))), "limits": dict(self.policy)}

    def maintain(self, now=None):
        with self._mutation():
            return self._maintain(now)

    @property
    def store(self):
        """Only called by the ACK path; polling never initializes/writes SQLite."""
        if self._read_only:
            raise QueueInboxError("inbox_read_only")
        if self._store is None:
            try:
                self._store = EventStore(self.source_dir)
            except (StoreError, OSError):
                raise QueueInboxError("outbox_ack_open_failed_result_preserved") from None
        return self._store

    @contextmanager
    def _readonly(self):
        db = None
        try:
            _guard(self.source_path)
            db = sqlite3.connect(self.source_path.as_uri() + "?mode=ro", uri=True, timeout=1)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            yield db
        except (sqlite3.Error, OSError):
            raise QueueInboxError("inbox_source_read_failed") from None
        finally:
            if db is not None:
                db.close()

    def delivery_reference(self, event_id):
        """Internal program admission metadata; never part of the MCP projection."""
        source = self._source_record(_identifier(event_id))
        if not source or "snapshot" not in source or source.get("delivery_status") == "ack":
            raise QueueInboxError("pending_admission_source_required")
        return {"event_id": event_id, "payload_hash": source["payload_hash"],
                "namespace": "test" if source["snapshot"]["synthetic"] else "live"}

    def pending_event_id(self):
        """Read one due, unleased candidate ID locally; no model/tool call."""
        synthetic = "" if self.allow_live else "AND json_extract(payload,'$.synthetic')=1"
        with self._readonly() as db:
            row = db.execute("""SELECT event_id FROM events
                WHERE delivery_status IN ('pending','retry')
                AND (next_retry_at IS NULL OR next_retry_at<=?)
                AND (lease_until IS NULL OR lease_until<=?) """ + synthetic +
                " ORDER BY created_at,event_id LIMIT 1", (time.time(), time.time())).fetchone()
        return _identifier(row[0]) if row else None

    def _bound(self, event_id=_UNSET):
        if self.event_id is None:
            raise QueueInboxError("bound_event_id_required")
        if event_id is not _UNSET and _identifier(event_id) != self.event_id:
            raise QueueInboxError("bound_event_id_mismatch")
        return self.event_id

    def _path(self, stage, identity):
        return _guard(self.state_dir / (stage + "-" + hashlib.sha256(identity.encode("ascii")).hexdigest() + ".json"))

    def _read_json(self, path):
        try:
            path = _guard(path)
            if not path.exists():
                return None
            with path.open("rb") as stream:
                raw = stream.read(MAX_RECORD_BYTES + 1)
            if len(raw) > MAX_RECORD_BYTES:
                raise QueueInboxError("inbox_record_capacity")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise QueueInboxError("inbox_record_invalid")
            return value
        except (OSError, ValueError):
            raise QueueInboxError("inbox_record_read_failed") from None

    def _immutable(self, path, value):
        """Fsync then atomic no-replace link; existing records are immutable."""
        if self._read_only:
            raise QueueInboxError("inbox_read_only")
        temporary = None
        try:
            encoded = _bytes(value)
            if len(encoded) > MAX_RECORD_BYTES:
                raise QueueInboxError("inbox_record_capacity")
            existing = self._read_json(path)
            if existing is not None:
                if existing != value:
                    raise QueueInboxError("inbox_immutable_record_conflict")
                return
            if path.name.startswith(("query-", "result-", "completed-")) and len(encoded) > STAGE_RESERVE:
                raise QueueInboxError("inbox_stage_reserve_exceeded")
            # Existing legacy triples may exceed the new reservation budget;
            # still let them make progress while actual bytes fit. New receive
            # admissions account for all missing stages before storing data.
            if self._usage() + len(encoded) > min(MAX_STATE_BYTES, self.policy["max_bytes"]):
                raise QueueInboxError("inbox_state_capacity_pending_preserved")
            fd, name = tempfile.mkstemp(prefix=".inbox-", suffix=".tmp", dir=self.state_dir)
            temporary = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            _guard(path)
            try:
                os.link(temporary, path)
            except FileExistsError:
                if self._read_json(path) != value:
                    raise QueueInboxError("inbox_immutable_record_conflict") from None
            # Windows guarantees atomic link creation; directory fsync is only
            # available on platforms that permit opening a directory handle.
            if os.name != "nt":
                directory_fd = os.open(str(self.state_dir), os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except (OSError, ValueError, TypeError):
            raise QueueInboxError("inbox_save_failed_pending_preserved") from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    raise QueueInboxError("inbox_temporary_cleanup_failed_pending_preserved") from None

    def _source_record(self, identity):
        with self._readonly() as db:
            row = db.execute("SELECT payload,payload_hash,delivery_status,receipt FROM events WHERE event_id=?", (identity,)).fetchone()
            if row is None:
                receipt = db.execute("SELECT payload_hash,receipt FROM receipts WHERE event_id=?", (identity,)).fetchone()
                if receipt:
                    return {"payload_hash": receipt["payload_hash"], "delivery_status": "ack", "receipt": receipt["receipt"]}
                entry = self._completed(identity)
                if entry is not None:
                    return {"payload_hash": entry["snapshot"].get("payload_hash"), "delivery_status": "ack",
                            "receipt": json.dumps({"ack_type": "receiver_persisted", "event_id": identity,
                                                   "receiver_receipt_id": entry["result"].get("result_id")})}
                raise QueueInboxError("bound_event_missing")
        try:
            if type(row["payload"]) is not str:
                raise QueueInboxError("inbox_source_event_invalid")
            if len(row["payload"].encode("utf-8")) > MAX_EVENT_BYTES:
                raise QueueInboxError("inbox_source_event_capacity")
            event = validate_event(json.loads(row["payload"]))
            if event["event_id"] != identity or event_payload_hash(event) != row["payload_hash"]:
                raise QueueInboxError("inbox_source_identity_conflict")
            if not self.allow_live and event["synthetic"] is not True:
                raise QueueInboxError("live_event_not_authorized")
            return {"payload_hash": row["payload_hash"], "snapshot": _projection(event),
                    "delivery_status": row["delivery_status"], "receipt": row["receipt"]}
        except (ValueError, TypeError, KeyError):
            raise QueueInboxError("inbox_source_event_invalid") from None

    def _snapshot_record(self, identity):
        record = self._read_json(self._path("snapshot", identity))
        if record is None:
            completed = self._completed(identity)
            record = completed["snapshot"] if completed else None
            if record is None:
                return None
        if (set(record) != {"event_id", "payload_hash", "snapshot", "received_at"}
                or record.get("event_id") != identity
                or type(record.get("payload_hash")) is not str or not _HASH.fullmatch(record["payload_hash"])):
            raise QueueInboxError("inbox_snapshot_record_invalid")
        _validate_snapshot(record["snapshot"], identity)
        _timestamp(record["received_at"])
        if not self.allow_live and record["snapshot"]["synthetic"] is not True:
            raise QueueInboxError("live_event_not_authorized")
        return record

    def _checked_record(self, identity):
        record = self._snapshot_record(identity)
        if record is None:
            raise QueueInboxError("receive_event_required")
        source = self._source_record(identity)
        if self._completed(identity) is not None and source["delivery_status"] != "ack":
            raise QueueInboxError("inbox_completed_event_reappeared_pending_preserved")
        if source["payload_hash"] != record["payload_hash"] or ("snapshot" in source and source["snapshot"] != record["snapshot"]):
            raise QueueInboxError("inbox_source_identity_conflict")
        return record, source

    def receive_event(self):
        identity = self._bound()
        with self._mutation():
            self._maintain()
            record = self._snapshot_record(identity)
            if record is None:
                source = self._source_record(identity)
                if "snapshot" not in source or source["delivery_status"] not in {"pending", "retry"}:
                    raise QueueInboxError("bound_event_not_pending")
                if len(list(self.state_dir.glob("snapshot-*.json"))) >= min(MAX_EVENTS, self.policy["max_events"]):
                    raise QueueInboxError("inbox_event_capacity_pending_preserved")
                record = {"event_id": identity, "payload_hash": source["payload_hash"],
                          "snapshot": source["snapshot"], "received_at": _utc()}
                self._maintain(needed=len(_bytes(record)), reserve_extra=3*STAGE_RESERVE)
                if self._usage()+len(_bytes(record))+self._reserve()+3*STAGE_RESERVE > min(MAX_STATE_BYTES, self.policy["max_bytes"]):
                    raise QueueInboxError("inbox_state_capacity_pending_preserved")
                self._immutable(self._path("snapshot", identity), record)
            else:
                self._checked_record(identity)
            return {"status": "event_available", "event_id": identity,
                    "snapshot": record["snapshot"], "received_at": record["received_at"]}

    def _query_record(self, identity, snapshot):
        query = self._read_json(self._path("query", identity))
        if query is None:
            completed = self._completed(identity)
            query = completed["query"] if completed else None
        expected = "query-" + _digest([identity, snapshot["payload_hash"]])[:40]
        if query is not None:
            if set(query) != {"event_id", "payload_hash", "query_id", "queried_at"} or query.get("event_id") != identity or query.get("payload_hash") != snapshot["payload_hash"] or query.get("query_id") != expected:
                raise QueueInboxError("inbox_query_identity_conflict")
            _timestamp(query["queried_at"])
        return query, expected

    def query_evidence(self, event_id):
        identity = self._bound(event_id)
        with self._mutation():
            record, _ = self._checked_record(identity)
            query, expected = self._query_record(identity, record)
            if query is None:
                query = {"event_id": identity, "payload_hash": record["payload_hash"],
                         "query_id": expected, "queried_at": _utc()}
                self._immutable(self._path("query", identity), query)
            return {"status": "stored_minimal_snapshot", "event_id": identity,
                    "query_id": query["query_id"], "snapshot": record["snapshot"],
                    "snapshot_only": True, "system_query_executed": False}

    def _result_record(self, identity, snapshot, query):
        result = self._read_json(self._path("result", identity))
        if result is None:
            completed = self._completed(identity)
            result = completed["result"] if completed else None
        if result is not None:
            fields = {"status", "event_id", "query_id", "decision", "result_id", "recorded_at", "incident_conclusion", "real_agent_wake_verified"}
            if (query is None or set(result) != fields or result.get("status") != "review_recorded"
                    or result.get("event_id") != identity or result.get("query_id") != query["query_id"]
                    or result.get("decision") not in DECISIONS or result.get("incident_conclusion") != "not_assessed"
                    or result.get("real_agent_wake_verified") is not False):
                raise QueueInboxError("inbox_result_invalid")
            expected = "result-" + _digest([identity, snapshot["payload_hash"], query["query_id"], result["decision"]])[:40]
            if result.get("result_id") != expected:
                raise QueueInboxError("inbox_result_identity_conflict")
            _timestamp(result["recorded_at"])
        return result

    @staticmethod
    def _ack_matches(source, result):
        if source["delivery_status"] != "ack":
            return False
        try:
            receipt = json.loads(source["receipt"])
            matches = (receipt.get("ack_type") == "receiver_persisted"
                       and receipt.get("event_id") == result["event_id"]
                       and receipt.get("receiver_receipt_id") == result["result_id"])
        except (ValueError, TypeError, AttributeError):
            matches = False
        if not matches:
            raise QueueInboxError("outbox_ack_identity_conflict")
        return True

    def ack_event(self, event_id, query_id, decision):
        identity, query_id = self._bound(event_id), _identifier(query_id)
        if type(decision) is not str or decision not in DECISIONS:
            raise QueueInboxError("invalid_metadata_decision")
        with self._mutation():
            record, source = self._checked_record(identity)
            query, _ = self._query_record(identity, record)
            if query is None or query["query_id"] != query_id:
                raise QueueInboxError("same_event_query_required")
            result = self._result_record(identity, record, query)
            if result is not None and result["decision"] != decision:
                raise QueueInboxError("inbox_result_decision_conflict")
            if result is None:
                result = {"status": "review_recorded", "event_id": identity, "query_id": query_id,
                          "decision": decision,
                          "result_id": "result-" + _digest([identity, record["payload_hash"], query_id, decision])[:40],
                          "recorded_at": _utc(), "incident_conclusion": "not_assessed",
                          "real_agent_wake_verified": False}
                self._immutable(self._path("result", identity), result)
            if not self._ack_matches(source, result):
                receipt = {"ack_type": "receiver_persisted", "event_id": identity,
                           "receiver_receipt_id": result["result_id"], "wake_state": "unknown",
                           "received_at": result["recorded_at"]}
                try:
                    if self.store.acknowledge(identity, receipt) is not True:
                        raise QueueInboxError("outbox_ack_failed_result_preserved")
                except StoreError:
                    raise QueueInboxError("outbox_ack_failed_result_preserved") from None
            completed = {"kind": "inbox-completed-v1", "snapshot": record, "query": query, "result": result,
                         "acked_at": result["recorded_at"]}
            self._immutable(self._path("completed", identity), completed)
            # Keep this freshly ACKed record for idempotent immediate replay;
            # older completed records rotate on the next receive/maintenance.
            for stage in ("snapshot", "query", "result"):
                self._path(stage, identity).unlink(missing_ok=True)
            self._maintain(protect=identity)
            return {**result, "outbox_acknowledged": True}

    def evidence(self, event_id):
        """Local audit reads; unbound dispatcher can inspect only saved records."""
        identity = _identifier(event_id)
        if self.event_id is not None:
            self._bound(identity)
        with self._lock:
            record = self._snapshot_record(identity)
            if record is None:
                return None
            query, _ = self._query_record(identity, record)
            result = self._result_record(identity, record, query)
            value = dict(record)
            if query is not None:
                value.update(query_id=query["query_id"], queried_at=query["queried_at"])
            if result is not None:
                value["result"] = result
            return value

    def acknowledged(self, event_id):
        identity = _identifier(event_id)
        if self.event_id is not None:
            self._bound(identity)
        with self._lock:
            evidence = self.evidence(identity)
            if evidence is None or "result" not in evidence:
                return False
            _, source = self._checked_record(identity)
            return self._ack_matches(source, evidence["result"])
