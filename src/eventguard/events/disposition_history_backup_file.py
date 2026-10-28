"""Explicit no-overwrite local history backup; does not free or restore capacity."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile

from ..runtime import safe_child
from .disposition_history_backup import MAX_EXPORT_BYTES, verify_snapshot


def write_backup(root, filename, value):
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
                "directory_entry_durability": "not_verified", "source_history_removed": False}
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
