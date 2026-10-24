"""Bounded, read-only public advisory retrieval. No model or subprocess calls.

The caller owns durable caching, scheduling and backoff. A failed fetch never
means an empty or withdrawn advisory set. Source text is untrusted data.
"""
from __future__ import annotations

import email.utils
import errno
import hashlib
import ipaddress
import json
import re
import socket
import ssl
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

DEFAULT_BODY = 2 * 1024 * 1024
MAX_BODY = 8 * 1024 * 1024
MAX_RECORDS = 512
MAX_TEXT = 2048
ADAPTERS = {"osv", "rustsec", "feed", "zdi", "github_advisories", "html", "cve", "nvidia_csaf"}
ID_RE = re.compile(r"\b(?:CVE-\d{4}-\d{4,10}|RUSTSEC-\d{4}-\d{4}|ZDI-CAN-\d{4,8}|ZDI-\d{2}-\d{1,6}|GHSA-[23456789cfghjmpqrvwx]{4}-[23456789cfghjmpqrvwx]{4}-[23456789cfghjmpqrvwx]{4})\b", re.I)


class SourceError(ValueError):
    """A stable reason code. Never includes a server body or exception text."""


class SourceRecords(list):
    """List-compatible parse result with bounded, non-prose item failures."""

    def __init__(self, values=(), *, item_errors=()):
        super().__init__(values)
        self.item_errors = list(item_errors)
        self.coverage = "partial" if self.item_errors or any(
            evidence.get("coverage") == "partial" for record in self for evidence in record.get("evidence", [])) else "success"


