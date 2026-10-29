"""Responsive, local Tk desktop view of the shared EventGuard controller.

No collector, agent runtime or scheduler is implemented in this module.  All
controller calls run on one worker; Tk only renders inert, bounded values.
"""
from __future__ import annotations

from pathlib import Path
import queue
import threading
import uuid

from .gui_presenter import (DELIVERY_FILTERS, SEVERITY_FILTERS, detail_text,
                            event_list_view, event_summary, safe_text, source_success_text, source_gap_text)


SOURCE_NAMES = {"defender": "Defender 防護", "listeners": "監聽端點", "processes": "程序",
                "startup": "啟動項", "services": "服務", "tasks": "排程工作", "versions": "版本"}
HUMAN_STATES = {"new": "新增", "read": "已讀", "handled": "已處理", "ignored": "忽略"}
OPERATION_NAMES = {"capabilities": "查看能力", "status": "查看狀態", "overview": "查看總覽",
    "observation": "查看來源觀察", "stop": "暫停監看", "monitor": "單輪採集", "events": "列出事件",
    "inspect_event": "查看事件", "diagnose_event": "唯讀查證", "receive_event": "接收事件",
    "ack_event": "確認收到", "retry_event": "重試投遞", "report": "匯出報告",
    "background_start": "開始持續監看", "background_status": "查看背景狀態", "background_stop": "暫停監看",
    "gui_start": "開始監看", "gui_pause": "暫停監看", "gui_inspect": "查看事件", "gui_investigate": "保存調查",
    "gui_set_status": "保存人工狀態", "gui_receive_permission": "設定接收開關", "gui_automatic_agent": "設定自動處理"}
ACTIVITY_STATES = {"running": "執行中／待結果", "completed": "已完成", "blocked": "受阻",
                   "failed": "失敗", "interrupted": "中斷，結果未確認"}
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
                              safe_text(item.get("observed_at"), 80), source_success_text(item),
                              safe_text(item.get("reason"), 180))))
    event_view = event_list_view(value, severity=severity, delivery=delivery)
    agent = value.get("agent_delivery") if isinstance(value.get("agent_delivery"), dict) else {}
    enabled = agent.get("enabled") is True
    connection = "已允許接收；尚未證明有 agent 連線或收到事件。" if enabled else "未開放 agent 接收；事件仍保留，可由人類查看。"
    automatic = value.get("automatic_agent") if isinstance(value.get("automatic_agent"), dict) else {}
    auto_enabled = automatic.get("enabled") is True
    auto_state = automatic.get("state", "disabled")
    auto_labels = {"disabled": "自動處理未啟用。", "armed": "已保存自動處理選擇；按開始後待命。",
        "starting": "正在啟動事件待命。", "waiting": "等待事件；無事件不呼叫模型。",
        "running": "專用 agent 正在處理事件。", "waiting_budget": "舊派送狀態需重新核對；事件保留，不自動啟動模型。",
        "waiting_attention": "需要人類處理；事件保留，不自動重試失敗任務。",
        "waiting_task_limit": "本次執行已達任務上限；事件保留，不再啟動新任務。上限只屬於本次執行。",
        "waiting_disabled": "接收權限已關閉；事件仍保留。", "stopped": "事件待命已停止。",
        "blocked": "自動處理受阻。", "shutdown_unconfirmed": "自動處理退出尚未確認。"}
    auto_message = auto_labels.get(auto_state, "自動處理狀態：" + safe_text(auto_state, 80))
    if automatic.get("reason"):
        auto_message += " 原因：" + safe_text(automatic["reason"], 120)
    from .presentation import mcp_lifecycle_text
    auto_message += " " + mcp_lifecycle_text(automatic.get("mcp_lifecycle"))
    auto_message += " 模型任務須有有效的明確授權；使用專用 agent，不接續本聊天。"
    activity = value.get("activity") if isinstance(value.get("activity"), dict) else {}
    activity_rows = []
    entries = activity.get("entries") if isinstance(activity.get("entries"), list) else []
    for row in entries[:100]:
        if not isinstance(row, dict) or not isinstance(row.get("operation"), str) or row["operation"] not in OPERATION_NAMES:
            continue
        activity_rows.append((safe_text(row.get("id"), 40), (
            safe_text(row.get("started_at"), 80),
            {"agent_mcp": "Agent 工具", "human_gui": "人類視窗"}.get(row.get("actor") if isinstance(row.get("actor"), str) else "", "未知入口"),
            OPERATION_NAMES[row["operation"]], ACTIVITY_STATES.get(row.get("state") if isinstance(row.get("state"), str) else "", "未知"),
            safe_text(row.get("elapsed_ms"), 24), safe_text(row.get("reason_code") or row.get("result_code"), 100))))
    active_count = activity.get("active") if type(activity.get("active")) is int else "未知"
    total_count = activity.get("total") if type(activity.get("total")) is int else "未知"
    activity_status = (f"執行中 {active_count}；顯示 {len(activity_rows)}／保存 {total_count} 筆。"
                       if activity.get("state") in {"available", "not_created"} else "操作紀錄目前無法讀取；不能解讀為沒有操作。")
    return {"headline": state_text(state), "state": state, "monitoring": monitoring,
            "updated_at": safe_text(value.get("updated_at"), 80),
            "counts": f"待接手 {count('pending')}　已接收 {count('acked')}　投遞失敗 {count('failed')}",
            "sources": rows, "source_gaps": source_gap_text([sources.get(key, {}) for key in SOURCE_NAMES]),
            **event_view, "agent_enabled": enabled, "agent_status": connection,
            "automatic_enabled": auto_enabled, "automatic_status": auto_message,
            "automatic_executable": safe_text(automatic.get("executable"), 2048) if automatic.get("executable") else "",
            "activity_rows": activity_rows, "activity_status": activity_status,
            "error": safe_text(value.get("last_error"), 300) if value.get("last_error") else ""}


