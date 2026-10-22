"""No production transport is configured. Local mock never wakes an agent."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid

from eventguard.events.schema import validate_event, redact_text, utc_now
from eventguard.events.store import StoreError, CapacityError, _guard,event_payload_hash


class DisabledAdapter:
    connected = False
    kind = "disabled"
    real_agent_woken = False

    def send(self, event):
        return {"ack":False,"retryable":False,"reason":"receiver_unconfigured","real_agent_woken":False}


SAFE_RESULT_KEYS = frozenset({
    "schema_version","request_id","operation","status","source","observed_at","window","start","end",
    "coverage","gaps","rows","truncated","evidence_ref","error_code","elapsed_ms","elapsed_seconds",
    "mock","synthetic","section","reason","count","name","protocol","address","port","local_port",
    "pid","scope","binding_scope","path","path_status","value","item","process_instance_ref",
    "signature_status","previous","current","state","enabled","available","limits",
})


def _safe_result(value, depth=0):
    if depth > 4:
        return None
    if value is None or type(value) in (bool,int):
        return value
    if isinstance(value,float):
        return value if value==value and abs(value)!=float("inf") else None
    if isinstance(value,str):
        return redact_text(value)[:512]
    if isinstance(value,list):
        return [_safe_result(item,depth+1) for item in value[:20]]
    if isinstance(value,dict):
        return {key:_safe_result(item,depth+1) for key,item in value.items() if key in SAFE_RESULT_KEYS}
    return None


class MockReceiverAdapter:
    """SQLite receiver for synthetic contract tests; no sockets or model APIs.

    send() proves durable local mock acceptance only. process_mock() invokes a
    caller-supplied, trusted read-only diagnostic callback with the sanitized event.
    It never executes event text, shell commands, actions, or an actual agent.
    """
    connected = True
    kind = "local_mock"
    real_agent_woken = False

    def __init__(self,data_dir,max_events=1000):
        if type(max_events) is not int or not 1<=max_events<=1000:
            raise StoreError("invalid_mock_capacity")
        self.directory=_guard(Path(data_dir))
        self.directory.mkdir(parents=True,exist_ok=True)
        self.path=_guard(self.directory/"mock-receiver.sqlite3")
        self.max_events=max_events
        try:
            with self._connect() as db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS received(event_id TEXT PRIMARY KEY,payload TEXT NOT NULL,
                        receipt TEXT NOT NULL,received_at REAL NOT NULL);
                    CREATE TABLE IF NOT EXISTS cases(event_id TEXT PRIMARY KEY,payload TEXT NOT NULL,
                        updated_at REAL NOT NULL,lease_until REAL,lease_token TEXT);
                """)
        except sqlite3.Error as exc:
            raise StoreError("mock_receiver_unavailable") from exc

    @contextmanager
    def _connect(self):
        _guard(self.path)
        db=sqlite3.connect(str(self.path),timeout=3)
        try:
            db.row_factory=sqlite3.Row
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA busy_timeout=3000")
            page_size=db.execute("PRAGMA page_size").fetchone()[0]
            db.execute("PRAGMA max_page_count="+str((8*1024*1024)//page_size))
            with db:
                yield db
        finally:
            db.close()

    def send(self,event):
        clean=validate_event(event)
        if clean["synthetic"] is not True:
            return {"ack":False,"retryable":False,"reason":"mock_rejects_real_events","real_agent_woken":False}
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                previous=db.execute("SELECT receipt,payload FROM received WHERE event_id=?",(clean["event_id"],)).fetchone()
                if previous:
                    if event_payload_hash(json.loads(previous["payload"]))!=event_payload_hash(clean):
                        raise StoreError("event_identity_conflict")
                    return json.loads(previous["receipt"])
                if db.execute("SELECT COUNT(*) FROM received").fetchone()[0]>=self.max_events:
                    raise CapacityError("mock_receiver_capacity")
                receipt={"ack_type":"receiver_persisted","event_id":clean["event_id"],
                         "receiver_receipt_id":"mock-receipt-"+uuid.uuid4().hex,
                         "received_at":utc_now(),"receiver_kind":"local_mock", "task_ref":"local_mock_test_only",
                         "wake_state":"mock_only_no_agent","real_agent_woken":False}
                db.execute("INSERT INTO received(event_id,payload,receipt,received_at) VALUES(?,?,?,?)",
                           (clean["event_id"],json.dumps(clean,ensure_ascii=False),json.dumps(receipt),time.time()))
                return receipt
        except sqlite3.Error as exc:
            raise StoreError("mock_receiver_write_failed") from exc

    def get_receipt(self,event_id):
        try:
            with self._connect() as db:
                row=db.execute("SELECT receipt FROM received WHERE event_id=?",(event_id,)).fetchone()
                return json.loads(row[0]) if row else None
        except (sqlite3.Error,ValueError) as exc:
            raise StoreError("mock_receipt_read_failed") from exc

    def list_received(self,limit=100):
        try:
            with self._connect() as db:
                return [dict(validate_event(json.loads(row["payload"])),receipt=json.loads(row["receipt"]),
                             receiver_kind="local_mock",real_agent_woken=False)
                        for row in db.execute("SELECT payload,receipt FROM received ORDER BY received_at DESC LIMIT ?",(max(0,min(1000,int(limit))),))]
        except (sqlite3.Error,ValueError) as exc:
            raise StoreError("mock_receiver_read_failed") from exc

    def list_cases(self,limit=100):
        try:
            with self._connect() as db:
                return [json.loads(row[0]) for row in db.execute("SELECT payload FROM cases ORDER BY updated_at DESC LIMIT ?",(max(0,min(1000,int(limit))),))]
        except (sqlite3.Error,ValueError) as exc:
            raise StoreError("mock_case_read_failed") from exc

    def status(self):
        with self._connect() as db:
            total=db.execute("SELECT COUNT(*) FROM received").fetchone()[0]
        cases=self.list_cases(1000)
        return {"receiver_kind":"local_mock","receiver_accepted":total,"mock_processed":sum(case.get("mock_processed") is True for case in cases),
                "mock_closed":sum(case.get("case_state")=="mock_closed" for case in cases),"real_agent_woken":False,
                "model_calls":0,"external_transport":False,"max_events":self.max_events}

    def process_mock(self,event_id,diagnostic_callable):
        try:
            return self._process_mock(event_id,diagnostic_callable)
        except (sqlite3.Error,ValueError) as exc:
            raise StoreError("mock_case_storage_failed") from exc

    def _process_mock(self,event_id,diagnostic_callable):
        """Run a synthetic read-only diagnostic callback; never a real agent wake.

        Repeating a completed event returns the same case. An interrupted callback
        may be repeated after lease expiry, so callbacks must be read-only. This
        is deliberately not an exactly-once execution claim.
        """
        token=uuid.uuid4().hex
        now=time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            received=db.execute("SELECT payload,receipt FROM received WHERE event_id=?",(event_id,)).fetchone()
            if not received:
                raise StoreError("mock_event_not_received")
            event=validate_event(json.loads(received["payload"]))
            if event["synthetic"] is not True:
                raise StoreError("mock_rejects_real_events")
            existing=db.execute("SELECT payload,lease_until FROM cases WHERE event_id=?",(event_id,)).fetchone()
            if existing:
                previous=json.loads(existing["payload"])
                if previous.get("mock_processed") is True or (existing["lease_until"] or 0)>now:
                    return previous
            case={"schema_version":"1.0","case_id":"mock-case-"+hashlib.sha256(event_id.encode()).hexdigest()[:24],
                  "event_id":event_id,"event_ids":[event_id],"receiver_receipt_id":json.loads(received["receipt"])["receiver_receipt_id"],
                  "agent_kind":"local_mock_no_model","real_agent_woken":False,"agent_started":False,"agent_processed":False,
                  "mock_processing_started_at":utc_now(),"mock_processed":False,"case_state":"mock_processing",
                  "actions_executed":[],"approval_ref":None}
            db.execute("INSERT OR REPLACE INTO cases(event_id,payload,updated_at,lease_until,lease_token) VALUES(?,?,?,?,?)",
                       (event_id,json.dumps(case),now,now+60,token))
        try:
            raw=diagnostic_callable(event)
            result=_safe_result(raw)
            if not isinstance(result,dict):
                result={"status":"error","error_code":"invalid_mock_diagnostic_result"}
            if len(json.dumps(result,ensure_ascii=False).encode("utf-8"))>16384:
                result={"status":"partial","error_code":"mock_result_capacity"}
        except Exception:
            result={"status":"error","error_code":"mock_diagnostic_failed"}
        case.update(mock_processed=True,mock_processed_at=utc_now(),diagnostic_result=result,
                    case_state="mock_closed" if result.get("status") in ("ok","not_applicable") else "mock_needs_evidence",
                    closure_reason="synthetic_contract_test_only" if result.get("status") in ("ok","not_applicable") else None)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed=db.execute("UPDATE cases SET payload=?,updated_at=?,lease_until=NULL,lease_token=NULL WHERE event_id=? AND lease_token=?",
                               (json.dumps(case,ensure_ascii=False),time.time(),event_id,token)).rowcount
            if not changed:
                row=db.execute("SELECT payload FROM cases WHERE event_id=?",(event_id,)).fetchone()
                return json.loads(row[0]) if row else {"case_state":"mock_unknown","real_agent_woken":False}
        return case