def _text(value: Any, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join("".join(c for c in value if c >= " " and c != "\x7f").split())[:limit]


def _url(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise SourceError("invalid_url")
    try:
        parsed = urllib.parse.urlsplit(value)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.fragment:
            raise ValueError
        if parsed.port not in (None, 443) or host.lower() in {"localhost", "localhost.localdomain"} or "." not in host:
            raise ValueError
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError
        except ValueError as exc:
            if re.fullmatch(r"[\d.:]+", host):
                raise ValueError from exc
        if any(ord(c) < 33 or ord(c) == 127 for c in value):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise SourceError("invalid_url") from exc
    return value


def _ids(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    return sorted({m.group(0).upper() if not m.group(0).lower().startswith("ghsa-") else m.group(0).lower().replace("ghsa-", "GHSA-")
                   for value in values[:128] if isinstance(value, str) for m in ID_RE.finditer(value)})[:64]


def _date(value: Any) -> str | None:
    if not isinstance(value, (str, datetime)):
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (ValueError, OverflowError):
        try:
            parsed = email.utils.parsedate_to_datetime(value)
            return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError):
            return None


def _source(source: dict) -> dict:
    if not isinstance(source, dict):
        raise SourceError("invalid_source")
    result = dict(source)
    if not isinstance(result.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", result["id"]):
        raise SourceError("invalid_source_id")
    if result.get("adapter") not in ADAPTERS:
        raise SourceError("invalid_adapter")
    result["url"] = _url(result.get("url"))
    if result["adapter"] == "nvidia_csaf":
        # This adapter has one publisher. Never follow bulletin-supplied URLs.
        parsed = urllib.parse.urlsplit(result["url"])
        if (parsed.hostname != "raw.githubusercontent.com" or parsed.query
                or not re.fullmatch(r"/NVIDIA/product-security/(?:main|[0-9a-f]{40})/20\d{2}/([0-9]{4,8})/\1\.json", parsed.path)):
            raise SourceError("invalid_nvidia_source_url")
    for key, default, low, high in (("interval_seconds", 3600, 60, 604800),
                                    ("stale_after_seconds", 86400, 60, 2592000),
                                    ("timeout_seconds", 10, 1, 30),
                                    ("max_bytes", DEFAULT_BODY, 128, MAX_BODY)):
        value = result.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise SourceError("invalid_" + key)
        result[key] = value
    if result["stale_after_seconds"] < result["interval_seconds"]:
        raise SourceError("stale_before_interval")
    tracked = result.get("tracking_ids", [])
    if not isinstance(tracked, list) or len(tracked) > 64 or any(not isinstance(x, str) or _ids([x]) != [x] for x in tracked):
        raise SourceError("invalid_tracking_ids")
    result["tracking_ids"] = tracked
    if type(result.get("important", True)) is not bool:
        raise SourceError("invalid_important")
    result.setdefault("important", True)
    if type(result.get("enabled", True)) is not bool:
        raise SourceError("invalid_enabled")
    result.setdefault("enabled", True)
    threshold = result.get("failure_threshold", 3)
    if type(threshold) is not int or not 1 <= threshold <= 1000:
        raise SourceError("invalid_failure_threshold")
    result["failure_threshold"] = threshold
    if result["adapter"] == "html":
        # Literal markers only. Source-controlled regular expressions are not executed.
        markers = result.get("html_markers", [])
        if not isinstance(markers, list) or not 1 <= len(markers) <= 8 or any(not isinstance(x, str) or not 1 <= len(x) <= 128 for x in markers):
            raise SourceError("invalid_html_markers")
    return result


def load_config(path: str | Path) -> dict:
    path = Path(path)
    if path.stat().st_size > 262144:
        raise SourceError("config_too_large")
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise SourceError("invalid_config")
    sources = data.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 64:
        raise SourceError("invalid_sources")
    threshold = data.get("failure_threshold", 3)
    if type(threshold) is not int or not 1 <= threshold <= 1000:
        raise SourceError("invalid_failure_threshold")
    sources = [_source({"failure_threshold": threshold, **source}) if isinstance(source, dict) else _source(source) for source in sources]
    if len({source["id"] for source in sources}) != len(sources):
        raise SourceError("duplicate_source_id")
    result = dict(data)
    result["sources"] = sources
    namespace = result.get("namespace", "live")
    if not isinstance(namespace, str) or namespace not in {"live", "test"}:
        raise SourceError("invalid_namespace")
    result["namespace"] = namespace
    policy = result.get("storage", {})
    if not isinstance(policy, dict) or set(policy) - {"max_records", "max_changes", "max_bytes", "cooldown_seconds"}:
        raise SourceError("invalid_storage")
    policy = dict(policy)
    for key, default, minimum, maximum in (("max_records", 4096, 1, 1000000), ("max_changes", 16384, 1, 1000000),
                                          ("max_bytes", 33554432, 65536, 1073741824), ("cooldown_seconds", 3600, 0, 31536000)):
        value = policy.get(key, default)
        if type(value) is not int or not minimum <= value <= maximum:
            raise SourceError("invalid_storage_" + key)
        policy[key] = value
    result["storage"] = policy
    reasons = {"possible_relevance", "fix_available", "exploitation_confirmed", "exposure_changed", "withdrawn", "source_stale", "recovered"}
    rules = result.get("rules", {"enabled_reasons": sorted(reasons), "severity": {"possible_relevance": "warning", "fix_available": "warning", "exploitation_confirmed": "high", "exposure_changed": "warning", "withdrawn": "info", "source_stale": "warning", "recovered": "info"}})
    if not isinstance(rules, dict) or set(rules) != {"enabled_reasons", "severity"}:
        raise SourceError("invalid_rules")
    enabled, severities = rules["enabled_reasons"], rules["severity"]
    if not isinstance(enabled, list) or len(enabled) > len(reasons) or any(not isinstance(item, str) or item not in reasons for item in enabled) or len(set(enabled)) != len(enabled):
        raise SourceError("invalid_enabled_reasons")
    if not isinstance(severities, dict) or any(key not in reasons or not isinstance(value, str) or value not in {"info", "warning", "high", "critical"} for key, value in severities.items()):
        raise SourceError("invalid_rule_severity")
    result["rules"] = rules
    inventory = result.get("inventory", {"paths": []})
    if not isinstance(inventory, dict) or not isinstance(inventory.get("paths", []), list):
        raise SourceError("invalid_inventory")
    result["inventory"] = inventory
    return result


def _record(source: dict, *, ids: list[str], component: str = "", ecosystem: str = "", title: str = "",
            published: Any = None, updated: Any = None, withdrawn: bool = False,
            affected: list | None = None, fixes: list | None = None, evidence: list | None = None,
            conditions: dict | None = None, url: str | None = None) -> dict:
    return {"ids": _ids(ids), "component": _text(component or source.get("component", "unknown"), 160),
            "ecosystem": _text(ecosystem or source.get("ecosystem", "unknown"), 80), "title": _text(title, 512),
            "published_at": _date(published), "updated_at": _date(updated), "withdrawn": withdrawn,
            "affected": affected or [], "fixes": fixes or [], "conditions": conditions or {},
            "evidence": evidence or [{"url": url or source["url"], "stage": "published", "claim": "advisory_present", "confidence": "high"}],
            "exploitation": "unknown", "confidence": "high", "source_url": url or source["url"]}


def _select(records: list[dict], source: dict) -> list[dict]:
    tracked = set(source.get("tracking_ids", []))
    result = [r for r in records if r["ids"] and (not tracked or tracked.intersection(r["ids"]))]
    if len(result) > MAX_RECORDS:
        raise SourceError("too_many_records")
    return result


def _osv(data: Any, source: dict) -> list[dict]:
    items = data if isinstance(data, list) else [data]
    if len(items) > MAX_RECORDS:
        raise SourceError("too_many_records")
    records = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or "affected" not in item:
            raise SourceError("invalid_osv")
        affected, fixes = [], []
        if not isinstance(item["affected"], list) or len(item["affected"]) > 128:
            raise SourceError("invalid_affected")
        for entry in item["affected"]:
            package = entry.get("package", {})
            ranges = entry.get("ranges", [])
            if not isinstance(package, dict) or not isinstance(ranges, list) or len(ranges) > 64:
                raise SourceError("invalid_affected")
            safe_ranges = []
            for span in ranges:
                if not isinstance(span, dict) or span.get("type") not in {"SEMVER", "ECOSYSTEM", "GIT"} or not isinstance(span.get("events"), list) or len(span["events"]) > 128:
                    raise SourceError("invalid_range")
                events = []
                for event in span["events"]:
                    if not isinstance(event, dict) or len(event) != 1 or next(iter(event)) not in {"introduced", "fixed", "last_affected", "limit"}:
                        raise SourceError("invalid_range_event")
                    key, value = next(iter(event.items()))
                    if not isinstance(value, str) or len(value) > 160:
                        raise SourceError("invalid_version")
                    events.append({key: value})
                    if key == "fixed":
                        fixes.append({"stage": "released" if span["type"] != "GIT" else "unknown", "version": value if span["type"] != "GIT" else None,
                                      "commit": value if span["type"] == "GIT" else None, "package": _text(package.get("name"), 160), "source_url": source["url"]})
                safe_ranges.append({"type": span["type"], "events": events})
            versions = entry.get("versions", [])
            if not isinstance(versions, list) or len(versions) > 4096 or any(not isinstance(v, str) or len(v) > 160 for v in versions):
                raise SourceError("invalid_versions")
            affected.append({"ecosystem": _text(package.get("ecosystem"), 80), "package": _text(package.get("name"), 160), "ranges": safe_ranges, "versions": versions})
        records.append(_record(source, ids=[item["id"], *item.get("aliases", [])], title=item.get("summary", item["id"]),
                               component=affected[0]["package"] if affected else "", ecosystem=affected[0]["ecosystem"] if affected else "",
                               published=item.get("published"), updated=item.get("modified"), withdrawn=bool(item.get("withdrawn")), affected=affected, fixes=fixes))
    return _select(records, source)


def _rustsec(text: str, source: dict) -> list[dict]:
    match = re.search(r"\A\s*```toml\s*\n(.*?)\n```", text, re.S)
    data = tomllib.loads(match.group(1) if match else text)
    advisory, versions = data.get("advisory", {}), data.get("versions", {})
    if not isinstance(advisory.get("id"), str) or not isinstance(advisory.get("package"), str):
        raise SourceError("invalid_rustsec")
    requirements = {}
    for key in ("patched", "unaffected"):
        values = versions.get(key, [])
        if not isinstance(values, list) or len(values) > 64 or any(not isinstance(v, str) or len(v) > 160 for v in values):
            raise SourceError("invalid_requirements")
        requirements[key] = values
    # Preserve Cargo requirements. The matcher must evaluate them, never compare strings.
    affected = [{"ecosystem": "crates.io", "package": advisory["package"], "ranges": [], "versions": [], **requirements}]
    fixes = [{"stage": "released", "version": requirement, "commit": None, "package": advisory["package"], "source_url": source["url"]}
             for requirement in requirements["patched"]]
    rest = text[match.end():] if match else ""
    title = next((line.lstrip("# ").strip() for line in rest.splitlines() if line.startswith("# ")), advisory["id"])
    conditions = {"deployment": "unknown", "features": "unknown", "tls_backend": "unknown", "trust_roots": "unknown"}
    if advisory["package"] in {"webpki-roots", "webpki-root-certs"} and "0.26.11" in " ".join(requirements["unaffected"]):
        conditions["compatibility_wrapper"] = {"version": "0.26.11", "requires_parent": advisory["package"], "parent_min_version": "1.0.10"}
    return _select([_record(source, ids=[advisory["id"], *advisory.get("aliases", [])], component=advisory["package"], ecosystem="crates.io", title=title,
                            published=str(advisory.get("date", "")), withdrawn=bool(advisory.get("withdrawn")), affected=affected, fixes=fixes, conditions=conditions)], source)


class _HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.parts: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._hidden += 1
        if tag == "tr":
            self._row = []
        if tag in {"td", "th"}:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._hidden = max(0, self._hidden - 1)
        if tag in {"td", "th"} and self._cell is not None:
            if self._row is not None:
                self._row.append(_text(" ".join(self._cell)))
            self._cell = None
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, text):
        if not self._hidden:
            self.parts.append(text)
            if self._cell is not None:
                self._cell.append(text)


def _html(text: str, source: dict) -> list[dict]:
    parser = _HTML()
    parser.feed(text)
    plain = _text(" ".join(parser.parts), MAX_BODY)
    if source["adapter"] == "zdi":
        # A missing table or changed header is a parser failure, not zero findings.
        if "ZDI-CAN-" not in plain or not parser.rows:
            raise SourceError("zdi_format_changed")
        records = []
        for row in parser.rows:
            identifier_match = re.match(r"(ZDI-CAN-\d+)\b", row[0]) if row else None
            if len(row) < 4 or not identifier_match:
                continue
            identifier, vendor = identifier_match.group(1), row[1]
            component = "connman" if vendor.lower() == "connman" else "linux-kernel" if vendor.lower() == "linux" else vendor.lower()
            # Upcoming table dates are vendor-notified / deadline. NOT publication.
            notified = next((x for x in row[2:] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)), None)
            records.append(_record(source, ids=[identifier], component=component, ecosystem="Linux" if component == "linux-kernel" else "system", title=identifier,
                                   conditions={"vendor_notified_at": notified, "exposure": "unknown", "affected_versions": "unknown", "fix_status": "unknown"},
                                   evidence=[{"url": source["url"], "stage": "reported", "claim": "vendor_notified", "confidence": "high"}]))
        result = _select(records, source)
        # Removal from Upcoming can mean publication; preserve cache and require investigation.
        observed_ids = {identifier for record in result for identifier in record["ids"]}
        if set(source.get("tracking_ids", [])) - observed_ids:
            raise SourceError("tracked_ids_missing")
        return result
    if any(marker not in plain for marker in source.get("html_markers", [])):
        raise SourceError("html_format_changed")
    identifiers = [identifier for identifier in source.get("tracking_ids", []) if identifier in plain] or _ids([plain])
    if not identifiers:
        raise SourceError("html_ids_absent")
    # A list or discussion may mention unrelated IDs. Co-occurrence is NOT alias evidence.
    return _select([_record(source, ids=[identifier], title=identifier,
                           conditions={"affected_versions": "unknown", "fix_status": "unknown", "exposure": "unknown"})
                    for identifier in identifiers], source)


def _csaf_products(tree: Any) -> dict[str, dict]:
    """Resolve bounded CSAF branch IDs. Vendor version labels stay uninterpreted."""
    if not isinstance(tree, dict):
        raise SourceError("invalid_csaf_product_tree")
    products, visited = {}, 0
    stack = [(tree, (), 0)]
    while stack:
        node, path, depth = stack.pop()
        visited += 1
        if not isinstance(node, dict) or depth > 16 or visited > 2048:
            raise SourceError("invalid_csaf_product_tree")
        category = _text(node.get("category"), 80)
        label = _text(node.get("name"), 160)
        branch = path + (({"category": category, "name": label},) if category or label else ())
        values = node.get("full_product_names", [])
        if not isinstance(values, list) or len(values) > 512:
            raise SourceError("invalid_csaf_products")
        if "product" in node:
            values = [*values, node["product"]]
        for item in values:
            if not isinstance(item, dict):
                raise SourceError("invalid_csaf_products")
            identifier = item.get("product_id")
            if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 160
                    or _text(identifier, 160) != identifier or identifier in products):
                raise SourceError("invalid_csaf_product_id")
            helper = item.get("product_identification_helper", {})
            if not isinstance(helper, dict):
                raise SourceError("invalid_csaf_products")
            products[identifier] = {"product_id": identifier, "name": _text(item.get("name"), 160),
                                    "version_label": _text(item.get("name"), 160) if category == "product_version" else None,
                                    "cpe": _text(helper.get("cpe"), 512) or None, "branch_path": list(branch)}
        children = node.get("branches", [])
        if not isinstance(children, list) or len(children) > 512 or len(products) > 1024:
            raise SourceError("invalid_csaf_product_tree")
        stack.extend((child, branch, depth + 1) for child in reversed(children))
    return products


