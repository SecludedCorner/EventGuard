"""Bounded, untrusted handling-history records; no database writes or identity claims."""
from __future__ import annotations

import math
import re

MAX_HISTORY_ENTRIES = 4096
MAX_HISTORY_PER_EVENT = 32
STATUSES = frozenset({"new", "read", "handled", "ignored"})
SOURCES = frozenset({"gui", "mcp", "cli", "startup", "system", "unknown"})
IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
OPERATION = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


def validate_record(value, *, allow_unchanged=False):
    """Validate a single transition without asserting who operated it.

    Operation identifiers are opaque idempotency keys, not authenticated user
    identities. Legacy changes cannot be reconstructed from the latest state.
    """
    fields = {"event_id", "operation_id", "previous_status", "status", "source", "at"}
    if type(value) is not dict or set(value) != fields:
        raise ValueError("invalid_history_record")
    event_id, operation_id = value["event_id"], value["operation_id"]
    if (type(event_id) is not str or not IDENTIFIER.fullmatch(event_id) or
            type(operation_id) is not str or not OPERATION.fullmatch(operation_id)):
        raise ValueError("invalid_history_identity")
    if (type(value["previous_status"]) is not str or value["previous_status"] not in STATUSES or
            type(value["status"]) is not str or value["status"] not in STATUSES or
            (not allow_unchanged and value["previous_status"] == value["status"])):
        raise ValueError("invalid_history_transition")
    if type(value["source"]) is not str or value["source"] not in SOURCES:
        raise ValueError("invalid_history_source")
    if type(value["at"]) not in (int, float) or not math.isfinite(value["at"]) or not 0 <= value["at"] <= 253402300799:
        raise ValueError("invalid_history_time")
    return dict(value)


def has_capacity(total, per_event):
    """A full history fails closed; it must not evict pending or ACK evidence."""
    if any(type(n) is not int or n < 0 for n in (total, per_event)) or per_event > total:
        raise ValueError("invalid_history_count")
    return total < MAX_HISTORY_ENTRIES and per_event < MAX_HISTORY_PER_EVENT
