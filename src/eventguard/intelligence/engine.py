"""Program-owned advisory comparison and durable handoff to the existing outbox."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

from ..runtime import Runtime, atomic_json, read_json
from ..events.schema import stable_event_id, validate_event
from ..events.store import EventStore


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def config_path(root, path=None):
    runtime = Runtime(root)
    relative = Path("config/advisories.json") if path is None else Path(path)
    if relative.is_absolute():
        relative = relative.relative_to(runtime.root)
    if relative.parts[:1] != ("config",):
        raise ValueError("advisory_config_directory_required")
    return runtime.path(relative)


def make_event(change, *, synthetic=False):
    """No advisory text, URLs, product names or inventory enters agent snapshots."""
    now = change["observed_at"]
    identity = stable_event_id("advisory-v1", change["change_id"])
    # Alias merging may change case_id after an outbox write. Only the
    # immutable change ID can determine replayed event bytes.
    case_ref = str(change["change_id"])
    case_hash = hashlib.sha256(case_ref.encode("utf-8")).hexdigest()
    return validate_event({
        "schema_version": "2.0", "event_id": identity, "host_id": "local-advisory-tracker",
        "episode_id": "advisory-" + case_hash, "correlation_id": "advisory-" + case_hash,
        "sequence": 1, "event_type": "advisory.changed", "transition": "new",
        "severity": change.get("severity", "warning"), "synthetic": synthetic,
        "observed_at": now, "persisted_at": now, "window": {"start": now, "end": now},
        "detector": {"id": "advisory-tracker", "version": "1"},
        "rule_ref": {"rule_id": "advisory-significant-change", "version": "1"},
        "baseline_version": "advisory-v1", "evidence": {"source": "advisories", "reason": change["reason"]},
        "evidence_refs": ["intel-" + case_hash],
        "inference": {"summary": "Advisory evidence changed; human investigation is required.",
                      "compromise_conclusion": "undetermined"},
        "coverage": {"status": change.get("coverage_status", "unknown")},
        "privacy": {"profile": "fixed-minimal-v1", "redacted": True}})


def emit_pending(root, store, namespace, *, synthetic=False, now=None):
    runtime = Runtime(root)
    store.bind_namespace(namespace,synthetic)
    pending = store.pending_changes(100, now=now)
    if not pending:
        return 0
    outbox = EventStore(runtime.data_dir(namespace))
    emitted = 0
    for change in pending:
        event = make_event(change, synthetic=synthetic)
        # Crash between these writes reuses the same EventStore ID. The source
        # change remains pending on capacity/storage failure. ACK is untouched.
        outbox.enqueue(event)
        store.mark_emitted(change["change_id"], event["event_id"])
        emitted += 1
    return emitted


def cycle(root,path=None,**options):
    from ..acceptance_control import FileLease
    path_lock=Runtime(root).path("data/advisories/cycle.lock")
    path_lock.parent.mkdir(parents=True,exist_ok=True)
    lease=FileLease(path_lock)
    if not lease.acquire():
        raise RuntimeError("advisory_cycle_busy")
    try:
        return _cycle(root,path,**options)
    finally:
        lease.release()


def _cycle(root, path=None, *, fetcher=None, inventory_reader=None, now=None, synthetic=False, cancelled=None, progress=None):
    from .sources import load_config, fetch_source
    from .inventory import collect_inventory
    from .applicability import evaluate
    from .store import IntelligenceStore, source_identity
    now = now or stamp()
    runtime = Runtime(root)
    config = load_config(config_path(root, path))
    # Relative paths are anchored to this project, never the launcher's cwd.
    inventory_config = dict(config.get("inventory", {}))
    allowed = []
    for entry in inventory_config.get("paths", []):
        if isinstance(entry, str):
            item = Path(entry)
            allowed.append(str(item if item.is_absolute() else runtime.root / item))
        elif isinstance(entry, dict) and isinstance(entry.get("path"), str):
            item = Path(entry["path"])
            allowed.append(dict(entry, path=str(item if item.is_absolute() else runtime.root / item)))
        else:
            raise ValueError("advisory_inventory_path_invalid")
    inventory_config["paths"] = allowed
    config["inventory"] = inventory_config
    namespace = config.get("namespace", "live")
    if namespace not in {"live", "test"} or synthetic and namespace != "test":
        raise ValueError("advisory_namespace_invalid")
    policy = config.get("storage", {})
    directory = runtime.path("data/advisories")
    store = IntelligenceStore(directory / "intelligence.sqlite3", event_rules=config.get("rules"), **{
        key: policy[key] for key in ("max_records", "max_changes", "max_bytes", "cooldown_seconds") if key in policy})
    store.bind_namespace(namespace,synthetic)
    result = {"state": "running", "last_progress": "inventory", "observed_at": now,
              "sources_checked": 0, "events_emitted": 0, "errors": [], "model_calls": 0,
              "namespace": namespace, "synthetic": synthetic, "agent_enabled": False}
    inventory = (inventory_reader or collect_inventory)(config, now=now)
    if inventory.get("synthetic") is True and not synthetic:
        raise ValueError("synthetic_inventory_requires_test_scope")
    if inventory.get("status")!="success":
        result["errors"].append({"source_id":"local_inventory","reason":"inventory_"+inventory.get("status","unknown")})
    # Inventory contains only explicitly allowed static inputs. It is local,
    # never part of QueueInbox/query_evidence or the seven-field snapshot.
    atomic_json(directory / "inventory.json", inventory, 4 * 1024 * 1024)
    due = {source["id"] for source in store.due_sources(config["sources"], now)}
    host_requests={}
    for source in config["sources"]:
        if source.get("enabled",True) is False:
            continue
        if cancelled and cancelled():
            raise InterruptedError("advisory_stop_requested")
        identity = source["id"]
        if progress:
            progress("source:" + identity)
        if identity in due:
            previous=store.source_state(identity,now=now)
            if previous and previous.get("configuration_fingerprint")!=source_identity(source):
                previous=None
            host=urlsplit(source["url"]).hostname
            if fetcher is None:
                # One real request per origin per second, in addition to
                # durable source intervals and Retry-After/backoff.
                until=host_requests.get(host,0)+1
                while time.monotonic()<until:
                    if cancelled and cancelled():
                        raise InterruptedError("advisory_stop_requested")
                    time.sleep(min(.1,until-time.monotonic()))
                host_requests[host]=time.monotonic()
            fetched = (fetcher or fetch_source)(source, previous, now=now)
            store.record_fetch(source, fetched, now)
            result["sources_checked"] += 1
        previous = store.source_state(identity, now=now) or {}
        if previous.get("status") in {"failed", "partial"} or previous.get("freshness") in {"stale","unknown"}:
            result["errors"].append({"source_id":identity,"reason":previous.get("error_code") or "source_evidence_unavailable"})
        fresh = previous.get("last_success_at", previous.get("last_success"))
        for record in store.cached_records(identity):
            record = dict(record)
            record.setdefault("fetched_at", previous.get("last_success_at", previous.get("last_success")))
            record.setdefault("content_hash", previous.get("content_hash"))
            assessment = evaluate(record, inventory, now=now)
            if previous.get("has_partial_cache") or previous.get("status") == "partial":
                assessment.update(status="unknown", reason_codes=sorted(set(assessment.get("reason_codes", []) + ["source_evidence_partial"])))
            elif not fresh:
                assessment.update(status="unknown")
            else:
                try:
                    age = (datetime.fromisoformat(now.replace("Z", "+00:00")) - datetime.fromisoformat(fresh.replace("Z", "+00:00"))).total_seconds()
                    if not 0 <= age <= source.get("stale_after_seconds", 86400):
                        assessment.update(status="unknown", reason_codes=sorted(set(assessment.get("reason_codes", []) + ["source_evidence_stale"])))
                except (ValueError, TypeError):
                    assessment.update(status="unknown", reason_codes=["source_time_unknown"])
            store.ingest(record, assessment, identity, now)
    result["last_progress"] = "outbox"
    if cancelled and cancelled():
        raise InterruptedError("advisory_stop_requested")
    result["events_emitted"] = emit_pending(root, store, namespace, synthetic=synthetic, now=now)
    result["last_progress"] = "cycle_completed"
    result["state"] = "partial" if result["errors"] else "waiting"
    atomic_json(directory / "last-cycle.json", result)
    return result


def status(root):
    from .store import IntelligenceStore
    from ..agent_budget import public_status
    runtime = Runtime(root)
    path = runtime.path("data/advisories/intelligence.sqlite3")
    # Status before first start does not initialize an intelligence database.
    result = {"state": "not_started", "sources": [], "cases": 0, "pending_changes": 0,
              "model_calls": 0, "agent_enabled": False, "last_progress": "not_started"}
    if path.exists():
        result.update(IntelligenceStore(path, readonly=True).status(stamp()))
    last = runtime.path("data/advisories/last-cycle.json")
    namespace = "live"
    if last.exists():
        saved = read_json(last)
        namespace = saved.get("namespace", "live")
        result.update(last_cycle=saved, last_progress=saved.get("last_progress"))
    result["pending_events"] = 0
    outbox_path = runtime.path(Path("data") / namespace / "eventguard.sqlite3")
    if outbox_path.exists():
        # Read only: status must not initialize/rewrite the outbox policy.
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(outbox_path.as_uri() + "?mode=ro", uri=True)) as db:
            result["pending_events"] = db.execute("SELECT COUNT(*) FROM events WHERE delivery_status<>'ack'").fetchone()[0]
            result["pending_advisory_events"] = db.execute("SELECT COUNT(*) FROM events WHERE delivery_status<>'ack' AND json_extract(payload,'$.event_type')='advisory.changed'").fetchone()[0]
    budget = public_status()
    result["agent_budget"] = budget
    result["daily_remaining"] = budget.get("remaining") if budget.get("usage_known") is True else None
    result["agent_blocked_reason"] = "not_enabled_this_round"
    return result
