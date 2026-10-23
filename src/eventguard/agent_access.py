"""Durable permission switch for optional live agent adapters.

Human OperatorAPI calls and monitor persistence do not use this gate. Enabling
access does not start a receiver or model and is never connection evidence.
This installation-local setting is a user control, not a same-user ACL boundary.
"""
from __future__ import annotations

from datetime import datetime

from .runtime import Runtime, atomic_json, read_json, utc_now


KIND = "eventguard-agent-access-v1"
SETTING_PATH = "data/agent-delivery.json"
MAX_SETTING_BYTES = 4096


def _projection(enabled=False, *, reason="default_disabled", blocked=False):
    return {"status": "blocked" if blocked else "enabled_waiting_receiver" if enabled else "disabled",
            "enabled": enabled, "delivery_allowed": enabled and not blocked,
            "receiver_state": "not_verified", "receiver_verified": False,
            "receiver_connected": None, "reason": reason, "model_calls": 0,
            "pending_disposition": "retained"}


def _validate(value):
    if (type(value) is not dict or set(value) != {"kind", "enabled", "updated_at"}
            or value.get("kind") != KIND or type(value.get("enabled")) is not bool
            or type(value.get("updated_at")) is not str or len(value["updated_at"]) > 64):
        raise ValueError("agent_setting_invalid")
    stamp = datetime.fromisoformat(value["updated_at"].replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("agent_setting_invalid")
    return value["enabled"]


def status(root):
    """Read the fixed setting without creating data or inspecting any events."""
    try:
        path = Runtime(root).path(SETTING_PATH)
        if not path.exists():
            return _projection()
        enabled = _validate(read_json(path, MAX_SETTING_BYTES))
    except (ValueError, TypeError, OverflowError):
        return _projection(reason="agent_setting_invalid", blocked=True)
    except OSError:
        return _projection(reason="agent_setting_unavailable", blocked=True)
    return _projection(enabled, reason="enabled_without_receiver_proof" if enabled else "explicitly_disabled")


def set_enabled(root, enabled):
    """Persist an explicit boolean; never scan, connect, dispatch, ACK or launch."""
    if type(enabled) is not bool:
        raise ValueError("agent_setting_requires_boolean")
    try:
        path = Runtime(root).path(SETTING_PATH)
        atomic_json(path, {"kind": KIND, "enabled": enabled, "updated_at": utc_now()}, MAX_SETTING_BYTES)
    except (OSError, ValueError, TypeError, OverflowError):
        # A failed disable must never claim the old enabled setting changed.
        # Report the last readable state; the caller must keep the error visible.
        return {**status(root), "status": "blocked", "reason": "agent_setting_write_failed", "setting_saved": False}
    return {**status(root), "setting_saved": True}


def guard(root, namespace="live"):
    """Return a fixed refusal, or None to allow adapter dispatch.

    Explicit test/synthetic adapters remain compatible. Every live adapter call
    must recheck before touching its event backend, including queries and ACKs
    issued after a previously successful receive. Disabling retains pending data
    and query receipts so human callers, or a later enabled agent, can resume.
    """
    if namespace == "test":
        return None
    if namespace != "live":
        reason = "agent_namespace_invalid"
    else:
        value = status(root)
        if value["delivery_allowed"]:
            return None
        reason = "agent_delivery_disabled" if value["status"] == "disabled" else value["reason"]
    return {"status": "blocked", "reason": reason, "agent_delivery_enabled": False,
            "data_disclosed": False, "model_calls": 0}
