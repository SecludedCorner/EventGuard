"""Responsive, local Tk desktop view of the shared EventGuard controller.

No collector, agent runtime or scheduler is implemented in this module.  All
controller calls run on one worker; Tk only renders inert, bounded values.
"""
from __future__ import annotations

from pathlib import Path
import queue
import threading

from .gui_presenter import (DELIVERY_FILTERS, SEVERITY_FILTERS, detail_text,
                            event_list_view, event_summary, safe_text)


SOURCE_NAMES = {"defender": "Defender 防護", "listeners": "監聽端點", "processes": "程序",
                "startup": "啟動項", "services": "服務", "tasks": "排程工作", "versions": "版本"}
STATE_NAMES = {"running": "監看中", "running_verified": "監看中", "started": "啟動中",
               "starting": "啟動中", "enabled_not_running": "已啟用，目前尚未運作",
               "disabled": "已暫停", "stopped": "已暫停", "paused": "已暫停",
               "not_started": "尚未開始", "backoff": "等待後重試", "stopping": "正在暫停",
               "stop_requested": "正在暫停", "blocked": "監看受阻", "startup_failed": "啟動失敗",
               "shutdown_unconfirmed": "退出尚未確認", "unknown": "狀態未知",
               "error": "讀取失敗", "ok": "可讀", "success": "可讀", "partial": "部分可讀",
               "denied": "拒讀", "not_requested": "尚未查詢", "not_observed": "尚無觀察",
               "not_applicable": "不適用", "n-a": "不適用", "timeout": "逾時",
               "fresh": "新鮮", "stale": "過期", "pending": "待接手", "retry": "待重試",
               "acked": "已接收", "ack": "已接收", "failed": "投遞失敗", "cancelled": "已取消"}


def state_text(value):
    return STATE_NAMES.get(value, safe_text(value)) if isinstance(value, str) else "未知"


def view_snapshot(document, *, severity="all", delivery="all"):
    """Small pure presentation contract, also testable without a display."""
    value = document if isinstance(document, dict) else {}
    monitoring = value.get("monitoring") is True
    state = value.get("state", "unknown")
    # A durable enabled flag is not proof that collection is running.
    if not monitoring and state in {"running", "running_verified"}:
        state = "enabled_not_running" if value.get("desired_enabled") is True else "unknown"
    counts = value.get("counts") if isinstance(value.get("counts"), dict) else {}
    count = lambda key: str(counts[key]) if type(counts.get(key)) is int and counts[key] >= 0 else "未知"
    saved_sources = value.get("sources", [])
    if isinstance(saved_sources, dict):
        saved_sources = [dict(item, source_id=source) for source, item in saved_sources.items()
                         if isinstance(item, dict)]
    sources = {item["source_id"]: item for item in saved_sources
               if isinstance(item, dict) and isinstance(item.get("source_id"), str)
               and item["source_id"] in SOURCE_NAMES} if isinstance(saved_sources, list) else {}
    rows = []
    for source, title in SOURCE_NAMES.items():
        item = sources.get(source, {})
        fresh = item.get("freshness", {})
        fresh = fresh.get("state") if isinstance(fresh, dict) else fresh
        rows.append((source, (title, state_text(item.get("status", "not_observed")),
                              safe_text(item.get("row_count"), 24), state_text(fresh),
                              safe_text(item.get("observed_at"), 80), safe_text(item.get("reason"), 180))))
    event_view = event_list_view(value, severity=severity, delivery=delivery)
    agent = value.get("agent_delivery") if isinstance(value.get("agent_delivery"), dict) else {}
    enabled = agent.get("enabled") is True
    connection = "已允許接收；尚未證明有 agent 連線或收到事件。" if enabled else "未開放 agent 接收；事件仍保留，可由人類查看。"
    return {"headline": state_text(state), "state": state, "monitoring": monitoring,
            "updated_at": safe_text(value.get("updated_at"), 80),
            "counts": f"待接手 {count('pending')}　已接收 {count('acked')}　投遞失敗 {count('failed')}",
            "sources": rows, **event_view, "agent_enabled": enabled, "agent_status": connection,
            "error": safe_text(value.get("last_error"), 300) if value.get("last_error") else ""}


