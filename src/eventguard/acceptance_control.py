"""Small local control primitives; no processes, network, or credential reads."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time

from .local_wait import _guard, LocalWaitError

MAX_METADATA = 256 * 1024


def read_json(path, limit=MAX_METADATA):
    path = _guard(path)
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise LocalWaitError("acceptance_metadata_capacity")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise LocalWaitError("acceptance_metadata_invalid")
    return value


def write_json(path, value):
    path = _guard(path)
    encoded = json.dumps(value, indent=2, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_METADATA:
        raise LocalWaitError("acceptance_metadata_capacity")
    fd, name = tempfile.mkstemp(prefix=".acceptance-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(20):
            _guard(path)
            try:
                os.replace(temporary, path)
                break
            except PermissionError as error:
                # Windows JSON readers can briefly deny rename/delete sharing.
                # Retry only this local replace, with a 190 ms total wait cap;
                # persistent denial still fails closed without changing rights.
                if os.name != "nt" or getattr(error, "winerror", None) not in (5, 32, 33) or attempt == 19:
                    raise
                time.sleep(.01)
    finally:
        temporary.unlink(missing_ok=True)


class FileLease:
    """OS releases the lease on process exit; persistent file is never deleted."""
    def __init__(self, path):
        self.path = _guard(path)
        self.stream = None

    def acquire(self):
        if self.stream is not None:
            raise LocalWaitError("acceptance_lease_already_owned")
        stream = _guard(self.path).open("a+b")
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            return False
        self.stream = stream
        return True

    def release(self):
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
