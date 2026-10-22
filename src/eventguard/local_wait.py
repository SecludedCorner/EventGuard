"""One synthetic local-wait protocol experiment, not a monitor or agent runner.

LocalWait(experiment_dir) requires a new/empty dedicated experiment directory;
it creates its own marker, bounded JSON ledger, and EventStore in ``outbox``.
Producer fixtures may use ``backend.store.enqueue(synthetic_event)``.
``await wait_for_event(timeout_seconds=30)`` waits 1..45 seconds, one waiter per
experiment/process. ``query_evidence(event_id)`` reads only a delivered snapshot.
``ack_event(event_id, query_id, decision)`` accepts needs_more_evidence or
reviewed_synthetic; its durable result precedes the outbox ACK. No model,
subprocess, network, native collector, arbitrary path, or shell is available.
Expiration is an experiment stopping point, never a request for model re-polling.
The one-waiter guard is process-local, not a cross-process lease. Producers must
wait for the server-created experiment marker before opening this directory.
Small SQLite/JSON reads and atomic fsync writes are synchronous and can briefly
block the async loop; no measured background performance claim is made.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid

from .events.store import EventStore, StoreError
from .mcp.protocol import project_event

KIND = "eventguard-single-synthetic-local-wait-experiment"
MAX_LEDGER_BYTES = 256 * 1024
MAX_EVENTS = 64
MAX_WAITS = 128
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_REGISTRY_LOCK = threading.Lock()
_IO_LOCKS = {}
_WAITERS = set()


class LocalWaitError(RuntimeError):
    """Fixed error codes only, never raw stored values or paths."""


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise LocalWaitError("invalid_identifier")
    return value


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        raise LocalWaitError("stored_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise LocalWaitError("stored_timestamp_invalid") from None


def _guard(path):
    path = Path(path)
    if ".." in path.parts:
        raise LocalWaitError("experiment_parent_path_rejected")
    path = path.absolute()
    for part in [*reversed(path.parents), path]:
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise LocalWaitError("experiment_path_redirect_rejected")
    return path


def _bytes(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _digest(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


class LocalWait:
    def __init__(self, experiment_dir):
        self.directory = _guard(experiment_dir)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.marker_path = _guard(self.directory / "local-wait-experiment.json")
        self.ledger_path = _guard(self.directory / "local-wait-results.json")
        self._key = os.path.normcase(str(self.directory))
        with _REGISTRY_LOCK:
            self._lock = _IO_LOCKS.setdefault(self._key, threading.RLock())
        with self._lock:
            if not self.marker_path.exists():
                if any(self.directory.iterdir()):
                    raise LocalWaitError("dedicated_empty_experiment_directory_required")
                self.experiment_id = "experiment-" + uuid.uuid4().hex
                self._atomic(self.marker_path, {"kind": KIND, "schema_version": "1.0", "experiment_id": self.experiment_id})
            else:
                marker = self._read(self.marker_path, 1024)
                if not isinstance(marker, dict) or set(marker) != {"kind", "schema_version", "experiment_id"} or marker.get("kind") != KIND or marker.get("schema_version") != "1.0":
                    raise LocalWaitError("foreign_experiment_directory")
                self.experiment_id = _identifier(marker.get("experiment_id"))
            _guard(self.directory / "outbox")
            self.store = EventStore(self.directory / "outbox", max_events=MAX_EVENTS)
            if not self.ledger_path.exists():
                self._save({"schema_version": "1.0", "kind": KIND, "experiment_id": self.experiment_id, "events": {}, "waits": []})
            self._load()

    @staticmethod
    def _read(path, limit):
        _guard(path)
        try:
            if path.stat().st_size > limit:
                raise LocalWaitError("experiment_file_capacity")
            with path.open("rb") as stream:
                raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise LocalWaitError("experiment_file_capacity")
            return json.loads(raw)
        except (OSError, ValueError):
            raise LocalWaitError("experiment_file_invalid") from None

    def _atomic(self, path, value):
        _guard(path)
        encoded = _bytes(value)
        if len(encoded) > MAX_LEDGER_BYTES:
            raise LocalWaitError("experiment_ledger_capacity")
        temporary = _guard(self.directory / (".local-wait-" + uuid.uuid4().hex + ".tmp"))
        try:
            with temporary.open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            _guard(path)
            os.replace(temporary, path)
        except OSError:
            raise LocalWaitError("experiment_write_failed") from None
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _envelope(value):
        """Rebuild through the existing typed projection; reject extra data."""
        try:
            data = value["data"]
            core = {"schema_version": "2.0", "event_id": value["eventId"], "host_id": data["host_ref"],
                    "episode_id": data["episode_id"], "correlation_id": data["episode_id"], "sequence": 1,
                    "event_type": data["event_type"], "transition": data["transition"], "severity": data["severity"],
                    "synthetic": data["synthetic"], "observed_at": value["timestamp"], "persisted_at": value["timestamp"],
                    "evidence": data["evidence"], "coverage": {"status": data["coverage_status"]}}
            clean = project_event(core)
            if clean != value:
                raise ValueError()
            return clean
        except (KeyError, TypeError, ValueError):
            raise LocalWaitError("stored_snapshot_invalid") from None

    def _load(self):
        value = self._read(self.ledger_path, MAX_LEDGER_BYTES)
        if not isinstance(value, dict) or set(value) != {"schema_version", "kind", "experiment_id", "events", "waits"} or value.get("schema_version") != "1.0" or value.get("kind") != KIND or value.get("experiment_id") != self.experiment_id:
            raise LocalWaitError("foreign_experiment_ledger")
        events, waits = value["events"], value["waits"]
        if not isinstance(events, dict) or len(events) > MAX_EVENTS or not isinstance(waits, list) or len(waits) > MAX_WAITS:
            raise LocalWaitError("experiment_ledger_capacity")
        for identity, record in events.items():
            _identifier(identity)
            if not isinstance(record, dict) or set(record) - {"event", "delivered_at", "query_id", "queried_at", "result"} or not {"event", "delivered_at"} <= set(record):
                raise LocalWaitError("stored_snapshot_invalid")
            if self._envelope(record["event"])["eventId"] != identity:
                raise LocalWaitError("stored_snapshot_invalid")
            _timestamp(record["delivered_at"])
            if "query_id" in record:
                _identifier(record["query_id"])
                _timestamp(record.get("queried_at"))
            if "result" in record:
                result = record["result"]
                if not isinstance(result, dict) or set(result) != {"status", "event_id", "query_id", "decision", "result_id", "recorded_at", "incident_conclusion", "real_agent_wake_verified", "experiment_only"} or result.get("status") != "synthetic_result_recorded" or result.get("event_id") != identity or result.get("query_id") != record.get("query_id") or result.get("decision") not in ("needs_more_evidence", "reviewed_synthetic") or result.get("incident_conclusion") != "not_assessed" or result.get("real_agent_wake_verified") is not False or result.get("experiment_only") is not True:
                    raise LocalWaitError("stored_result_invalid")
                _identifier(result["result_id"])
                _timestamp(result["recorded_at"])
        for wait in waits:
            if not isinstance(wait, dict) or set(wait) - {"wait_id", "status", "started_at", "finished_at", "duration_seconds"} or wait.get("status") not in ("waiting", "event_available", "wait_expired", "cancelled", "error"):
                raise LocalWaitError("stored_wait_invalid")
            _identifier(wait.get("wait_id"))
            _timestamp(wait.get("started_at"))
            if wait["status"] != "waiting":
                _timestamp(wait.get("finished_at"))
                duration = wait.get("duration_seconds")
                if type(duration) not in (int, float) or not 0 <= duration < 86400:
                    raise LocalWaitError("stored_wait_invalid")
        return value

    def _save(self, ledger):
        self._atomic(self.ledger_path, ledger)

    def _finish_wait(self, wait_id, status, began):
        finished = _utc()
        duration = round(max(0, time.monotonic() - began), 3)
        with self._lock:
            ledger = self._load()
            for record in ledger["waits"]:
                if record["wait_id"] == wait_id:
                    record.update(status=status, finished_at=finished, duration_seconds=duration)
                    break
            self._save(ledger)
        return {"wait_id": wait_id, "finished_at": finished, "duration_seconds": duration}

    def _next_synthetic(self):
        """Read only candidate IDs, then only a synthetic candidate payload."""
        _guard(self.store.path)
        db = None
        try:
            db = sqlite3.connect(str(self.store.path), timeout=1)
            rows = db.execute("""SELECT event_id FROM events WHERE delivery_status IN('pending','retry')
              AND json_extract(payload,'$.synthetic')=1
              AND (next_retry_at IS NULL OR next_retry_at<=?)
              AND (lease_until IS NULL OR lease_until<=?) ORDER BY created_at,event_id LIMIT 64""", (time.time(), time.time())).fetchall()
        except sqlite3.Error:
            raise LocalWaitError("experiment_outbox_read_failed") from None
        finally:
            if db is not None:
                db.close()
        if not rows:
            return None
        try:
            record = self.store.get_event(rows[0][0])
            if record is None or record.get("synthetic") is not True:
                return None
            return project_event(record)
        except (StoreError, ValueError):
            raise LocalWaitError("experiment_synthetic_event_invalid") from None

    async def wait_for_event(self, timeout_seconds=30):
        if type(timeout_seconds) not in (int, float) or not 1 <= timeout_seconds <= 45:
            raise LocalWaitError("invalid_wait_timeout")
        with _REGISTRY_LOCK:
            if self._key in _WAITERS:
                return {"status": "busy", "experiment_only": True, "do_not_model_repoll": True}
            _WAITERS.add(self._key)
        began, started, wait_id = time.monotonic(), _utc(), "wait-" + uuid.uuid4().hex
        registered = False
        try:
            with self._lock:
                ledger = self._load()
                ledger["waits"] = ledger["waits"][-(MAX_WAITS - 1):] + [{"wait_id": wait_id, "status": "waiting", "started_at": started}]
                self._save(ledger)
                registered = True
            while True:
                envelope = self._next_synthetic()
                if envelope is not None:
                    with self._lock:
                        ledger = self._load()
                        identity = envelope["eventId"]
                        existing = ledger["events"].get(identity)
                        if existing is not None and existing["event"] != envelope:
                            raise LocalWaitError("delivered_event_identity_conflict")
                        if existing is None:
                            if len(ledger["events"]) >= MAX_EVENTS:
                                raise LocalWaitError("experiment_event_capacity")
                            ledger["events"][identity] = {"event": envelope, "delivered_at": _utc()}
                            self._save(ledger)
                    timing = self._finish_wait(wait_id, "event_available", began)
                    return {"status": "event_available", "event_id": envelope["eventId"], "event": envelope, "started_at": started, **timing, "experiment_only": True, "real_agent_wake_verified": False}
                remaining = timeout_seconds - (time.monotonic() - began)
                if remaining <= 0:
                    timing = self._finish_wait(wait_id, "wait_expired", began)
                    return {"status": "wait_expired", "started_at": started, **timing, "experiment_only": True, "do_not_model_repoll": True, "next_action": "stop_this_protocol_experiment"}
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            if registered:
                try:
                    self._finish_wait(wait_id, "cancelled", began)
                except LocalWaitError:
                    pass  # Cancellation must propagate even if storage fails.
            raise
        except Exception:
            if registered:
                self._finish_wait(wait_id, "error", began)
            raise
        finally:
            with _REGISTRY_LOCK:
                _WAITERS.discard(self._key)

    def query_evidence(self, event_id):
        identity = _identifier(event_id)
        with self._lock:
            ledger = self._load()
            record = ledger["events"].get(identity)
            if record is None:
                raise LocalWaitError("event_not_delivered_in_experiment")
            if "query_id" not in record:
                record["query_id"] = "query-" + _digest([self.experiment_id, identity, record["event"]])[:40]
                record["queried_at"] = _utc()
                self._save(ledger)
            return {"status": "synthetic_snapshot", "event_id": identity, "query_id": record["query_id"], "event": record["event"], "snapshot_only": True, "system_query_executed": False, "experiment_only": True}

    def ack_event(self, event_id, query_id, decision):
        identity, query = _identifier(event_id), _identifier(query_id)
        if not isinstance(decision, str) or decision not in ("needs_more_evidence", "reviewed_synthetic"):
            raise LocalWaitError("invalid_synthetic_decision")
        with self._lock:
            ledger = self._load()
            record = ledger["events"].get(identity)
            if record is None or record.get("query_id") != query:
                raise LocalWaitError("same_event_query_required")
            result = record.get("result")
            if result is not None and (result["query_id"] != query or result["decision"] != decision):
                raise LocalWaitError("synthetic_result_identity_conflict")
            if result is None:
                result = {"status": "synthetic_result_recorded", "event_id": identity, "query_id": query, "decision": decision,
                          "result_id": "result-" + _digest([self.experiment_id, identity, query, decision])[:40],
                          "recorded_at": _utc(), "incident_conclusion": "not_assessed", "real_agent_wake_verified": False, "experiment_only": True}
                record["result"] = result
                self._save(ledger)  # Result must survive a crash before core outbox ACK.
            receipt = {"ack_type": "receiver_persisted", "event_id": identity, "receiver_receipt_id": result["result_id"], "wake_state": "unknown"}
            try:
                acknowledged = self.store.acknowledge(identity, receipt)
            except StoreError:
                raise LocalWaitError("outbox_ack_failed_result_preserved") from None
            return {**result, "outbox_acknowledged": acknowledged}


LocalWaitBackend = LocalWait
