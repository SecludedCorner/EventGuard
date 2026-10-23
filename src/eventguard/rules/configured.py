"""Bounded local severity rules. Conditions are data, never executable code.

The detector still owns event identity, episodes, cooldown and recovery. These
rules classify its candidates before the state/event transaction is committed.
An unmatched or disabled rule never drops a candidate or changes its evidence.
"""
from __future__ import annotations

import copy
import json
import re

from ..runtime import safe_child

MAX_RULE_BYTES = 131072
MAX_RULES = 64
MAX_CONDITIONS = 12
SEVERITIES = frozenset({"info", "warning", "high", "critical"})
SOURCES = frozenset({"defender", "listeners", "processes", "startup", "services", "tasks", "versions"})
ENUM_FIELDS = {
    "event_type": frozenset({"protection.changed", "listener.changed", "persistence.changed", "coverage.degraded"}),
    "source": SOURCES,
    "transition": frozenset({"new", "escalated", "resolved"}),
    "coverage_status": frozenset({"ok", "partial", "denied", "unknown", "not_applicable", "error", "timeout", "cancelled", "busy", "not_requested", "stale", "limit_exceeded"}),
    "evidence.protocol": frozenset({"TCP", "UDP"}),
    "evidence.scope": frozenset({"all_interfaces"}),
    "evidence.reason": frozenset({"initial_inventory", "added_metadata", "delivery_batch_limit"}),
    "evidence.kind": frozenset({"startup", "services", "tasks"}),
}
NUMBER_FIELDS = {"evidence.count": 1000000, "evidence.port": 65535,
                 "evidence.pid": 2**32 - 1, "evidence.suppression_count": 1000000}


class RulesValidationError(ValueError):
    """Fixed reason codes. Config contents and OS errors are not echoed."""


def _condition(field, op, value):
    return {"field": field, "op": op, "value": value}


DEFAULT_RULES = [
    {"id": "protection-disabled", "name": "兩項防護功能關閉", "enabled": True,
     "severity": "high", "conditions": [_condition("event_type", "eq", "protection.changed"),
                                         _condition("transition", "in", ["new", "escalated"]),
                                         _condition("evidence.count", "gte", 2)]},
    {"id": "listener-all-interfaces", "name": "全介面監聽端點變化", "enabled": True,
     "severity": "warning", "conditions": [_condition("event_type", "eq", "listener.changed"),
                                            _condition("transition", "eq", "new")]},
    {"id": "persistence-added", "name": "新增持久化項目", "enabled": True,
     "severity": "warning", "conditions": [_condition("event_type", "eq", "persistence.changed"),
                                            _condition("transition", "in", ["new", "escalated"]),
                                            _condition("evidence.reason", "eq", "added_metadata")]},
    {"id": "persistence-baseline", "name": "首次持久化盤點", "enabled": True,
     "severity": "info", "conditions": [_condition("event_type", "eq", "persistence.changed"),
                                         _condition("transition", "eq", "new"),
                                         _condition("evidence.reason", "eq", "initial_inventory")]},
    {"id": "collection-failed", "name": "採集錯誤或逾時", "enabled": True,
     "severity": "high", "conditions": [_condition("event_type", "eq", "coverage.degraded"),
                                         _condition("transition", "in", ["new", "escalated"]),
                                         _condition("coverage_status", "in", ["error", "timeout"])]},
]


def _validate_condition(condition):
    if not isinstance(condition, dict) or set(condition) != {"field", "op", "value"}:
        raise RulesValidationError("rules_invalid_condition")
    field, op, value = condition["field"], condition["op"], condition["value"]
    if not isinstance(field, str) or not isinstance(op, str):
        raise RulesValidationError("rules_invalid_condition")
    if field in ENUM_FIELDS:
        if op == "eq":
            values = [value]
        elif op == "in" and isinstance(value, list) and 1 <= len(value) <= 20:
            values = value
        else:
            raise RulesValidationError("rules_invalid_operator")
        if any(not isinstance(item, str) or item not in ENUM_FIELDS[field] for item in values):
            raise RulesValidationError("rules_invalid_enum")
        if len(set(values)) != len(values):
            raise RulesValidationError("rules_duplicate_enum")
    elif field in NUMBER_FIELDS:
        if op not in {"eq", "gte", "lte"}:
            raise RulesValidationError("rules_invalid_operator")
        if type(value) is not int or not 0 <= value <= NUMBER_FIELDS[field]:
            raise RulesValidationError("rules_invalid_number")
    else:
        raise RulesValidationError("rules_field_not_allowed")
    return copy.deepcopy(condition)


