"""Bounded, inert desktop presentation of saved evidence; no system operations.

These views are independently implemented for EventGuard's existing contract.
Filtering only changes the loaded view, never the queue or ACK state.
"""
from __future__ import annotations

import json
import unicodedata
from datetime import datetime, timezone


SEVERITY_FILTERS = {"所有嚴重度": "all", "資訊": "info", "注意": "warning", "高": "high",
                    "嚴重": "critical", "未知嚴重度": "unknown"}
DELIVERY_FILTERS = {"所有接收狀態": "all", "待接手": "pending", "待重試": "retry",
                    "投遞失敗": "failed", "已接收": "ack", "未知接收狀態": "unknown"}
SEVERITY_NAMES = {value: key for key, value in SEVERITY_FILTERS.items() if value != "all"}
DELIVERY_NAMES = {value: key for key, value in DELIVERY_FILTERS.items() if value != "all"}
EVENT_TITLES = {"listener.changed": "本機監聽端點變化", "protection.changed": "防護狀態變化",
                "persistence.changed": "啟動／服務／排程變化", "coverage.degraded": "來源可見性降低",
                "monitor_gap": "監看未觀測區間"}
TRANSITIONS = {"new": "新增觀察", "updated": "更新觀察", "resolved": "已記錄恢復轉換"}
FACT_NAMES = {"protocol": "協定", "port": "連接埠", "pid": "程序 PID",
              "process_created_at": "程序建立時間", "created_at": "建立時間",
              "process_instance_ref": "程序實例 ID", "instance_ref": "實例 ID",
              "binding_scope": "綁定範圍", "scope": "範圍", "address": "位址",
              "source": "來源", "section": "來源區段", "section_id": "來源區段",
              "kind": "種類", "property": "防護欄位", "item": "項目",
              "value": "值", "previous": "先前值", "current": "觀察值",
              "authority": "證據範圍", "state": "保存狀態", "reason": "原因碼",
              "count": "筆數", "changed_count": "變化筆數", "changed_keys": "變化項目 ID",
              "gap_seconds": "未觀測秒數", "name_ref": "名稱 ID", "display_name": "顯示名稱（不可信）"}
UNCERTAINTIES = {
    "saved_event_not_current_state": "保存事件不能證明目前仍是同一狀態。",
    "resolved_event_uses_historical_binding": "恢復轉換使用先前觀察的綁定；目前查詢不能重建歷史。",
    "listener_binding_missing": "事件缺少可供查證的協定／連接埠綁定。",
    "process_binding_missing": "事件缺少同一程序實例的身分，不能只用 PID 判定。",
    "persistence_current_only": "目前清單不能單獨重建歷史變化或判定恢復。",
    "persistence_binding_missing": "事件缺少可唯一識別的啟動／服務／排程來源。",
    "coverage_event_no_automatic_source_rescan": "可見性事件不會額外自動重掃來源。",
    "unobserved_monitor_interval": "未採集期間沒有歷史證據，不能視為沒有事件。",
    "unsupported_event_type": "此事件型別尚無既有唯讀查證路徑。",
    "synthetic_native_query_blocked": "合成事件不會觸發實機查詢。",
    "not_observed_is_not_recovery": "查無結果不能單獨證明恢復。",
    "diagnostic_truncated": "查證結果已截斷，不能視為完整清單。",
}


def safe_text(value, limit=200):
    if value is None:
        return "未知"
    if type(value) is bool:
        return "是" if value else "否"
    if not isinstance(value, (str, int, float)):
        return "未知"
    raw = str(value)
    result = "".join("\\u" + format(ord(char), "04x")
                     if unicodedata.category(char) in {"Cc", "Cf", "Cs"} else char
                     for char in raw[:limit])
    return result + ("…" if len(raw) > limit else "")


def source_success_text(item, *, now=None):
    """Historical success is separate from present coverage and freshness."""
    value = item.get("last_success_at")
    if item.get("last_success_state") != "known" or not isinstance(value, str) or len(value) > 80:
        return "未知／尚無成功紀錄"
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if at.tzinfo is None or at.utcoffset() is None or at > (now or datetime.now(timezone.utc)):
            return "未知／尚無成功紀錄"
        return at.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, TypeError, OverflowError):
        return "未知／尚無成功紀錄"