def _nvidia_csaf(data: Any, source: dict, *, _isolated=False) -> list[dict]:
    """NVIDIA's public CSAF 2.0 bulletin, not an installed-product assertion.

    CSAF 2.0 has no withdrawn document status. Missing bulletins, disputed
    involvements, free text and known_not_affected never become a withdrawal.
    Unsupported formats fail and let the existing durable cache become stale.
    """
    if not isinstance(data, dict) or not isinstance(data.get("document"), dict):
        raise SourceError("invalid_csaf")
    document = data["document"]
    if document.get("csaf_version") != "2.0" or document.get("category") != "csaf_security_advisory":
        raise SourceError("unsupported_csaf_format")
    publisher, tracking = document.get("publisher", {}), document.get("tracking", {})
    if (not isinstance(publisher, dict) or not isinstance(tracking, dict)
            or publisher.get("category") != "vendor"
            or publisher.get("namespace") not in {"https://www.nvidia.com/security", "https://www.nvidia.com/security/"}):
        raise SourceError("invalid_csaf_publisher")
    status = tracking.get("status")
    if status not in {"draft", "interim", "final"}:
        raise SourceError("unsupported_csaf_status")
    bulletin = _text(tracking.get("id"), 80)
    expected = urllib.parse.urlsplit(source["url"]).path.rsplit("/", 1)[-1][:-5]
    if bulletin != expected or not _text(tracking.get("version"), 80):
        raise SourceError("invalid_csaf_tracking")
    vulnerabilities = data.get("vulnerabilities")
    if not isinstance(vulnerabilities, list) or not 1 <= len(vulnerabilities) <= MAX_RECORDS:
        raise SourceError("invalid_csaf_vulnerabilities")
    products = _csaf_products(data.get("product_tree", {}))
    if not _isolated:
        records, errors, seen = [], [], set()
        # A malformed vulnerability must not erase valid siblings. The source
        # remains explicitly partial; callers cannot promote this to success.
        item_source = dict(source, tracking_ids=[])
        for index, item in enumerate(vulnerabilities):
            try:
                if isinstance(item, dict) and isinstance(item.get("cve"), str):
                    if item["cve"] in seen:
                        raise SourceError("duplicate_csaf_vulnerability")
                    seen.add(item["cve"])
                records.extend(_nvidia_csaf(dict(data, vulnerabilities=[item]), item_source, _isolated=True))
            except SourceError as exc:
                errors.append({"index": index, "reason": str(exc)})
        observed = {identifier for record in records for identifier in record["ids"]}
        if set(source.get("tracking_ids", [])) - observed:
            errors.append({"index": -1, "reason": "tracked_ids_missing"})
        return SourceRecords(_select(records, source), item_errors=errors)
    records, observed = [], set()
    allowed = {"first_affected", "last_affected", "known_affected", "known_not_affected",
               "first_fixed", "fixed", "recommended", "under_investigation"}
    for item in vulnerabilities:
        if not isinstance(item, dict):
            raise SourceError("invalid_csaf_vulnerability")
        identifier = item.get("cve")
        if not isinstance(identifier, str) or not re.fullmatch(r"CVE-\d{4}-\d{4,10}", identifier) or identifier in observed:
            raise SourceError("invalid_csaf_vulnerability_id")
        observed.add(identifier)
        states = item.get("product_status", {})
        if not isinstance(states, dict) or set(states) - allowed:
            raise SourceError("invalid_csaf_product_status")
        affected, fixes, count = [], [], 0
        partial = not states or not products
        for state, identifiers in sorted(states.items()):
            if not isinstance(identifiers, list) or not 1 <= len(identifiers) <= 128:
                raise SourceError("invalid_csaf_product_status")
            seen = set()
            for product_id in identifiers:
                count += 1
                if (count > 256 or not isinstance(product_id, str) or not 1 <= len(product_id) <= 160
                        or _text(product_id, 160) != product_id or product_id in seen):
                    raise SourceError("invalid_csaf_product_status")
                seen.add(product_id)
                product = products.get(product_id, {"product_id": product_id, "name": "", "version_label": None, "cpe": None, "branch_path": []})
                partial |= product_id not in products or not product["version_label"]
                # No generic SemVer range is inferred from CPE or vendor prose.
                affected.append({"package": {"ecosystem": source.get("ecosystem", "NVIDIA"), "name": source.get("component", "unknown")},
                                 "ranges": [], "versions": [], "csaf_status": state, "csaf_product": product,
                                 "version_interpretation": "unknown"})
                if state in {"fixed", "first_fixed"}:
                    version = product["version_label"]
                    fixes.append({"stage": "released" if version and status != "draft" and _date(item.get("release_date")) else "unknown",
                                  "version": version, "commit": None, "package": source.get("component", "unknown"),
                                  "ecosystem": source.get("ecosystem", "NVIDIA"), "csaf_product_id": product_id,
                                  "source_url": source["url"], "installed": "unknown", "running": "unknown"})
        published, updated = tracking.get("initial_release_date"), tracking.get("current_release_date")
        partial |= not _date(published) or not _date(updated)
        evidence = [{"url": source["url"], "stage": "published" if status != "draft" else "reported",
                     "claim": "advisory_present", "confidence": "high", "format": "CSAF-2.0",
                     "bulletin_id": bulletin, "revision": _text(tracking.get("version"), 80),
                     "document_status": status, "coverage": "partial" if partial else "success"}]
        records.append(_record(source, ids=[identifier], title=document.get("title", identifier),
                               ecosystem=source.get("ecosystem", "NVIDIA"), published=published, updated=updated,
                               affected=affected, fixes=fixes, evidence=evidence,
                               conditions={"deployment": "unknown", "affected_versions": "unknown", "version_comparison": "unknown",
                                           "withdrawal_status": "unknown", "local_applicability": "unknown"}))
    return _select(records, source)


