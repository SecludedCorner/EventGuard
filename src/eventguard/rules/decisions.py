"""Saved winning-rule snapshots; hashes identify content, never authority."""
import copy
import hashlib
import json
import re

MAX_CLASSIFICATION_EVENTS = 1000


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("ascii")).hexdigest()


def validate_decision(value, event):
    from .configured import SEVERITIES, validate_rules, _matches
    def invalid():
        raise ValueError("classification_invalid")
    fields = {"schema_version", "rule_set_hash", "base_severity", "matched", "rule_index", "rule", "rule_hash"}
    if (type(value) is not dict or set(value) != fields or value.get("schema_version") != "1.0"
            or type(value.get("rule_set_hash")) is not str or not re.fullmatch(r"[a-f0-9]{64}", value["rule_set_hash"])
            or type(value.get("base_severity")) is not str or value["base_severity"] not in SEVERITIES
            or type(value.get("matched")) is not bool or type(event) is not dict):
        invalid()
    if not value["matched"]:
        if any(value[key] is not None for key in ("rule_index", "rule", "rule_hash")) or event.get("severity") != value["base_severity"]:
            invalid()
    else:
        rule = value["rule"]
        if (type(value["rule_index"]) is not int or not 0 <= value["rule_index"] < 64
                or type(rule) is not dict or set(rule) != {"id", "severity", "conditions"}):
            invalid()
        try:
            normalized = validate_rules([{**rule, "name": "stored classification", "enabled": True}])[0]
        except (ValueError, TypeError):
            invalid()
        if (type(value["rule_hash"]) is not str or value["rule_hash"] != fingerprint(rule)
                or event.get("severity") != normalized["severity"]
                or not all(_matches(event, condition) for condition in normalized["conditions"])):
            invalid()
    return copy.deepcopy(value)


def classify(events, rules):
    """Return independent classified candidates plus their original decisions.

    Keep only the winner's executable conditions, never its display name. The
    full configuration is fingerprinted, not backed up. A later explicit
    reclassification uses recorded input severity without mutating history.
    """
    from .configured import validate_rules, apply_rules, _winner, SEVERITIES
    from ..events.schema import validate_event
    configured = validate_rules(rules)
    if type(events) is not list or len(events) > MAX_CLASSIFICATION_EVENTS or any(type(event) is not dict for event in events):
        raise ValueError("rules_invalid_events")
    working = []
    for original in events:
        event = validate_event(original)
        if "classification" in original:
            previous = validate_decision(original["classification"], event)
            event["severity"] = previous["base_severity"]
        if type(event.get("severity")) is not str or event["severity"] not in SEVERITIES:
            raise ValueError("rules_invalid_classification")
        working.append(event)
    result = apply_rules(working, configured)
    digest = fingerprint(configured)
    for original, event in zip(working, result):
        index, rule = _winner(original, configured)
        snapshot = {key: copy.deepcopy(rule[key]) for key in ("id", "severity", "conditions")} if rule else None
        event["classification"] = {"schema_version": "1.0", "rule_set_hash": digest,
            "base_severity": original["severity"], "matched": rule is not None,
            "rule_index": index, "rule": snapshot, "rule_hash": fingerprint(snapshot) if snapshot else None}
        validate_decision(event["classification"], event)
        event.update(validate_event(event))  # Includes trace in the same UTF-8 event budget.
    return result
