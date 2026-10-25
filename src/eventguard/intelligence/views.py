"""Bounded public advisory views. Local read only; no inventory or agent data."""
from __future__ import annotations

from datetime import datetime, timezone
import re
import sqlite3
import stat
import unicodedata
from urllib.parse import unquote, urlsplit

from ..events.schema import IDENTIFIER
from ..runtime import Runtime
from .store import IntelligenceError, IntelligenceStore


MAX_CASES = 50
MAX_SOURCES = 50
MAX_CASE_SOURCES = 16
MAX_ALIASES = 32
MAX_ERRORS = 16
_CURRENT_REASONS = frozenset({
    "source_state_missing", "source_evidence_partial", "source_tracking_disabled",
    "source_success_unknown", "source_binding_changed", "source_evidence_stale",
    "source_freshness_unknown", "source_assertion_not_current", "assessment_time_unknown",
    "inventory_freshness_unknown", "inventory_evidence_stale", "assessment_unresolved",
})
_SOURCE_ERRORS = frozenset({
    "partial_parse", "csaf_evidence_incomplete", "parse_failed", "fetch_failed",
    "network_error", "timeout", "deadline_exceeded", "body_too_large",
    "unsupported_encoding", "pagination_required", "cross_origin_redirect",
    "tracked_ids_missing", "invalid_csaf", "unsupported_csaf_format",
    "invalid_csaf_publisher", "unsupported_csaf_status", "invalid_csaf_tracking",
    "invalid_csaf_vulnerabilities", "duplicate_csaf_vulnerability",
    "invalid_csaf_vulnerability", "invalid_csaf_vulnerability_id",
    "invalid_csaf_product_status", "invalid_csaf_product_tree",
    "invalid_csaf_products", "invalid_csaf_product_id", "too_many_records",
    "invalid_osv", "invalid_affected", "invalid_range", "invalid_range_event",
    "invalid_version", "invalid_versions", "invalid_rustsec", "invalid_requirements",
    "zdi_format_changed", "html_format_changed", "html_ids_absent", "invalid_cve",
    "unsafe_xml", "invalid_feed", "invalid_github_advisories", "invalid_github_advisory",
    "tls_verification_failed", "tls_error", "dns_error", "transport_denied",
    "connection_refused", "transport_error", "unexpected_304",
    "invalid_github_source_url", "github_redirect_rejected",
    "github_pagination_invalid_link", "github_pagination_ambiguous_next",
    "github_pagination_invalid_query", "github_pagination_cursor_unsupported",
    "github_pagination_initial_page_required", "github_pagination_cycle",
    "github_pagination_scope_changed", "github_pagination_page_limit",
    "github_record_conflict", "invalid_max_pages", "github_repository_identity_unverified",
})
# Only these finite protocol status codes are public. A source-provided suffix
# or exception message can never become an accepted reason.
_PROXY_ERRORS = frozenset("proxy_connect_" + str(code) for code in range(100, 600))


def _identifier(value):
    return value if isinstance(value, str) and IDENTIFIER.fullmatch(value) else None


def _title(value):
    if not isinstance(value, str):
        return ""
    # Also remove bidi, surrogate and other invisible control characters.
    return " ".join("".join(char for char in value[:2048]
                             if not unicodedata.category(char).startswith("C")).split())[:256]


def _date(value):
    if not isinstance(value, str) or len(value) > 80:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, TypeError, OverflowError):
        return None


def _url(value):
    """Validate display text only. This function never follows a URL."""
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        return None
    if any(char.isspace() or unicodedata.category(char).startswith("C") for char in value) or "\\" in value:
        return None
    decoded = unquote(value)
    if any(unicodedata.category(char).startswith("C") for char in decoded):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.fragment
                or parsed.port is not None and not 1 <= parsed.port <= 65535):
            return None
        parsed.hostname.encode("idna")
    except (ValueError, UnicodeError):
        return None
    return value


