"""Owned runtime files, bounded health and cooperative single-instance control."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import tempfile
import time
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_child(root, relative):
    root = Path(root).absolute()
    relative = Path(relative)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        raise ValueError("path_outside_project")
    current = root
    for part in (None,) + relative.parts:
        if part is not None:
            current = current / part
        if current.is_symlink() or current.is_junction():
            raise ValueError("redirected_runtime_path")
    return current


def read_json(path, limit=65536):
    path = Path(path)
    if path.stat().st_size > limit:
        raise ValueError("json_size_limit")
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, value, limit=65536):
    path = Path(path)
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    if len(encoded) > limit:
        raise ValueError("runtime_metadata_limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".eventguard-", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(20):
            try:
                os.replace(temporary, path)
                break
            except OSError as error:
                # A concurrent Windows JSON reader can briefly withhold delete
                # sharing. Retry this replace only, for at most 190 ms of
                # waiting; never change ACLs or hide persistent access denial.
                if os.name != "nt" or getattr(error, "winerror", None) not in (5, 32, 33) or attempt == 19:
                    raise
                time.sleep(.01)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


class Runtime:
    def __init__(self, root):
        self.root = Path(root).absolute()
        safe_child(self.root, ".")

    def path(self, relative):
        return safe_child(self.root, relative)

    def ensure(self):
        for name in ("data", "logs", "reports"):
            self.path(name).mkdir(parents=True, exist_ok=True)

    def data_dir(self, namespace="live", create=True):
        if namespace not in ("live", "test"):
            raise ValueError("invalid_namespace")
        path = self.path(Path("data") / namespace)
        if create:
            self.ensure()
            path.mkdir(exist_ok=True)
        return path

    def identity(self):
        self.ensure()
        path = self.path("data/identity.json")
        if path.exists():
            value = read_json(path)
            host_id = value.get("host_id")
            if not isinstance(host_id, str) or not host_id.startswith("host-") or len(host_id) != 37:
                raise ValueError("invalid_local_identity")
            return host_id
        host_id = "host-" + uuid.uuid4().hex
        atomic_json(path, {"host_id":host_id, "created_at":utc_now()})
        return host_id

    def config(self):
        config = read_json(self.path("config/default.json"))
        if not isinstance(config, dict) or config.get("schema_version") != "1.0":
            raise ValueError("invalid_config")
        expected = {"defender":120,"listeners":120,"processes":120,"startup":600,"services":600,"tasks":600,"versions":21600}
        intervals = config.get("interval_seconds", expected)
        if not isinstance(intervals, dict) or set(intervals) != set(expected):
            raise ValueError("invalid_intervals")
        for key, value in intervals.items():
            minimum = 30 if key in ("defender", "listeners", "processes") else (3600 if key == "versions" else 300)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= 86400:
                raise ValueError("interval_out_of_bounds")
        timeout=config.get("query_timeout_seconds",15)
        if type(timeout) not in (int,float) or not 0<timeout<=60:
            raise ValueError("query_timeout_out_of_bounds")
        if config.get("transport", {}).get("adapter", "disabled") != "disabled":
            raise ValueError("real_transport_not_configured_or_authorized")
        from .storage_policy import limits
        for section in ("outbox", "inbox", "dispatcher"):
            limits(section, config.get(section))
        return config

    def health(self):
        path = self.path("data/health.json")
        return read_json(path,2*1024*1024) if path.exists() else {"state":"not_started", "monitoring":False, "real_agent_connected":False}

    def save_health(self, document):
        atomic_json(self.path("data/health.json"), document,limit=2*1024*1024)
        if document.get("namespace") in {"live", "test"}:
            keys = {"pid", "process_created_at", "instance_id", "namespace", "state", "monitoring", "started_at", "heartbeat_at", "stopped_at"}
            atomic_json(self.path("data/" + document["namespace"] + "/monitor-checkpoint.json"), {key: document[key] for key in keys if key in document})

    def save_observation(self, section, namespace="live", instance_id=None):
        """Persist a bounded, typed projection, never raw names, paths or errors."""
        from .collectors.contract import SECTION_IDS, STATUSES
        from .collectors.windows import coverage_metadata
        from .diagnostics.review import row_view
        source_id = section.get("id") if isinstance(section, dict) else None
        if source_id not in SECTION_IDS or namespace not in ("live", "test"):
            raise ValueError("invalid_observation_source")
        rows = section.get("rows")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("invalid_observation_rows")
        safe_rows = [row_view(row) for row in rows[:200]]
        total = len(rows)
        status = section.get("status") if section.get("status") in STATUSES else "unknown"
        duration = section.get("elapsed_ms")
        duration = duration if type(duration) is int and 0 <= duration <= 2**31-1 else None
        coverage = coverage_metadata(section)
        saved_at = utc_now()
        value = {"schema_version": "1.0", "namespace": namespace, "instance_id": instance_id,
                 "saved_at": saved_at, "total": total, "exported": len(safe_rows),
                 "truncated": len(safe_rows) < total or coverage.get("truncated", False),
                 "data_trust": "untrusted_data", "incident_conclusion": "not_assessed",
                 "section": {"id": source_id, "status": status, "observed_at": section.get("observed_at"),
                             "elapsed_ms": duration, "coverage": coverage, "rows": safe_rows}}
        atomic_json(self.path("data/" + namespace + "/observations/" + source_id + ".json"), value, 1024*1024)
        return {"saved_at": saved_at, "total": total, "exported": len(safe_rows), "truncated": value["truncated"]}

    def observation(self, source_id, namespace="live", limit=20):
        """Read a saved projection only; absence never starts a query or creates data."""
        from .collectors.contract import SECTION_IDS
        if source_id not in SECTION_IDS or namespace not in ("live", "test"):
            raise ValueError("invalid_observation_source")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("invalid_observation_limit")
        path = self.path("data/" + namespace + "/observations/" + source_id + ".json")
        if not path.exists():
            return None
        value = read_json(path, 1024*1024)
        section = value.get("section") if isinstance(value, dict) else None
        if (not isinstance(value, dict) or value.get("schema_version") != "1.0" or value.get("namespace") != namespace
                or not isinstance(section, dict) or section.get("id") != source_id
                or not isinstance(section.get("rows"), list)
                or type(value.get("total")) is not int or value["total"] < len(section["rows"])):
            raise ValueError("invalid_saved_observation")
        section["rows"] = section["rows"][:limit]
        value["exported"] = len(section["rows"])
        value["truncated"] = value.get("truncated") is True or value["exported"] < value["total"]
        return value

    def block_monitor_shutdown(self, document):
        """Keep the last private query job unresolved across owner/lock exit."""
        from .collectors.windows import process_metadata
        process = process_metadata(document.get("query_shutdown", {}))
        value = {"kind": "eventguard-monitor-shutdown-gate-v1", "recorded_at": utc_now(),
                 "instance_id": document.get("instance_id"), "namespace": document.get("namespace"),
                 "owner_pid": document.get("pid"), "owner_created_at": document.get("process_created_at"),
                 "process": process}
        atomic_json(self.path("data/monitor-shutdown-gate.json"), value)
        return {"state": "blocked", "reason": "previous_query_exit_unconfirmed", "process": process}

    def monitor_shutdown_gate(self, *, recover=False):
        """Query only this marker's private job; never stop or enumerate processes.

        Lock ownership and a missing owner PID do not prove subtree exit. A
        named Job remains queryable while processes/handles keep it alive; an
        explicit missing-object result or active=0 proves this job is clear.
        """
        path = self.path("data/monitor-shutdown-gate.json")
        if not path.exists():
            return {"state": "clear", "reason": "no_unresolved_query"}
        try:
            value = read_json(path)
            process = value.get("process") if isinstance(value, dict) else None
            if (not isinstance(value, dict) or value.get("kind") != "eventguard-monitor-shutdown-gate-v1"
                    or not isinstance(process, dict) or process.get("managed") is not True):
                raise ValueError("invalid_monitor_shutdown_gate")
            name = process.get("job_name")
            if not isinstance(name, str) or not re.fullmatch(r"Local\\EventGuard-[a-f0-9]{32}", name):
                return {"state": "blocked", "reason": "previous_query_job_identity_unavailable", "process": process}
            from .processes import current_job_active
            try:
                active = current_job_active(name)
            except OSError as error:
                if getattr(error, "winerror", None) != 2:  # ERROR_FILE_NOT_FOUND only.
                    raise
                active = 0
            if type(active) is not int or active < 0:
                raise ValueError("private_job_query_unknown")
            if active:
                return {"state": "blocked", "reason": "previous_owned_job_still_active",
                        "remaining_owned_processes": active, "process": process}
            result = {"state": "confirmed_exited", "reason": "previous_private_job_empty_or_destroyed",
                      "remaining_owned_processes": 0, "process": process}
            if recover:
                # Preserve the recovery evidence before clearing the barrier.
                atomic_json(self.path("data/monitor-shutdown-recovered.json"),
                            {"kind": "eventguard-monitor-shutdown-recovered-v1", "verified_at": utc_now(),
                             "previous": value, "verification": result})
                path.unlink()
                result["state"] = "clear"
            return result
        except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
            return {"state": "blocked", "reason": "previous_query_exit_unverifiable", "raw_error_omitted": True}

    def log(self, code, details=None):
        """Fixed operational codes only; no raw exceptions, event evidence or commands."""
        self.ensure()
        path = self.path("logs/operations.jsonl")
        if path.exists() and path.stat().st_size > 1024 * 1024:
            for index in (2, 1):
                old = self.path("logs/operations.jsonl." + str(index))
                new = self.path("logs/operations.jsonl." + str(index+1))
                if old.exists():
                    os.replace(old, new)
            os.replace(path, self.path("logs/operations.jsonl.1"))
        safe = {key:value for key,value in (details or {}).items() if key in {"count","namespace","state","instance_id"} and isinstance(value,(str,int,bool))}
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"at":utc_now(),"code":str(code)[:80],"details":safe}, ensure_ascii=False)+"\n")

    def request_stop(self):
        owner = self.path("data/monitor-owner.json")
        if not owner.exists():
            return {"status":"not_running", "reason":"no_current_owner_record", "process_terminated":False}
        value = read_json(owner)
        instance = value.get("instance_id")
        if not isinstance(instance,str) or len(instance)!=32:
            raise ValueError("invalid_owner_record")
        atomic_json(self.path("data/stop-request.json"), {"instance_id":instance,"requested_at":utc_now()})
        return {"status":"stop_requested", "instance_id":instance, "process_terminated":False,
                "note":"Cooperative stop first; owned Windows query jobs receive a grace period then job-only cleanup."}


class InstanceLock:
    def __init__(self, runtime):
        self.runtime = runtime
        self.instance_id = uuid.uuid4().hex
        self.stream = None
        self.process_identity = None

    def acquire(self):
        self.runtime.ensure()
        path = self.runtime.path("data/monitor.lock")
        self.stream = path.open("a+b")
        self.stream.seek(0,2)
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            self.stream = None
            return False
        try:
            from .processes import identity
            self.process_identity = identity()
            atomic_json(self.runtime.path("data/monitor-owner.json"), {"pid":os.getpid(), "process_created_at": self.process_identity.get("created_at"), "instance_id":self.instance_id,"started_at":utc_now()})
        except Exception:
            self._unlock()
            raise
        return True

    def stop_requested(self):
        path = self.runtime.path("data/stop-request.json")
        if not path.exists():
            return False
        try:
            return read_json(path).get("instance_id") == self.instance_id
        except (ValueError,OSError):
            return False

    def release(self):
        if self.stream is None:
            return
        owner = self.runtime.path("data/monitor-owner.json")
        try:
            if owner.exists() and read_json(owner).get("instance_id") == self.instance_id:
                owner.unlink()
        finally:
            self._unlock()

    def _unlock(self):
        if self.stream is None:
            return
        try:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()
            self.stream = None