def source_gap_text(sources):
    """Count saved source gaps; categories may overlap, never infer safety."""
    counts = dict(fresh=0, denied=0, partial=0, failed=0, stale=0, unknown=0, na=0)
    known = {"ok", "success", "denied", "partial", "error", "timeout", "cancelled", "stale", "not_applicable", "n-a"}
    for item in sources:
        status = item.get("status")
        status = status if isinstance(status, str) else "unknown"
        freshness = item.get("freshness")
        fresh = freshness.get("state") if isinstance(freshness, dict) else freshness
        counts["fresh"] += status in {"ok", "success"} and fresh == "fresh"
        counts["denied"] += status == "denied"
        counts["partial"] += status == "partial"
        counts["failed"] += status in {"error", "timeout", "cancelled"}
        counts["stale"] += fresh == "stale" or status == "stale"
        counts["unknown"] += status not in known or fresh not in ("fresh", "stale")
        counts["na"] += status in {"not_applicable", "n-a"}
    return ("來源觀測：可讀且新鮮 {fresh}；拒讀 {denied}；部分可讀 {partial}；讀取失敗 {failed}；"
            "過期 {stale}；未知／尚無觀察 {unknown}；不適用 {na}。分類可重疊，均非安全判定。").format(**counts)


def detail_text(value, limit=60000):
    """Inert JSON disclosure; existing evidence is never rewritten."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    except (ValueError, TypeError, OverflowError, RecursionError):
        return "無法顯示此結構化資料。"
    safe = "".join("\\u" + format(ord(char), "04x")
                   if unicodedata.category(char) in {"Cf", "Cs"} else char
                   for char in encoded[:limit])
    return safe + ("\n（顯示已截斷；原始事件仍保留於本機佇列。）" if len(encoded) > limit else "")


def event_title(event, guidance=None):
    kind = event.get("event_type")
    title = EVENT_TITLES.get(kind, safe_text(kind, 100)) if isinstance(kind, str) else "未知事件型別"
    facts = event.get("facts")
    if not isinstance(facts, dict):
        facts = (guidance or {}).get("binding_facts", {})
    if kind == "persistence.changed" and isinstance(facts, dict) and facts.get("reason") == "initial_inventory":
        title = "首次持久化項目盤點"
    if event.get("transition") == "resolved":
        title += "（已記錄恢復轉換）"
    return title


def _severity(event):
    value = event.get("severity")
    return value if isinstance(value, str) and value in SEVERITY_NAMES else "unknown"


def _delivery(event):
    value = event.get("delivery_status", "pending")
    value = "ack" if value == "acked" else value
    return value if isinstance(value, str) and value in DELIVERY_NAMES else "unknown"


def event_list_view(document, *, severity="all", delivery="all"):
    """Filter only the first 100 loaded rows; disclose all completeness limits."""
    severity = severity if severity in SEVERITY_FILTERS.values() else "all"
    delivery = delivery if delivery in DELIVERY_FILTERS.values() else "all"
    supplied = document.get("events", [])
    supplied = supplied if isinstance(supplied, list) else []
    loaded, events, seen = 0, [], set()
    for item in supplied[:100]:
        if not isinstance(item, dict) or not isinstance(item.get("event_id"), str):
            continue
        event_id = item["event_id"]
        if not 1 <= len(event_id) <= 160 or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in event_id):
            continue
        if event_id in seen:
            continue
        seen.add(event_id)
        loaded += 1
        if severity != "all" and _severity(item) != severity or delivery != "all" and _delivery(item) != delivery:
            continue
        stamp = item.get("observed_at", item.get("occurred_at", item.get("created_at")))
        events.append((event_id, (safe_text(stamp, 80), event_title(item), SEVERITY_NAMES[_severity(item)],
                                  DELIVERY_NAMES[_delivery(item)], safe_text(event_id, 160))))
    total = document.get("events_total")
    total = total if type(total) is int and total >= len(supplied) else None
    truncated = document.get("events_truncated") is True or len(supplied) > 100 or total is not None and total > len(supplied)
    note = f"顯示 {len(events)} / 已載入 {loaded}；儲存總數 {total if total is not None else '未知'}。"
    note += "只篩選目前載入的清單（最多 100 件）；不改動事件。"
    if truncated:
        note += " 清單已截斷，較早事件仍在本機保存。"
    if loaded < min(len(supplied), 100):
        note += " 部分格式無法顯示。"
    if not events:
        note += " 目前未顯示事件不代表沒有事件或主機安全。"
    return {"events": events, "events_note": note, "events_visible": len(events),
            "events_loaded": loaded, "events_total": total, "events_truncated": truncated}


def investigation_timeline(value, case):
    """Keep saved order and per-member uncertainty; never derive new edges."""
    rows = case.get("timeline")
    if not isinstance(rows, list) or len(rows) > 16 or any(not isinstance(row, dict) for row in rows):
        return ["保存時間線格式或上限無法核對，保持未知。"]
    lines = ["保存時間線（最多16項，快照保存順序，非因果鏈）"]
    sources = {"listeners": "監聽端點", "processes": "程序", "defender": "Defender", "startup": "啟動項",
               "services": "服務", "tasks": "排程工作", "versions": "版本", "monitor": "監看", "advisories": "安全公告"}
    missing, changed = value.get("missing_event_ids"), value.get("changed_event_ids")
    identities_known = isinstance(missing, list) and isinstance(changed, list)
    coverage = {"ok": "可讀（非安全判定）", "partial": "部分可讀", "denied": "拒讀", "error": "讀取失敗"}
    for row in rows:
        identity = row.get("event_id")
        state = ("原事件缺失，未知" if identities_known and identity in missing else
                 "事件內容已變更，未知" if identities_known and identity in changed else
                 "與保存雜湊相符" if identities_known and value.get("evidence_status") == "saved_snapshot" else "成員證據未知")
        lines.append(safe_text(row.get("observed_at"), 80) + " | " + safe_text(identity, 160) + " | "
                     + sources.get(safe_text(row.get("source")), "未知來源") + " | " + event_title(row)
                     + " | " + TRANSITIONS.get(safe_text(row.get("transition")), "轉換未知") + " | " + state
                     + " | 保存可見性：" + coverage.get(safe_text(row.get("coverage_status")), "未知"))
    if not rows:
        lines.append("尚無可顯示的保存項目，不代表沒有事件。")
    gaps = case.get("gaps")
    if not isinstance(gaps, list):
        return [*lines, "證據缺口格式未知。"]
    reasons = {"stable_entity_missing": "缺少穩定實體身分", "source_unknown": "來源未知",
               "source_incomplete": "來源資料不完整", "saved_observation_stale": "保存觀測已過期",
               "observation_in_future": "觀測時間在未來", "simultaneous_metadata_conflict": "同時觀測內容衝突",
               "sequence_time_conflict": "序號與時間順序衝突", "candidate_or_member_limit": "候選或成員數達上限"}
    for gap in gaps[:8]:
        reason = gap.get("reason") if isinstance(gap, dict) else None
        lines.append("證據缺口：" + reasons.get(safe_text(reason), "未分類或格式未知，請核對原始資料"))
    if len(gaps) > 8:
        lines.append("僅顯示前8項缺口，完整資料可展開原始結構化檢視。")
    return lines


def investigation_summary(value, event_id):
    """Summarize only the shared catalog's saved case, without constructing one."""
    if value is None:
        return ["尚未保存調查；不代表沒有事件或主機安全。"]
    case = value.get("case") if isinstance(value, dict) else None
    if not isinstance(case, dict) or not isinstance(event_id, str) or case.get("anchor_event_id") != event_id:
        return ["保存調查未知；格式或事件身分無法核對。"]
    evidence = "成員與保存雜湊相符（非來源認證）" if value.get("evidence_status") == "saved_snapshot" else "未知，原事件缺失或內容已變更"
    freshness = {"ok": "保存未過期，非目前主機狀態", "stale": "過期"}.get(safe_text(value.get("snapshot_freshness")), "未知")
    diagnostic = {"matched": "保存診斷相符", "changed": "診斷已變更，保留未知",
                  "missing": "診斷缺失，保留未知", "not_bound": "未綁定診斷"}.get(safe_text(value.get("diagnostic_evidence_status")), "未知")
    state = {"limited": "證據有缺口", "related_metadata_only": "僅保存 metadata 關聯"}.get(safe_text(case.get("status")), "未知")
    timeline, gaps = case.get("timeline"), case.get("gaps")
    count = len(timeline) if isinstance(timeline, list) and len(timeline) <= 16 else "未知"
    gap_count = len(gaps) if isinstance(gaps, list) else "未知"
    return ["調查 ID：" + safe_text(case.get("case_id"), 80),
            "保存時間：" + safe_text(case.get("as_of"), 80), "調查狀態：" + state,
            "成員證據：" + evidence, "診斷證據：" + diagnostic, "快照新鮮度：" + freshness,
            f"保存關聯項目 {count}；證據缺口 {gap_count}。完整資料可展開原始結構化檢視。",
            "關聯不等於因果；未推定程序樹或攻擊鏈，未判定安全／入侵；作業系統帳戶身分仍未知。",
            *investigation_timeline(value, case)]


