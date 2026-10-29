"""Explicit no-overwrite local history backup; does not free or restore capacity."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile

from ..runtime import safe_child
from .disposition_history_backup import MAX_EXPORT_BYTES, verify_snapshot


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def read_known_backup(root, filename, identity):
    """Read only the exact file previously written by this process, bounded."""
    if type(filename) is not str or re.fullmatch(r"history-backup-[a-zA-Z0-9_-]{1,64}\.json", filename) is None:
        raise ValueError("history_backup_filename_invalid")
    path = safe_child(root, Path("reports") / filename)
    expected, digest = identity
    if not 0 < expected[2] <= MAX_EXPORT_BYTES + 1024:
        raise ValueError("history_backup_bytes_limit")
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("history_backup_file_changed")
    with path.open("rb") as stream:
        if _identity(os.fstat(stream.fileno())) != expected:
            raise ValueError("history_backup_file_changed")  # Before any content read.
        encoded = stream.read(MAX_EXPORT_BYTES + 1025)
        if _identity(os.fstat(stream.fileno())) != expected:
            raise ValueError("history_backup_file_changed")
    if (_identity(safe_child(root, Path("reports") / filename).lstat()) != expected
            or hashlib.sha256(encoded).hexdigest() != digest):
        raise ValueError("history_backup_file_changed")
    value = json.loads(encoded)
    verify_snapshot(value)
    return value


def write_backup(root, filename, value, *, with_identity=False):
    """Persist a verified snapshot under reports; never replace an existing file."""
    if type(filename) is not str or re.fullmatch(r"history-backup-[a-zA-Z0-9_-]{1,64}\.json", filename) is None:
        raise ValueError("history_backup_filename_invalid")
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    if len(encoded) > MAX_EXPORT_BYTES + 1024:
        raise ValueError("history_backup_bytes_limit")
    validated = verify_snapshot(json.loads(encoded))
    root = Path(root).absolute()
    reports = safe_child(root, "reports")
    reports.mkdir(exist_ok=True)
    path = safe_child(root, Path("reports") / filename)
    temporary = None
    try:
        fd, name = tempfile.mkstemp(prefix=".history-backup-", suffix=".tmp", dir=reports)
        temporary = Path(name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
            identity = (_identity(os.fstat(stream.fileno())), hashlib.sha256(encoded).hexdigest())
        if temporary.read_bytes() != encoded:
            raise ValueError("history_backup_verify_failed")
        safe_child(root, Path("reports") / filename)
        os.link(temporary, path)  # Exclusive: never replace an existing destination.
        if not os.path.samefile(temporary, path) or path.read_bytes() != encoded:
            raise ValueError("history_backup_verify_failed")
        verified = verify_snapshot(json.loads(path.read_bytes()))
        if verified != validated:
            raise ValueError("history_backup_verify_failed")
        return {"path": "reports/" + filename, **verified, "file_fsynced": True,
                "directory_entry_durability": "not_verified", "source_history_removed": False,
                **({"file_identity": identity} if with_identity else {})}
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
