"""Bounded, explicit pending-list mode on the existing Tk event components."""
from .gui_pending import page


class PendingView:
    def _init_pending(self):
        self._pending_mode = False
        self._pending_page = self._pending_expected = self._recent_context = None
        self._pending_offset = 0
        self._recent_document = {}

    def _build_pending_controls(self, parent):
        bar = self.ttk.Frame(parent)
        bar.grid(row=1, column=0, columnspan=7, sticky='w', pady=(5, 0))
        self.pending_button = self.ttk.Button(bar, text='查看待確認要求', command=lambda: self.show_pending(0))
        self.pending_previous = self.ttk.Button(bar, text='上一頁', command=lambda: self.show_pending(max(0, self._pending_offset-100)))
        self.pending_next = self.ttk.Button(bar, text='下一頁', command=lambda: self.show_pending(self._pending_offset+100))
        self.pending_back = self.ttk.Button(bar, text='返回最近事件', command=self.return_recent)
        for index, button in enumerate((self.pending_button, self.pending_previous, self.pending_next, self.pending_back)):
            button.grid(row=0, column=index, padx=(0, 8))
        self._update_pending_controls()

    def _update_pending_controls(self):
        if not hasattr(self, 'pending_button'):
            return
        ready = not self._closed and not self._busy and not self.worker.pending
        self.refresh_button.configure(state='disabled' if self._busy or (self._pending_mode and self.worker.pending) else 'normal')
        value = self._pending_page or {}
        enabled = (ready, ready and self._pending_mode and self._pending_offset > 0,
                   ready and self._pending_mode and value.get('has_more') is True, self._pending_mode and not self._closed)
        for button, active in zip((self.pending_button, self.pending_previous, self.pending_next, self.pending_back), enabled):
            button.configure(state='normal' if active else 'disabled')

    def _pending_document(self):
        value = self._pending_page or {}
        return {'events': value.get('events', []), 'events_total': value.get('total'), 'events_limit': 100}

    def show_pending(self, offset=0):
        if self._busy or self.worker.pending or type(offset) is not int or offset not in (0, 100):
            return
        filters = (self.severity_filter, self.delivery_filter, self.handling_filter)
        context = (tuple(v.get() for v in filters), self.events.selection(), self.events.yview()[0])
        if not self._request('pending_requests', offset):
            return
        first = not self._pending_mode
        if first:
            self._recent_context = context
        self._pending_mode, self._pending_offset, self._pending_expected = True, offset, offset
        self._pending_page = None
        self._last_event = None
        self.events.selection_remove(self.events.selection())
        self._show_detail(None)
        self._event_document = self._pending_document()
        if first:
            self.clear_filters()
        else:
            self.filter_events()
        self.message.set('正在唯讀查看待確認要求；不採集、不呼叫模型、不 ACK。')

    def _receive_pending(self, value):
        if not self._pending_mode or self._pending_expected is None:
            return
        self._pending_page = page(value, namespace='live', offset=self._pending_expected)
        self._pending_expected = None
        self._event_document = self._pending_document()
        self.filter_events()
        self.message.set('待確認清單快照已讀取；選事件查看原識別，明確核對才執行。' if self._pending_page is not None else
                         '待確認清單未知；回條或資料無法核對，不能推論沒有要求。可重試或返回最近事件。')

    def _pending_note(self, view):
        if not self._pending_mode:
            return view['events_note']
        if self._pending_expected is not None:
            return '正在讀取待確認清單；尚未取得可驗資料。'
        value = self._pending_page
        if value is None:
            return '待確認清單未知，不能推論沒有要求或主機安全；請重試或返回最近事件。'
        count = len(value['events'])
        bounds = f"{value['offset']+1}–{value['offset']+count}" if count else '本頁無事件'
        return (f"待確認清單快照：{bounds}／{value['total']}件事件，{value['request_total']}個要求；本頁篩選顯示{view['events_visible']}件。"
                '每頁最多100件；完成核對後請刷新，不代表主機安全。')

    def return_recent(self):
        if not self._pending_mode:
            return
        context = self._recent_context
        self._pending_mode = False
        self._pending_page = self._pending_expected = None
        self._last_event = None
        self.events.selection_remove(self.events.selection())
        self._show_detail(None)
        self._event_document = self._recent_document
        if context is not None:
            for variable, value in zip((self.severity_filter, self.delivery_filter, self.handling_filter), context[0]):
                variable.set(value)
        self.filter_events()
        if context and context[1] and self.events.exists(context[1][0]):
            identity = context[1][0]
            self.events.selection_set(identity)
            self.events.focus(identity)
            self.events.yview_moveto(context[2])
            self.select_event()
        self.events.focus_set()
        self._update_pending_controls()
        self.message.set('已返回最近事件，保留原篩選；選取僅在該事件仍可見時恢復。')
