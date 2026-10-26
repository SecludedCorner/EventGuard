"""Bounded saved-metadata correlation. No collection, model, ACK or response."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re

from ..diagnostics.review import row_view, _binding_evidence
from .schema import IDENTIFIER, STATUS_VALUES, _timestamp, validate_event
from .store import event_payload_hash

MAX_CANDIDATES = 256
MAX_MEMBERS = 16
WINDOW_SECONDS = 900
SOURCES = frozenset({"listeners", "processes", "defender", "startup", "services", "tasks", "versions",
                     "monitor", "advisories", "unknown"})
REASONS = frozenset({"different_owner", "different_source", "outside_window", "missing_binding", "different_entity"})
FACT_FIELDS = frozenset({"protocol", "port", "binding_scope", "property", "value", "current", "previous",
                         "status", "kind", "section", "state", "start_mode", "entry_ref", "name_ref"})
RECORD_FIELDS = frozenset({"event_id", "payload_hash", "owner_ref", "episode_ref", "source", "synthetic", "observed_at",
                           "sequence", "event_type", "transition", "severity", "coverage_status", "entity", "facts"})
HASH = re.compile(r"[a-f0-9]{64}\Z")
PROCESS = re.compile(r"proc-[a-f0-9]{24}\Z")


def _encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _seconds(value):
    return (datetime.fromisoformat(_timestamp(value))-datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()


def _facts(value):
    return {k: v for k, v in row_view(value).items() if k in FACT_FIELDS}


def _entity(evidence, source):
    ref = evidence.get("process_instance_ref", evidence.get("instance_ref"))
    ref = ref if type(ref) is str and PROCESS.fullmatch(ref) else None
    pid, created = evidence.get("pid"), evidence.get("process_created_at")
    pid = pid if type(pid) is int and 0 < pid <= 2**32 - 1 else None
    try:
        created = _timestamp(created)
    except ValueError:
        created = None
    if ref is not None or pid is not None and created is not None:
        return {"kind": "process", "ref": ref, "pid": pid, "created_at": created}
    entry = evidence.get("entry_ref")
    keys = evidence.get("changed_keys")
    if entry is None and isinstance(keys, list) and len(keys) == 1:
        entry = keys[0]
    if source in {"startup", "services", "tasks"} and type(entry) is str and re.fullmatch(r"[a-f0-9]{32}", entry):
        return {"kind": "persistence", "ref": entry}
    return None


def project(event, source):
    event = validate_event(event)
    evidence, _ = _binding_evidence(event)
    return {"event_id": event["event_id"], "payload_hash": event_payload_hash(event),
            "owner_ref": hashlib.sha256(_encoded([event["host_id"], event["synthetic"]]).encode()).hexdigest(),
            "episode_ref": hashlib.sha256(event["episode_id"].encode()).hexdigest(),
            "source": source if source in SOURCES else "unknown", "synthetic": event["synthetic"],
            "observed_at": event["observed_at"], "sequence": event["sequence"], "event_type": event["event_type"],
            "transition": event["transition"], "severity": event["severity"],
            "coverage_status": event["coverage"]["status"], "entity": _entity(evidence, source), "facts": _facts(evidence)}


def same_entity(left, right):
    if left is None or right is None or left["kind"] != right["kind"]:
        return False
    if left["kind"] == "persistence":
        return left["ref"] == right["ref"]
    # A known reference conflict is never repaired with a reused PID.
    if left["ref"] is not None and right["ref"] is not None and left["ref"] != right["ref"]:
        return False
    for field in ("pid", "created_at"):
        if left[field] is not None and right[field] is not None and left[field] != right[field]:
            return False
    return (left["ref"] is not None and left["ref"] == right["ref"] or
            left["pid"] is not None and left["created_at"] is not None and
            (left["pid"], left["created_at"]) == (right["pid"], right["created_at"]))


def exclusion(anchor, item):
    if item["owner_ref"] != anchor["owner_ref"] or item["synthetic"] != anchor["synthetic"]:
        return "different_owner"
    if item["source"] != anchor["source"] or anchor["source"] == "unknown":
        return "different_source"
    if abs(_seconds(item["observed_at"]) - _seconds(anchor["observed_at"])) > WINDOW_SECONDS:
        return "outside_window"
    if item["entity"] is None or anchor["entity"] is None:
        return "missing_binding"
    if not same_entity(anchor["entity"], item["entity"]):
        return "different_entity"
    return None


def _render(anchor, members, *, as_of, examined, truncated, excluded):
    timeline = sorted(members, key=lambda x: (x["observed_at"], x["sequence"], x["event_id"]))
    gaps = []
    for item in timeline:
        identity = item["event_id"]
        if item["entity"] is None:
            gaps.append({"event_id": identity, "reason": "stable_entity_missing"})
        if item["source"] == "unknown":
            gaps.append({"event_id": identity, "reason": "source_unknown"})
        if item["coverage_status"] != "ok":
            gaps.append({"event_id": identity, "reason": "source_incomplete"})
        age = _seconds(as_of) - _seconds(item["observed_at"])
        if age > WINDOW_SECONDS:
            gaps.append({"event_id": identity, "reason": "saved_observation_stale"})
        if age < -60:
            gaps.append({"event_id": identity, "reason": "observation_in_future"})
    for index, item in enumerate(timeline):
        for previous in timeline[:index]:
            if (previous["episode_ref"] == item["episode_ref"] and previous["event_type"] == item["event_type"] and previous["observed_at"] == item["observed_at"]
                    and previous["sequence"] == item["sequence"] and
                    (previous["facts"] != item["facts"] or previous["transition"] != item["transition"])):
                gaps.append({"event_id": item["event_id"], "reason": "simultaneous_metadata_conflict"})
                break
        prior_episode = [row for row in timeline[:index] if row["episode_ref"] == item["episode_ref"]]
        if prior_episode and item["sequence"] < prior_episode[-1]["sequence"]:
            gaps.append({"event_id": item["event_id"], "reason": "sequence_time_conflict"})
    if truncated:
        gaps.append({"event_id": anchor["event_id"], "reason": "candidate_or_member_limit"})
    identity = hashlib.sha256(_encoded([anchor["owner_ref"], anchor["event_id"], anchor["payload_hash"]]).encode()).hexdigest()[:32]
    return {"schema_version": "1.0", "engine_version": "saved-metadata-1", "case_id": "case-"+identity,
            "anchor_event_id": anchor["event_id"], "anchor_payload_hash": anchor["payload_hash"], "as_of": as_of,
            "status": "limited" if gaps else "related_metadata_only", "timeline": timeline,
            "correlation": {"basis": "same_host_source_stable_entity", "window_seconds": WINDOW_SECONDS,
                            "examined": examined, "truncated": truncated, "excluded": excluded},
            "gaps": gaps, "incident_conclusion": "not_assessed", "allowed_actions": [], "os_owner_status": "unknown",
            "next_steps": [{"action": "review_saved_metadata", "requires_approval": False},
                           {"action": "request_fresh_source_observation", "requires_approval": True}],
            "limitations": ["metadata_relationship_is_not_causality", "no_process_tree_or_attack_chain_inferred",
                            "saved_observation_is_not_current_host_state", "os_account_owner_not_observed", "ack_and_handling_are_separate"],
            "model_calls": 0, "native_queries": 0, "data_trust": "untrusted_data"}


def build(anchor, candidates, *, as_of=None, truncated=False):
    if type(candidates) is not list or len(candidates) > MAX_CANDIDATES:
        raise ValueError("investigation_candidate_limit")
    as_of = _timestamp(as_of or datetime.now(timezone.utc).isoformat())
    excluded = {key: 0 for key in sorted(REASONS)}
    members, seen = [anchor], {anchor["event_id"]}
    for item in candidates:
        if item["event_id"] in seen:
            continue
        seen.add(item["event_id"])
        reason = exclusion(anchor, item)
        if reason:
            excluded[reason] += 1
        elif len(members) < MAX_MEMBERS:
            members.append(item)
        else:
            truncated = True
    return _render(anchor, members, as_of=as_of, examined=len(candidates), truncated=truncated, excluded=excluded)


def validate_saved(value, event):
    """Rebuild derived text/flags from strictly typed, bounded saved metadata."""
    try:
        timeline = value["timeline"]
        if type(timeline) is not list or not 1 <= len(timeline) <= MAX_MEMBERS:
            raise ValueError()
        seen = set()
        for row in timeline:
            if type(row) is not dict or set(row) != RECORD_FIELDS:
                raise ValueError()
            if any(type(row[k]) is not str or not IDENTIFIER.fullmatch(row[k]) for k in ("event_id", "event_type")):
                raise ValueError()
            if row["event_id"] in seen:
                raise ValueError()
            seen.add(row["event_id"])
            if any(type(row[k]) is not str or not HASH.fullmatch(row[k]) for k in ("payload_hash", "owner_ref", "episode_ref")):
                raise ValueError()
            if (type(row["source"]) is not str or row["source"] not in SOURCES or type(row["synthetic"]) is not bool
                    or _timestamp(row["observed_at"]) != row["observed_at"] or type(row["sequence"]) is not int
                    or not 1 <= row["sequence"] <= 2**53-1 or row["transition"] not in {"new", "escalated", "resolved"}
                    or row["severity"] not in {"info", "warning", "high", "critical"}
                    or row["coverage_status"] not in STATUS_VALUES or type(row["facts"]) is not dict
                    or _facts(row["facts"]) != row["facts"]):
                raise ValueError()
            entity = row["entity"]
            if entity is not None:
                if type(entity) is not dict:
                    raise ValueError()
                if entity.get("kind") == "persistence":
                    if set(entity) != {"kind", "ref"} or type(entity["ref"]) is not str or not re.fullmatch(r"[a-f0-9]{32}", entity["ref"]):
                        raise ValueError()
                elif (set(entity) != {"kind", "ref", "pid", "created_at"} or entity.get("kind") != "process"
                      or _entity({"process_instance_ref": entity["ref"], "pid": entity["pid"],
                                  "process_created_at": entity["created_at"]}, row["source"]) != entity):
                    raise ValueError()
        anchor = next(row for row in timeline if row["event_id"] == event["event_id"])
        if project(event, anchor["source"]) != anchor or any(exclusion(anchor, row) for row in timeline if row is not anchor):
            raise ValueError()
        correlation = value["correlation"]
        excluded = correlation["excluded"]
        if (type(excluded) is not dict or set(excluded) != REASONS or any(type(n) is not int or not 0 <= n <= MAX_CANDIDATES for n in excluded.values())
                or type(correlation["examined"]) is not int or not 0 <= correlation["examined"] <= MAX_CANDIDATES
                or type(correlation["truncated"]) is not bool):
            raise ValueError()
        rebuilt = _render(anchor, timeline, as_of=_timestamp(value["as_of"]), examined=correlation["examined"],
                          truncated=correlation["truncated"], excluded=excluded)
        if rebuilt != value:
            raise ValueError()
        return value
    except (ValueError, TypeError, KeyError, StopIteration, OverflowError):
        raise ValueError("saved_investigation_invalid") from None
