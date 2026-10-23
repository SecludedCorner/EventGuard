"""Bounded CloudEvents export and read-only delivery inspection.

This is an adapter over the existing outbox/inbox, not a receiver or queue.
The caller supplies an opaque, persistent producer UUID; reads never invent a
new installation identity. Only the existing seven-field snapshot is exported.
Neither an exported envelope nor receipt evidence proves model execution.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid

from .events.schema import MAX_EVENT_BYTES, validate_event
from .events.store import event_payload_hash, validate_receipt, StoreError
from .queue_inbox import (QueueInbox, QueueInboxError, _guard, _identifier,
                          _projection, _timestamp, _validate_snapshot)

MAX_ENVELOPE_BYTES = 4096
ENVELOPE_TYPE = "org.eventguard.snapshot.v1"
SCHEMA_URI = "urn:eventguard:snapshot:1"
_FIELDS = frozenset({"specversion", "id", "source", "type", "time",
                     "datacontenttype", "dataschema", "data"})
_HASH = re.compile(r"[a-f0-9]{64}\Z")
_TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")


class EventIngressError(ValueError):
    """Fixed reason codes; never include untrusted event text or file paths."""


def _encoded(value):
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise EventIngressError("ingress_invalid_json") from None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EventIngressError("ingress_duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise EventIngressError("ingress_invalid_json")


def _scope(producer_id):
    if type(producer_id) is not str:
        raise EventIngressError("ingress_persistent_producer_scope_required")
    value = producer_id.removeprefix("urn:uuid:")
    try:
        identity = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise EventIngressError("ingress_invalid_producer_scope") from None
    # UUID1 contains machine-derived metadata. This profile admits only random
    # UUID4 identities, explicitly provisioned once by the installation owner.
    if identity.version != 4 or str(identity) != value:
        raise EventIngressError("ingress_invalid_producer_scope")
    return "urn:uuid:" + value


def validate_envelope(value):
    """Strictly validate and canonicalize this *profile* of CloudEvents 1.0.

    Unknown fields/extensions are rejected, including in ``data``. Equivalent
    UTC offsets and JSON whitespace do not change the canonical wire hash.
    No schema URL is fetched and no external string is interpreted as a command.
    """
    if isinstance(value, (str, bytes)):
        try:
            raw = value.encode("utf-8") if isinstance(value, str) else value
            if len(raw) > MAX_ENVELOPE_BYTES:
                raise EventIngressError("ingress_envelope_capacity")
            value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject_constant)
        except EventIngressError:
            raise
        except (ValueError, UnicodeError, RecursionError):
            raise EventIngressError("ingress_invalid_json") from None
    if type(value) is not dict or set(value) != _FIELDS:
        raise EventIngressError("ingress_envelope_fields_invalid")
    if len(_encoded(value)) > MAX_ENVELOPE_BYTES:
        raise EventIngressError("ingress_envelope_capacity")
    if (value["specversion"] != "1.0" or value["type"] != ENVELOPE_TYPE
            or value["datacontenttype"] != "application/json"
            or value["dataschema"] != SCHEMA_URI):
        raise EventIngressError("ingress_unsupported_schema")
    if type(value["source"]) is not str or not value["source"].startswith("urn:uuid:"):
        raise EventIngressError("ingress_invalid_producer_scope")
    try:
        identity = _identifier(value["id"])
        _validate_snapshot(value["data"], identity)
        if any(type(stamp) is not str or not _TIME.fullmatch(stamp)
               for stamp in (value["time"], value["data"]["observed_at"])):
            raise QueueInboxError("inbox_timestamp_invalid")
        stamp = _timestamp(value["time"])
        observed = _timestamp(value["data"]["observed_at"])
    except (QueueInboxError, TypeError, ValueError, KeyError):
        raise EventIngressError("ingress_snapshot_invalid") from None
    if stamp != observed:
        raise EventIngressError("ingress_timestamp_mismatch")
    snapshot = dict(value["data"], observed_at=observed)
    return {"specversion": "1.0", "id": identity, "source": _scope(value["source"]),
            "type": ENVELOPE_TYPE, "time": stamp, "datacontenttype": "application/json",
            "dataschema": SCHEMA_URI, "data": snapshot}


def build_envelope(snapshot, producer_id):
    """Wrap the seven-field projection without adding model-visible fields."""
    if type(snapshot) is not dict:
        raise EventIngressError("ingress_snapshot_invalid")
    return validate_envelope({"specversion": "1.0", "id": snapshot.get("event_id"),
        "source": _scope(producer_id), "type": ENVELOPE_TYPE,
        "time": snapshot.get("observed_at"), "datacontenttype": "application/json",
        "dataschema": SCHEMA_URI, "data": snapshot})


def envelope_hash(value):
    """Hash canonical wire content, distinct from EventStore payload_hash."""
    return hashlib.sha256(_encoded(validate_envelope(value))).hexdigest()


def assert_same_identity(original, candidate):
    """Compare against the retained original; no third deduplication database."""
    first, second = validate_envelope(original), validate_envelope(candidate)
    if (first["source"], first["id"]) != (second["source"], second["id"]):
        raise EventIngressError("ingress_identity_mismatch")
    if envelope_hash(first) != envelope_hash(second):
        raise EventIngressError("ingress_identity_conflict")
    return {"status": "duplicate", "event_id": first["id"], "wire_hash": envelope_hash(first)}


@contextmanager
def _source_db(source_dir):
    db = None
    try:
        source = _guard(source_dir)
        path = _guard(source / "eventguard.sqlite3")
        if not path.is_file():
            raise EventIngressError("ingress_existing_eventstore_required")
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        yield db
    except (sqlite3.Error, OSError, QueueInboxError):
        raise EventIngressError("ingress_source_read_failed") from None
    finally:
        if db is not None:
            db.close()


def _source_state(db, identity, allow_live):
    row = db.execute("SELECT payload,payload_hash,delivery_status,receipt FROM events WHERE event_id=?", (identity,)).fetchone()
    columns = {r[1] for r in db.execute("PRAGMA table_info(receipts)")}
    pin = "pending_finalization" if "pending_finalization" in columns else "NULL AS pending_finalization"
    receipt = db.execute("SELECT payload_hash,receipt," + pin + " FROM receipts WHERE event_id=?", (identity,)).fetchone()
    if row is None and receipt is None:
        raise EventIngressError("ingress_event_not_retained")
    result = {"snapshot": None, "payload_hash": None, "delivery_status": None,
              "receipt": None, "pending_finalization": None}
    try:
        if row is not None:
            if type(row["payload"]) is not str or len(row["payload"].encode("utf-8")) > MAX_EVENT_BYTES:
                raise EventIngressError("ingress_source_payload_invalid")
            event = validate_event(json.loads(row["payload"]))
            if event["event_id"] != identity or event_payload_hash(event) != row["payload_hash"]:
                raise EventIngressError("ingress_source_identity_conflict")
            if not allow_live and event["synthetic"] is not True:
                raise EventIngressError("ingress_live_event_not_authorized")
            if row["delivery_status"] not in {"pending", "retry", "ack", "failed"}:
                raise EventIngressError("ingress_source_status_invalid")
            result.update(snapshot=_projection(event), payload_hash=row["payload_hash"],
                          delivery_status=row["delivery_status"])
            if row["receipt"] is not None:
                if type(row["receipt"]) is not str or len(row["receipt"].encode("utf-8")) > MAX_EVENT_BYTES:
                    raise EventIngressError("ingress_source_receipt_invalid")
                result["receipt"] = validate_receipt(identity, json.loads(row["receipt"]))
        if receipt is not None:
            if type(receipt["receipt"]) is not str or len(receipt["receipt"].encode("utf-8")) > MAX_EVENT_BYTES:
                raise EventIngressError("ingress_source_receipt_invalid")
            saved = validate_receipt(identity, json.loads(receipt["receipt"]))
            if (result["payload_hash"] is not None and receipt["payload_hash"] != result["payload_hash"]
                    or result["receipt"] is not None and saved != result["receipt"]):
                raise EventIngressError("ingress_source_identity_conflict")
            if not _HASH.fullmatch(receipt["payload_hash"]):
                raise EventIngressError("ingress_source_identity_conflict")
            if receipt["pending_finalization"] not in (0, 1, None):
                raise EventIngressError("ingress_source_receipt_invalid")
            result.update(payload_hash=receipt["payload_hash"], receipt=saved,
                          pending_finalization=receipt["pending_finalization"])
            if row is None:
                result["delivery_status"] = "ack"
            elif result["delivery_status"] != "ack":
                raise EventIngressError("ingress_source_identity_conflict")
        if result["delivery_status"] == "ack" and result["receipt"] is None:
            raise EventIngressError("ingress_source_receipt_invalid")
    except EventIngressError:
        raise
    except (ValueError, TypeError, RecursionError, QueueInboxError, StoreError):
        raise EventIngressError("ingress_source_invalid") from None
    return result


def _inbox_evidence(source_dir, state_dir, identity, allow_live, source):
    try:
        state = _guard(state_dir)
        if not state.exists():
            return None, "inbox_state_not_present", False
        inbox = QueueInbox.open_readonly(source_dir, state, identity, allow_live)
        evidence = inbox.evidence(identity)
        if evidence is not None and evidence["payload_hash"] != source["payload_hash"]:
            raise EventIngressError("ingress_inbox_identity_conflict")
        if evidence is not None and source["snapshot"] is not None and evidence["snapshot"] != source["snapshot"]:
            raise EventIngressError("ingress_inbox_identity_conflict")
        completed = inbox._completed(identity) is not None
        if completed and source["delivery_status"] != "ack":
            raise EventIngressError("ingress_inbox_identity_conflict")
        return evidence, None if evidence is not None else "inbox_evidence_not_retained", completed
    except EventIngressError:
        raise
    except (QueueInboxError, OSError, TypeError, ValueError, RecursionError):
        raise EventIngressError("ingress_inbox_evidence_invalid") from None


def _profile(identity, allow_live):
    try:
        identity = _identifier(identity)
    except QueueInboxError:
        raise EventIngressError("ingress_invalid_event_id") from None
    if type(allow_live) is not bool:
        raise EventIngressError("ingress_invalid_live_profile")
    return identity


def export_event(source_dir, state_dir, event_id, allow_live=False, producer_id=None):
    """Read a retained event; never receive/query/ACK or create files/identity."""
    identity = _profile(event_id, allow_live)
    producer = _scope(producer_id)
    with _source_db(source_dir) as db:
        source = _source_state(db, identity, allow_live)
    evidence, _, _ = _inbox_evidence(source_dir, state_dir, identity, allow_live, source)
    snapshot = source["snapshot"] or (evidence["snapshot"] if evidence is not None else None)
    if snapshot is None:
        raise EventIngressError("ingress_snapshot_not_retained")
    envelope = build_envelope(snapshot, producer)
    return {"envelope": envelope, "wire_hash": envelope_hash(envelope),
            "export_only": True, "model_calls": 0, "real_agent_woken": False}


def _confirmed(evidence, **extra):
    return {"status": "confirmed", "evidence": evidence, **extra}


def _unknown(reason):
    return {"status": "unknown", "reason": reason}


def inspect_delivery(source_dir, state_dir, event_id, allow_live=False, producer_id=None):
    """Inspect retained proof, not inferred lifecycle or incident conclusions.

    ``producer_id`` is optional here; it is only validated when supplied. Source
    and inbox storage can change between reads. This is an observation, not an
    atomic global snapshot or authorization for another delivery attempt.
    """
    identity = _profile(event_id, allow_live)
    if producer_id is not None:
        _scope(producer_id)
    with _source_db(source_dir) as db:
        source = _source_state(db, identity, allow_live)
        has_dispositions = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_dispositions'").fetchone()
        disposition = db.execute("SELECT status,updated_at FROM event_dispositions WHERE event_id=?", (identity,)).fetchone() if has_dispositions else None
    evidence, reason, completed = _inbox_evidence(source_dir, state_dir, identity, allow_live, source)
    if source["snapshot"] is None and evidence is None and not allow_live:
        raise EventIngressError("ingress_synthetic_profile_unverifiable")
    stages = {name: _unknown(reason or "no_retained_stage_evidence")
              for name in ("received", "queried", "result_saved", "finalization")}
    stages["persisted"] = _confirmed("outbox_payload" if source["snapshot"] is not None else "outbox_receipt")
    if evidence is not None:
        stages["received"] = _confirmed("inbox_snapshot", at=evidence["received_at"])
        if "query_id" in evidence:
            stages["queried"] = _confirmed("inbox_query", query_id=evidence["query_id"], at=evidence["queried_at"])
        if "result" in evidence:
            result = evidence["result"]
            stages["result_saved"] = _confirmed("inbox_result", result_id=result["result_id"], at=result["recorded_at"],
                                               incident_conclusion="not_assessed")
            if source["receipt"] is not None and source["receipt"]["receiver_receipt_id"] != result["result_id"]:
                raise EventIngressError("ingress_ack_result_identity_conflict")
    acked = source["delivery_status"] == "ack"
    stages["ack"] = _confirmed("outbox_receipt") if acked else {"status": "pending", "reason": "source_not_acked"}
    if source["pending_finalization"] == 1:
        stages["finalization"] = {"status": "pending", "reason": "receiver_finalization_pinned"}
    elif acked and completed and source["pending_finalization"] == 0:
        stages["finalization"] = _confirmed("inbox_completed_and_unpinned_source_receipt")
    for stage in ("notification_submitted", "agent_started", "agent_turn_completed", "agent_process_exited"):
        stages[stage] = _unknown("provider_lifecycle_not_inspected")
    if disposition is not None:
        if disposition["status"] not in {"new", "read", "handled", "ignored"}:
            raise EventIngressError("ingress_human_status_invalid")
        try:
            at = datetime.fromtimestamp(disposition["updated_at"], timezone.utc).isoformat(timespec="seconds")
        except (TypeError, ValueError, OverflowError, OSError):
            raise EventIngressError("ingress_human_status_invalid") from None
        handling = _confirmed("event_disposition", value=disposition["status"], at=at)
    elif source["snapshot"] is not None:
        handling = _confirmed("eventstore_default_no_disposition", value="new")
    else:
        handling = _unknown("event_disposition_not_retained")
    return {"event_id": identity, "stages": stages, "human_handling": handling,
            "source_delivery_status": source["delivery_status"], "read_only": True,
            "model_calls": 0, "real_agent_wake_verified": False,
            "incident_conclusion": "not_assessed"}


def capabilities():
    return {"profile": "eventguard-cloudevents-minimal-v1", "specversion": "1.0",
            "schema": SCHEMA_URI, "max_envelope_bytes": MAX_ENVELOPE_BYTES,
            "model_snapshot_fields": ["event_id", "event_type", "transition", "severity",
                                      "synthetic", "observed_at", "coverage_status"],
            "producer_scope": "caller_provisioned_persistent_uuid4", "export": "read_only",
            "receive": "existing_queue_inbox", "agent_wake": "unverified",
            "transport": "caller_supplied_no_listener", "delivery": "at_least_once",
            "deduplication": "compare_retained_original", "model_calls": 0}