def _cve(data: Any, source: dict) -> list[dict]:
    if not isinstance(data, dict) or data.get("dataType") != "CVE_RECORD":
        raise SourceError("invalid_cve")
    metadata = data.get("cveMetadata", {})
    identifier, state = metadata.get("cveId"), metadata.get("state")
    if not isinstance(identifier, str) or not identifier.startswith("CVE-") or state not in {"PUBLISHED", "REJECTED"}:
        raise SourceError("invalid_cve")
    cna = data.get("containers", {}).get("cna", {})
    affected = []
    # CVE custom version types need ecosystem-specific interpretation. Preserve typed
    # conditions without pretending that arbitrary vendor versions are SemVer.
    for entry in cna.get("affected", [])[:128]:
        if not isinstance(entry, dict):
            raise SourceError("invalid_affected")
        versions = entry.get("versions", [])
        if not isinstance(versions, list) or len(versions) > 128:
            raise SourceError("invalid_versions")
        conditions = []
        for version in versions:
            if not isinstance(version, dict):
                raise SourceError("invalid_versions")
            conditions.append({key: _text(version.get(key), 160) for key in ("version", "status", "versionType", "lessThan", "lessThanOrEqual") if key in version})
        affected.append({"ecosystem": source.get("ecosystem", "unknown"), "package": _text(entry.get("packageName", entry.get("product")), 160), "ranges": [], "versions": [], "cve_versions": conditions})
    return _select([_record(source, ids=[identifier], title=cna.get("title", identifier), published=metadata.get("datePublished"), updated=metadata.get("dateUpdated"),
                            withdrawn=state == "REJECTED", affected=affected, conditions={"cve_state": state, "deployment": "unknown"})], source)


