"""Deterministic, read-only admission filtering over the existing outbox.

Policy contains only fixed enums. It cannot supply commands, prompts, paths,
tools, recipients or permissions. No event is received, ACKed, reclassified or
removed by this module. Deduplication/cooldown remain producer responsibilities.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
import time

from .events.schema import MAX_EVENT_BYTES, EventValidationError, validate_event
from .events.store import event_payload_hash
from .queue_inbox import QueueInbox, QueueInboxError, EVENT_TYPES, _guard, _identifier

MAX_POLICY_BYTES = 8192
PAGE_SIZE = 100
MAX_CANDIDATES = 1000
MAX_SCHEDULE_TIME = 253402300800  # Exclusive: first instant after year 9999 UTC.
_FIELDS = frozenset({"severities", "event_types", "human_statuses"})
_VALUES = {"severities": frozenset({"info", "warning", "high", "critical"}),
           "event_types": EVENT_TYPES, "human_statuses": frozenset({"new", "read"})}
DEFAULT_POLICY = {"severities": ["high", "critical"],
                  "event_types": sorted(EVENT_TYPES), "human_statuses": ["new", "read"]}
REASON_CODES = frozenset({
    "dispatch_policy_fields_invalid", "dispatch_policy_condition_invalid",
    "dispatch_policy_duplicate_key", "dispatch_policy_capacity", "dispatch_policy_read_failed",
    "dispatch_policy_inbox_required", "dispatch_policy_scan_limit_pending_preserved",
    "dispatch_pending_payload_malformed", "dispatch_pending_payload_capacity",
    "dispatch_pending_schema_invalid", "dispatch_pending_identity_conflict",
    "dispatch_pending_human_status_invalid", "dispatch_pending_capacity_pending_preserved",
    "dispatch_pending_schedule_invalid",
    "dispatch_selection_failed_pending_preserved",
})


class DispatchPolicyError(ValueError):
    """Fixed reason codes; never repeat untrusted configuration or raw SQL."""

    def __init__(self, reason):
        self.code = (reason if type(reason) is str and reason in REASON_CODES
                     else "dispatch_selection_failed_pending_preserved")
        super().__init__(self.code)


def validate_policy(value):
    """Return a detached validated policy. Handled/ignored are never admitted."""
    if type(value) is not dict or set(value) != _FIELDS:
        raise DispatchPolicyError("dispatch_policy_fields_invalid")
    result = {}
    for field, allowed in _VALUES.items():
        items = value[field]
        if (type(items) is not list or not 1 <= len(items) <= len(allowed)
                or any(type(item) is not str or item not in allowed for item in items)
                or len(set(items)) != len(items)):
            raise DispatchPolicyError("dispatch_policy_condition_invalid")
        result[field] = list(items)
    return result


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DispatchPolicyError("dispatch_policy_duplicate_key")
        result[key] = value
    return result


def load_policy(path=None):
    """Read an explicit local JSON file, or return detached safe defaults."""
    if path is None:
        return validate_policy(DEFAULT_POLICY)
    try:
        target = _guard(Path(path))
        with target.open("rb") as stream:
            raw = stream.read(MAX_POLICY_BYTES + 1)
        if len(raw) > MAX_POLICY_BYTES:
            raise DispatchPolicyError("dispatch_policy_capacity")
        return validate_policy(json.loads(raw, object_pairs_hook=_pairs))
    except DispatchPolicyError:
        raise
    except (OSError, ValueError, TypeError, RecursionError, QueueInboxError):
        raise DispatchPolicyError("dispatch_policy_read_failed") from None


def _value(field):
    # SQLite may reorder WHERE predicates. CASE makes malformed/oversized JSON
    # safe independently of query planning, before any json_extract operation.
    return ("CASE WHEN typeof(e.payload)='text' AND length(CAST(e.payload AS BLOB))<="
            + str(MAX_EVENT_BYTES) + " AND json_valid(e.payload) THEN json_extract(e.payload,'$."
            + field + "') END")


def _event_pairs(pairs):
    """Reject duplicate keys: SQLite and Python must see the same conditions."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_event_json_key")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("nonfinite_event_json")


