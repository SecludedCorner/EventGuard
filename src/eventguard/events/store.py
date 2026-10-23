"""Transactional detector state + outbox using Python's built-in SQLite.

No network access, subprocesses, model calls, or implicit delivery. An ACK means
only durable receiver acceptance and never claims agent execution or case closure.
"""
from __future__ import annotations

from contextlib import contextmanager, closing
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

from .schema import validate_event

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_STATE_BYTES = 4 * 1024 * 1024
MAX_ATTEMPTS = 8
LEASE_SECONDS = 60
DEDUP_RETENTION = 30 * 86400


class StoreError(RuntimeError):
    pass


class CapacityError(StoreError):
    """The transaction was rolled back, including detector state changes."""


def _epoch(value=None):
    if value is None:
        return time.time()
    if isinstance(value, datetime):
        value = value.timestamp()
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise StoreError("invalid_clock")
    return float(value)


def _iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds")


def event_payload_hash(event):
    return hashlib.sha256(json.dumps(event,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii")).hexdigest()


def _guard(path):
    """Reject symlinks/junctions before using this installation's data files."""
    path = Path(path).absolute()
    for component in [*reversed(path.parents), path]:
        if component.is_symlink() or component.is_junction():
            raise StoreError("data_path_redirect_rejected")
    return path


def validate_receipt(event_id, receipt):
    if not isinstance(receipt, dict) or receipt.get("ack_type") != "receiver_persisted":
        raise StoreError("invalid_receipt_type")
    if receipt.get("event_id") != event_id:
        raise StoreError("receipt_event_mismatch")
    receipt_id = receipt.get("receiver_receipt_id", receipt.get("receipt_id"))
    if not isinstance(receipt_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}",receipt_id):
        raise StoreError("invalid_receipt_identity")
    result = {"ack_type":"receiver_persisted", "event_id":event_id,
              "receiver_receipt_id":receipt_id}
    if receipt.get("receiver_kind") in ("local_mock","verified_receiver"):
        result["receiver_kind"]=receipt["receiver_kind"]
    if receipt.get("wake_state") in ("mock_only_no_agent","queued","unconfigured","unknown"):
        result["wake_state"]=receipt["wake_state"]
    if isinstance(receipt.get("task_ref"),str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}",receipt["task_ref"]):
        result["task_ref"]=receipt["task_ref"]
    if isinstance(receipt.get("received_at"),str) and len(receipt["received_at"])<=64:
        try:
            stamp=datetime.fromisoformat(receipt["received_at"].replace("Z","+00:00"))
            if stamp.tzinfo is not None:
                result["received_at"]=stamp.astimezone(timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            pass
    # This local store has no proof of a real agent wake-up. Never invent one.
    result["real_agent_woken"] = False
    return result


class EventStore:
    def __init__(self, data_dir, max_events=None, max_bytes=None, *, acked_retention_seconds=None,
                 receipt_retention_seconds=None, receipt_limit=None):
        self.directory = _guard(Path(data_dir))
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = _guard(self.directory / "eventguard.sqlite3")
        supplied = {key: value for key, value in locals().copy().items() if key in
                    {"max_events", "max_bytes", "acked_retention_seconds", "receipt_retention_seconds", "receipt_limit"} and value is not None}
        previous = {}
        if self.path.exists():
            try:
                with closing(sqlite3.connect(self.path.as_uri()+"?mode=ro", uri=True, timeout=3)) as db:
                    if db.execute("SELECT 1 FROM sqlite_master WHERE name='meta'").fetchone():
                        row = db.execute("SELECT value FROM meta WHERE key='storage_policy'").fetchone()
                        previous = json.loads(row[0]) if row else {}
            except (sqlite3.Error, ValueError):
                raise StoreError("store_policy_unreadable") from None
        from ..storage_policy import limits
        try:
            self.policy = limits("outbox", {**limits("outbox", previous), **supplied})
        except (ValueError, TypeError):
            raise StoreError("invalid_storage_policy") from None
        self.max_events, self.max_bytes = self.policy["max_events"], self.policy["max_bytes"]
        self.ack_reserve_bytes=min(2*1024*1024,self.max_bytes//4)
        self._lock = threading.RLock()
        try:
            if self.path.exists() and self.path.stat().st_size > self.max_bytes:
                raise CapacityError("database_already_over_capacity")
            with self._connect() as db:
                db.execute("PRAGMA auto_vacuum=INCREMENTAL")
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS events(
                      event_id TEXT PRIMARY KEY,payload TEXT NOT NULL,
                      delivery_status TEXT NOT NULL CHECK(delivery_status IN('pending','retry','ack','failed')),
                      attempts INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL,updated_at REAL NOT NULL,
                      next_retry_at REAL,reason TEXT NOT NULL DEFAULT '',lease_until REAL,lease_token TEXT,
                      receipt TEXT,payload_hash TEXT NOT NULL DEFAULT '');
                    CREATE INDEX IF NOT EXISTS events_due ON events(delivery_status,next_retry_at,lease_until);
                    CREATE TABLE IF NOT EXISTS receipts(event_id TEXT PRIMARY KEY,receipt TEXT NOT NULL,acked_at REAL NOT NULL,payload_hash TEXT NOT NULL DEFAULT '',
                      pending_finalization INTEGER NOT NULL DEFAULT 0 CHECK(pending_finalization IN(0,1)));
                """)
                for table in ("events","receipts"):
                    if "payload_hash" not in {row[1] for row in db.execute("PRAGMA table_info("+table+")")}:
                        db.execute("ALTER TABLE "+table+" ADD COLUMN payload_hash TEXT NOT NULL DEFAULT ''")
                if "pending_finalization" not in {row[1] for row in db.execute("PRAGMA table_info(receipts)")}:
                    db.execute("ALTER TABLE receipts ADD COLUMN pending_finalization INTEGER NOT NULL DEFAULT 0 CHECK(pending_finalization IN(0,1))")
                for row in db.execute("SELECT event_id,payload FROM events WHERE payload_hash=''").fetchall():
                    db.execute("UPDATE events SET payload_hash=? WHERE event_id=?",(event_payload_hash(json.loads(row["payload"])),row["event_id"]))
                db.execute("UPDATE receipts SET payload_hash=COALESCE((SELECT payload_hash FROM events WHERE events.event_id=receipts.event_id),'') WHERE payload_hash=''")
                if previous != self.policy:
                    db.execute("INSERT OR REPLACE INTO meta VALUES('storage_policy',?)", (json.dumps(self.policy),))
        except (sqlite3.Error, OSError,ValueError) as exc:
            raise StoreError("store_initialization_failed") from exc

    @contextmanager
    def _connect(self):
        _guard(self.path)
        db = sqlite3.connect(str(self.path), timeout=3)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA busy_timeout=3000")
            page_size = db.execute("PRAGMA page_size").fetchone()[0]
            db.execute("PRAGMA max_page_count=" + str(self.max_bytes // page_size))
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _sqlite_error(exc):
        if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL or "full" in str(exc).lower():
            return CapacityError("store_capacity_transaction_rolled_back")
        return StoreError("store_transaction_failed")

    @staticmethod
    def _increment(db, key, amount):
        previous = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        count = int(previous[0]) if previous else 0
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, str(count + amount)))

    def _prune(self, db, now, slots=1):
        self._expire(db, now)
        count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        needed = max(0, count + slots - self.max_events)
        if needed:
            rows = db.execute("""SELECT event_id,delivery_status FROM events
                WHERE delivery_status='ack'
                ORDER BY updated_at,event_id LIMIT ?""", (needed,)).fetchall()
            has_reviews = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_reviews'").fetchone()
            for row in rows:
                if has_reviews:
                    db.execute("DELETE FROM event_reviews WHERE event_id=?", (row["event_id"],))
                db.execute("DELETE FROM events WHERE event_id=?", (row["event_id"],))
                self._increment(db, "rotated_" + row["delivery_status"], 1)

    def _expire(self, db, now):
        rows = db.execute("SELECT event_id,delivery_status FROM events WHERE delivery_status='ack' AND updated_at<?",
                          (now-self.policy["acked_retention_seconds"],)).fetchall()
        self._delete_completed(db, rows)
        removed = db.execute("DELETE FROM receipts WHERE pending_finalization=0 AND acked_at<?", (now-self.policy["receipt_retention_seconds"],)).rowcount
        pinned = db.execute("SELECT COUNT(*) FROM receipts WHERE pending_finalization=1").fetchone()[0]
        removed += db.execute("""DELETE FROM receipts WHERE event_id IN (
            SELECT event_id FROM receipts WHERE pending_finalization=0
            ORDER BY acked_at DESC,event_id DESC LIMIT -1 OFFSET ?)""", (max(0,self.policy["receipt_limit"]-pinned),)).rowcount
        if removed:
            self._increment(db, "expired_receipts", removed)

    def _delete_completed(self, db, rows):
        has_reviews = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_reviews'").fetchone()
        for row in rows:
            if has_reviews:
                db.execute("DELETE FROM event_reviews WHERE event_id=?", (row["event_id"],))
            db.execute("DELETE FROM events WHERE event_id=? AND delivery_status='ack'", (row["event_id"],))
            self._increment(db, "rotated_ack", 1)

    def _insert(self, db, event, now):
        event_id = event["event_id"]
        payload_hash=event_payload_hash(event)
        previous=db.execute("SELECT payload_hash FROM events WHERE event_id=?",(event_id,)).fetchone()
        if previous is None:
            previous=db.execute("SELECT payload_hash FROM receipts WHERE event_id=?",(event_id,)).fetchone()
        if previous is not None:
            if previous[0]!=payload_hash:
                raise StoreError("event_identity_conflict")
            return False
        self._prune(db, now)
        if db.execute("SELECT COUNT(*) FROM events").fetchone()[0] >= self.max_events:
            raise CapacityError("event_queue_full_pending_preserved")
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        page_size=db.execute("PRAGMA page_size").fetchone()[0]
        estimated=((len(payload.encode("utf-8"))+page_size-1)//page_size+1)*page_size
        if self._used_bytes(db)+estimated+self.ack_reserve_bytes>self.max_bytes:
            self._rotate_completed(db,now)
            for _ in range(16):
                if self._used_bytes(db)+estimated+self.ack_reserve_bytes <= self.max_bytes or not self._trim_receipts(db):
                    break
            if self._used_bytes(db)+estimated+self.ack_reserve_bytes>self.max_bytes:
                raise CapacityError("event_bytes_full_ack_space_reserved_pending_preserved")
        db.execute("INSERT INTO events(event_id,payload,delivery_status,created_at,updated_at,payload_hash) VALUES(?,?,'pending',?,?,?)", (event_id, payload, now, now,payload_hash))
        return True

    @staticmethod
    def _used_bytes(db):
        return (db.execute("PRAGMA page_count").fetchone()[0]-db.execute("PRAGMA freelist_count").fetchone()[0])*db.execute("PRAGMA page_size").fetchone()[0]

    def _rotate_completed(self,db,now):
        rows=db.execute("SELECT event_id,delivery_status FROM events WHERE delivery_status='ack' ORDER BY updated_at,event_id LIMIT 100").fetchall()
        self._delete_completed(db, rows)
        return len(rows)

    def _trim_receipts(self, db):
        count = db.execute("SELECT COUNT(*) FROM receipts WHERE pending_finalization=0").fetchone()[0]
        if count <= 1:
            return 0
        removed = db.execute("""DELETE FROM receipts WHERE event_id IN (
            SELECT event_id FROM receipts WHERE pending_finalization=0 ORDER BY acked_at,event_id LIMIT ?)""", (max(1,count//2),)).rowcount
        self._increment(db, "pressure_rotated_receipts", removed)
        return removed

    def maintain(self, now=None):
        """Expire ACKed payloads/receipts only; free pages stay reusable, no VACUUM."""
        try:
            with self._lock, self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                self._prune(db, _epoch(now), slots=0)
            return self.stats()
        except sqlite3.Error as exc:
            raise self._sqlite_error(exc) from exc

    def _reclaim_completed(self, now):
        """Bounded rotation when byte pressure occurs before the event-count cap."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._rotate_completed(db,now) + self._trim_receipts(db)

    def _commit_batch(self, clean, state=None):
        now=time.time()
        for attempt in range(2):
            inserted=0
            try:
                with self._lock,self._connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    for event in clean:
                        inserted+=int(self._insert(db,event,now))
                    if state is not None:
                        old=db.execute("SELECT length(CAST(value AS BLOB)) FROM meta WHERE key='detector_state'").fetchone()
                        growth=max(0,len(state.encode("utf-8"))-(old[0] if old else 0))
                        if self._used_bytes(db)+growth+self.ack_reserve_bytes>self.max_bytes:
                            raise CapacityError("state_bytes_full_ack_space_reserved")
                        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('detector_state',?)",(state,))
                return inserted
            except sqlite3.Error as exc:
                full=getattr(exc,"sqlite_errorcode",None)==sqlite3.SQLITE_FULL
                if full and attempt==0:
                    try:
                        if self._reclaim_completed(now):
                            continue
                    except sqlite3.Error as maintenance:
                        raise self._sqlite_error(maintenance) from maintenance
                raise self._sqlite_error(exc) from exc

    def commit_evaluation(self, detector_state, events):
        """All new events and detector state commit together, or neither does."""
        if not isinstance(detector_state, dict) or not isinstance(events, (list, tuple)) or len(events) > 1000:
            raise StoreError("invalid_evaluation")
        try:
            state = json.dumps(detector_state, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise StoreError("invalid_detector_state") from exc
        if len(state.encode("utf-8")) > MAX_STATE_BYTES:
            raise CapacityError("detector_state_capacity")
        clean = [validate_event(event) for event in events]
        inserted=self._commit_batch(clean,state)
        return {"inserted":inserted, "duplicates":len(clean)-inserted, "state_saved":True}

    def load_detector_state(self):
        try:
            with self._lock, self._connect() as db:
                row = db.execute("SELECT value FROM meta WHERE key='detector_state'").fetchone()
                if row is None:
                    return None
                value = json.loads(row[0])
                if not isinstance(value, dict):
                    raise ValueError()
                return value
        except (ValueError, sqlite3.Error) as exc:
            raise StoreError("detector_state_unreadable") from exc

    def enqueue(self, event):
        clean = validate_event(event)
        return bool(self._commit_batch([clean]))

    @staticmethod
    def _row(row):
        event = validate_event(json.loads(row["payload"]))
        if row["payload_hash"]!=event_payload_hash(event):
            raise StoreError("stored_event_identity_mismatch")
        event.update(delivery_status=row["delivery_status"], attempts=row["attempts"],
                     next_retry_at=row["next_retry_at"], delivery_reason=row["reason"],
                     created_at=_iso(row["created_at"]), updated_at=_iso(row["updated_at"]),
                     receipt=validate_receipt(row["event_id"],json.loads(row["receipt"])) if row["receipt"] else None)
        return event

    def list_events(self, limit=100):
        if type(limit) is not int:
            raise StoreError("invalid_limit")
        try:
            with self._lock, self._connect() as db:
                return [self._row(row) for row in db.execute("SELECT * FROM events ORDER BY created_at DESC,event_id LIMIT ?", (max(0,min(1000,limit)),))]
        except (sqlite3.Error, ValueError) as exc:
            raise StoreError("event_read_failed") from exc

    def stats(self):
        try:
            with self._lock, self._connect() as db:
                counts = {key:0 for key in ("pending","retry","ack","failed")}
                counts.update(dict(db.execute("SELECT delivery_status,COUNT(*) FROM events GROUP BY delivery_status")))
                rotated = {row[0]:int(row[1]) for row in db.execute("SELECT key,value FROM meta WHERE key IN ('rotated_ack','rotated_failed')")}
                counts.update(total=sum(counts.values()), max_events=self.max_events,
                              storage_bytes=self.path.stat().st_size, max_bytes=self.max_bytes,
                              ack_reserve_bytes=self.ack_reserve_bytes,
                              receipt_count=db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0],
                              pending_receiver_finalizations=db.execute("SELECT COUNT(*) FROM receipts WHERE pending_finalization=1").fetchone()[0],
                              rotated_ack=rotated.get("rotated_ack",0),rotated_failed=rotated.get("rotated_failed",0),
                              real_agent_connected=False)
                counts.update(retention=dict(self.policy), used_bytes=self._used_bytes(db),
                              reusable_bytes=db.execute("PRAGMA freelist_count").fetchone()[0]*db.execute("PRAGMA page_size").fetchone()[0],
                              receipt_rotation=dict(db.execute("SELECT key,value FROM meta WHERE key IN ('expired_receipts','pressure_rotated_receipts')")))
                return counts
        except (sqlite3.Error,OSError) as exc:
            raise StoreError("store_status_failed") from exc

    def get_event(self,event_id):
        try:
            with self._lock,self._connect() as db:
                row=db.execute("SELECT * FROM events WHERE event_id=?",(str(event_id),)).fetchone()
                return self._row(row) if row else None
        except (sqlite3.Error,ValueError) as exc:
            raise StoreError("event_read_failed") from exc

    def save_review(self, event_id, payload_hash, result):
        """Keep the latest read-only diagnosis with its unchanged source event.

        This is not a delivery receipt, ACK or case closure. Pending events and
        ACK reserve survive any failed/capacity-limited review transaction.
        """
        encoded = json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False)
        if len(encoded.encode("ascii")) > 65536:
            raise CapacityError("review_result_capacity")
        try:
            with self._lock, self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT payload_hash FROM events WHERE event_id=?", (event_id,)).fetchone()
                if row is None or row[0] != payload_hash or result.get("payload_hash") != payload_hash:
                    raise StoreError("review_source_identity_conflict")
                db.execute("""CREATE TABLE IF NOT EXISTS event_reviews(event_id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,
                    result TEXT NOT NULL,updated_at REAL NOT NULL)""")
                previous = db.execute("SELECT length(CAST(result AS BLOB)) FROM event_reviews WHERE event_id=?", (event_id,)).fetchone()
                growth = max(0, len(encoded) - (previous[0] if previous else 0))
                page = db.execute("PRAGMA page_size").fetchone()[0]
                if self._used_bytes(db) + growth + page + self.ack_reserve_bytes > self.max_bytes:
                    raise CapacityError("review_capacity_pending_and_ack_space_preserved")
                db.execute("INSERT OR REPLACE INTO event_reviews(event_id,payload_hash,result,updated_at) VALUES(?,?,?,?)",
                           (event_id, payload_hash, encoded, time.time()))
        except sqlite3.Error as exc:
            raise self._sqlite_error(exc) from exc

    def _pin_receipt(self, db, event_id, encoded, payload_hash, acked_at):
        """Protect the original ACK until its receiver completion is durable."""
        previous = db.execute("SELECT receipt,payload_hash,pending_finalization FROM receipts WHERE event_id=?", (event_id,)).fetchone()
        if previous is not None and (json.loads(previous["receipt"]) != json.loads(encoded) or previous["payload_hash"] != payload_hash):
            raise StoreError("ack_receipt_identity_conflict")
        if previous is not None and previous["pending_finalization"]:
            return
        if db.execute("SELECT COUNT(*) FROM receipts WHERE pending_finalization=1").fetchone()[0] >= self.policy["receipt_limit"]:
            raise CapacityError("receiver_finalization_capacity_pending_preserved")
        if previous is None:
            db.execute("INSERT INTO receipts(event_id,receipt,acked_at,payload_hash,pending_finalization) VALUES(?,?,?,?,1)",
                       (event_id,encoded,acked_at,payload_hash))
        else:
            db.execute("UPDATE receipts SET pending_finalization=1 WHERE event_id=?", (event_id,))

    def _ack(self, db, event_id, receipt, now, receiver_finalization=False):
        clean = validate_receipt(event_id, receipt)
        encoded = json.dumps(clean, ensure_ascii=False, separators=(",", ":"))
        row = db.execute("SELECT payload_hash,delivery_status,receipt,updated_at FROM events WHERE event_id=?",(event_id,)).fetchone()
        if not row:
            previous = db.execute("SELECT receipt,payload_hash,acked_at FROM receipts WHERE event_id=?",(event_id,)).fetchone()
            if previous and json.loads(previous[0]) != clean:
                raise StoreError("ack_receipt_identity_conflict")
            if previous and receiver_finalization:
                self._pin_receipt(db,event_id,encoded,previous["payload_hash"],previous["acked_at"])
            return previous is not None
        if row["delivery_status"] == "ack":
            if json.loads(row["receipt"]) != clean:
                raise StoreError("ack_receipt_identity_conflict")
            if receiver_finalization:
                self._pin_receipt(db,event_id,encoded,row["payload_hash"],row["updated_at"])
            return True
        db.execute("UPDATE events SET delivery_status='ack',receipt=?,updated_at=?,reason='receiver_persisted',next_retry_at=NULL,lease_until=NULL,lease_token=NULL WHERE event_id=?",(encoded,now,event_id))
        db.execute("INSERT OR IGNORE INTO receipts(event_id,receipt,acked_at,payload_hash) VALUES(?,?,?,?)",(event_id,encoded,now,row["payload_hash"]))
        if receiver_finalization:
            self._pin_receipt(db,event_id,encoded,row["payload_hash"],now)
        self._prune(db,now,slots=0)
        return True

    def acknowledge(self, event_id, receipt, *, receiver_finalization=False):
        if type(receiver_finalization) is not bool:
            raise StoreError("invalid_receiver_finalization_profile")
        for attempt in range(2):
            try:
                with self._lock, self._connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    return self._ack(db,str(event_id),receipt,time.time(),receiver_finalization)
            except sqlite3.Error as exc:
                if attempt == 0 and getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL:
                    try:
                        if self._reclaim_completed(time.time()):
                            continue
                    except sqlite3.Error as maintenance:
                        raise self._sqlite_error(maintenance) from maintenance
                raise self._sqlite_error(exc) from exc

    def finalize_receiver(self, event_id, receipt):
        """Release only a matching ACK pin after receiver completion is durable.

        A missing/previously released pin is an idempotent no-op. This never
        creates a receipt, acknowledges a pending event, or changes ACK time.
        """
        clean = validate_receipt(str(event_id),receipt)
        try:
            with self._lock,self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                previous = db.execute("SELECT receipt,pending_finalization FROM receipts WHERE event_id=?", (str(event_id),)).fetchone()
                if previous is None:
                    return False
                if json.loads(previous["receipt"]) != clean:
                    raise StoreError("ack_receipt_identity_conflict")
                if not previous["pending_finalization"]:
                    return False
                db.execute("UPDATE receipts SET pending_finalization=0 WHERE event_id=?", (str(event_id),))
                self._prune(db,time.time(),slots=0)
                return True
        except sqlite3.Error as exc:
            raise self._sqlite_error(exc) from exc

    @staticmethod
    def _recover(db, now):
        return db.execute("""UPDATE events SET delivery_status='failed',reason='last_attempt_uncertain',
            next_retry_at=NULL,lease_until=NULL,lease_token=NULL,updated_at=?
            WHERE delivery_status='retry' AND attempts>=? AND (lease_until IS NULL OR lease_until<=?)""",(now,MAX_ATTEMPTS,now)).rowcount

    def retry_failed(self, event_id):
        """Explicit one-event replay; old dedup windows require receipt review."""
        now=time.time()
        try:
            with self._lock,self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row=db.execute("SELECT created_at,delivery_status FROM events WHERE event_id=?",(event_id,)).fetchone()
                if not row or row["delivery_status"] != "failed":
                    return False
                if now-row["created_at"]>DEDUP_RETENTION:
                    raise StoreError("replay_requires_receipt_check")
                db.execute("UPDATE events SET delivery_status='pending',attempts=0,next_retry_at=NULL,lease_until=NULL,lease_token=NULL,reason='explicit_retry',updated_at=? WHERE event_id=?",(now,event_id))
                return True
        except sqlite3.Error as exc:
            raise self._sqlite_error(exc) from exc

    def pump(self, adapter, now=None):
        """At-least-once attempts; adapter.send must be bounded and idempotent.

        No model or network function exists here. An unconfigured adapter never
        consumes attempts. Successful receiver ACK never claims agent processing.
        """
        current=_epoch(now)
        result={"attempted":0,"acknowledged":0,"retry":0,"failed":0,"pending":0,"real_agent_woken":False}
        try:
            with self._lock:
                with self._connect() as db:
                    db.execute("BEGIN IMMEDIATE")
                    result["failed"]+=self._recover(db,current)
                if getattr(adapter,"connected",False) is not True:
                    stats=self.stats()
                    result.update(pending=stats["pending"]+stats["retry"],remaining_pending=stats["pending"],remaining_retry=stats["retry"],reason="receiver_unconfigured")
                    return result
                with self._connect() as db:
                    rows=db.execute("""SELECT * FROM events WHERE delivery_status IN ('pending','retry')
                        AND attempts<? AND (next_retry_at IS NULL OR next_retry_at<=?)
                        AND (lease_until IS NULL OR lease_until<=?) ORDER BY created_at,event_id LIMIT 100""",(MAX_ATTEMPTS,current,current)).fetchall()
                for row in rows:
                    try:
                        clean_event=validate_event(json.loads(row["payload"]))
                        if event_payload_hash(clean_event)!=row["payload_hash"]:
                            raise ValueError("payload identity differs")
                    except (ValueError,TypeError):
                        with self._connect() as db:
                            db.execute("UPDATE events SET delivery_status='failed',reason='stored_payload_invalid',updated_at=?,next_retry_at=NULL WHERE event_id=? AND delivery_status IN ('pending','retry')",(current,row["event_id"]))
                        result["failed"]+=1
                        continue
                    if current-row["created_at"]>DEDUP_RETENTION:
                        with self._connect() as db:
                            db.execute("UPDATE events SET delivery_status='failed',reason='dedup_window_expired',updated_at=?,next_retry_at=NULL WHERE event_id=? AND delivery_status IN ('pending','retry')",(current,row["event_id"]))
                        result["failed"]+=1
                        continue
                    token=uuid.uuid4().hex
                    attempt=row["attempts"]+1
                    # Deterministic bounded jitter avoids synchronized retries
                    # while keeping tests and recovery calculations reproducible.
                    fraction=int(hashlib.sha256((row["event_id"]+str(attempt)).encode()).hexdigest()[:8],16)/0xFFFFFFFF
                    delay=min(3600,30*(2**(attempt-1))*(0.8+0.4*fraction))
                    retry_at=current+delay
                    with self._connect() as db:
                        db.execute("BEGIN IMMEDIATE")
                        changed=db.execute("""UPDATE events SET delivery_status='retry',attempts=attempts+1,
                            lease_until=?,lease_token=?,next_retry_at=?,reason='delivery_uncertain',updated_at=?
                            WHERE event_id=? AND delivery_status IN ('pending','retry') AND attempts=?
                            AND (lease_until IS NULL OR lease_until<=?)""",(current+LEASE_SECONDS,token,retry_at,current,row["event_id"],row["attempts"],current)).rowcount
                    if not changed:
                        continue
                    result["attempted"]+=1
                    try:
                        response=adapter.send(clean_event)
                    except Exception:
                        response={"ack":False,"retryable":True}
                    with self._connect() as db:
                        db.execute("BEGIN IMMEDIATE")
                        active=db.execute("SELECT lease_token,delivery_status FROM events WHERE event_id=?",(row["event_id"],)).fetchone()
                        if not active or active["lease_token"]!=token or active["delivery_status"]=="ack":
                            continue
                        try:
                            self._ack(db,row["event_id"],response,current)
                        except StoreError:
                            retryable=not isinstance(response,dict) or response.get("retryable") is not False
                            status="retry" if retryable and attempt<MAX_ATTEMPTS else "failed"
                            reason="retry_limit" if attempt>=MAX_ATTEMPTS else ("delivery_uncertain" if retryable else "receiver_rejected")
                            db.execute("UPDATE events SET delivery_status=?,reason=?,updated_at=?,next_retry_at=?,lease_until=NULL,lease_token=NULL WHERE event_id=? AND lease_token=?",(status,reason,current,retry_at if status=="retry" else None,row["event_id"],token))
                            result[status]+=1
                        else:
                            result["acknowledged"]+=1
                stats=self.stats()
                result.update(pending=stats["pending"]+stats["retry"],remaining_pending=stats["pending"],remaining_retry=stats["retry"])
                return result
        except sqlite3.Error as exc:
            raise self._sqlite_error(exc) from exc
