"""Local opt-in for event-driven models; separate from tool receive permission.

This is configuration, not a queue or budget. Reading it never launches a
dispatcher, model or collector. A later explicit Start may use a saved opt-in.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime

from .runtime import Runtime, atomic_json, read_json, utc_now

KIND = "eventguard-agent-automation-v1"
PATH = "data/agent-automation.json"


def status(root):
    default = {"enabled": False, "executable": None, "reason": "default_disabled"}
    try:
        path = Runtime(root).path(PATH)
        if not path.exists():
            return default
        value = read_json(path, 8192)
        if (type(value) is not dict or set(value) != {"kind", "enabled", "executable", "updated_at"}
                or value["kind"] != KIND or type(value["enabled"]) is not bool
                or type(value["executable"]) is not str or len(value["executable"]) > 2048
                or any(ord(char) < 32 for char in value["executable"])
                or type(value["updated_at"]) is not str or len(value["updated_at"]) > 80):
            raise ValueError("invalid_automation_setting")
        stamp = datetime.fromisoformat(value["updated_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("invalid_automation_setting")
        return {"enabled": value["enabled"], "executable": value["executable"] or None,
                "reason": "saved_opt_in" if value["enabled"] else "explicitly_disabled"}
    except (OSError, ValueError, TypeError, RuntimeError):
        return dict(default, reason="automation_setting_unavailable", blocked=True)


def set_enabled(root, enabled, executable=None):
    if type(enabled) is not bool:
        raise ValueError("automation_boolean_required")
    previous = status(root)
    candidate = executable if enabled and executable is not None else previous["executable"]
    if enabled:
        if (type(candidate) is not str or not candidate or len(candidate) > 2048
                or any(ord(char) < 32 for char in candidate)
                or Path(candidate).suffix.lower() != ".exe" or not Path(candidate).is_file()):
            raise ValueError("native_codex_executable_required")
        candidate = str(Path(candidate).resolve())
    atomic_json(Runtime(root).path(PATH), {"kind": KIND, "enabled": enabled,
        "executable": candidate or "", "updated_at": utc_now()}, 8192)
    return status(root)