class ControllerWorker:
    """Serialize local operations without invoking Tk on a worker thread."""
    ACTIONS = frozenset({"snapshot", "start", "pause", "set_agent_delivery", "inspect", "close"})

    def __init__(self, controller):
        self.controller = controller
        self.results = queue.Queue()
        self._requests = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._pending = False
        self._closed = False
        self.thread = threading.Thread(target=self._run, name="EventGuard-UI-operations", daemon=True)
        self.thread.start()

    @property
    def pending(self):
        with self._lock:
            return self._pending

    def submit(self, action, *arguments):
        if action not in self.ACTIONS:
            raise ValueError("unsupported_desktop_action")
        with self._lock:
            if self._closed or self._pending:
                return False
            self._pending = True
            self._requests.put_nowait((action, arguments))
        return True

    def _run(self):
        while True:
            request = self._requests.get()
            if request is None:
                return
            action, arguments = request
            try:
                result = getattr(self.controller, action)(*arguments)
                if not isinstance(result, dict):
                    result = {"state": "error", "reason": "desktop_result_invalid"}
            except Exception as error:
                # Do not store raw exception text: it may contain private paths.
                result = {"state": "error", "reason": "desktop_operation_failed",
                          "error_type": safe_text(type(error).__name__, 80)}
            self.results.put((action, result))
            with self._lock:
                self._pending = False
                if self._closed:
                    return

    def shutdown(self, *, wait=False):
        with self._lock:
            if not self._closed:
                self._closed = True
                # There is at most one in-flight request and none queued behind it.
                try:
                    self._requests.put_nowait(None)
                except queue.Full:
                    pass  # The already queued request will exit after completion.
        if wait:
            self.thread.join(timeout=2)