def _feed(text: str, source: dict) -> list[dict]:
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise SourceError("unsafe_xml")
    root = ET.fromstring(text)
    local = lambda tag: tag.rsplit("}", 1)[-1]
    if local(root.tag) not in {"rss", "feed", "RDF"}:
        raise SourceError("invalid_feed")
    entries = [x for x in root.iter() if local(x.tag) in {"item", "entry"}]
    if len(entries) > MAX_RECORDS:
        raise SourceError("too_many_records")
    records = []
    for entry in entries:
        values: dict[str, str] = {}
        for child in entry:
            name = local(child.tag)
            if name == "link":
                if child.get("rel", "alternate") == "alternate":
                    values["link"] = child.get("href") or child.text or ""
            else:
                values[name] = " ".join(child.itertext())
        identifiers = _ids(list(values.values()))
        if not identifiers:
            continue
        url = _url(urllib.parse.urljoin(source["url"], values.get("link", source["url"])))
        # Feed prose has no alias contract. Two IDs mentioned in one post can
        # describe independent flaws, even when they share a component.
        for identifier in identifiers:
            records.append(_record(source, ids=[identifier], title=values.get("title", ""), published=values.get("published", values.get("pubDate")),
                                   updated=values.get("updated"), url=url))
    return _select(records, source)


