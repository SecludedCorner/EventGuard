"""Owned runtime files, bounded health and cooperative single-instance control."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
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
        os.replace(temporary, path)
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
        if config.get("transport", {}).get("adapter", "disabled") != "disabled":
            raise ValueError("real_transport_not_configured_or_authorized")
        return config

    def health(self):
        path = self.path("data/health.json")
        return read_json(path) if path.exists() else {"state":"not_started", "monitoring":False, "real_agent_connected":False}

    def save_health(self, document):
        atomic_json(self.path("data/health.json"), document)

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
                "note":"Cooperative stop only; an existing read-only query exits naturally."}


class InstanceLock:
    def __init__(self, runtime):
        self.runtime = runtime
        self.instance_id = uuid.uuid4().hex
        self.stream = None

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
            atomic_json(self.runtime.path("data/monitor-owner.json"), {"pid":os.getpid(),"instance_id":self.instance_id,"started_at":utc_now()})
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