class EventGuardWindow:
    """A single normal-user application window; X minimizes, Pause is durable."""

    def __init__(self, window, controller, *, refresh_ms=5000):
        import tkinter as tk
        from tkinter import ttk
        if type(refresh_ms) is not int or not 250 <= refresh_ms <= 60000:
            raise ValueError("invalid_desktop_refresh_interval")
        self.window, self.tk, self.ttk = window, tk, ttk
        self.worker = ControllerWorker(controller)
        self.refresh_ms = refresh_ms
        self._closed = False
        self.verified_close = False
        self._busy = False
        self._inspect_after_refresh = None
        self._deferred_request = None
        self._snapshot = {}
        self._event_document = {}
        self._detail_document = None
        self._last_event = None
        self._timers = set()
        self.window.title("EventGuard — 本機唯讀監看")
        self.window.geometry("1080x760")
        self.window.minsize(850, 620)
        self.window.protocol("WM_DELETE_WINDOW", self.minimize)
        self.headline = tk.StringVar(value="正在讀取狀態…")
        self.counts = tk.StringVar(value="待接手 未知　已接收 未知　投遞失敗 未知")
        self.updated = tk.StringVar(value="尚無更新")
        self.message = tk.StringVar(value="按「開始」持續監看；按「暫停」停止採集，事件仍會保留。")
        self.agent_enabled = tk.BooleanVar(value=False)
        self.agent_status = tk.StringVar(value="正在讀取接收設定…")
        self.severity_filter = tk.StringVar(value="所有嚴重度")
        self.delivery_filter = tk.StringVar(value="所有接收狀態")
        self.events_note = tk.StringVar(value="尚未載入事件；不能以此判定主機安全。")
        self.show_raw = tk.BooleanVar(value=False)
        self._build()
        self._request("snapshot")
        self._after(75, self._drain)
        self._after(self.refresh_ms, self._refresh)

    def _build(self):
        tk, ttk = self.tk, self.ttk
        menu = tk.Menu(self.window)
        application = tk.Menu(menu, tearoff=False)
        application.add_command(label="重新整理", command=self.refresh)
        application.add_separator()
        application.add_command(label="暫停並結束", command=self.pause_and_exit)
        menu.add_cascade(label="應用程式", menu=application)
        self.window.configure(menu=menu)
        outer = ttk.Frame(self.window, padding=16)
        outer.grid(sticky="nsew")
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)
        bar = ttk.Frame(outer)
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)
        ttk.Label(bar, textvariable=self.headline, font=("Microsoft JhengHei UI", 20, "bold")).grid(row=0, column=0, sticky="w")
        self.start_button = ttk.Button(bar, text="開始", width=10, command=self.start)
        self.start_button.grid(row=0, column=1, padx=(10, 6))
        self.pause_button = ttk.Button(bar, text="暫停", width=10, command=self.pause)
        self.pause_button.grid(row=0, column=2)
        self.refresh_button = ttk.Button(bar, text="重新整理", width=10, command=self.refresh)
        self.refresh_button.grid(row=0, column=3, padx=(6, 0))
        ttk.Label(outer, textvariable=self.counts).grid(row=1, column=0, sticky="w", pady=(10, 4))
        ttk.Label(outer, textvariable=self.updated, foreground="#53606d").grid(row=2, column=0, sticky="w")
        agent = ttk.Frame(outer)
        agent.grid(row=3, column=0, sticky="ew", pady=(12, 8))
        self.agent_check = ttk.Checkbutton(agent, text="允許 agent 接收事件（不自動呼叫模型）",
                                           variable=self.agent_enabled, command=self.change_agent_delivery)
        self.agent_check.grid(row=0, column=0, sticky="w")
        ttk.Label(agent, textvariable=self.agent_status, foreground="#53606d").grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Label(outer, textvariable=self.message, wraplength=1000).grid(row=4, column=0, sticky="ew", pady=(0, 8))
        notebook = ttk.Notebook(outer)
        notebook.grid(row=5, column=0, sticky="nsew")
        source_frame = ttk.Frame(notebook, padding=8)
        source_frame.columnconfigure(0, weight=1)
        source_frame.rowconfigure(0, weight=1)
        self.sources = ttk.Treeview(source_frame, show="headings", height=8,
                                   columns=("source", "coverage", "count", "freshness", "time", "reason"))
        for key, label, width in (("source", "來源", 130), ("coverage", "可見性", 110), ("count", "筆數", 65),
                                  ("freshness", "新鮮度", 90), ("time", "最後觀察時間", 220), ("reason", "原因", 260)):
            self.sources.heading(key, text=label)
            self.sources.column(key, width=width, minwidth=50, stretch=key in {"time", "reason"})
        self.sources.grid(row=0, column=0, sticky="nsew")
        source_scroll = ttk.Scrollbar(source_frame, orient="vertical", command=self.sources.yview)
        source_scroll.grid(row=0, column=1, sticky="ns")
        self.sources.configure(yscrollcommand=source_scroll.set)
        source_horizontal = ttk.Scrollbar(source_frame, orient="horizontal", command=self.sources.xview)
        source_horizontal.grid(row=1, column=0, sticky="ew")
        self.sources.configure(xscrollcommand=source_horizontal.set)
        ttk.Label(source_frame, text="部分、拒讀、過期或未知都不代表安全。此處只讀取保存觀察，不另行掃描。").grid(row=2, column=0, sticky="w", pady=(8, 0))
        notebook.add(source_frame, text="七個來源")
        event_frame = ttk.Frame(notebook, padding=8)
        event_frame.columnconfigure(0, weight=1)
        event_frame.rowconfigure(1, weight=1)
        event_frame.rowconfigure(2, weight=1)
        filters = ttk.Frame(event_frame)
        filters.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(filters, text="嚴重度").grid(row=0, column=0, sticky="w")
        self.severity_choice = ttk.Combobox(filters, textvariable=self.severity_filter, state="readonly",
                                            values=tuple(SEVERITY_FILTERS), width=14)
        self.severity_choice.grid(row=0, column=1, padx=(6, 12))
        ttk.Label(filters, text="接收狀態").grid(row=0, column=2, sticky="w")
        self.delivery_choice = ttk.Combobox(filters, textvariable=self.delivery_filter, state="readonly",
                                            values=tuple(DELIVERY_FILTERS), width=16)
        self.delivery_choice.grid(row=0, column=3, padx=(6, 12))
        self.clear_filters_button = ttk.Button(filters, text="清除篩選", command=self.clear_filters)
        self.clear_filters_button.grid(row=0, column=4)
        self.severity_choice.bind("<<ComboboxSelected>>", self.filter_events)
        self.delivery_choice.bind("<<ComboboxSelected>>", self.filter_events)
        ttk.Label(filters, textvariable=self.events_note, wraplength=1000).grid(
            row=1, column=0, columnspan=5, sticky="ew", pady=(5, 0))
        self.events = ttk.Treeview(event_frame, show="headings", height=7,
                                  columns=("time", "type", "severity", "delivery", "id"))
        for key, label, width in (("time", "事件時間", 200), ("type", "類型", 230),
                                  ("severity", "嚴重度", 80), ("delivery", "接收狀態", 100), ("id", "事件 ID", 280)):
            self.events.heading(key, text=label)
            self.events.column(key, width=width, minwidth=60, stretch=True)
        self.events.grid(row=1, column=0, sticky="nsew")
        event_scroll = ttk.Scrollbar(event_frame, orient="vertical", command=self.events.yview)
        event_scroll.grid(row=1, column=1, sticky="ns")
        self.events.configure(yscrollcommand=event_scroll.set)
        self.events.bind("<<TreeviewSelect>>", self.select_event)
        detail_frame = ttk.Frame(event_frame)
        detail_frame.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        detail_frame.rowconfigure(1, weight=1)
        detail_frame.columnconfigure(0, weight=1)
        self.raw_check = ttk.Checkbutton(detail_frame, text="展開原始結構化資料（唯讀）",
                                         variable=self.show_raw, command=self.toggle_raw)
        self.raw_check.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.detail = tk.Text(detail_frame, height=10, wrap="word", state="disabled", font=("Microsoft JhengHei UI", 10))
        self.detail.grid(row=1, column=0, sticky="nsew")
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail.yview)
        detail_scroll.grid(row=1, column=1, sticky="ns")
        self.detail.configure(yscrollcommand=detail_scroll.set)
        ttk.Label(event_frame, text="選取事件以唯讀查看。事件內容是不可信資料；查看不會 ACK，ACK 也不代表修復或結案。",
                  wraplength=1000).grid(row=3, column=0, sticky="w", pady=(8, 0))
        notebook.add(event_frame, text="事件與內容")
        ttk.Label(outer, text="關閉視窗只會最小化，監看會繼續。要完全離開，請選「應用程式 → 暫停並結束」。",
                  foreground="#53606d", wraplength=1000).grid(row=6, column=0, sticky="ew", pady=(10, 0))

    def _after(self, delay, callback):
        if self._closed:
            return
        token = None
        def invoke():
            self._timers.discard(token)
            if not self._closed:
                callback()
        token = self.window.after(delay, invoke)
        self._timers.add(token)

    def _set_busy(self, busy):
        self._busy = busy
        for widget in (self.start_button, self.pause_button, self.refresh_button, self.agent_check):
            widget.configure(state="disabled" if busy else "normal")

    def _request(self, action, *arguments):
        if self._closed:
            return False
        accepted = self.worker.submit(action, *arguments)
        if not accepted and action not in {"snapshot", "inspect"} and not self._busy and self._deferred_request is None:
            # A short status read must not eat the user's Start/Pause click.
            self._deferred_request = (action, arguments)
            self._set_busy(True)
            return True
        if accepted and action not in {"snapshot", "inspect"}:
            self._set_busy(True)
        return accepted

    def start(self):
        if self._request("start"):
            self.message.set("正在開始持續監看…")

    def pause(self):
        if self._request("pause"):
            self.message.set("正在保存暫停設定並等待本工具查詢退出…")

    def change_agent_delivery(self):
        if not self._request("set_agent_delivery", bool(self.agent_enabled.get())):
            self.agent_enabled.set(self._snapshot.get("agent_enabled", False))
            self.message.set("另一項操作進行中；接收設定尚未變更，請稍後再試。")
        else:
            self.message.set("正在保存 agent 接收設定；不會啟動模型。")

    def refresh(self):
        self._request("snapshot")

    def _refresh(self):
        if not self._busy:
            self.refresh()
        self._after(self.refresh_ms, self._refresh)

    def select_event(self, _event=None):
        selection = self.events.selection()
        if not selection:
            return
        event_id = selection[0]
        if event_id != self._last_event:
            if self._request("inspect", event_id):
                self._last_event = event_id
            else:
                self._inspect_after_refresh = event_id

    def filter_events(self, _event=None):
        self._render_events(view_snapshot(self._event_document,
            severity=SEVERITY_FILTERS.get(self.severity_filter.get(), "all"),
            delivery=DELIVERY_FILTERS.get(self.delivery_filter.get(), "all")))

    def clear_filters(self):
        self.severity_filter.set("所有嚴重度")
        self.delivery_filter.set("所有接收狀態")
        self.filter_events()

    def toggle_raw(self):
        self._render_detail()

    def minimize(self):
        self.window.iconify()

    def pause_and_exit(self):
        if self._request("close"):
            self.message.set("正在暫停並確認所有本工具子程序已退出…")
        else:
            self.message.set("目前操作進行中；完成後可再選「暫停並結束」。")

    def _show_detail(self, value):
        self._detail_document = value
        self.show_raw.set(False)
        self._render_detail()

    def _render_detail(self):
        value = self._detail_document
        text = event_summary(value) if value is not None else "選取事件以查看保存的觀察事實與唯讀下一步。"
        if value is not None and self.show_raw.get():
            text += "\n\n原始結構化資料（不可信資料，僅供核對）\n" + detail_text(value)
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _apply_snapshot(self, value):
        self._event_document = value if isinstance(value, dict) else {}
        view = view_snapshot(value,
            severity=SEVERITY_FILTERS.get(self.severity_filter.get(), "all"),
            delivery=DELIVERY_FILTERS.get(self.delivery_filter.get(), "all"))
        self._snapshot = view
        self.headline.set(view["headline"])
        self.counts.set(view["counts"])
        self.updated.set("最後更新：" + view["updated_at"])
        self.agent_enabled.set(view["agent_enabled"])
        self.agent_status.set(view["agent_status"])
        for source, row in view["sources"]:
            if self.sources.exists(source):
                self.sources.item(source, values=row)
            else:
                self.sources.insert("", "end", iid=source, values=row)
        self._render_events(view)
        if view["error"]:
            self.message.set("尚未完成：" + view["error"])

    def _render_events(self, view):
        self.events_note.set(view["events_note"])
        present = {event_id for event_id, _ in view["events"]}
        for item in self.events.get_children():
            if item not in present:
                self.events.delete(item)
        for index, (event_id, row) in enumerate(view["events"]):
            if self.events.exists(event_id):
                self.events.item(event_id, values=row)
                self.events.move(event_id, "", index)
            else:
                self.events.insert("", "end", iid=event_id, values=row)
        if self._last_event is not None and self._last_event not in present:
            self._last_event = None
            self._detail_document = None
            self.show_raw.set(False)
            self._render_detail()

    def _drain(self):
        refresh_needed = False
        while True:
            try:
                action, value = self.worker.results.get_nowait()
            except queue.Empty:
                break
            if action == "snapshot":
                if value.get("state") == "error":
                    self.message.set("狀態讀取失敗：" + safe_text(value.get("reason"), 160))
                else:
                    self._apply_snapshot(value)
            elif action == "inspect":
                inspected = value.get("event") if isinstance(value.get("event"), dict) else value
                event_id = inspected.get("event_id")
                # An in-flight read may finish after a filter hides that event.
                # Never put its details under another selected row.
                selected = self.events.selection()
                if (selected and self._last_event == selected[0] and self.events.exists(self._last_event)
                        and event_id in (None, self._last_event)):
                    self._show_detail(value)
            else:
                self._set_busy(False)
                if action == "close" and value.get("can_close") is True:
                    self.verified_close = True
                    self.dispose()
                    self.window.destroy()
                    return
                if action == "close":
                    self.window.deiconify()
                    self.message.set("尚未確認暫停，視窗會保留。原因：" + safe_text(value.get("reason", value.get("state")), 220))
                elif value.get("state") in {"blocked", "error", "startup_failed", "shutdown_unconfirmed", "stop_not_persisted"}:
                    self.message.set("操作尚未完成：" + safe_text(value.get("reason", value.get("state")), 220))
                elif action == "start":
                    self.message.set("已送出開始要求；以下顯示實際監看狀態。")
                elif action == "pause":
                    self.message.set("已保存暫停設定；已保存的事件仍可查看。")
                else:
                    self.message.set("接收設定已保存；事件仍先落本機佇列，不會自動呼叫模型。")
                refresh_needed = True
        if self._deferred_request is not None and not self.worker.pending:
            action, arguments = self._deferred_request
            if self.worker.submit(action, *arguments):
                self._deferred_request = None
        elif refresh_needed:
            self.refresh()
        elif self._inspect_after_refresh is not None and not self.worker.pending:
            event_id, self._inspect_after_refresh = self._inspect_after_refresh, None
            if self.events.exists(event_id) and self._request("inspect", event_id):
                self._last_event = event_id
        self._after(75, self._drain)

    def dispose(self):
        """Stop UI timers after a verified close; never implicitly stop monitoring."""
        if self._closed:
            return
        self._closed = True
        for token in self._timers:
            try:
                self.window.after_cancel(token)
            except self.tk.TclError:
                pass
        self._timers.clear()
        self.worker.shutdown()