@lru_cache(maxsize=MAX_CANDIDATES)
def _validated_pending_payload(identity, payload, stored_hash):
    """Pure validation cache. Caller bounds raw UTF-8 before admitting a key.

    The complete raw text is part of the key, not just its mutable claimed hash.
    At most 1000 records of <=8192 bytes are retained, in memory only. This is
    not a tamper-proof log or a guarantee against other same-user modifications.
    """
    try:
        event = json.loads(payload, object_pairs_hook=_event_pairs, parse_constant=_nonfinite)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return "dispatch_pending_payload_malformed"
    try:
        clean = validate_event(event)
    except (EventValidationError, TypeError, ValueError, OverflowError, RecursionError):
        return "dispatch_pending_schema_invalid"
    if clean["event_id"] != identity or event_payload_hash(clean) != stored_hash:
        return "dispatch_pending_identity_conflict"
    return None


def _pending_payload_reason(identity, payload, stored_hash):
    # Guard before the LRU: oversized or non-text values cannot consume its
    # bounded record budget. SQLite calls this with its scalar storage types.
    if type(payload) is not str:
        return "dispatch_pending_payload_malformed"
    try:
        if len(payload.encode("utf-8")) > MAX_EVENT_BYTES:
            return "dispatch_pending_payload_capacity"
    except UnicodeError:
        return "dispatch_pending_payload_malformed"
    try:
        _identifier(identity)
    except QueueInboxError:
        return "dispatch_pending_identity_conflict"
    if (type(stored_hash) is not str or len(stored_hash) != 64
            or any(char not in "0123456789abcdef" for char in stored_hash)):
        return "dispatch_pending_identity_conflict"
    return _validated_pending_payload(identity, payload, stored_hash)


def _assert_pending_invariants(db, disposition_exists):
    """Do not turn corrupt pending data into an empty or filtered queue.

    The outbox policy caps all events at 1000. A tampered larger queue is
    explicitly blocked after a bounded count, never scanned without a bound.
    Only the local queue is inspected; no inventory, network or model work runs.
    Valid low-priority events usually hit the pure validation LRU on later polls.
    """
    count = db.execute("""SELECT COUNT(*) FROM (
        SELECT 1 FROM events WHERE delivery_status IN ('pending','retry') LIMIT ?)
        """, (MAX_CANDIDATES + 1,)).fetchone()[0]
    if count > MAX_CANDIDATES:
        raise DispatchPolicyError("dispatch_pending_capacity_pending_preserved")
    db.create_function("eventguard_dispatch_pending_reason", 3, _pending_payload_reason, deterministic=True)
    join = " LEFT JOIN event_dispositions d ON d.event_id=e.event_id" if disposition_exists else ""
    human = ("WHEN d.event_id IS NOT NULL AND (typeof(d.status)!='text' OR "
             "d.status NOT IN ('new','read','handled','ignored')) "
             "THEN 'dispatch_pending_human_status_invalid' " if disposition_exists else "")
    schedule = "".join(
        "WHEN e." + field + " IS NOT NULL AND (typeof(e." + field + ") NOT IN ('integer','real') "
        "OR e." + field + "<0 OR e." + field + ">=" + str(MAX_SCHEDULE_TIME) + ") "
        "THEN 'dispatch_pending_schedule_invalid' "
        for field in ("next_retry_at", "lease_until"))
    # CASE checks size before crossing the SQLite/Python callback boundary.
    # Invariants apply before severity/type/due/namespace filtering: an invalid
    # event cannot establish that its own exclusion condition is trustworthy.
    sql = ("SELECT reason FROM (SELECT CASE "
           "WHEN typeof(e.payload)!='text' THEN 'dispatch_pending_payload_malformed' "
           "WHEN length(CAST(e.payload AS BLOB))>" + str(MAX_EVENT_BYTES) +
           " THEN 'dispatch_pending_payload_capacity' "
           "WHEN typeof(e.event_id)!='text' OR length(e.event_id) NOT BETWEEN 1 AND 160 "
           "OR typeof(e.payload_hash)!='text' OR length(e.payload_hash)!=64 "
           "THEN 'dispatch_pending_identity_conflict' " + human + schedule +
           "ELSE eventguard_dispatch_pending_reason(e.event_id,e.payload,e.payload_hash) END AS reason "
           "FROM events e" + join + " WHERE e.delivery_status IN ('pending','retry') LIMIT ?) "
           "WHERE reason IS NOT NULL LIMIT 1")
    failure = db.execute(sql, (MAX_CANDIDATES,)).fetchone()
    if failure is not None:
        raise DispatchPolicyError(failure["reason"])