class ControllerWorker:
    """Serialize local operations without invoking Tk on a worker thread."""
    ACTIONS = frozenset({"snapshot", "start", "pause", "set_agent_delivery", "set_automatic_agent", "inspect", "investigate", "set_status", "close"})

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
                from .events.store import CapacityError
                # Do not store raw exception text: it may contain private paths.
                result = {"state": "error", "reason": "desktop_operation_failed",
                          "error_type": safe_text(type(error).__name__, 80)}
                if action == "investigate" and isinstance(error, CapacityError):
                    result["reason"] = "investigation_capacity"
                if action == "set_status" and isinstance(error, CapacityError):
                    result["reason"] = "event_status_capacity"
            if action in {"inspect", "investigate", "set_status"}:
                result = dict(result, requested_event_id=arguments[0])
            if action == "set_status":
                result.update(requested_status=arguments[1], requested_operation_id=arguments[2])
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
        self._pending_status = {}  # Bounded, in-session keys for explicit uncertain retries.
        self._last_event = None
        self._timers = set()
        self.window.title("EventGuard — 本機唯讀監看")
        self.window.geometry("1080x760")
        self.window.minsize(850, 620)
        self.window.protocol("WM_DELETE_WINDOW", self.minimize)
        self.headline = tk.StringVar(value="正在讀取狀態…")
        self.counts = tk.StringVar(value="待接手 未知　已接收 未知　投遞失敗 未知")
        self.updated = tk.StringVar(value="尚無更新")
        self.source_gaps = tk.StringVar(value="正在讀取保存的來源觀察…")
        self.message = tk.StringVar(value="按「開始」持續監看；按「暫停」停止採集，事件仍會保留。")
        self.agent_enabled = tk.BooleanVar(value=False)
        self.agent_status = tk.StringVar(value="正在讀取接收設定…")
        self.automatic_enabled = tk.BooleanVar(value=False)
        self.automatic_status = tk.StringVar(value="自動處理未啟用；不呼叫模型。")
        self.automatic_executable = tk.StringVar(value="")
        self.activity_status = tk.StringVar(value="尚未讀取操作紀錄。")
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
        self.automatic_check = ttk.Checkbutton(agent, text="自動交給專用 agent（會使用模型額度）",
            variable=self.automatic_enabled, command=self.change_automatic_agent)
        self.automatic_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.automatic_path = ttk.Entry(agent, textvariable=self.automatic_executable, width=72)
        self.automatic_path.grid(row=3, column=0, sticky="ew", pady=(3, 0))
        self.automatic_browse = ttk.Button(agent, text="選擇 codex.exe", command=self.choose_codex)
        self.automatic_browse.grid(row=3, column=1, padx=(6, 0))
        ttk.Label(agent, textvariable=self.automatic_status, foreground="#53606d", wraplength=1000).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(3, 0))
        agent.columnconfigure(0, weight=1)
        ttk.Label(outer, textvariable=self.message, wraplength=1000).grid(row=4, column=0, sticky="ew", pady=(0, 8))
        notebook = ttk.Notebook(outer)
        notebook.grid(row=5, column=0, sticky="nsew")
        source_frame = ttk.Frame(notebook, padding=8)
        source_frame.columnconfigure(0, weight=1)
        source_frame.rowconfigure(0, weight=1)
        self.sources = ttk.Treeview(source_frame, show="headings", height=8,
                                   columns=("source", "coverage", "count", "freshness", "time", "success", "reason"))
        for key, label, width in (("source", "來源", 130), ("coverage", "可見性", 110), ("count", "筆數", 65),
                                  ("freshness", "新鮮度", 90), ("time", "最後觀察時間", 220),
                                  ("success", "最後成功時間（歷史）", 220), ("reason", "原因", 260)):
            self.sources.heading(key, text=label)
            self.sources.column(key, width=width, minwidth=50, stretch=key in {"time", "reason"})
        self.sources.grid(row=0, column=0, sticky="nsew")
        source_scroll = ttk.Scrollbar(source_frame, orient="vertical", command=self.sources.yview)
        source_scroll.grid(row=0, column=1, sticky="ns")
        self.sources.configure(yscrollcommand=source_scroll.set)
        source_horizontal = ttk.Scrollbar(source_frame, orient="horizontal", command=self.sources.xview)
        source_horizontal.grid(row=1, column=0, sticky="ew")
        self.sources.configure(xscrollcommand=source_horizontal.set)
        ttk.Label(source_frame, textvariable=self.source_gaps, wraplength=790).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(source_frame, text="部分、拒讀、過期或未知都不代表安全。此處只讀取保存觀察，不另行掃描。").grid(row=3, column=0, sticky="w", pady=(8, 0))
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
        detail_actions = ttk.Frame(detail_frame)
        detail_actions.grid(row=0, column=0, columnspan=2, sticky="ew")
        detail_actions.columnconfigure(0, weight=1)
        self.raw_check = ttk.Checkbutton(detail_actions, text="展開原始結構化資料（唯讀）",
                                         variable=self.show_raw, command=self.toggle_raw)
        self.raw_check.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.investigate_button = ttk.Button(detail_actions, text="建立／更新保存調查", command=self.investigate, state="disabled")
        self.investigate_button.grid(row=0, column=1, sticky="e", padx=(8, 0), pady=(0, 5))
        ttk.Label(detail_frame, text="保存調查只關聯已保存資料；不採集、不呼叫模型、不 ACK。").grid(row=2, column=0, columnspan=2, sticky="w")
        self.detail = tk.Text(detail_frame, height=10, wrap="word", state="disabled", font=("Microsoft JhengHei UI", 10))
        self.detail.grid(row=1, column=0, sticky="nsew")
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail.yview)
        detail_scroll.grid(row=1, column=1, sticky="ns")
        self.detail.configure(yscrollcommand=detail_scroll.set)
        handling_bar = ttk.Frame(detail_frame)
        handling_bar.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.handling_buttons = {}
        for column, (status, label) in enumerate(HUMAN_STATES.items()):
            button = ttk.Button(handling_bar, text=label, state="disabled", command=lambda s=status: self.set_status(s))
            button.grid(row=0, column=column, padx=(0, 6))
            self.handling_buttons[status] = button
        self.handling_status = tk.StringVar(value="人工狀態未知；與 ACK 獨立。")
        ttk.Label(handling_bar, textvariable=self.handling_status).grid(row=1, column=0, columnspan=4, sticky="w")
        ttk.Label(event_frame, text="選取事件以唯讀查看。事件內容是不可信資料；查看不會 ACK，ACK 也不代表修復或結案。",
                  wraplength=1000).grid(row=3, column=0, sticky="w", pady=(8, 0))
        notebook.add(event_frame, text="事件與內容")
        activity_frame = ttk.Frame(notebook, padding=8)
        activity_frame.columnconfigure(0, weight=1)
        activity_frame.rowconfigure(1, weight=1)
        ttk.Label(activity_frame, textvariable=self.activity_status).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.activities = ttk.Treeview(activity_frame, show="headings", height=10,
                                      columns=("time", "actor", "operation", "state", "elapsed", "result"))
        for key, title, width in (("time", "開始時間", 230), ("actor", "操作入口", 100),
                                   ("operation", "操作", 145), ("state", "狀態", 150),
                                   ("elapsed", "耗時 ms", 90), ("result", "結果／原因", 210)):
            self.activities.heading(key, text=title)
            self.activities.column(key, width=width, minwidth=70, stretch=True)
        self.activities.grid(row=1, column=0, sticky="nsew")
        activity_scroll = ttk.Scrollbar(activity_frame, orient="vertical", command=self.activities.yview)
        activity_scroll.grid(row=1, column=1, sticky="ns")
        self.activities.configure(yscrollcommand=activity_scroll.set)
        ttk.Label(activity_frame, text="只記錄經 EventGuard 的操作；不讀聊天思考、提示、完整命令列或其他程式歷史。入口標籤不是身分驗證。",
                  wraplength=1000).grid(row=2, column=0, sticky="w", pady=(8, 0))
        notebook.add(activity_frame, text="操作紀錄")
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
        for widget in (self.start_button, self.pause_button, self.refresh_button, self.agent_check,
                       self.automatic_check, self.automatic_browse, self.automatic_path):
            widget.configure(state="disabled" if busy else "normal")
        self._update_investigate_button()

    def _can_investigate(self):
        value = self._detail_document or {}
        event = value.get("event", value)
        selection = self.events.selection()
        return (not self._busy and not self._closed and bool(selection) and isinstance(event, dict)
                and event.get("event_id") == selection[0] == self._last_event)

    def _update_investigate_button(self):
        self.investigate_button.configure(state="normal" if self._can_investigate() else "disabled")
        value = self._detail_document or {}
        status = value.get("status")
        ready = self._can_investigate() and isinstance(status, str) and status in HUMAN_STATES
        event_id = self._last_event
        for key, button in self.handling_buttons.items():
            enabled = ready and (key != status or (event_id, key) in self._pending_status)
            button.configure(state="normal" if enabled else "disabled")
        self.handling_status.set("人工狀態：" + (HUMAN_STATES[status] if ready else "未知") + "；與 ACK 獨立，不代表修復。")

    def set_status(self, status):
        if not isinstance(status, str) or status not in HUMAN_STATES or not self._can_investigate():
            return
        current = (self._detail_document or {}).get("status")
        if not isinstance(current, str) or current not in HUMAN_STATES:
            return
        key = (self.events.selection()[0], status)
        if (self._detail_document or {}).get("status") == status and key not in self._pending_status:
            return
        if key not in self._pending_status and len(self._pending_status) >= 128:
            self.message.set("未確認要求已達上限，請先核對或重試原要求；不丟棄冪等識別。")
            return
        operation_id = self._pending_status.setdefault(key, uuid.uuid4().hex)
        if self._request("set_status", key[0], status, operation_id):
            self.message.set("正在保存人工狀態；不 ACK、不採集、不呼叫模型。")

    def _refresh_selected_detail(self, event_id):
        if self.events.selection() == (event_id,) and self.events.exists(event_id):
            self._last_event = None
            self.select_event()

    def investigate(self):
        if self._can_investigate() and self._request("investigate", self.events.selection()[0]):
            self.message.set("正在保存調查；只關聯既有保存資料，不採集、不呼叫模型、不 ACK。")

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

    def choose_codex(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.window, title="選擇已安裝的原生 codex.exe",
            filetypes=(("原生 Codex", "codex.exe"), ("執行檔", "*.exe")))
        if path:
            self.automatic_executable.set(path)

    def change_automatic_agent(self):
        enabled = bool(self.automatic_enabled.get())
        if not self._request("set_automatic_agent", enabled, self.automatic_executable.get() or None):
            self.automatic_enabled.set(self._snapshot.get("automatic_enabled", False))
            self.message.set("另一項操作進行中；自動處理設定尚未變更。")
        else:
            self.message.set("正在保存自動處理選擇；模型任務仍須有有效的明確授權。" if enabled
                             else "正在停止自動處理；事件仍保留。")

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
            self._show_detail({"state": "loading"})
            self._last_event = event_id
            self._inspect_after_refresh = None
            if not self._request("inspect", event_id):
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
        self._update_investigate_button()

    def _apply_snapshot(self, value):
        self._event_document = value if isinstance(value, dict) else {}
        view = view_snapshot(value,
            severity=SEVERITY_FILTERS.get(self.severity_filter.get(), "all"),
            delivery=DELIVERY_FILTERS.get(self.delivery_filter.get(), "all"))
        self._snapshot = view
        self.headline.set(view["headline"])
        self.counts.set(view["counts"])
        self.updated.set("最後更新：" + view["updated_at"])
        self.source_gaps.set(view["source_gaps"])
        self.agent_enabled.set(view["agent_enabled"])
        self.agent_status.set(view["agent_status"])
        self.automatic_enabled.set(view["automatic_enabled"])
        self.automatic_status.set(view["automatic_status"])
        self.activity_status.set(view["activity_status"])
        for item in self.activities.get_children():
            self.activities.delete(item)
        for row_id, row in view["activity_rows"]:
            if row_id and not self.activities.exists(row_id):
                self.activities.insert("", "end", iid=row_id, values=row)
        if not self.automatic_executable.get():
            self.automatic_executable.set(view["automatic_executable"])
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
        self._update_investigate_button()

    def _drain(self):
        refresh_needed = False
        while True:
            try:
                action, value = self.worker.results.get_nowait()
            except queue.Empty:
                break
            if action == "snapshot":
                if value.get("state") == "error":
                    self._apply_snapshot({})
                    self.agent_status.set("接收設定目前未知；讀取失敗不代表已撤銷接收權限。")
                    self.automatic_status.set("自動處理狀態目前未知；未確認是否執行或停止。")
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
                        and value.get("requested_event_id") == self._last_event):
                    if value.get("state") == "error" or event_id != self._last_event:
                        self._show_detail({"state": "error"})
                        self._last_event = None  # Permit retrying the same selected row.
                    else:
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
                elif action == "investigate":
                    event_id = value.get("requested_event_id")
                    confirmed = value.get("state") == "investigation_saved" and value.get("event_id") == event_id
                    self.message.set("已保存調查（事件：" + safe_text(event_id, 160) + "）；不代表已 ACK、修復或主機安全。" if confirmed else
                        "調查保存空間或版本容量不足，原調查與事件保留。" if value.get("reason") == "investigation_capacity" else
                        "保存結果未確認；請查看保存資料，不自動重試。")
                    self._refresh_selected_detail(event_id)
                elif action == "set_status":
                    event_id, status = value.get("requested_event_id"), value.get("requested_status")
                    key = (event_id, status)
                    correlated = self._pending_status.get(key) == value.get("requested_operation_id")
                    confirmed = (correlated and value.get("state") == "event_status_updated" and value.get("event_id") == event_id
                                 and isinstance(value.get("status"), str) and value["status"] in HUMAN_STATES and value.get("ack_performed") is False)
                    if confirmed:
                        self._pending_status.pop(key, None)
                        self.message.set("人工狀態已核對（事件：" + safe_text(event_id, 160) + "）：" + HUMAN_STATES[value["status"]] + "；不是 ACK 或修復。")
                    elif value.get("reason") == "event_status_capacity" or value.get("operation_started") is False:
                        if correlated:
                            self._pending_status.pop(key, None)
                        self.message.set("人工狀態未保存，容量或活動紀錄受阻；原資料與 pending 保留。")
                    else:
                        self.message.set("人工狀態結果未確認；重新點選原狀態會沿用同一識別，不自動重送。")
                    self._refresh_selected_detail(event_id)
                elif value.get("state") in {"blocked", "error", "startup_failed", "shutdown_unconfirmed", "stop_not_persisted"}:
                    self.message.set("操作尚未完成：" + safe_text(value.get("reason", value.get("state")), 220))
                elif action == "start":
                    self.message.set("已送出開始要求；以下顯示實際監看狀態。")
                elif action == "pause":
                    self.message.set("已保存暫停設定；已保存的事件仍可查看。")
                elif action == "set_automatic_agent":
                    self.message.set("自動處理選擇已保存；有事件才啟動專用 agent，無事件由程式等待。")
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
            if (self.events.exists(event_id) and self.events.selection() == (event_id,)
                    and self._request("inspect", event_id)):
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
