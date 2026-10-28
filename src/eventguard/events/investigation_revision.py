"""Bounded investigation revision metadata, without storage or inferred history."""
from __future__ import annotations

import hashlib
import json
import math
import re

from .investigation import validate_saved

MAX_REVISIONS = 256
MAX_REVISIONS_PER_EVENT = 16
MAX_CASE_BYTES = 65536
_HASH = re.compile(r"[a-f0-9]{64}\Z")


def encode_case(case):
    """Use one canonical encoding; the digest detects accidental changes only."""
    encoded = json.dumps(case, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(encoded) > MAX_CASE_BYTES:
        raise ValueError("investigation_revision_case_limit")
    return encoded


def make_revision(case, anchor_event, *, saved_at):
    """Bind the previous saved case to its event; never infer earlier versions."""
    if type(saved_at) not in (int, float) or not math.isfinite(saved_at) or not 0 <= saved_at <= 253402300799:
        raise ValueError("investigation_revision_time_invalid")
    validate_saved(case, anchor_event)
    encoded = encode_case(case)
    return {"schema_version": "1.0", "event_id": anchor_event["event_id"],
            "payload_hash": case["anchor_payload_hash"], "case_hash": hashlib.sha256(encoded).hexdigest(),
            "saved_at": saved_at, "case": case}


def validate_revision(value, anchor_event):
    if type(value) is not dict or set(value) != {"schema_version", "event_id", "payload_hash", "case_hash", "saved_at", "case"}:
        raise ValueError("investigation_revision_invalid")
    if value["schema_version"] != "1.0" or type(value["case_hash"]) is not str or not _HASH.fullmatch(value["case_hash"]):
        raise ValueError("investigation_revision_invalid")
    try:
        expected = make_revision(value["case"], anchor_event, saved_at=value["saved_at"])
    except (TypeError, ValueError, KeyError, OverflowError):
        raise ValueError("investigation_revision_invalid") from None
    if value != expected:
        raise ValueError("investigation_revision_invalid")
    return value


def has_revision_capacity(total, per_event):
    if any(type(value) is not int or value < 0 for value in (total, per_event)) or per_event > total:
        raise ValueError("investigation_revision_count_invalid")
    return total < MAX_REVISIONS and per_event < MAX_REVISIONS_PER_EVENT