def select_pending(inbox, policy=None):
    """Select one due permitted ID without head-of-line low-severity blocking.

    Critical precedes high, warning and info; ties use persisted time and ID.
    SQL filters before pagination, so any number of low-severity rows cannot
    hide a later high-severity candidate. Bounded pages avoid loading a queue.
    Pending invariants are checked before filtering; corruption cannot establish
    an exclusion condition. Valid payload checks are bounded and cached by full
    raw content, PK and stored hash. Every selected candidate is independently
    revalidated using QueueInbox's existing source reader. A scan limit is an
    error, never an empty-queue assertion. Selection is not launch authorization.
    """
    if not isinstance(inbox, QueueInbox):
        raise DispatchPolicyError("dispatch_policy_inbox_required")
    checked = load_policy() if policy is None else validate_policy(policy)
    severity, kind = _value("severity"), _value("event_type")
    priority = "CASE " + severity + " WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END"
    now = time.time()
    with inbox._readonly() as db:
        # One local read transaction bounds the observation. It reserves no
        # events and grants no right to ignore later pause/budget/launch gates.
        db.execute("BEGIN")
        disposition_exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_dispositions'").fetchone()
        _assert_pending_invariants(db, disposition_exists)
        join = " LEFT JOIN event_dispositions d ON d.event_id=e.event_id" if disposition_exists else ""
        human = "COALESCE(d.status,'new')" if disposition_exists else "'new'"
        placeholders = lambda values: ",".join("?" for _ in values)
        sql = ("SELECT e.event_id FROM events e" + join +
               " WHERE e.delivery_status IN ('pending','retry')"
               " AND (e.next_retry_at IS NULL OR e.next_retry_at<=?)"
               " AND (e.lease_until IS NULL OR e.lease_until<=?)"
               " AND " + severity + " IN (" + placeholders(checked["severities"]) + ")"
               " AND " + kind + " IN (" + placeholders(checked["event_types"]) + ")"
               " AND " + human + " IN (" + placeholders(checked["human_statuses"]) + ")")
        parameters = [now, now, *checked["severities"], *checked["event_types"], *checked["human_statuses"]]
        if not inbox.allow_live:
            sql += " AND " + _value("synthetic") + "=1"
        sql += " ORDER BY " + priority + ",e.created_at,e.event_id LIMIT ? OFFSET ?"
        for offset in range(0, MAX_CANDIDATES, PAGE_SIZE):
            rows = db.execute(sql, [*parameters, PAGE_SIZE, offset]).fetchall()
            for row in rows:
                identity = _identifier(row["event_id"])
                source = inbox._source_record(identity)
                snapshot = source.get("snapshot")
                if source.get("delivery_status") not in {"pending", "retry"} or snapshot is None:
                    continue
                if (snapshot["severity"] in checked["severities"]
                        and snapshot["event_type"] in checked["event_types"]
                        and (inbox.allow_live or snapshot["synthetic"] is True)):
                    return identity
            if len(rows) < PAGE_SIZE:
                return None
    raise DispatchPolicyError("dispatch_policy_scan_limit_pending_preserved")