def _error(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return "source_error_unrecognized"
    if value in _SOURCE_ERRORS or value in _PROXY_ERRORS:
        return value
    if re.fullmatch(r"http_[1-5][0-9]{2}", value):
        return "http_error"
    return "source_error_unrecognized"


def _errors(items):
    if not isinstance(items, list):
        return [{"index": -1, "reason": "source_item_error_unrecognized"}]
    result = []
    for item in items[:MAX_ERRORS]:
        index = item.get("index") if isinstance(item, dict) else None
        reason = item.get("reason") if isinstance(item, dict) else None
        result.append({"index": index if type(index) is int and -1 <= index <= 10000 else -1,
                       "reason": reason if isinstance(reason, str) and reason in _SOURCE_ERRORS
                       else "source_item_error_unrecognized"})
    return result


def _source(state, record=None):
    state = state if isinstance(state, dict) else {}
    record = record if isinstance(record, dict) else {}
    config = state.get("config") if isinstance(state.get("config"), dict) else {}
    source_url = _url(record.get("source_url", config.get("url")))
    status = state.get("status")
    status = status if status in {"success", "not_modified", "partial", "failed"} else "unknown"
    freshness = state.get("freshness")
    freshness = freshness if freshness in {"fresh", "stale", "unknown"} else "unknown"
    errors = _errors(state.get("item_errors", []))
    incomplete = (state.get("has_partial_cache") is True or status == "partial"
                  or bool(errors) or source_url is None)
    return {"source_id": _identifier(state.get("source_id")), "source_url": source_url,
            "status": status, "reason_code": _error(state.get("error_code")),
            "published_at": _date(record.get("published_at")),
            "updated_at": _date(record.get("updated_at")),
            "fetched_at": _date(record.get("fetched_at")),
            "last_success_at": _date(state.get("last_success_at", state.get("last_success"))),
            "freshness": freshness, "partial": incomplete, "item_errors": errors,
            "item_errors_truncated": isinstance(state.get("item_errors"), list)
            and len(state["item_errors"]) > MAX_ERRORS}


def _case(case, sources):
    record = case.get("record") if isinstance(case.get("record"), dict) else {}
    current = case.get("current_assessment") if isinstance(case.get("current_assessment"), dict) else {}
    raw_reasons = current.get("reason_codes", [])
    reasons = {reason if isinstance(reason, str) and reason in _CURRENT_REASONS
               else "assessment_reason_unrecognized" for reason in raw_reasons[:32]} if isinstance(raw_reasons, list) else {"assessment_reason_unrecognized"}
    status = current.get("status")
    status = status if status in {"possible", "not_applicable", "unknown"} else "unknown"
    assertions = case.get("sources") if isinstance(case.get("sources"), list) else []
    public_sources = []
    for assertion in assertions[:MAX_CASE_SOURCES]:
        if isinstance(assertion, dict):
            source_id = _identifier(assertion.get("source_id"))
            source_state = sources.get(source_id, {"source_id": source_id})
            public_sources.append(_source(source_state, assertion.get("record")))
    partial = (status == "unknown" or len(assertions) > MAX_CASE_SOURCES
               or any(item["partial"] or item["freshness"] != "fresh" for item in public_sources)
               or not public_sources)
    # A read-time source failure/partial state cannot retain a historical
    # exclusion. It is unknown, never a local safety conclusion.
    if partial and status == "not_applicable":
        status = "unknown"
        reasons.add("public_evidence_incomplete")
    aliases = case.get("aliases") if isinstance(case.get("aliases"), list) else []
    confidence = record.get("confidence")
    return {"case_id": _identifier(case.get("case_id")),
            "aliases": [value for value in aliases[:MAX_ALIASES] if _identifier(value)],
            "aliases_truncated": len(aliases) > MAX_ALIASES,
            "title": _title(record.get("title")),
            "current_assessment": {"status": status, "reason_codes": sorted(reasons),
                                   "evaluated_at": _date(current.get("evaluated_at")),
                                   "incident_conclusion": "not_assessed"},
            "confidence": confidence if confidence in {"high", "medium", "low"} else "unknown",
            "partial": partial, "sources": public_sources,
            "sources_truncated": len(assertions) > MAX_CASE_SOURCES,
            "incident_conclusion": "not_assessed"}


def public_advisories(root, namespace, limit=50, event_id=None):
    """Read public advisory metadata; never return local facts or raw evidence.

    There is one installation database. Its durable binding must match the
    requested namespace before any case is exposed. Missing stores stay absent.
    """
    if namespace not in {"live", "test"}:
        raise ValueError("invalid_namespace")
    if type(limit) is not int or not 1 <= limit <= MAX_CASES:
        raise ValueError("advisory_view_limit_out_of_bounds")
    if event_id is not None and _identifier(event_id) is None:
        raise ValueError("invalid_event_identifier")
    result = {"state": "not_started", "namespace": namespace, "advisories": [], "sources": [],
              "total": 0, "limit": limit, "has_more": False, "sources_truncated": False,
              "reason_codes": [], "data_trust": "untrusted_data",
              "incident_conclusion": "not_assessed", "model_calls": 0}
    try:
        path = Runtime(root).path("data/advisories/intelligence.sqlite3")
        try:
            mode = path.stat().st_mode
        except FileNotFoundError:
            return result
        if not stat.S_ISREG(mode):
            raise IntelligenceError("advisory_view_store_unreadable")
        with IntelligenceStore(path, readonly=True) as store:
            state = store.status()
            binding = state.get("namespace_binding")
            if (not isinstance(binding, dict) or binding.get("namespace") != namespace
                    or type(binding.get("synthetic")) is not bool
                    or binding["synthetic"] and namespace != "test"):
                result.update(state="blocked", reason_codes=["advisory_namespace_binding_mismatch"])
                return result
            raw_sources = state.get("sources", [])
            if not isinstance(raw_sources, list):
                raise IntelligenceError("advisory_view_store_unreadable")
            source_map = {_identifier(source.get("source_id")): source for source in raw_sources
                          if isinstance(source, dict) and _identifier(source.get("source_id"))}
            if event_id is None:
                cases = store.cases(limit=limit)
                total = state.get("advisories", 0)
                total = total if type(total) is int and total >= 0 else 0
            else:
                case = store.event_case(event_id)
                cases = [case] if case is not None else []
                total = len(cases)
            public_cases = [_case(case, source_map) for case in cases if isinstance(case, dict)]
            public_sources = [_source(source) for source in raw_sources[:MAX_SOURCES] if isinstance(source, dict)]
            partial = (any(case["partial"] for case in public_cases)
                       or any(source["partial"] or source["freshness"] != "fresh"
                              or source["status"] not in {"success", "not_modified"} for source in public_sources))
            result.update(state="partial" if partial else "ready", advisories=public_cases,
                          sources=public_sources, total=total, has_more=total > len(public_cases),
                          sources_truncated=len(raw_sources) > MAX_SOURCES)
            return result
    except (IntelligenceError, sqlite3.Error, OSError, ValueError, TypeError, KeyError, RecursionError):
        # Never expose exceptions that can contain paths, SQL or source prose.
        result.update(state="blocked", reason_codes=["advisory_view_unavailable"])
        return result
