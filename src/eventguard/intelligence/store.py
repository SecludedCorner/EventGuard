"""Durable advisory evidence and change queue. No network, model, or execution.

This database is local evidence, not a second receiver. ``mark_emitted`` means
the existing EventStore accepted a change. It does not mean received or fixed.
Pending changes, including emitted changes without an ACK contract, are never
silently removed to make space.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import threading
import time
import uuid


class IntelligenceError(RuntimeError):
    pass


class IntelligenceCapacityError(IntelligenceError):
    pass


StoreError = IntelligenceError
CapacityError = IntelligenceCapacityError
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_STATUSES = {"success", "not_modified", "failed"}
CHANGE_REASONS = frozenset({"possible_relevance", "fix_available", "exploitation_confirmed", "exposure_changed", "withdrawn", "source_stale", "recovered"})


def _epoch(value=None):
    if value is None:
        return time.time()
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise IntelligenceError("invalid_clock") from None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise IntelligenceError("invalid_clock")
        value = value.timestamp()
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise IntelligenceError("invalid_clock")
    try:
        datetime.fromtimestamp(value, timezone.utc)
    except (ValueError, OverflowError, OSError):
        raise IntelligenceError("invalid_clock") from None
    return float(value)


def _iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds")


def _json(value, limit=512 * 1024):
    try:
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise IntelligenceError("invalid_json_value") from None
    if len(encoded) > limit:
        raise IntelligenceCapacityError("evidence_record_too_large")
    return encoded


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise IntelligenceError("invalid_identifier")
    return value


def _guard(path):
    path = Path(path).absolute()
    for item in [*reversed(path.parents), path]:
        if item.is_symlink() or item.is_junction():
            raise IntelligenceError("data_path_redirect_rejected")
    return path


def _number(source, key, default, minimum=0, maximum=31_536_000):
    value = source.get(key, default)
    if value is None:
        value = default
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise IntelligenceError("invalid_source_policy")
    return float(value)


def _hash(value):
    return hashlib.sha256(_json(value).encode("ascii")).hexdigest()


def _setlike(value):
    """Ignore list ordering, including repeated official repost evidence."""
    if isinstance(value, dict):
        return {key: _setlike(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return sorted({_json(_setlike(item)) for item in value})
    return value


def _meaning(record, assessment):
    # Titles, prose, URLs, fetch hashes, publication times and alias additions do
    # not independently change local risk. Evidence remains in the full record.
    return {
        "withdrawn": bool(record.get("withdrawn", False)),
        "affected": _setlike(record.get("affected", [])),
        "conditions": _setlike(record.get("conditions", {})),
        "fixes": _setlike([{key: value for key, value in fix.items() if key in {"stage", "version", "commit", "package", "ecosystem", "distribution", "architecture"}}
                            if isinstance(fix, dict) else fix for fix in record.get("fixes", [])]),
        "exploitation": record.get("exploitation", "unknown"),
        "assessment_status": assessment.get("status", "unknown"),
        "reason_codes": _setlike(assessment.get("reason_codes", [])),
        "asset_refs": _setlike(assessment.get("asset_refs", [])),
        "local_conditions": _setlike(assessment.get("conditions", {})),
        "fix_available": assessment.get("fix_available") is True,
    }


def _assertion_id(record):
    # Advisory aliases may be added later. They must not turn the same source's
    # component assertion into a new observation.
    return _hash({"component": record.get("component"), "ecosystem": record.get("ecosystem")})


def source_identity(source):
    """Cache identity excludes wait/retry/display policy, not adapter settings."""
    policy = {"interval_seconds", "stale_after_seconds", "timeout_seconds", "max_bytes", "failure_threshold", "important", "enabled"}
    return _hash({key: value for key, value in source.items() if key not in policy})


def _case_status(statuses):
    return ("possible" if "possible" in statuses else "not_applicable"
            if statuses and all(value == "not_applicable" for value in statuses) else "unknown")


def _current_assertion(item, source, now):
    """A read-time projection. Historical assessment/evidence is never rewritten."""
    reasons = set()
    assessment, record = item["assessment"], item["record"]
    if source is None:
        reasons.add("source_state_missing")
    else:
        if source["config"].get("enabled", True) is False:
            reasons.add("source_tracking_disabled")
        if source["last_success"] is None:
            reasons.add("source_success_unknown")
        elif not source["cache_matches_config"]:
            reasons.add("source_binding_changed")
        if source["freshness"] == "stale":
            reasons.add("source_evidence_stale")
        elif source["freshness"] != "fresh":
            reasons.add("source_freshness_unknown")
        # An empty fetch is not a withdrawal, nor proof that an older exclusion
        # remains current. A changed range also needs a new local assessment.
        ids = {value.upper() for value in record.get("ids", []) + record.get("aliases", []) if isinstance(value, str)}
        matched = False
        for cached in source["cached_records"]:
            if not isinstance(cached, dict) or _assertion_id(cached) != item["assertion_id"]:
                continue
            cached_ids = {value.upper() for value in cached.get("ids", []) + cached.get("aliases", []) if isinstance(value, str)}
            if ids & cached_ids and _meaning(cached, {}) == _meaning(record, {}):
                matched = True
                break
        if not matched:
            reasons.add("source_assertion_not_current")
    try:
        observed = _epoch(item["last_seen"])
        if observed > now:
            reasons.add("assessment_time_unknown")
    except IntelligenceError:
        observed = None
        reasons.add("assessment_time_unknown")
    validity = assessment.get("inventory_freshness")
    if not isinstance(validity, dict):
        reasons.add("inventory_freshness_unknown")
    else:
        try:
            start, end = _epoch(validity.get("observed_at")), _epoch(validity.get("valid_until"))
            if validity.get("observed_at") is None or validity.get("valid_until") is None or start > now or end <= start or observed is None or start > observed:
                reasons.add("inventory_freshness_unknown")
            elif now >= end:
                reasons.add("inventory_evidence_stale")
            elif validity.get("status") != "fresh":
                reasons.add("inventory_freshness_unknown")
        except IntelligenceError:
            reasons.add("inventory_freshness_unknown")
    historical = assessment.get("status", "unknown")
    status = historical if historical in {"possible", "not_applicable", "unknown"} and not reasons else "unknown"
    if status == "unknown" and not reasons:
        reasons.add("assessment_unresolved")
    return {"status": status, "reason_codes": sorted(reasons), "evaluated_at": _iso(now),
            "evidence_as_of": _iso(observed) if observed is not None else None,
            "incident_conclusion": "not_assessed"}


class IntelligenceStore:
    def __init__(self, path, max_records=None, max_changes=None,
                 max_bytes=None, cooldown_seconds=None,
                 readonly=False, read_only=None, event_rules=None):
        self.path = _guard(path)
        prior = {}
        if self.path.is_file():
            db = None
            try:
                db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
                if db.execute("SELECT 1 FROM sqlite_master WHERE name='meta'").fetchone():
                    row = db.execute("SELECT value FROM meta WHERE key='storage_policy'").fetchone()
                    prior = json.loads(row[0]) if row else {}
            except (sqlite3.Error, ValueError, TypeError):
                raise IntelligenceError("database_policy_unreadable") from None
            finally:
                if db is not None:
                    db.close()
        max_records = max_records if max_records is not None else prior.get("max_records", 10000)
        max_changes = max_changes if max_changes is not None else prior.get("max_changes", 10000)
        max_bytes = max_bytes if max_bytes is not None else prior.get("max_bytes", 64 * 1024 * 1024)
        cooldown_seconds = cooldown_seconds if cooldown_seconds is not None else prior.get("cooldown_seconds", 3600)
        event_rules = event_rules if event_rules is not None else prior.get("event_rules", {})
        if not isinstance(event_rules, dict) or set(event_rules) - {"enabled_reasons", "severity"}:
            raise IntelligenceError("invalid_event_rules")
        enabled_reasons = event_rules.get("enabled_reasons", sorted(CHANGE_REASONS))
        severities = event_rules.get("severity", {})
        if not isinstance(enabled_reasons, list) or any(not isinstance(item, str) or item not in CHANGE_REASONS for item in enabled_reasons):
            raise IntelligenceError("invalid_event_rules")
        if not isinstance(severities, dict) or any(not isinstance(key, str) or key not in CHANGE_REASONS or not isinstance(value, str) or value not in {"info", "warning", "high", "critical"} for key, value in severities.items()):
            raise IntelligenceError("invalid_event_rules")
        self.event_rules = {"enabled_reasons": sorted(set(enabled_reasons)), "severity": severities}
        for value in (max_records, max_changes):
            if type(value) is not int or value < 1:
                raise IntelligenceError("invalid_capacity")
        if type(max_bytes) is not int or max_bytes < 64 * 1024:
            raise IntelligenceError("invalid_capacity")
        if type(cooldown_seconds) not in (int, float) or not 0 <= cooldown_seconds <= 31_536_000:
            raise IntelligenceError("invalid_cooldown")
        self.readonly = bool(readonly if read_only is None else read_only)
        if self.readonly:
            if not self.path.is_file():
                raise IntelligenceError("database_not_initialized")
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_records, self.max_changes, self.max_bytes = max_records, max_changes, max_bytes
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.RLock()
        if self.path.exists() and self.path.stat().st_size > max_bytes:
            raise IntelligenceCapacityError("database_already_over_capacity")
        if self.readonly:
            return
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sources(
                  source_id TEXT PRIMARY KEY, config TEXT NOT NULL,
                  last_attempt REAL, last_success REAL, next_fetch REAL NOT NULL,
                  failures INTEGER NOT NULL, status TEXT NOT NULL,
                  error_code TEXT, etag TEXT, last_modified TEXT, content_hash TEXT,
                  cached_records TEXT NOT NULL DEFAULT '[]', alert_state TEXT NOT NULL DEFAULT 'fresh',
                  cache_config TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS cases(
                  case_id TEXT PRIMARY KEY, record TEXT NOT NULL, assessment TEXT NOT NULL,
                  semantic_hash TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS aliases(alias TEXT PRIMARY KEY,case_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS redirects(old_id TEXT PRIMARY KEY,case_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS case_sources(
                  case_id TEXT NOT NULL,source_id TEXT NOT NULL,assertion_id TEXT NOT NULL,record TEXT NOT NULL,
                  assessment TEXT NOT NULL,last_seen REAL NOT NULL,PRIMARY KEY(case_id,source_id,assertion_id));
                CREATE TABLE IF NOT EXISTS changes(
                  change_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,reason TEXT NOT NULL,
                  severity TEXT NOT NULL,observed REAL NOT NULL,available_at REAL NOT NULL,
                  coverage_status TEXT NOT NULL,signature TEXT NOT NULL,
                  emitted_event_id TEXT,synthetic INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS changes_pending ON changes(emitted_event_id,available_at,observed);
            """)
            if "cache_config" not in {row[1] for row in db.execute("PRAGMA table_info(sources)")}:
                db.execute("ALTER TABLE sources ADD COLUMN cache_config TEXT NOT NULL DEFAULT '{}'")
                db.execute("UPDATE sources SET cache_config=config WHERE last_success IS NOT NULL")
            if "assertion_id" not in {row[1] for row in db.execute("PRAGMA table_info(case_sources)")}:
                db.execute("ALTER TABLE case_sources RENAME TO case_sources_legacy")
                db.execute("CREATE TABLE case_sources(case_id TEXT NOT NULL,source_id TEXT NOT NULL,assertion_id TEXT NOT NULL,record TEXT NOT NULL,assessment TEXT NOT NULL,last_seen REAL NOT NULL,PRIMARY KEY(case_id,source_id,assertion_id))")
                for row in db.execute("SELECT * FROM case_sources_legacy").fetchall():
                    db.execute("INSERT INTO case_sources VALUES(?,?,?,?,?,?)", (row["case_id"], row["source_id"], _assertion_id(json.loads(row["record"])), row["record"], row["assessment"], row["last_seen"]))
                db.execute("DROP TABLE case_sources_legacy")
            policy = {"max_records": max_records, "max_changes": max_changes, "max_bytes": max_bytes, "cooldown_seconds": cooldown_seconds, "event_rules": self.event_rules}
            if policy != prior:
                db.execute("INSERT OR REPLACE INTO meta VALUES('storage_policy',?)", (_json(policy),))

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()

    def close(self):
        # Connections have transaction scope. There is no background worker.
        return None

    def bind_namespace(self, namespace, synthetic=False):
        if self.readonly:
            raise IntelligenceError("read_only_store")
        if namespace not in {"test", "live"} or type(synthetic) is not bool or synthetic and namespace != "test":
            raise IntelligenceError("invalid_namespace_binding")
        binding = _json({"namespace": namespace, "synthetic": synthetic})
        with self._connect() as db:
            old = db.execute("SELECT value FROM meta WHERE key='namespace_binding'").fetchone()
            if old is not None and old[0] != binding:
                raise IntelligenceError("intelligence_namespace_binding_mismatch")
            if old is None:
                db.execute("INSERT INTO meta VALUES('namespace_binding',?)", (binding,))

    @contextmanager
    def _connect(self):
        with self._lock:
            _guard(self.path)
            db = None
            try:
                db = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5) if self.readonly else sqlite3.connect(str(self.path), timeout=5)
                db.row_factory = sqlite3.Row
                if not self.readonly:
                    db.execute("PRAGMA journal_mode=DELETE")
                    db.execute("PRAGMA synchronous=FULL")
                    pagesize = db.execute("PRAGMA page_size").fetchone()[0]
                    db.execute("PRAGMA max_page_count=" + str(self.max_bytes // pagesize))
                    db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except sqlite3.Error as exc:
                if db is not None:
                    db.rollback()
                if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
                    raise IntelligenceCapacityError("database_capacity_transaction_rolled_back") from None
                raise IntelligenceError("database_transaction_failed") from None
            except BaseException:
                if db is not None:
                    db.rollback()
                raise
            finally:
                if db is not None:
                    db.close()

    def _source(self, row, now):
        if row is None:
            return None
        config = json.loads(row["config"])
        cache_config = json.loads(row["cache_config"])
        cache_matches = row["last_success"] is not None and source_identity(config) == source_identity(cache_config)
        last_success = row["last_success"]
        stale_after = _number(config, "stale_after_seconds", 86400)
        freshness = "unknown" if not cache_matches or last_success is None or now < last_success else ("stale" if now - last_success >= stale_after else "fresh")
        return {
            "source_id": row["source_id"], "status": row["status"],
            "last_attempt": _iso(row["last_attempt"]) if row["last_attempt"] is not None else None,
            "last_success": _iso(last_success) if last_success is not None else None,
            "last_success_at": _iso(last_success) if last_success is not None else None,
            "next_fetch_at": _iso(row["next_fetch"]), "consecutive_failures": row["failures"],
            "error_code": row["error_code"], "etag": row["etag"] if cache_matches else None, "last_modified": row["last_modified"] if cache_matches else None,
            "content_hash": row["content_hash"], "freshness": freshness,
            "cached_records": json.loads(row["cached_records"]), "alert_state": row["alert_state"],
            "config": config, "cache_config": cache_config, "cache_matches_config": cache_matches,
            "configuration_fingerprint": source_identity(config),
            "cache_status": "available" if cache_matches else "disabled_old_cache" if row["last_success"] is not None else "empty",
        }

    def source_state(self, source_id, now=None):
        with self._connect() as db:
            return self._source(db.execute("SELECT * FROM sources WHERE source_id=?", (_identifier(source_id),)).fetchone(), _epoch(now))

    def source_states(self, now=None):
        stamp = _epoch(now)
        with self._connect() as db:
            return [self._source(row, stamp) for row in db.execute("SELECT * FROM sources ORDER BY source_id")]

    def cached_records(self, source_id):
        row = self.source_state(source_id)
        return row["cached_records"] if row and row["cache_matches_config"] else []

    def due_sources(self, config_sources, now=None):
        stamp = _epoch(now)
        with self._connect() as db:
            states = {row["source_id"]: (row["next_fetch"], source_identity(json.loads(row["config"]))) for row in db.execute("SELECT source_id,next_fetch,config FROM sources")}
        return [source for source in config_sources if source.get("enabled", True)
                and (_identifier(source["id"]) not in states or states[source["id"]][0] <= stamp or states[source["id"]][1] != source_identity(source))]

    def _change(self, db, case_id, reason, signature, now, severity="warning", coverage="unknown", synthetic=False):
        if reason not in self.event_rules["enabled_reasons"]:
            return None
        severity = self.event_rules["severity"].get(reason, severity)
        previous = db.execute("SELECT * FROM changes WHERE case_id=? AND reason=? ORDER BY observed DESC,change_id DESC LIMIT 1", (case_id, reason)).fetchone()
        # Never mutate a pending change: EventStore.enqueue might already have
        # committed while mark_emitted failed. Retrying must use identical data.
        if db.execute("SELECT COUNT(*) FROM changes").fetchone()[0] >= self.max_changes:
            raise IntelligenceCapacityError("change_capacity_pending_preserved")
        available = max(now, previous["observed"] + self.cooldown_seconds) if previous else now
        change_id = "intel-change-" + uuid.uuid4().hex
        db.execute("INSERT INTO changes VALUES(?,?,?,?,?,?,?,?,NULL,?)",
                   (change_id, case_id, reason, severity, now, available, coverage, signature, int(synthetic)))
        return self._change_dict(db.execute("SELECT * FROM changes WHERE change_id=?", (change_id,)).fetchone())

    @staticmethod
    def _change_dict(row):
        return {"change_id": row["change_id"], "case_id": row["case_id"], "reason": row["reason"],
                "severity": row["severity"], "observed_at": _iso(row["observed"]),
                "available_at": _iso(row["available_at"]), "coverage_status": row["coverage_status"],
                "synthetic": bool(row["synthetic"]), "event_id": row["emitted_event_id"]}

    def record_fetch(self, source, result, now=None):
        if self.readonly:
            raise IntelligenceError("read_only_store")
        stamp = _epoch(now)
        source_id = _identifier(source["id"])
        status = result.get("status")
        if status not in _STATUSES:
            raise IntelligenceError("invalid_fetch_status")
        interval = _number(source, "interval_seconds", 3600, 1)
        stale_after = _number(source, "stale_after_seconds", 86400, 1)
        threshold = _number(source, "failure_threshold", 3, 1, 1000)
        config = _json(source, 65536)
        error = result.get("error_code")
        if error is not None:
            _identifier(error)
        for key in ("etag", "last_modified", "content_hash"):
            value = result.get(key)
            if value is not None and (not isinstance(value, str) or len(value) > 2048 or any(ord(ch) < 32 for ch in value)):
                raise IntelligenceError("invalid_cache_header")
        with self._connect() as db:
            old = db.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
            cache_config = json.loads(old["cache_config"]) if old else {}
            cache_matches = old is not None and old["last_success"] is not None and source_identity(source) == source_identity(cache_config)
            same_config = old is not None and source_identity(source) == source_identity(json.loads(old["config"]))
            failures = (old["failures"] if same_config else 0) + 1 if status == "failed" else 0
            if status == "not_modified" and not cache_matches:
                raise IntelligenceError("not_modified_without_cached_success")
            last_success = (old["last_success"] if old else None) if status == "failed" else stamp
            cached = old["cached_records"] if old else "[]"
            if status == "success":
                records = result.get("records", [])
                if not isinstance(records, list) or len(records) > self.max_records:
                    raise IntelligenceCapacityError("source_cache_capacity")
                cached = _json(records, min(4 * 1024 * 1024, self.max_bytes // 2))
                cache_config = source
            retry = _number(result, "retry_after_seconds", 0, 0)
            delay = max(interval, retry) if status != "failed" else max(interval, retry, min(interval * 2 ** min(failures - 1, 10), 86400))
            alert = old["alert_state"] if same_config else "fresh"
            stale = source.get("important", True) is not False and status == "failed" and (failures >= threshold or (cache_matches and last_success is not None and stamp - last_success >= stale_after))
            if stale and alert != "stale":
                self._change(db, "intel-source-" + hashlib.sha256(source_id.encode("ascii")).hexdigest()[:32],
                             "source_stale", _hash({"state": "stale", "cycle": stamp}), stamp)
                alert = "stale"
            elif status != "failed" and alert == "stale":
                if source.get("important", True) is not False:
                    self._change(db, "intel-source-" + hashlib.sha256(source_id.encode("ascii")).hexdigest()[:32],
                                 "recovered", _hash({"state": "fresh", "cycle": stamp}), stamp, "info", "ok")
                alert = "fresh"
            values = [result.get(key) if result.get(key) is not None else (old[key] if old and (cache_matches or status == "failed") else None)
                      for key in ("etag", "last_modified", "content_hash")]
            db.execute("INSERT OR REPLACE INTO sources VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (source_id, config, stamp, last_success, stamp + delay, failures, status, error,
                        *values, cached, alert, _json(cache_config, 65536)))

    def _resolve(self, db, case_id):
        seen = set()
        while case_id not in seen:
            seen.add(case_id)
            row = db.execute("SELECT case_id FROM redirects WHERE old_id=?", (case_id,)).fetchone()
            if row is None:
                return case_id
            case_id = row[0]
        raise IntelligenceError("case_redirect_cycle")

    def ingest(self, record, assessment, source_id, now=None):
        if self.readonly:
            raise IntelligenceError("read_only_store")
        stamp = _epoch(now)
        source_id = _identifier(source_id)
        if not isinstance(record, dict) or not isinstance(assessment, dict):
            raise IntelligenceError("invalid_advisory")
        if any(not isinstance(record.get(key, []), list) for key in ("affected", "fixes", "evidence")) or not isinstance(record.get("conditions", {}), dict):
            raise IntelligenceError("invalid_advisory")
        if "withdrawn" in record and type(record["withdrawn"]) is not bool:
            raise IntelligenceError("invalid_advisory")
        if not isinstance(record.get("exploitation", "unknown"), str) or record.get("exploitation", "unknown") not in {"unknown", "none", "poc", "laboratory", "in_the_wild"}:
            raise IntelligenceError("invalid_advisory")
        if any(not isinstance(assessment.get(key, []), list) for key in ("asset_refs", "reason_codes")) or not isinstance(assessment.get("conditions", {}), dict):
            raise IntelligenceError("invalid_assessment")
        if not isinstance(assessment.get("status", "unknown"), str) or assessment.get("status", "unknown") not in {"possible", "not_applicable", "unknown"}:
            raise IntelligenceError("invalid_assessment_status")
        primary, aliases = record.get("ids", []), record.get("aliases", [])
        if not isinstance(primary, list) or not isinstance(aliases, list):
            raise IntelligenceError("invalid_advisory_ids")
        ids = primary + aliases
        if not isinstance(ids, list) or not 1 <= len(ids) <= 64:
            raise IntelligenceError("invalid_advisory_ids")
        if any(not isinstance(item, str) for item in ids):
            raise IntelligenceError("invalid_advisory_ids")
        ids = sorted({_identifier(item.upper()) for item in ids})
        if not ids:
            raise IntelligenceError("invalid_advisory_ids")
        record = dict(record)
        if record.get("fetched_at") is None:
            record["fetched_at"] = _iso(stamp)
        if record.get("content_hash") is None:
            record["content_hash"] = _hash({key: value for key, value in record.items() if key not in {"content_hash", "fetched_at"}})
        record_text, assessment_text = _json(record), _json(assessment)
        assertion_id = _assertion_id(record)
        meaning = _meaning(record, assessment)
        signature = _hash(meaning)
        with self._connect() as db:
            placeholders = ",".join("?" for unused in ids)
            cases = db.execute("SELECT DISTINCT c.* FROM cases c JOIN aliases a ON c.case_id=a.case_id WHERE a.alias IN (" + placeholders + ") ORDER BY c.created,c.case_id", ids).fetchall()
            if cases:
                case_id = cases[0]["case_id"]
                old = cases[0]
                for duplicate in cases[1:]:
                    other_id = duplicate["case_id"]
                    db.execute("UPDATE aliases SET case_id=? WHERE case_id=?", (case_id, other_id))
                    db.execute("UPDATE changes SET case_id=? WHERE case_id=?", (case_id, other_id))
                    for saved in db.execute("SELECT * FROM case_sources WHERE case_id=?", (other_id,)).fetchall():
                        existing = db.execute("SELECT last_seen FROM case_sources WHERE case_id=? AND source_id=? AND assertion_id=?", (case_id, saved["source_id"], saved["assertion_id"])).fetchone()
                        if existing is None or existing[0] < saved["last_seen"]:
                            db.execute("INSERT OR REPLACE INTO case_sources VALUES(?,?,?,?,?,?)", (case_id, saved["source_id"], saved["assertion_id"], saved["record"], saved["assessment"], saved["last_seen"]))
                    db.execute("DELETE FROM case_sources WHERE case_id=?", (other_id,))
                    db.execute("INSERT OR REPLACE INTO redirects VALUES(?,?)", (other_id, case_id))
                    db.execute("DELETE FROM cases WHERE case_id=?", (other_id,))
            else:
                if db.execute("SELECT COUNT(*) FROM cases").fetchone()[0] >= self.max_records:
                    raise IntelligenceCapacityError("advisory_capacity_pending_preserved")
                case_id, old = "intel-case-" + uuid.uuid4().hex, None
            for alias in ids:
                db.execute("INSERT OR REPLACE INTO aliases VALUES(?,?)", (alias, case_id))
            old_assertion = db.execute("SELECT record,assessment FROM case_sources WHERE case_id=? AND source_id=? AND assertion_id=?", (case_id, source_id, assertion_id)).fetchone()
            if old_assertion is None:
                # A repost of the same component assertion is not new evidence.
                # Keep its provenance, but compare equal normalized risk once.
                for candidate in db.execute("SELECT record,assessment FROM case_sources WHERE case_id=? AND assertion_id=? ORDER BY last_seen DESC", (case_id, assertion_id)):
                    if _meaning(json.loads(candidate["record"]), json.loads(candidate["assessment"])) == meaning:
                        old_assertion = candidate
                        break
            db.execute("INSERT OR REPLACE INTO case_sources VALUES(?,?,?,?,?,?)", (case_id, source_id, assertion_id, record_text, assessment_text, stamp))
            # Preserve every source assertion independently. The last ingested
            # assertion is the current comparison; it is not proof of safety.
            previous = _meaning(json.loads(old_assertion["record"]), json.loads(old_assertion["assessment"])) if old_assertion else None
            db.execute("INSERT OR REPLACE INTO cases VALUES(?,?,?,?,?,?)", (case_id, record_text, assessment_text, signature, old["created"] if old else stamp, stamp))
            reason, severity = None, "warning"
            possible = meaning["assessment_status"] == "possible"
            relevant = possible or (meaning["assessment_status"] == "unknown" and bool(meaning["asset_refs"]))
            previous_relevant = previous is not None and (previous["assessment_status"] == "possible" or previous["assessment_status"] == "unknown" and bool(previous["asset_refs"]))
            if meaning["withdrawn"] and (relevant or previous_relevant) and (previous is None or not previous["withdrawn"]):
                reason = "withdrawn"
            elif relevant and meaning["exploitation"] == "in_the_wild" and (previous is None or previous["exploitation"] != "in_the_wild"):
                reason, severity = "exploitation_confirmed", "high"
            elif relevant and meaning["fix_available"] and (previous is None or not previous["fix_available"] or meaning["fixes"] != previous["fixes"]):
                reason = "fix_available"
            elif previous is not None and (relevant or previous_relevant) and (meaning["local_conditions"] != previous["local_conditions"] or meaning["asset_refs"] != previous["asset_refs"] or meaning["assessment_status"] != previous["assessment_status"]):
                reason = "exposure_changed"
            elif relevant and (previous is None or previous["withdrawn"] and not meaning["withdrawn"] or not previous_relevant or meaning["affected"] != previous["affected"] or meaning["conditions"] != previous["conditions"] or meaning["reason_codes"] != previous["reason_codes"]):
                reason = "possible_relevance"
            if reason is None:
                return []
            change = self._change(db, case_id, reason, signature, stamp, severity,
                                  "partial" if possible else "unknown", record.get("synthetic") is True)
            return [change] if change else []

    def pending_changes(self, limit=100, now=None):
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise IntelligenceError("invalid_limit")
        with self._connect() as db:
            return [self._change_dict(row) for row in db.execute("SELECT * FROM changes WHERE emitted_event_id IS NULL AND available_at<=? ORDER BY observed,change_id LIMIT ?", (_epoch(now), limit))]

    def mark_emitted(self, change_id, event_id):
        if self.readonly:
            raise IntelligenceError("read_only_store")
        _identifier(change_id)
        _identifier(event_id)
        with self._connect() as db:
            row = db.execute("SELECT emitted_event_id FROM changes WHERE change_id=?", (change_id,)).fetchone()
            if row is None:
                raise IntelligenceError("unknown_change")
            if row[0] is not None and row[0] != event_id:
                raise IntelligenceError("change_event_id_conflict")
            db.execute("UPDATE changes SET emitted_event_id=? WHERE change_id=?", (event_id, change_id))

    def event_case(self, event_id, now=None):
        with self._connect() as db:
            row = db.execute("SELECT case_id FROM changes WHERE emitted_event_id=? ORDER BY observed DESC LIMIT 1", (_identifier(event_id),)).fetchone()
            case_id = row[0] if row else None
        return self.advisory(case_id, now=now) if case_id else None

    def advisory(self, case_id, now=None):
        stamp = _epoch(now)
        with self._connect() as db:
            case_id = self._resolve(db, _identifier(case_id))
            row = db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
            if row is None:
                return None
            sources = [{"source_id": item["source_id"], "assertion_id": item["assertion_id"], "record": json.loads(item["record"]),
                        "assessment": json.loads(item["assessment"]), "last_seen": _iso(item["last_seen"])}
                       for item in db.execute("SELECT * FROM case_sources WHERE case_id=? ORDER BY source_id,assertion_id", (case_id,))]
            source_states = {source_id: self._source(db.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone(), stamp)
                             for source_id in {item["source_id"] for item in sources}}
            for item in sources:
                item["assessment_scope"] = "historical"
                item["current_assessment"] = _current_assertion(item, source_states[item["source_id"]], stamp)
            statuses = [item["current_assessment"]["status"] for item in sources]
            case_status = _case_status(statuses)
            current_reasons = sorted({reason for item in sources for reason in item["current_assessment"]["reason_codes"]})
            return {"case_id": case_id, "record": json.loads(row["record"]),
                    "assessment": json.loads(row["assessment"]), "assessment_scope": "historical",
                    "historical_case_status": _case_status([item["assessment"].get("status", "unknown") for item in sources]),
                    "current_assessment": {"status": case_status, "reason_codes": current_reasons,
                                           "evaluated_at": _iso(stamp), "incident_conclusion": "not_assessed"},
                    "created_at": _iso(row["created"]),
                    "updated_at": _iso(row["updated"]), "case_status": case_status,
                    "components": sorted({str(item["record"].get("component", "unknown")) for item in sources}),
                    "aliases": [item[0] for item in db.execute("SELECT alias FROM aliases WHERE case_id=? ORDER BY alias", (case_id,))],
                    "sources": sources}

    def cases(self, limit=100, now=None):
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise IntelligenceError("invalid_limit")
        with self._connect() as db:
            ids = [row[0] for row in db.execute("SELECT case_id FROM cases ORDER BY created,case_id LIMIT ?", (limit,))]
        stamp = _epoch(now)
        return [self.advisory(case_id, now=stamp) for case_id in ids]

    def status(self, now=None):
        stamp = _epoch(now)
        with self._connect() as db:
            pending = db.execute("SELECT COUNT(*) FROM changes WHERE emitted_event_id IS NULL").fetchone()[0]
            deferred = db.execute("SELECT COUNT(*) FROM changes WHERE emitted_event_id IS NULL AND available_at>?", (stamp,)).fetchone()[0]
            records = db.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
            changes = db.execute("SELECT COUNT(*) FROM changes").fetchone()[0]
            sources = [self._source(row, stamp) for row in db.execute("SELECT * FROM sources ORDER BY source_id")]
            binding = db.execute("SELECT value FROM meta WHERE key='namespace_binding'").fetchone()
            for source in sources:
                source.pop("cached_records", None)
            return {"advisories": records, "pending_changes": pending, "deferred_changes": deferred,
                    "emitted_changes": changes - pending, "sources": sources,
                    "capacity": {"max_records": self.max_records, "max_changes": self.max_changes,
                                 "max_bytes": self.max_bytes, "database_bytes": self.path.stat().st_size},
                    "event_rules": self.event_rules,
                    "namespace_binding": json.loads(binding[0]) if binding else None,
                    "blocked_reason": "advisory_capacity" if records >= self.max_records else ("change_capacity" if changes >= self.max_changes else None),
                    "ack_meaning": "received_only_not_remediated", "model_calls": 0}
