"""Validate declarative playbooks and describe a dry-run; never execute actions.

This module has no subprocess, network, filesystem mutation or model interface.
A rule is a reference/contract, not an authority to perform an operation.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import re

MAX_BYTES = 256 * 1024
MAX_RULES = 64
ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
VERSION = re.compile(r"^\d{1,5}\.\d{1,5}\.\d{1,5}$")
SEVERITIES = {"info", "warning", "high", "critical"}
TRANSITIONS = {"new", "escalated", "resolved"}
FORBIDDEN_KEYS = {"shell", "command", "commandline", "script", "exec", "eval", "powershell", "python", "webhook", "url", "credential", "password", "token"}
OPERATIONS = {"capabilities", "health", "query_listener", "query_process", "query_defender", "query_persistence_diff", "query_version", "query_event_metadata", "verify_signature_offline", "read_evidence"}
NODE_TYPES = {"tool", "agent_decision", "approval_gate", "allowlisted_action", "verification", "case_result", "retain_case_and_ask_user"}
RULE_FIELDS = {
    "rule_id", "version", "enabled", "title", "event_type", "event_filter", "severity", "priority", "exclusive_group",
    "investigation_steps", "edges", "tool_io", "decision_basis", "allowed_actions", "approval_gate", "timeout_retry",
    "expected_evidence", "completion_conditions", "recovery_conditions", "on_failure", "on_unknown", "audit", "supersedes",
}
NODE_FIELDS = {"id", "type", "operation", "input_from", "output_schema", "max_rows", "deadline_ms", "branches", "when_no_allowed_action"}


def _issue(code, rule_id=None, field=None):
    result = {"code": code}
    if isinstance(rule_id, str) and ID.fullmatch(rule_id):
        result["rule_id"] = rule_id
    if isinstance(field, str) and len(field) <= 80:
        result["field"] = field
    return result


def _load(value):
    try:
        if isinstance(value, (str, Path)):
            path = Path(value)
            if path.stat().st_size > MAX_BYTES:
                return None, [_issue("playbook_size_limit")]
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        elif isinstance(value, dict):
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
            if len(encoded.encode("utf-8")) > MAX_BYTES:
                return None, [_issue("playbook_size_limit")]
            document = copy.deepcopy(value)
        else:
            return None, [_issue("invalid_playbook_document")]
    except (OSError, ValueError, TypeError, RecursionError):
        return None, [_issue("playbook_read_or_format_error")]
    return document, []


def _scan_untrusted_shape(value, depth=0):
    if depth > 12:
        return True
    if isinstance(value, dict):
        if len(value) > 40:
            return True
        for key, child in value.items():
            if not isinstance(key, str) or len(key) > 80:
                return True
            normalized = key.casefold().replace("_", "").replace("-", "")
            if normalized in FORBIDDEN_KEYS or _scan_untrusted_shape(child, depth + 1):
                return True
    elif isinstance(value, list):
        if len(value) > 256 or any(_scan_untrusted_shape(child, depth + 1) for child in value):
            return True
    elif isinstance(value, str):
        return len(value) > 1024 or any(ord(ch) < 32 and ch not in "\n\t" for ch in value)
    elif isinstance(value, float) and not math.isfinite(value):
        return True
    elif value is not None and not isinstance(value, (bool, int, float)):
        return True
    return False


def _text_list(value, minimum=1, maximum=30):
    return isinstance(value, list) and minimum <= len(value) <= maximum and all(isinstance(item, str) and 0 < len(item) <= 512 for item in value)


def _event_types(rule):
    value = rule.get("event_type")
    return value if isinstance(value, list) else [value]


def _filters_overlap(left, right):
    for key in ("transition_in", "severity_in", "kind_in"):
        a, b = left.get(key), right.get(key)
        if a is not None and b is not None and not set(a).intersection(b):
            return False
    if left.get("synthetic") is not None and right.get("synthetic") is not None:
        if left["synthetic"] != right["synthetic"]:
            return False
    return True


def validate_playbooks(path_or_dict):
    """Return fixed-code findings; [] means structurally valid and unambiguous.

    Paths are read only. Arbitrary diagnostic errors or file contents are never
    echoed into findings. Validation does not enable or execute any rule.
    """
    document, issues = _load(path_or_dict)
    if issues:
        return issues
    if not isinstance(document, dict) or set(document) - {"schema_version", "playbooks"}:
        return [_issue("invalid_playbook_document")]
    if document.get("schema_version") != "1.0":
        return [_issue("unsupported_playbook_schema")]
    rules = document.get("playbooks")
    if not isinstance(rules, list) or not 1 <= len(rules) <= MAX_RULES:
        return [_issue("invalid_playbook_count")]
    if _scan_untrusted_shape(document):
        return [_issue("forbidden_or_unbounded_content")]
    seen = set()
    valid = []
    for rule in rules:
        if not isinstance(rule, dict):
            issues.append(_issue("invalid_rule"))
            continue
        rid = rule.get("rule_id")
        before = len(issues)
        if not isinstance(rid, str) or not ID.fullmatch(rid):
            issues.append(_issue("invalid_rule_id"))
        elif rid in seen:
            issues.append(_issue("duplicate_rule_id", rid))
        seen.add(rid) if isinstance(rid, str) else None
        if set(rule) - RULE_FIELDS:
            issues.append(_issue("unknown_rule_field", rid))
        required = RULE_FIELDS - {"title", "audit", "supersedes"}
        for key in sorted(required - set(rule)):
            issues.append(_issue("missing_rule_field", rid, key))
        if not isinstance(rule.get("version"), str) or not VERSION.fullmatch(rule["version"]):
            issues.append(_issue("invalid_rule_version", rid))
        if type(rule.get("enabled")) is not bool:
            issues.append(_issue("invalid_enabled", rid))
        types = _event_types(rule)
        if not types or len(types) > 10 or not all(isinstance(item, str) and ID.fullmatch(item) for item in types):
            issues.append(_issue("invalid_event_type", rid))
        if not isinstance(rule.get("severity"), str) or rule["severity"] not in SEVERITIES:
            issues.append(_issue("invalid_severity", rid))
        if type(rule.get("priority")) is not int or not 0 <= rule["priority"] <= 1000:
            issues.append(_issue("invalid_priority", rid))
        if not isinstance(rule.get("exclusive_group"), str) or not ID.fullmatch(rule["exclusive_group"]):
            issues.append(_issue("invalid_exclusive_group", rid))
        filters = rule.get("event_filter")
        if not isinstance(filters, dict) or set(filters) - {"transition_in", "severity_in", "kind_in", "synthetic"}:
            issues.append(_issue("invalid_event_filter", rid))
        else:
            for key, allowed in (("transition_in", TRANSITIONS), ("severity_in", SEVERITIES)):
                if key in filters and (not _text_list(filters[key], maximum=5) or not set(filters[key]).issubset(allowed)):
                    issues.append(_issue("invalid_event_filter", rid, key))
            if "kind_in" in filters and (not _text_list(filters["kind_in"], maximum=10) or not all(ID.fullmatch(x) for x in filters["kind_in"])):
                issues.append(_issue("invalid_event_filter", rid, "kind_in"))
            if "synthetic" in filters and type(filters["synthetic"]) is not bool:
                issues.append(_issue("invalid_event_filter", rid, "synthetic"))
        for key in ("decision_basis", "expected_evidence", "completion_conditions", "recovery_conditions"):
            if not _text_list(rule.get(key)):
                issues.append(_issue("invalid_evidence_or_condition", rid, key))
        for key in ("on_failure", "on_unknown"):
            if rule.get(key) != "bounded_read_only_then_ask":
                issues.append(_issue("unsafe_fallback", rid, key))
        tool_io = rule.get("tool_io")
        if not isinstance(tool_io, dict) or set(tool_io) != {"input_schema", "output_schema"} or not all(isinstance(v, str) and ID.fullmatch(v) for v in tool_io.values()):
            issues.append(_issue("invalid_tool_io", rid))
        actions = rule.get("allowed_actions")
        if not isinstance(actions, list) or len(actions) > 10 or not all(isinstance(item, str) and ID.fullmatch(item) for item in actions):
            issues.append(_issue("invalid_allowed_actions", rid))
        gate = rule.get("approval_gate")
        if not isinstance(gate, dict) or gate != {"required_for_sensitive_actions": True, "authority_source": "separate_valid_user_approval", "missing_or_expired": "do_not_execute"}:
            issues.append(_issue("invalid_approval_gate", rid))
        limits = rule.get("timeout_retry")
        if not isinstance(limits, dict) or set(limits) != {"query_deadline_ms", "active_diagnosis_budget_ms", "read_only_retries"}:
            issues.append(_issue("invalid_timeout_retry", rid))
        elif any(type(limits[key]) is not int or not low <= limits[key] <= high for key, low, high in (("query_deadline_ms",1,15000),("active_diagnosis_budget_ms",1,60000),("read_only_retries",0,1))):
            issues.append(_issue("invalid_timeout_retry", rid))
        nodes = rule.get("investigation_steps")
        edges = rule.get("edges")
        ids = set()
        if not isinstance(nodes, list) or not 1 <= len(nodes) <= 30:
            issues.append(_issue("invalid_steps", rid))
            nodes = []
        for node in nodes:
            if not isinstance(node, dict) or set(node) - NODE_FIELDS:
                issues.append(_issue("invalid_node", rid))
                continue
            nid = node.get("id")
            if not isinstance(nid, str) or not ID.fullmatch(nid) or nid in ids:
                issues.append(_issue("invalid_node_id", rid))
            elif nid:
                ids.add(nid)
            if not isinstance(node.get("type"), str) or node["type"] not in NODE_TYPES:
                issues.append(_issue("invalid_node_type", rid))
            if node.get("type") == "tool":
                if not isinstance(node.get("operation"), str) or node["operation"] not in OPERATIONS:
                    issues.append(_issue("unsupported_tool_operation", rid))
                if not _text_list(node.get("input_from", []), minimum=0, maximum=10) or not all(re.fullmatch(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*", x) for x in node.get("input_from", [])):
                    issues.append(_issue("invalid_tool_binding", rid))
                if not isinstance(node.get("output_schema"), str) or not ID.fullmatch(node["output_schema"]):
                    issues.append(_issue("invalid_output_schema", rid))
                if type(node.get("max_rows")) is not int or not 1 <= node["max_rows"] <= 100:
                    issues.append(_issue("invalid_tool_limit", rid))
                if type(node.get("deadline_ms")) is not int or not 1 <= node["deadline_ms"] <= 15000:
                    issues.append(_issue("invalid_tool_limit", rid))
            if node.get("type") == "agent_decision" and (not _text_list(node.get("branches"), maximum=10) or not all(ID.fullmatch(x) for x in node.get("branches", []))):
                issues.append(_issue("invalid_decision_branches", rid))
            if node.get("type") == "allowlisted_action" and node.get("when_no_allowed_action") != "blocked":
                issues.append(_issue("unsafe_action_fallback", rid))
        adjacency = {nid: [] for nid in ids}
        if not isinstance(edges, list) or not 1 <= len(edges) <= 100:
            issues.append(_issue("invalid_edges", rid))
            edges = []
        for edge in edges:
            if not isinstance(edge, dict) or set(edge) != {"from", "on", "to"} or not isinstance(edge.get("from"), str) or not isinstance(edge.get("to"), str) or edge["from"] not in ids or edge["to"] not in ids or not _text_list(edge.get("on"), maximum=10) or not all(ID.fullmatch(x) for x in edge.get("on", [])):
                issues.append(_issue("invalid_edge_reference", rid))
            else:
                adjacency[edge["from"]].append(edge["to"])
        def cyclic(node, visiting, visited):
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(cyclic(child, visiting, visited) for child in adjacency[node]):
                return True
            visiting.remove(node)
            visited.add(node)
            return False
        visited = set()
        if any(cyclic(node, set(), visited) for node in ids if node not in visited):
            issues.append(_issue("unbounded_graph_cycle", rid))
        if len(issues) == before:
            valid.append(rule)
    for index, left in enumerate(valid):
        if not left["enabled"]:
            continue
        for right in valid[index + 1:]:
            if right["enabled"] and left["priority"] == right["priority"] and left["exclusive_group"] == right["exclusive_group"] and set(_event_types(left)).intersection(_event_types(right)) and _filters_overlap(left["event_filter"], right["event_filter"]):
                issues.append(_issue("conflicting_rules", left["rule_id"]))
                issues.append(_issue("conflicting_rules", right["rule_id"]))
    return issues[:100]


def _matches(event, rule):
    if not rule["enabled"] or event.get("event_type") not in _event_types(rule):
        return False
    filters = rule["event_filter"]
    for key, field in (("transition_in", "transition"), ("severity_in", "severity")):
        if key in filters and event.get(field) not in filters[key]:
            return False
    if "synthetic" in filters and event.get("synthetic") is not filters["synthetic"]:
        return False
    if "kind_in" in filters:
        evidence = event.get("evidence")
        if not isinstance(evidence, dict) or evidence.get("kind") not in filters["kind_in"]:
            return False
    return True


def simulate(event, playbooks):
    """Return a plan only; event contents cannot supply rules or authorization."""
    base = {"execution_mode":"dry_run", "authorization_granted":False,
            "rule_is_authorization":False, "tools_executed":[], "actions_executed":[],
            "matched_rules":[], "selected_rule":None, "steps":[], "blocked_actions":[],
            "diagnostic_operations":[], "requires_approval":False,
            "next":"bounded_read_only_then_ask"}
    document, loading = _load(playbooks)
    findings = loading or validate_playbooks(document)
    structural = [item for item in findings if item["code"] != "conflicting_rules"]
    if structural:
        return dict(base, status="invalid_playbooks", findings=findings,
                    conclusion="規則格式或安全驗證未通過；未執行任何工具或動作。")
    if not isinstance(event, dict) or ("schema_version" in event and event["schema_version"] != "2.0") or not isinstance(event.get("event_type"), str) or not ID.fullmatch(event["event_type"]):
        return dict(base, status="invalid_event", conclusion="事件格式未知；僅可安全查證來源並提問。")
    matches = [rule for rule in document["playbooks"] if _matches(event, rule)]
    matches.sort(key=lambda rule:(-rule["priority"], rule["rule_id"]))
    base["matched_rules"] = [{"rule_id":r["rule_id"],"version":r["version"]} for r in matches]
    if not matches:
        return dict(base, status="no_match", conclusion="沒有適用規則；只可在有效授權內做有界唯讀調查並提問。")
    highest = matches[0]["priority"]
    if len([rule for rule in matches if rule["priority"] == highest]) > 1:
        return dict(base, status="conflict", findings=[_issue("multiple_equal_priority_rules")],
                    conclusion="多條規則同優先序且有歧義；保留事件，不猜處置。")
    selected = matches[0]
    base["selected_rule"] = {"rule_id":selected["rule_id"],"version":selected["version"]}
    base["steps"] = copy.deepcopy(selected["investigation_steps"])
    base["edges"] = copy.deepcopy(selected["edges"])
    base["diagnostic_operations"] = list(dict.fromkeys(node["operation"] for node in selected["investigation_steps"] if node["type"] == "tool"))
    base["blocked_actions"] = [{"action_id":action,"reason":"dry_run_has_no_execution_authority"} for action in selected["allowed_actions"]]
    base["requires_approval"] = bool(selected["allowed_actions"])
    base["approval_policy"] = copy.deepcopy(selected["approval_gate"])
    base["expected_evidence"] = list(selected["expected_evidence"])
    base["unknown_route"] = selected["on_unknown"]
    return dict(base, status="planned", requires_agent_decision=True,
                conclusion="僅列出已驗證規則的調查計畫；沒有工具執行、批准或系統處置。")