def _github(data: Any, source: dict) -> list[dict]:
    if not isinstance(data, list) or len(data) > MAX_RECORDS:
        raise SourceError("invalid_github_advisories")
    result = []
    for item in data:
        if not isinstance(item, dict) or not item.get("ghsa_id"):
            raise SourceError("invalid_github_advisory")
        affected, fixes = [], []
        for vulnerability in item.get("vulnerabilities", [])[:128]:
            package = vulnerability.get("package", {})
            requirement = _text(vulnerability.get("vulnerable_version_range"), 160)
            affected.append({"ecosystem": _text(package.get("ecosystem"), 80), "package": _text(package.get("name"), 160),
                             "ranges": [], "versions": [], "vulnerable_requirement": requirement})
            patched = vulnerability.get("first_patched_version", vulnerability.get("patched_versions"))
            if isinstance(patched, dict):
                patched = patched.get("identifier")
            if isinstance(patched, str) and patched:
                fixes.append({"stage": "released", "version": _text(patched, 160), "commit": None, "package": _text(package.get("name"), 160), "source_url": source["url"]})
        result.append(_record(source, ids=[item["ghsa_id"], item.get("cve_id", "")], title=item.get("summary", ""),
                              component=affected[0]["package"] if affected else "", ecosystem=affected[0]["ecosystem"] if affected else "",
                              published=item.get("published_at"), updated=item.get("updated_at"), withdrawn=bool(item.get("withdrawn_at")),
                              affected=affected, fixes=fixes, conditions=source.get("conditions", {}), url=_url(item.get("html_url", source["url"]))))
    return _select(result, source)


