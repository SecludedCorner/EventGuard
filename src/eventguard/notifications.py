"""Local high-severity notices. No model, network, shell or subprocess calls."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import os
import re
import sqlite3
import threading
import time

from .runtime import Runtime, utc_now
from .source_status import SOURCE_NAMES
from .events.store import StoreError

MAX_RECEIPTS = 10000
MAX_SCAN = 100000
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_EVENT_NAMES = {
    "protection.changed": "防護狀態變更", "listener.changed": "監聽狀態變更",
    "persistence.changed": "持久設定變更", "coverage.degraded": "來源可見性降低",
    "monitor_gap": "監看缺口", "rule.matched": "規則符合",
}


class NotificationError(RuntimeError):
    """Fixed public reason code. Never contains native exception text."""


def _sort_key(item):
    try:
        stamp = datetime.fromisoformat(item.get("observed_at", "").replace("Z", "+00:00"))
        epoch = stamp.timestamp() if stamp.tzinfo is not None else 0
    except (ValueError, TypeError, AttributeError, OverflowError, OSError):
        epoch = 0
    return epoch, item["event_id"]


def _message(item):
    source = item.get("source")
    source = source if source in {*SOURCE_NAMES, "monitor", "unknown"} else "unknown"
    source_name = SOURCE_NAMES.get(source, "監看器" if source == "monitor" else "未知來源")
    severity = item["severity"]
    synthetic = item.get("synthetic") is True
    title = "EventGuard 嚴重事件" if severity == "critical" else "EventGuard 高嚴重度事件"
    if synthetic:
        title = "合成測試：" + title
    event_name = _EVENT_NAMES.get(item.get("event_type"), "資安事件")
    # Only fixed labels and a validated ID reach the desktop. Event names,
    # process names, paths and untrusted free text cannot become instructions.
    return {"event_id": item["event_id"], "severity": severity, "source": source,
            "synthetic": synthetic, "title": title,
            "body": source_name + "：" + event_name + "。\n請在 EventGuard 查看事件。\nID：" + item["event_id"][:24]}


class _WindowsBalloon:
    """An application-owned hidden window and standard Windows tray balloon.

    A True return means Windows accepted the request. Focus Assist or user
    notification settings can suppress it. It does not prove a person saw it.
    """
    display_scope = "os_notification_requested"
    cooldown_seconds = 10

    def __init__(self):
        self.hwnd = None
        self.added = False
        self.owner_thread = None
        self._api_ready = False
        self.user = None
        self.shell = None

    def _load_api(self):
        """Keep this sink's loaded DLLs when the desktop rejects an icon.

        A partial DLL load is retained too. Poll retries must not keep adding
        Windows loader references after Shell_NotifyIcon fails.
        """
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        class INFO_UNION(ctypes.Union):
            _fields_ = [("uTimeout", wintypes.UINT), ("uVersion", wintypes.UINT)]

        class NOTIFYICONDATAW(ctypes.Structure):
            _anonymous_ = ("timeout",)
            _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                        ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                        ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                        ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
                        ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                        ("timeout", INFO_UNION), ("szInfoTitle", wintypes.WCHAR * 64),
                        ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID),
                        ("hBalloonIcon", wintypes.HICON)]

        self.ctypes, self.wintypes, self.data_type = ctypes, wintypes, NOTIFYICONDATAW
        if self.user is None:
            self.user = ctypes.WinDLL("user32.dll", use_last_error=True, winmode=0x800)
        if self.shell is None:
            self.shell = ctypes.WinDLL("shell32.dll", use_last_error=True, winmode=0x800)
        self.user.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
            wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        self.user.CreateWindowExW.restype = wintypes.HWND
        self.user.DestroyWindow.argtypes = [wintypes.HWND]
        self.user.DestroyWindow.restype = wintypes.BOOL
        self.user.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
        self.user.LoadIconW.restype = wintypes.HICON
        self.user.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                          wintypes.UINT, wintypes.UINT, wintypes.UINT]
        self.user.PeekMessageW.restype = wintypes.BOOL
        self.user.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.user.TranslateMessage.restype = wintypes.BOOL
        self.user.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.user.DispatchMessageW.restype = ctypes.c_ssize_t
        self.shell.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
        self.shell.Shell_NotifyIconW.restype = wintypes.BOOL
        self._api_ready = True

    def _initialize(self):
        if os.name != "nt":
            raise NotificationError("local_notifications_unavailable")
        if not self._api_ready:
            self._load_api()
        self.hwnd = self.user.CreateWindowExW(0, "STATIC", "EventGuard notifications", 0,
                                            0, 0, 0, 0, None, None, None, None)
        if not self.hwnd:
            raise NotificationError("notification_window_unavailable")
        self.owner_thread = threading.get_ident()
        self.data = self.data_type()
        self.data.cbSize = self.ctypes.sizeof(self.data_type)
        self.data.hWnd, self.data.uID = self.hwnd, 1
        self.data.uFlags = 0x02 | 0x04  # NIF_ICON | NIF_TIP
        self.data.hIcon = self.user.LoadIconW(None, self.ctypes.c_void_p(32515))  # IDI_WARNING
        self.data.szTip = "EventGuard"
        if not self.shell.Shell_NotifyIconW(0, self.ctypes.byref(self.data)):  # NIM_ADD
            self.user.DestroyWindow(self.hwnd)
            self.hwnd = None
            raise NotificationError("notification_icon_unavailable")
        self.added = True

    def _pump(self):
        if self.hwnd is None:
            return
        if self.owner_thread != threading.get_ident():
            raise NotificationError("notification_thread_mismatch")
        message = self.wintypes.MSG()
        for _ in range(32):
            if not self.user.PeekMessageW(self.ctypes.byref(message), self.hwnd, 0, 0, 1):
                break
            self.user.TranslateMessage(self.ctypes.byref(message))
            self.user.DispatchMessageW(self.ctypes.byref(message))

    def __call__(self, message):
        if self.hwnd is None:
            self._initialize()
        self._pump()
        self.data.uFlags = 0x10  # NIF_INFO
        self.data.szInfoTitle, self.data.szInfo = message["title"][:63], message["body"][:255]
        self.data.dwInfoFlags = 0x03 if message["severity"] == "critical" else 0x02
        self.data.uTimeout = 10000
        if not self.shell.Shell_NotifyIconW(1, self.ctypes.byref(self.data)):  # NIM_MODIFY
            raise NotificationError("notification_display_failed")
        self._pump()
        return True

    def pump(self):
        self._pump()

    def close(self):
        if self.hwnd is None:
            return True
        if self.owner_thread != threading.get_ident():
            return False
        removed = not self.added or bool(self.shell.Shell_NotifyIconW(2, self.ctypes.byref(self.data)))
        destroyed = bool(self.user.DestroyWindow(self.hwnd))
        if destroyed:
            self.hwnd, self.added = None, False
        return removed and destroyed


class NotificationService:
    """One notice per poll. Existing event IDs survive process restarts.

    The sink accepts a fixed message mapping and must return exactly True.
    Receipts are written only after success. A receipt write failure is visible
    and can cause a repeat on retry; it never changes or discards the event.
    """

    def __init__(self, root, namespace="live", sink=None):
        self.runtime = Runtime(root)
        self.directory = self.runtime.data_dir(namespace, create=False)
        self.namespace = namespace
        self.sink = sink if sink is not None else _WindowsBalloon()
        self.closed = False
        self._next_display = 0.0
        self._lock = threading.Lock()
        self.last = self._result("idle", "not_polled")

    def _result(self, status, reason, *, pending_count=0, **values):
        return {"status": status, "reason": reason, "namespace": self.namespace,
                "pending_count": pending_count, "model_calls": 0,
                "display_scope": getattr(self.sink, "display_scope", "injected_local_sink"),
                **values}

    def _candidates(self):
        from .events.catalog import EventCatalog
        catalog = EventCatalog(self.runtime.root, self.namespace)
        candidates = {}
        for severity in ("high", "critical"):
            offset = 0
            while True:
                listing = catalog.list(severity=severity, limit=1000, offset=offset)
                items = listing["events"]
                for item in items:
                    event_id = item.get("event_id")
                    if (isinstance(event_id, str) and _ID.fullmatch(event_id)
                            and item.get("severity") in {"high", "critical"}
                            and item.get("status") not in {"handled", "ignored"}):
                        candidates[event_id] = item
                offset += len(items)
                if not listing.get("has_more"):
                    break
                if not items or offset >= MAX_SCAN:
                    raise NotificationError("notification_scan_limit")
        return sorted(candidates.values(), key=_sort_key)

    def _open(self):
        path = self.runtime.path(self.directory.relative_to(self.runtime.root) / "notifications.sqlite3")
        self.directory.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(path), timeout=0.2, isolation_level=None)
        try:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA max_page_count=512")
            db.execute("CREATE TABLE IF NOT EXISTS notified(event_id TEXT PRIMARY KEY,notified_at TEXT NOT NULL)")
        except Exception:
            db.close()
            raise
        return db

    def _prune_deleted_events(self, db):
        """Keep receipts for every retained event, including handled/ignored.

        Use one read-only source snapshot. A changing paginated UI listing is
        insufficient evidence that a historical event was actually removed.
        """
        source = self.runtime.path(self.directory.relative_to(self.runtime.root) / "eventguard.sqlite3")
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=0.2)) as events:
            events.execute("PRAGMA query_only=ON")
            existing = {row[0] for row in events.execute("SELECT event_id FROM events LIMIT ?", (MAX_SCAN + 1,))}
        if len(existing) > MAX_SCAN:
            raise NotificationError("notification_scan_limit")
        old = [row[0] for row in db.execute("SELECT event_id FROM notified") if row[0] not in existing]
        db.executemany("DELETE FROM notified WHERE event_id=?", ((event_id,) for event_id in old))

    def poll(self):
        with self._lock:
            if self.closed:
                return self._result("closed", "notification_service_closed")
            pending_count = 0
            try:
                pump = getattr(self.sink, "pump", None)
                if pump is not None:
                    pump()
                candidates = self._candidates()
                pending_count = len(candidates)
                if not candidates:
                    self.last = self._result("idle", "no_high_severity_events")
                    return self.last
                with closing(self._open()) as db:
                    db.execute("BEGIN IMMEDIATE")
                    known = {row[0] for row in db.execute("SELECT event_id FROM notified")}
                    pending = [item for item in candidates if item["event_id"] not in known]
                    pending_count = len(pending)
                    if not pending:
                        db.execute("COMMIT")
                        self.last = self._result("idle", "already_notified")
                        return self.last
                    if time.monotonic() < self._next_display:
                        db.execute("COMMIT")
                        self.last = self._result("pending", "notification_display_cooldown", pending_count=pending_count)
                        return self.last
                    if len(known) >= MAX_RECEIPTS:
                        self._prune_deleted_events(db)
                        count = db.execute("SELECT COUNT(*) FROM notified").fetchone()[0]
                        if count >= MAX_RECEIPTS:
                            raise NotificationError("notification_capacity_full")
                    item = pending[0]
                    try:
                        shown = self.sink(_message(item))
                    except NotificationError:
                        raise
                    except Exception:
                        raise NotificationError("notification_sink_failed") from None
                    if shown is not True:
                        raise NotificationError("notification_sink_failed")
                    cooldown = getattr(self.sink, "cooldown_seconds", 0)
                    self._next_display = time.monotonic() + (cooldown if type(cooldown) in (int, float) and 0 <= cooldown <= 60 else 0)
                    stamp = utc_now()
                    try:
                        db.execute("INSERT INTO notified(event_id,notified_at) VALUES(?,?)", (item["event_id"], stamp))
                        db.execute("COMMIT")
                    except (OSError, sqlite3.Error):
                        self.last = self._result("failed", "notification_receipt_failed",
                            pending_count=len(pending), display_requested=True)
                        return self.last
                    self.last = self._result("notified", "notification_requested", pending_count=len(pending)-1,
                        event_id=item["event_id"], notified_at=stamp, display_requested=True)
                    return self.last
            except NotificationError as error:
                reason = str(error)
                if reason not in {"local_notifications_unavailable", "notification_window_unavailable",
                                  "notification_icon_unavailable", "notification_thread_mismatch",
                                  "notification_display_failed", "notification_sink_failed",
                                  "notification_capacity_full", "notification_scan_limit"}:
                    reason = "notification_sink_failed"
                self.last = self._result("failed", reason, pending_count=pending_count)
            except sqlite3.OperationalError as error:
                code = getattr(error, "sqlite_errorcode", None)
                self.last = self._result("busy" if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} else "failed",
                    "notification_storage_busy" if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} else "notification_storage_unavailable",
                    pending_count=pending_count)
            except (OSError, ValueError, TypeError, KeyError, StoreError, sqlite3.Error):
                self.last = self._result("failed", "notification_storage_unavailable", pending_count=pending_count)
            return self.last

    def close(self):
        with self._lock:
            self.closed = True
            try:
                closer = getattr(self.sink, "close", None)
                closed = closer() if closer is not None else True
            except Exception:
                closed = False
            self.last = self._result("closed" if closed is not False else "failed",
                "notification_service_closed" if closed is not False else "notification_cleanup_unconfirmed")
            return self.last
