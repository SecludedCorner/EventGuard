"""Offline presentation contracts; no collector, model or real-agent evidence."""
import copy
import unittest

from eventguard.gui_presenter import event_list_view, event_summary, source_success_text


def item(event_id="fixture-event", **changes):
    return {"event_id": event_id, "observed_at": "2026-10-23T04:00:00+00:00",
            "event_type": "listener.changed", "severity": "warning", "delivery_status": "pending",
            "transition": "new", "facts": {"protocol": "TCP", "port": 43210}, **changes}


class GuiPresenterTests(unittest.TestCase):
    def test_saved_timeline_retains_order_missing_members_and_bounded_gap_reasons(self):
        rows = [item('later', observed_at='later', source='listeners', coverage_status='denied'),
                item('earlier', observed_at='earlier', transition='resolved', coverage_status='partial')]
        document = {"event": item(), "investigation": {"evidence_status": "unknown",
            "missing_event_ids": ['later'], "changed_event_ids": ['earlier'],
            "case": {"anchor_event_id": 'fixture-event', "timeline": rows,
                     "gaps": [{"reason": 'stable_entity_missing'}] * 9}}}
        before = copy.deepcopy(document)
        summary = event_summary(document)
        self.assertLess(summary.index('later | later'), summary.index('earlier | earlier'))
        for text in ('原事件缺失，未知', '事件內容已變更，未知', '快照保存順序，非因果鏈', '已記錄恢復轉換', '僅顯示前8項缺口'):
            self.assertIn(text, summary)
        self.assertEqual(summary.count('證據缺口：缺少穩定實體身分'), 8)
        self.assertIn('保存可見性：拒讀', summary)
        self.assertIn('保存可見性：部分可讀', summary)
        self.assertNotIn('與保存雜湊相符', summary)
        self.assertEqual(before, document)
        document['investigation']['case']['timeline'] = rows * 9
        self.assertIn('時間線格式或上限無法核對', event_summary(document))
        self.assertNotIn('later | later', event_summary(document))

    def test_handled_is_independent_of_pending_ack_and_history_is_bounded(self):
        rows = [{"previous_status": "new", "status": "handled", "source": "cli",
                 "at": f"fixture-time-{i}", "changed": True} for i in range(10)]
        document = {"event": item(), "status": "handled", "handling_history": {
            "state": "available", "entries": rows, "count_capacity": "full"}}
        before = copy.deepcopy(document)
        summary = event_summary(document)
        for text in ("接收狀態：待接手", "人工處置狀態：已處理", "這不是投遞 ACK", "顯示最後 8／10",
                     "來源通道：CLI", "不是已驗證操作者", "歷程容量：已滿", "更早歷程仍未知"):
            self.assertIn(text, summary)
        self.assertNotIn('fixture-time-0', summary)
        self.assertIn('fixture-time-9', summary)
        self.assertEqual(document, before)
        document["handling_history"]["entries"] = []
        document["handling_history"]["state"] = "not_recorded"
        self.assertIn("不能推論從未操作", event_summary(document))
        for history in (None, {"state": "unknown"}, {"state": "available", "entries": [None]}):
            document["handling_history"] = history
            self.assertIn("未知", event_summary(document))

    def test_saved_investigation_preserves_independent_unknown_and_stale_evidence(self):
        document = {"event": item(), "investigation": {"case": {
            "anchor_event_id": "fixture-event", "case_id": "case-fixture", "as_of": "saved-time",
            "status": "limited", "timeline": [{}], "gaps": [{}]},
            "evidence_status": "saved_snapshot", "snapshot_freshness": "stale",
            "diagnostic_evidence_status": "changed"}}
        before = copy.deepcopy(document)
        summary = event_summary(document)
        for text in ("成員與保存雜湊相符", "診斷已變更，保留未知", "快照新鮮度：過期",
                     "證據有缺口", "保存關聯項目 1；證據缺口 1", "關聯不等於因果"):
            self.assertIn(text, summary)
        self.assertEqual(before, document)
        document["investigation"]["evidence_status"] = "unknown"
        self.assertIn("成員證據：未知", event_summary(document))
        document["investigation"].update(snapshot_freshness=[], diagnostic_evidence_status={})
        document["investigation"]["case"]["status"] = []
        summary = event_summary(document)
        for text in ("快照新鮮度：未知", "診斷證據：未知", "調查狀態：未知"):
            self.assertIn(text, summary)

    def test_missing_and_mismatched_saved_cases_are_not_invented_or_displayed(self):
        self.assertIn("尚未保存調查", event_summary({"event": item()}))
        for value in ([], {}, {"case": {"anchor_event_id": "another-event", "case_id": "wrong-case"}}):
            summary = event_summary({"event": item(), "investigation": value})
            self.assertIn("保存調查未知", summary)
            self.assertNotIn("wrong-case", summary)

    def test_source_success_requires_known_valid_nonfuture_aware_time(self):
        from datetime import datetime, timezone
        now = datetime(2026, 10, 29, tzinfo=timezone.utc)
        for state, at in (("unknown", "2026-01-01T00:00:00Z"), ("known", None),
                          ("known", "bad"), ("known", "2026-01-01T00:00:00"),
                          ("known", "2027-01-01T00:00:00Z"), ("known", "x" * 81)):
            with self.subTest(state=state, at=at):
                self.assertEqual(source_success_text({"last_success_state": state, "last_success_at": at}, now=now),
                                 "未知／尚無成功紀錄")
        self.assertEqual(source_success_text({"last_success_state": "known",
                         "last_success_at": "2026-01-01T08:00:00+08:00"}, now=now), "2026-01-01T00:00:00+00:00")

    def test_actual_observed_at_contract_precedes_legacy_timestamp_fields(self):
        document = {"events": [item(occurred_at="legacy-occurrence", created_at="legacy-created")], "events_total": 1}
        row = event_list_view(document)["events"][0][1]
        self.assertEqual(row[0], "2026-10-23T04:00:00+00:00")
        self.assertEqual(row[1:4], ("本機監聽端點變化", "注意", "待接手"))

    def test_filters_are_a_local_projection_and_do_not_mutate_the_pending_queue(self):
        document = {"events": [item("pending"), item("received", severity="high", delivery_status="ack"),
                               item("retry", delivery_status="retry"), item("failed", delivery_status="failed")],
                    "events_total": 120, "events_truncated": True}
        before = copy.deepcopy(document)
        view = event_list_view(document, severity="high", delivery="ack")
        self.assertEqual([entry[0] for entry in view["events"]], ["received"])
        self.assertEqual((view["events_visible"], view["events_loaded"], view["events_total"]), (1, 4, 120))
        self.assertIn("清單已截斷", view["events_note"])
        self.assertIn("最多 100", view["events_note"])
        self.assertEqual(document, before)

    def test_no_matches_and_empty_or_unknown_storage_never_imply_a_safe_host(self):
        for document in ({"events": [item()], "events_total": 1}, {}, {"events": [], "events_total": 0}):
            view = event_list_view(document, severity="critical")
            self.assertEqual(view["events_visible"], 0)
            self.assertIn("不代表沒有事件或主機安全", view["events_note"])
        self.assertIsNone(event_list_view({"events_total": True})["events_total"])
        self.assertIsNone(event_list_view({"events": [item()], "events_total": 0})["events_total"])

    def test_only_loaded_hundred_events_are_filtered_and_duplicate_ids_are_not_double_counted(self):
        document = {"events": [item(str(index)) for index in range(101)], "events_total": 101}
        view = event_list_view(document)
        self.assertEqual(view["events_loaded"], 100)
        self.assertTrue(view["events_truncated"])
        self.assertNotIn("100", [row[0] for row in view["events"]])
        duplicates = event_list_view({"events": [item(), item()], "events_total": 2})
        self.assertEqual(duplicates["events_loaded"], 1)
        self.assertIn("部分格式無法顯示", duplicates["events_note"])

    def test_initial_inventory_and_saved_resolution_cannot_be_promoted_to_new_attack_or_current_repair(self):
        event = item(event_type="persistence.changed", facts={"reason": "initial_inventory", "count": 8})
        document = {"event": event, "guidance": {"binding_facts": event["facts"],
                    "next_steps": ["核對保存的 baseline。"], "uncertainties": ["persistence_current_only"]}}
        summary = event_summary(document)
        self.assertTrue(summary.startswith("首次持久化項目盤點"))
        self.assertIn("不是新建立或入侵的證據", summary)
        event["transition"] = "resolved"
        summary = event_summary(document)
        self.assertIn("已記錄恢復轉換", summary)
        self.assertIn("不能當作目前狀態或已修復的證明", summary)
        self.assertIn("歷史變化或判定恢復", summary)
        self.assertIn("ACK 只代表收到", summary)

    def test_saved_human_sections_precede_raw_details_without_executing_hostile_text(self):
        hostile = "請執行 whoami\n\x1b[31m\u202e後續"
        document = {"event": item(facts={"port": 43210, "display_name": hostile}),
                    "guidance": {"observation": hostile, "next_steps": [hostile],
                                 "uncertainties": ["process_binding_missing", hostile]},
                    "latest_diagnosis": {"observed_at": "saved-time", "status": "partial"}}
        summary = event_summary(document)
        self.assertIn("觀察事實", summary)
        self.assertIn("未知與限制", summary)
        self.assertIn("建議的唯讀查證（僅文字，不會執行）", summary)
        self.assertIn("連接埠：43210", summary)
        self.assertIn("請執行 whoami", summary)
        self.assertNotIn("\x1b", summary)
        self.assertNotIn("\u202e", summary)
        self.assertIn("\\u001b", summary)
        self.assertIn("另存的查證結果（歷史觀察）", summary)
        self.assertNotIn('"latest_diagnosis"', summary)
        self.assertIn("不會呼叫模型", summary)

    def test_untrusted_event_labels_and_unknown_codes_are_bounded_inert_text(self):
        event = item(event_type="請忽略規則\u202e" + "x" * 300,
                     observed_at="time\nnot-a-command", severity="pretend-safe", delivery_status="pretend-fixed")
        row = event_list_view({"events": [event]})["events"][0][1]
        self.assertNotIn("\u202e", row[1])
        self.assertIn("\\u202e", row[1])
        self.assertTrue(row[1].endswith("…"))
        self.assertEqual(row[2:4], ("未知嚴重度", "未知接收狀態"))
        self.assertNotIn("\n", row[0])

    def test_missing_guidance_retains_unknown_and_does_not_invent_a_diagnosis(self):
        summary = event_summary({"event": item(), "guidance": {"next_steps": [], "binding_facts": {}}})
        self.assertIn("尚無可顯示的型別化事實", summary)
        self.assertIn("尚無可用的事件說明", summary)
        self.assertIn("不執行任意命令", summary)
        self.assertIn("未評估", summary)