def parse_source(body: bytes, source: dict) -> list[dict]:
    """Parse fixture or downloaded bytes. A malformed source raises a reason code."""
    source = _source(source)
    if len(body) > source["max_bytes"]:
        raise SourceError("body_too_large")
    text = body.decode("utf-8-sig", "strict")
    adapter = source["adapter"]
    if adapter == "osv":
        return _osv(json.loads(text), source)
    if adapter == "rustsec":
        return _rustsec(text, source)
    if adapter == "feed":
        return _feed(text, source)
    if adapter == "github_advisories":
        return _github(json.loads(text), source)
    if adapter == "cve":
        return _cve(json.loads(text), source)
    if adapter == "nvidia_csaf":
        return _nvidia_csaf(json.loads(text), source)
    return _html(text, source)


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _url(newurl)
        if urllib.parse.urlsplit(newurl).netloc.lower() != urllib.parse.urlsplit(req.full_url).netloc.lower():
            raise SourceError("cross_origin_redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _retry(value: Any, now: str) -> int | None:
    try:
        seconds = int(value)
    except (ValueError, TypeError):
        date = _date(value)
        if not date:
            return None
        seconds = int((datetime.fromisoformat(date.replace("Z", "+00:00")) - datetime.fromisoformat(now.replace("Z", "+00:00"))).total_seconds())
    return min(86400, max(1, seconds))


def _network_error(error: Exception) -> str:
    reason = getattr(error, "reason", error)
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(reason, ssl.SSLCertVerificationError):
        return "tls_verification_failed"
    if isinstance(reason, ssl.SSLError):
        return "tls_error"
    if isinstance(reason, socket.gaierror):
        return "dns_error"
    if isinstance(reason, OSError):
        if reason.errno in {errno.EACCES, errno.EPERM} or getattr(reason, "winerror", None) == 10013:
            return "transport_denied"
        if reason.errno == errno.ECONNREFUSED:
            return "connection_refused"
    # Parse only a fixed proxy protocol signature. Never return the reason text.
    if isinstance(reason, (str, OSError)):
        match = re.search(r"Tunnel connection failed:\s*(\d{3})\b", str(reason)[:4096], re.I)
        if match and 100 <= int(match.group(1)) <= 599:
            return "proxy_connect_" + match.group(1)
    return "transport_error"


def fetch_source(source: dict, previous: dict | None = None, now: str | None = None, *, opener=None) -> dict:
    """Fetch once. Inject a callable opener(request, timeout=...) for fixture tests.

    Only return a 304 when the caller already has a successful cached body hash.
    No retries are made here. The durable scheduler owns rate limits/backoff.
    """
    timestamp = _date(now) or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    previous = previous or {}
    conditional_allowed = (previous.get("conditional_cache_allowed", True) is not False
                           and not previous.get("has_partial_cache") and previous.get("status") != "partial")
    result = {"status": "failed", "records": [], "etag": None, "last_modified": None, "error_code": None,
              "retry_after_seconds": None, "fetched_at": timestamp, "content_hash": None}
    try:
        source = _source(source)
        headers = {"User-Agent": "EventGuard/1.0 (read-only public advisory tracker)", "Accept": "application/json, application/atom+xml, application/rss+xml, text/plain, text/html", "Accept-Encoding": "identity"}
        for key, header in (("etag", "If-None-Match"), ("last_modified", "If-Modified-Since")):
            value = previous.get(key) if conditional_allowed else None
            if isinstance(value, str) and 0 < len(value) <= 512 and not any(ord(c) < 32 or ord(c) == 127 for c in value):
                headers[header] = value
        request = urllib.request.Request(source["url"], headers=headers, method="GET")
        do_open = opener or urllib.request.build_opener(_Redirect()).open
        started = time.monotonic()
        with do_open(request, timeout=source["timeout_seconds"]) as response:
            code = getattr(response, "status", 200)
            if code == 304:
                raise urllib.error.HTTPError(source["url"], 304, "not_modified", response.headers, None)
            if code != 200:
                raise urllib.error.HTTPError(source["url"], code, "http_error", response.headers, None)
            final_url = response.geturl() if hasattr(response, "geturl") else source["url"]
            if source["adapter"] == "nvidia_csaf":
                _source(dict(source, url=final_url))
            if urllib.parse.urlsplit(_url(final_url)).netloc.lower() != urllib.parse.urlsplit(source["url"]).netloc.lower():
                raise SourceError("cross_origin_redirect")
            if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
                raise SourceError("unsupported_encoding")
            if source["adapter"] == "github_advisories" and 'rel="next"' in response.headers.get("Link", ""):
                # Do not silently treat a truncated advisory listing as complete.
                raise SourceError("pagination_required")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdecimal() or int(length) > source["max_bytes"]):
                raise SourceError("body_too_large")
            chunks, total = [], 0
            read = getattr(response, "read1", response.read)
            while True:
                if time.monotonic() - started > source["timeout_seconds"]:
                    raise SourceError("deadline_exceeded")
                chunk = read(min(16384, source["max_bytes"] - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > source["max_bytes"]:
                    raise SourceError("body_too_large")
                chunks.append(chunk)
            body = b"".join(chunks)
            records = parse_source(body, source)
            result.update(status="success", records=records, content_hash=hashlib.sha256(body).hexdigest())
            if isinstance(records, SourceRecords) and records.coverage == "partial":
                result.update(status="partial" if records else "failed", coverage="partial",
                              error_code="partial_parse" if records.item_errors else "csaf_evidence_incomplete",
                              item_errors=records.item_errors)
                # Preserve the evidence time/hash of these new observations.
                # They do not refresh the older complete source cache.
                result["records"] = [dict(record, fetched_at=timestamp, content_hash=result["content_hash"]) for record in records]
            for name, key in (("ETag", "etag"), ("Last-Modified", "last_modified")):
                value = response.headers.get(name)
                if isinstance(value, str) and len(value) <= 512 and not any(ord(c) < 32 or ord(c) == 127 for c in value):
                    result[key] = value
    except urllib.error.HTTPError as exc:
        if exc.code == 304 and conditional_allowed and re.fullmatch(r"[a-f0-9]{64}", str(previous.get("content_hash", ""))):
            result.update(status="not_modified", etag=previous.get("etag"), last_modified=previous.get("last_modified"), content_hash=previous["content_hash"])
        else:
            result["error_code"] = "unexpected_304" if exc.code == 304 else "http_" + str(exc.code)
            result["retry_after_seconds"] = _retry(exc.headers.get("Retry-After") if exc.headers else None, timestamp)
        exc.close()
    except SourceError as exc:
        result["error_code"] = str(exc)
    except (urllib.error.URLError, OSError, TimeoutError, socket.timeout) as exc:
        result["error_code"] = _network_error(exc)
    except (ValueError, TypeError, KeyError, AttributeError, ET.ParseError, RecursionError):
        result["error_code"] = "parse_failed"
    return result