def revision_summary(value, event_id):
    """Show at most three saved prior cases; absent history stays unknown."""
    if not isinstance(event_id, str) or not isinstance(value, dict) or value.get("state") not in ("available", "not_recorded"):
        return ["前版調查歷程未知，不能推論沒有舊版本。"]
    rows = value.get("revisions")
    if not isinstance(rows, list) or len(rows) > 16 or any(not isinstance(row, dict) for row in rows):
        return ["前版調查格式或上限無法核對，保持未知。"]
    lines = [f"保存前版 {len(rows)}；最多顯示最近3版，依保存讀取順序。更早歷程仍未知。"]
    if not rows:
        lines.append("尚無可驗的保存前版；不補造歷史。")
    for row in rows[:3]:
        case = row.get("case")
        if not isinstance(case, dict) or case.get("anchor_event_id") != event_id:
            lines.append("前版事件身分無法核對，內容不顯示。")
            continue
        stamp = row.get("saved_at")
        try:
            time = datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec="seconds") if type(stamp) in (int, float) and 0 <= stamp <= 253402300799 else "未知"
        except (OverflowError, OSError, ValueError):
            time = "未知"
        member = "保存成員相符" if row.get("evidence_status") == "saved_snapshot" else "成員證據未知"
        diagnostic = {"matched": "保存診斷相符", "changed": "診斷已變更，未知", "missing": "診斷缺失，未知",
                      "not_bound": "未綁定診斷"}.get(safe_text(row.get("diagnostic_evidence_status")), "診斷未知")
        lines.append("前版保存時間：" + time + "；調查 ID：" + safe_text(case.get("case_id"), 80)
                     + "；" + member + "；" + diagnostic + "。歷史相符不代表目前主機安全。")
    if value.get("count_capacity") == "full":
        lines.append("修訂筆數已滿；更新可能被拒絕，不會在此清除前版。")
    return lines