def validate_rules(rules):
    """Return an independent rule list. Later matching rules take precedence."""
    if not isinstance(rules, list) or not 1 <= len(rules) <= MAX_RULES:
        raise RulesValidationError("rules_count_out_of_bounds")
    result, identities = [], set()
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - {"id", "name", "enabled", "severity", "conditions"}:
            raise RulesValidationError("rules_invalid_rule")
        identity, name = rule.get("id"), rule.get("name")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", identity):
            raise RulesValidationError("rules_invalid_id")
        if identity in identities:
            raise RulesValidationError("rules_duplicate_id")
        identities.add(identity)
        if (not isinstance(name, str) or not 1 <= len(name) <= 80 or not name.strip()
                or any(not char.isprintable() for char in name)):
            raise RulesValidationError("rules_invalid_name")
        enabled, severity, conditions = rule.get("enabled", True), rule.get("severity"), rule.get("conditions")
        if type(enabled) is not bool or not isinstance(severity, str) or severity not in SEVERITIES:
            raise RulesValidationError("rules_invalid_classification")
        if not isinstance(conditions, list) or not 1 <= len(conditions) <= MAX_CONDITIONS:
            raise RulesValidationError("rules_invalid_conditions")
        result.append({"id": identity, "name": name, "enabled": enabled, "severity": severity,
                       "conditions": [_validate_condition(item) for item in conditions]})
    return result


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RulesValidationError("rules_duplicate_json_key")
        result[key] = value
    return result


def load_rules(root):
    """Read config/rules.json; only an absent file selects the built-in defaults."""
    try:
        path = safe_child(root, "config/rules.json")
        with path.open("rb") as stream:
            content = stream.read(MAX_RULE_BYTES + 1)
    except FileNotFoundError:
        return validate_rules(DEFAULT_RULES)
    except (OSError, ValueError):
        raise RulesValidationError("rules_read_failed") from None
    if len(content) > MAX_RULE_BYTES:
        raise RulesValidationError("rules_file_too_large")
    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=_object)
    except RulesValidationError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise RulesValidationError("rules_invalid_json") from None
    if (not isinstance(document, dict) or set(document) != {"schema_version", "rules"}
            or document.get("schema_version") != "1.0"):
        raise RulesValidationError("rules_invalid_document")
    return validate_rules(document["rules"])


def _value(event, field):
    evidence = event.get("evidence", {})
    # A recovery uses the original observation under evidence.previous.
    if isinstance(evidence, dict) and event.get("transition") == "resolved":
        evidence = evidence.get("previous", evidence)
    if not isinstance(evidence, dict):
        evidence = {}
    if field == "source":
        if event.get("event_type") == "protection.changed":
            return "defender"
        if event.get("event_type") == "listener.changed":
            return "listeners"
        return evidence.get("section")
    if field == "coverage_status":
        coverage = event.get("coverage", {})
        return coverage.get("status") if isinstance(coverage, dict) else None
    if field.startswith("evidence."):
        return evidence.get(field.partition(".")[2])
    return event.get(field)


def _matches(event, condition):
    value, expected, field, op = (_value(event, condition["field"]), condition["value"],
                                  condition["field"], condition["op"])
    if field in NUMBER_FIELDS:
        if type(value) is not int or not 0 <= value <= NUMBER_FIELDS[field]:
            return False
        return value == expected if op == "eq" else (value >= expected if op == "gte" else value <= expected)
    if not isinstance(value, str) or value not in ENUM_FIELDS[field]:
        return False
    return value == expected if op == "eq" else value in expected


def apply_rules(events, rules):
    """Classify all candidates without mutating inputs or dropping any event."""
    configured = validate_rules(rules)
    if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        raise RulesValidationError("rules_invalid_events")
    result = copy.deepcopy(events)
    for event in result:
        for rule in configured:
            if rule["enabled"] and all(_matches(event, item) for item in rule["conditions"]):
                event["severity"] = rule["severity"]
    return result
