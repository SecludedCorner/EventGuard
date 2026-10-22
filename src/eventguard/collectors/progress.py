"""Bounded, best-effort collector progress; never copies query or row contents."""
from __future__ import annotations

import inspect
import time

from .contract import SECTION_IDS


class Progress:
    def __init__(self, callback, source_id, backend):
        self.callback = callback if callable(callback) else None
        self.source_id = source_id if source_id in SECTION_IDS else None
        self.backend = backend if backend in ("native", "powershell") else None
        self.started = time.monotonic()
        self.last_phase = None
        self.last_waiting = self.started

    def emit(self, phase):
        if self.callback is None or phase not in ("launch", "waiting", "completed"):
            return
        now = time.monotonic()
        if phase == "waiting":
            if now - self.last_waiting < 1:
                return
            self.last_waiting = now
        elif self.last_phase == phase:
            return
        self.last_phase = phase
        value = {"phase": phase, "source_id": self.source_id, "backend": self.backend,
                 "elapsed_ms": max(0, int((now - self.started) * 1000))}
        try:
            self.callback(value)
        except Exception:
            # Display callbacks are observational. A persistence-aware observer
            # must retain/report its own failure rather than alter source facts.
            pass

    def forward(self, event):
        if isinstance(event, dict):
            self.emit(event.get("phase"))


def invoke_with_progress(call, *args, progress=None, source_id=None, **kwargs):
    """Adapt once before invocation; a provider TypeError never retries a query."""
    if progress is not None:
        try:
            parameters = inspect.signature(call).parameters
        except (ValueError, TypeError):
            parameters = {}
        variadic = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())
        for key, value in (("progress", progress), ("source_id", source_id)):
            parameter = parameters.get(key)
            if variadic or parameter is not None and parameter.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY):
                kwargs[key] = value
    return call(*args, **kwargs)
