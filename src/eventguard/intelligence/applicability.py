"""Evidence-limited local relevance. A match never means exploitability or safety."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

from .versions import affected_by_osv, compare_versions, matches_cargo_requirement, matches_python_requirement, normalize_ecosystem
from .inventory import DEFAULT_MAX_AGE_SECONDS


def _time(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}", value):
        return None
    return value.lower().replace("_", "-")


def _fresh(observed, now, maximum=DEFAULT_MAX_AGE_SECONDS):
    timestamp = _time(observed)
    if type(maximum) is not int or not 1 <= maximum <= 30 * 86400:
        maximum = DEFAULT_MAX_AGE_SECONDS
    return timestamp is not None and -300 <= (now - timestamp).total_seconds() <= maximum


def _inventory_freshness(inventory, refs, now):
    """Local evidence validity only. Reading/304 must not refresh asserted facts."""
    value = {"status": "unknown", "observed_at": None, "valid_until": None,
             "reason_codes": ["inventory_freshness_unknown"]}
    if now is None or not refs:
        return value
    observations, deadlines = [], []

    def add(observed, maximum):
        stamp = _time(observed)
        if stamp is None or stamp > now or type(maximum) is not int or not 1 <= maximum <= 30 * 86400:
            return False
        observations.append(stamp)
        deadlines.append(stamp + timedelta(seconds=maximum))
        return True

    if not add(inventory.get("collected_at"), inventory.get("max_age_seconds", DEFAULT_MAX_AGE_SECONDS)):
        return value
    relevant = [asset for asset in inventory.get("assets", [])
                if isinstance(asset, dict) and asset.get("asset_id", "unknown") in refs]
    if len(relevant) < len(set(refs)):
        return value
    for asset in relevant:
        facts = asset.get("facts", {})
        if not isinstance(facts, dict):
            return value
        observed = facts.get("observed_at", asset.get("observed_at", inventory.get("collected_at")))
        if not add(observed, facts.get("max_age_seconds", DEFAULT_MAX_AGE_SECONDS)):
            return value
    deadline = min(deadlines)
    return {"status": "fresh" if now < deadline else "stale",
            "observed_at": min(observations).isoformat(timespec="seconds"),
            "valid_until": deadline.isoformat(timespec="seconds"),
            "reason_codes": [] if now < deadline else ["inventory_evidence_stale"]}


def _requirements(version, values):
    if not isinstance(values, list):
        return None
    answers = [matches_cargo_requirement(version, value) for value in values]
    return True if True in answers else None if None in answers else False


def _version_match(asset, affected):
    version = asset.get("version")
    if not isinstance(version, str):
        return None
    requirement = affected.get("vulnerable_requirement")
    if isinstance(requirement, str) and normalize_ecosystem(asset.get("ecosystem")) == "rust":
        return matches_cargo_requirement(version, requirement)
    if isinstance(requirement, str) and normalize_ecosystem(asset.get("ecosystem")) == "python":
        return matches_python_requirement(version, requirement)
    patched = affected.get("patched", affected.get("patched_versions", []))
    unaffected = affected.get("unaffected", affected.get("unaffected_versions", []))
    if patched or unaffected:
        if normalize_ecosystem(asset.get("ecosystem")) != "rust":
            return None
        patched_match, unaffected_match = _requirements(version, patched), _requirements(version, unaffected)
        if patched_match is True or unaffected_match is True:
            return False
        if patched_match is None or unaffected_match is None:
            return None
        return True
    return affected_by_osv(version, affected, normalize_ecosystem(asset.get("ecosystem")))


def _backport_applied(asset, record):
    facts = asset.get("facts", {})
    evidence = facts.get("backport_evidence")
    ids = list(record.get("ids", [])) + list(record.get("aliases", []))
    if not isinstance(evidence, dict):
        return False
    assertion_matches = (evidence.get("status") == "fixed" and evidence.get("advisory_id") in ids
            and evidence.get("package_version") == asset.get("version")
            and isinstance(evidence.get("vendor_url"), str)
            and evidence["vendor_url"].startswith("https://"))
    if not assertion_matches or record.get("confidence") != "high":
        return False
    # A manually supplied URL cannot establish that a vendor published this fix.
    # Require an independently ingested advisory mapping to the exact package.
    for fix in record.get("fixes", []):
        if (not isinstance(fix, dict) or fix.get("stage") not in {"released", "package_available"}
                or fix.get("source_url") != evidence["vendor_url"]
                or _name(fix.get("package")) != _name(asset.get("component"))):
            continue
        comparison = compare_versions(asset.get("version"), fix.get("version"), asset.get("ecosystem"))
        if comparison is not None and comparison >= 0:
            return True
    return False


def evaluate(record: dict, inventory: dict, now: str | None = None) -> dict:
    """Return possible/not_applicable/unknown; never execute a probe or return safe."""
    timestamp = _time(now) if now else datetime.now(timezone.utc)
    reasons, refs, evidence, condition_results = set(), [], [], {}
    fixes = record.get("fixes", [])
    fix_available = any(isinstance(fix, dict) and fix.get("stage") in {"released", "package_available"}
                        and bool(fix.get("version") or fix.get("package")) for fix in fixes) if isinstance(fixes, list) else False
    output = {"status": "unknown", "reason_codes": [], "asset_refs": refs, "evidence": evidence, "fix_available": fix_available, "conditions": condition_results}
    def finish(status):
        output["status"], output["reason_codes"] = status, sorted(reasons)
        output["inventory_freshness"] = _inventory_freshness(inventory, refs, timestamp)
        return output
    if timestamp is None:
        reasons.add("invalid_evaluation_time")
        return finish("unknown")
    if record.get("withdrawn"):
        reasons.add("advisory_withdrawn")
        return finish("not_applicable")
    if record.get("status") in {"stale", "error", "denied", "unknown"} or record.get("freshness") == "stale":
        reasons.add("advisory_evidence_unavailable")
        return finish("unknown")
    inventory_time = inventory.get("collected_at")
    if not _fresh(inventory_time, timestamp, inventory.get("max_age_seconds", DEFAULT_MAX_AGE_SECONDS)):
        reasons.add("inventory_stale_or_undated")
        return finish("unknown")
    if inventory.get("status") in {"unknown", "denied", "error", "stale"}:
        reasons.add("inventory_incomplete")
    assets = inventory.get("assets", [])
    affected_rows = record.get("affected", [])
    if not isinstance(assets, list) or not isinstance(affected_rows, list):
        reasons.add("invalid_applicability_schema")
        return finish("unknown")
    if not affected_rows:
        affected_rows = [{"package": {"ecosystem": record.get("ecosystem"), "name": record.get("component")}}]
    possible, unknown, excluded = False, False, False
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        asset_name, ecosystem = _name(asset.get("component")), normalize_ecosystem(asset.get("ecosystem"))
        if ecosystem == "linux" and asset_name in {"linux-kernel", "kernel"}:
            asset_name = "linux"
        if asset_name is None:
            reasons.add("invalid_asset_component")
            continue
        for affected in affected_rows:
            if not isinstance(affected, dict):
                reasons.add("invalid_affected_schema")
                unknown = True
                continue
            package = affected.get("package", {})
            if isinstance(package, str):
                package = {"name": package, "ecosystem": affected.get("ecosystem", record.get("ecosystem"))}
            if not isinstance(package, dict):
                continue
            target_name = _name(package.get("name", record.get("component")))
            target_ecosystem = normalize_ecosystem(package.get("ecosystem", record.get("ecosystem")))
            if target_ecosystem == "linux" and target_name in {"linux-kernel", "kernel"}:
                target_name = "linux"
            if target_name != asset_name or target_ecosystem != ecosystem:
                continue
            ref = asset.get("asset_id", "unknown")
            if ref not in refs:
                refs.append(ref)
            facts = asset.get("facts", {})
            if not isinstance(facts, dict):
                facts = {}
            if not _fresh(facts.get("observed_at", asset.get("observed_at", inventory_time)), timestamp, facts.get("max_age_seconds", DEFAULT_MAX_AGE_SECONDS)):
                unknown = True
                reasons.add("asset_facts_stale_or_undated")
                continue
            if ecosystem in {"linux", "debian", "rpm"} and _backport_applied(asset, record):
                excluded = True
                reasons.add("vendor_backport_evidence_matches_package")
                evidence.append({"asset_ref": ref, "kind": "vendor_backport_assertion", "user_asserted": True})
                continue
            record_conditions = record.get("conditions", {})
            if not isinstance(record_conditions, dict):
                unknown = True
                reasons.add("invalid_conditions")
                continue
            wrapper = affected.get("compatibility_wrapper", record.get("compatibility_wrapper", record_conditions.get("compatibility_wrapper")))
            if isinstance(wrapper, dict) and wrapper.get("version") == asset.get("version"):
                parent_name = wrapper.get("requires_parent", asset.get("component"))
                minimum = wrapper.get("parent_min_version")
                parent_found = any(other is not asset and other.get("component") == parent_name
                                   and isinstance(other.get("version"), str) and other.get("version") != asset.get("version")
                                   for other in assets if isinstance(other, dict))
                # Lockfile presence alone cannot prove dependency graph / resolved wrapper parent.
                unknown = True
                reasons.add("compatibility_wrapper_parent_requires_graph_evidence")
                condition_results["wrapper_parent_observed"] = parent_found
                condition_results["wrapper_parent_min_version"] = minimum
                continue
            match = _version_match(asset, affected)
            evidence.append({"asset_ref": ref, "kind": "version_match", "value": "unknown" if match is None else match,
                             "user_asserted": bool(asset.get("origin", {}).get("user_asserted", False))})
            if match is None:
                unknown = True
                reasons.add("version_or_affected_range_unknown")
                continue
            if match is False:
                excluded = True
                reasons.add("version_outside_advisory_range")
                continue
            if ecosystem in {"linux", "debian", "rpm"} and facts.get("distribution"):
                unknown = True
                reasons.add("vendor_backport_unverified")
                continue
            conditions = record.get("conditions", {})
            if not isinstance(conditions, dict):
                unknown = True
                reasons.add("invalid_conditions")
                continue
            eliminated = False
            required_features = conditions.get("required_features", [])
            if isinstance(required_features, list):
                for feature in required_features:
                    state = facts.get("features", {}).get(feature) if facts.get("feature_state") not in {"unknown", "declared_only", None} else None
                    condition_results["feature:" + str(feature)[:128]] = state if type(state) is bool else "unknown"
                    if state is False:
                        eliminated = True
                        reasons.add("required_feature_disabled")
                    elif state is None:
                        reasons.add("optional_feature_unverified")
            for key, condition in (("tls_backend", "tls_backends"), ("root_source", "root_sources")):
                required = conditions.get(condition)
                if isinstance(required, list) and required:
                    fact = facts.get(key, "unknown")
                    condition_results[key] = fact
                    if fact not in {"unknown", None} and fact not in required:
                        eliminated = True
                        reasons.add(key + "_different")
                    elif fact in {"unknown", None}:
                        reasons.add(key + "_unverified")
            if ecosystem in {"linux", "debian", "rpm"}:
                # Presence, built-in, loading and reachability are independent observations.
                for key in ("module_present", "module_builtin", "module_loaded", "service_enabled", "reachable", "host_kernel", "container"):
                    condition_results[key] = facts.get(key, "unknown")
                if facts.get("module_loaded") is False and facts.get("module_builtin") is not False:
                    reasons.add("module_not_loaded_does_not_exclude_builtin")
                if facts.get("container") is True and facts.get("host_kernel") in {None, "unknown"}:
                    reasons.add("container_host_kernel_unverified")
                for key in ("module_loaded", "service_enabled", "reachable"):
                    if conditions.get(key) is True and facts.get(key) not in {True, False}:
                        reasons.add(key + "_unverified")
                    elif conditions.get(key) is True and facts.get(key) is False:
                        # module absence excludes only when built-in status is also known false.
                        if key != "module_loaded" or facts.get("module_builtin") is False:
                            eliminated = True
                            reasons.add(key + "_condition_false")
            if eliminated:
                excluded = True
                continue
            if facts.get("deployed") is False:
                excluded = True
                reasons.add("not_deployed_as_observed")
                continue
            if facts.get("deployed") is not True:
                reasons.add("deployment_unverified")
            if facts.get("running") is not True:
                reasons.add("running_version_unverified")
            possible = True
            reasons.add("affected_component_observed")
    if possible:
        return finish("possible")
    if unknown or not refs or inventory.get("status") not in {"success", "ok"}:
        if not refs:
            reasons.add("component_not_observed_not_proof_of_absence")
        return finish("unknown")
    if excluded:
        return finish("not_applicable")
    reasons.add("applicability_unresolved")
    return finish("unknown")