def handling_summary(value):
    """Read-only human handling history, independent of delivery receipts."""
    states = {"new": "新增", "read": "已讀", "handled": "已處理", "ignored": "忽略"}
    label = lambda key: states.get(safe_text(key), "未知")
    lines = ["人工處置狀態：" + label(value.get("status")) + "。這不是投遞 ACK，也不代表已修復。"]
    history = value.get("handling_history")
    if not isinstance(history, dict) or history.get("state") not in ("available", "not_recorded"):
        return [*lines, "處置歷程未知；無法確認不等於沒有操作。"]
    capacity = {"full": "已滿，新變更可能被拒絕", "available": "未達筆數上限，仍需位元組空間"}.get(safe_text(history.get("count_capacity")), "未知")
    lines.append("歷程容量：" + capacity + "。更早歷程仍未知；來源通道不是已驗證操作者。")
    entries = history.get("entries")
    if not isinstance(entries, list) or len(entries) > 256 or any(not isinstance(row, dict) for row in entries):
        return [*lines, "處置歷程格式無法核對，保持未知。"]
    if not entries:
        return [*lines, "尚無可驗的保存歷程；不能推論從未操作。"]
    lines.append(f"顯示最後 {min(len(entries), 8)}／{len(entries)} 筆保存操作；完整資料可展開原始結構化檢視。")
    sources = {"gui": "桌面／網頁", "mcp": "MCP", "cli": "CLI", "startup": "啟動流程", "system": "系統通道", "unknown": "未知通道"}
    for row in entries[-8:]:
        source = sources.get(safe_text(row.get("source")), "未知通道")
        change = "狀態轉換" if row.get("changed") is True else "無狀態變更" if row.get("changed") is False else "變更未知"
        lines.append(safe_text(row.get("at"), 80) + "：" + label(row.get("previous_status")) + " → "
                     + label(row.get("status")) + "；" + change + "；來源通道：" + source)
    return lines