def main(argv=None, *, root=None, controller=None):
    """Open the standard-library application, without starting collection itself."""
    import argparse
    parser = argparse.ArgumentParser(description="EventGuard 本機唯讀監看視窗")
    parser.add_argument("--start", action="store_true", help="開啟視窗後明確開始持續監看")
    args = parser.parse_args(argv)
    if root is None:
        root = Path(__file__).resolve().parents[2]
    if controller is None:
        from .desktop import DesktopController
        controller = DesktopController(root)
    try:
        import tkinter as tk
    except ImportError as error:
        return {"state": "blocked", "reason": "desktop_gui_unavailable",
                "error_type": safe_text(type(error).__name__, 80), "model_calls": 0}
    try:
        window = tk.Tk()
    except (tk.TclError, RuntimeError, OSError) as error:
        return {"state": "blocked", "reason": "desktop_gui_unavailable",
                "error_type": safe_text(type(error).__name__, 80), "model_calls": 0}
    app = EventGuardWindow(window, controller)
    if args.start:
        app._after(100, app.start)
    result = {"state": "closed", "model_calls": 0}
    try:
        window.mainloop()
    finally:
        app.dispose()
        # Also cover unexpected mainloop exit.  Only the controller's own Job is
        # eligible for its bounded cleanup; never infer exit from a closed window.
        try:
            receipt = controller.close()
            if not isinstance(receipt, dict) or receipt.get("can_close") is not True:
                result = {"state": "shutdown_unconfirmed", "reason": "desktop_exit_unconfirmed",
                          "can_close": False, "model_calls": 0}
            else:
                result = dict(receipt, model_calls=0)
        except Exception as error:
            result = {"state": "shutdown_unconfirmed", "reason": "desktop_cleanup_failed",
                      "error_type": safe_text(type(error).__name__, 80), "can_close": False, "model_calls": 0}
    return result