def event_summary(value):
    """Human headings over the existing saved guidance, never a new diagnosis."""
    value = value if isinstance(value, dict) else {}
    event = value.get("event") if isinstance(value.get("event"), dict) else value
    guidance = value.get("guidance") if isinstance(value.get("guidance"), dict) else {}
    lines = [event_title(event, guidance), "事件 ID：" + safe_text(event.get("event_id"), 160),
             "觀察時間：" + safe_text(event.get("observed_at"), 80),
             "嚴重度：" + SEVERITY_NAMES[_severity(event)] + "；接收狀態：" + DELIVERY_NAMES[_delivery(event)],
             "", "觀察事實（保存資料，不是即時掃描）"]
    text = guidance.get("observation", event.get("explanation"))
    lines.append(safe_text(text, 1600) if text else "尚無可用的事件說明；保留未知。")
    facts = guidance.get("binding_facts", event.get("facts"))
    facts = facts if isinstance(facts, dict) else {}
    if event.get("event_type") == "persistence.changed" and facts.get("reason") == "initial_inventory":
        lines.append("這是首次盤點的現有項目，不是新建立或入侵的證據。")
    if event.get("transition") == "resolved":
        lines.append("這是已保存的恢復轉換，不能當作目前狀態或已修復的證明。")
    shown = False
    for key, label in FACT_NAMES.items():
        if key in facts:
            fact = facts[key]
            rendered = detail_text(fact, 300) if isinstance(fact, list) else safe_text(fact, 300)
            lines.append(label + "：" + rendered)
            shown = True
    if not shown:
        lines.append("尚無可顯示的型別化事實。")
    lines.extend(["", "未知與限制", "事件未評估是否構成資安事件；沒有事件也不能證明主機安全。"])
    codes = []
    for candidate in (guidance.get("uncertainties"), value.get("uncertainties")):
        if isinstance(candidate, list):
            codes.extend(code for code in candidate[:16] if isinstance(code, str))
    codes = list(dict.fromkeys(["saved_event_not_current_state", *codes]))[:24]
    for code in codes:
        lines.append("• " + UNCERTAINTIES.get(code, "未確定原因：" + safe_text(code, 120)))
    limits = guidance.get("limitations")
    if isinstance(limits, list):
        lines.extend("• " + safe_text(item, 600) for item in limits[:4] if isinstance(item, str))
    diagnosis = value.get("latest_diagnosis")
    if isinstance(diagnosis, dict):
        lines.append("有另存的查證結果（歷史觀察）時間：" + safe_text(diagnosis.get("observed_at"), 80))
    lines.extend(["", "保存調查（只讀，不建立或更新）",
                  *investigation_summary(value.get("investigation"), event.get("event_id"))])
    lines.extend(["", "保存前版調查（只讀）",
                  *revision_summary(value.get("investigation_revisions"), event.get("event_id"))])
    lines.extend(["", "人工處置與操作歷程（只讀）", *handling_summary(value)])
    lines.extend(["", "建議的唯讀查證（僅文字，不會執行）"])
    steps = guidance.get("next_steps")
    if isinstance(steps, list) and any(isinstance(item, str) for item in steps[:6]):
        lines.extend("• " + safe_text(item, 1000) for item in steps[:6] if isinstance(item, str))
    else:
        lines.append("保留事件與來源可見性，由人類核對；不執行任意命令。")
    lines.extend(["", "查看、篩選與展開資料不會 ACK、不會呼叫模型，也不會自動處置。",
                  "ACK 只代表收到，不代表修復或案件結束。事件與名稱是不可信資料。"])
    return "\n".join(lines)
