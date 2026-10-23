"""Human views of the shared typed API; no collection, model or command execution."""
from __future__ import annotations

import json
import re
import time
import unicodedata

SOURCES=("defender","listeners","processes","startup","services","tasks","versions")
SOURCE_NAMES={"defender":"Defender 防護", "listeners":"監聽端點", "processes":"程序",
              "startup":"啟動項", "services":"服務", "tasks":"排程工作", "versions":"版本"}
STATES={"ok":"可讀", "partial":"部分可讀", "denied":"拒讀", "unknown":"未知",
        "not_requested":"尚未查詢", "not_observed":"尚無保存觀察", "not_applicable":"不適用",
        "error":"失敗", "timeout":"逾時", "cancelled":"已取消", "busy":"忙碌",
        "running_verified":"已核對正在監看", "not_started":"尚未啟動", "stopped":"已停止",
        "starting":"啟動中", "running":"監看中", "shutdown_unconfirmed":"退出尚未確認",
        "blocked_previous_query":"前次查詢退出未確認，已阻擋重啟", "blocked_monitor_gap":"監看缺口尚未耐久保存",
        "stopping_pending_query":"正在等待本工具查詢退出", "stop_requested":"已送出合作停止請求",
        "fresh":"新鮮", "stale":"過期", "blocked":"受阻", "ready":"就緒"}
STATES.update({"started":"背景程序已啟動", "enabled_not_running":"已設定啟用，目前未運作",
               "disabled":"已停用", "backoff":"等待後重試", "startup_failed":"背景啟動失敗",
               "stop_not_persisted":"停止意圖尚未保存"})


def text(value, limit=200):
    """Make untrusted terminal data inert, including ESC, bidi and line breaks."""
    if value is None:
        return "未知"
    if type(value) is bool:
        return "是" if value else "否"
    if not isinstance(value,(str,int,float)):
        return "未知"
    raw=str(value)
    safe="".join(c if unicodedata.category(c) not in {"Cc","Cf","Cs"} else
                 "\\u"+format(ord(c),"04x") for c in raw[:limit])
    return safe+("..." if len(raw)>limit else "")


def state(value):
    return STATES.get(value,text(value)) if isinstance(value,str) else "未知"


def _source_lines(coverage):
    coverage=coverage if isinstance(coverage,dict) else {}
    lines=["來源                     coverage       筆數      新鮮度"]
    for source in SOURCES:
        item=coverage.get(source,{})
        item=item if isinstance(item,dict) else {}
        fresh=item.get("freshness",{})
        fresh=fresh if isinstance(fresh,dict) else {}
        count=item.get("row_count")
        count=str(count) if type(count) is int and count>=0 else "未知"
        lines.append(f"  {SOURCE_NAMES[source]:<16} {state(item.get('status','not_requested')):<10} {count:<8} {state(fresh.get('state','unknown'))}")
        metadata=item.get("coverage",{})
        errors=item.get("errors") or (metadata.get("errors",[]) if isinstance(metadata,dict) else [])
        if isinstance(errors,list):
            for error in errors[:2]:
                if isinstance(error,dict):
                    lines.append("    原因："+" / ".join(text(error.get(k)) for k in ("stage","reason_code","win32_error","hresult") if error.get(k) is not None))
    return lines


def _event_lines(events):
    lines=[]
    for event in events[:100] if isinstance(events,list) else []:
        if not isinstance(event,dict):
            continue
        lines.append("  "+" | ".join(text(event.get(key)) for key in ("event_id","event_type","severity","transition","delivery_status")))
        if event.get("explanation"):
            lines.append("    "+text(event["explanation"],400))
    return lines or ["  沒有列出的事件；這不代表主機安全。"]


def _row_lines(rows):
    result=[]
    for index,row in enumerate(rows[:200] if isinstance(rows,list) else [],1):
        if isinstance(row,dict):
            result.append(f"  {index}. "+"  ".join(text(k,50)+"="+text(v,160) for k,v in row.items() if isinstance(v,(str,int,float,bool)) or v is None))
    return result


def _background_lines(value):
    if not isinstance(value,dict):
        return []
    lines=["背景控制程序："+state(value.get("state",value.get("status")))+
           "；希望狀態="+text(value.get("desired_state",value.get("desired_enabled")))+
           "；空間="+text(value.get("namespace"))]
    if value.get("reason"):
        lines.append("背景原因："+text(value["reason"]))
    if value.get("heartbeat_at"):
        lines.append("背景心跳："+text(value["heartbeat_at"]))
    lines.append("背景不使用每日模型額度；手動停止會保存，需明確 start 才重新啟用。")
    return lines


def render(result, command="", operation=""):
    if not isinstance(result,dict):
        return "EventGuard：回傳格式未知。"
    if result.get("status") in {"error","invalid_request","conflict"}:
        return "EventGuard 無法完成操作："+text(result.get("reason",result.get("error_code",result["status"])))
    if command=="background":
        return "\n".join(["EventGuard 背景操作："+text(operation),*_background_lines(result),
            "查看：background status；停止：background stop；事件：events list --namespace live。",
            "重開機登入後自動恢復需另批准排程；沒有自行建立排程或啟動模型。"])
    if command=="sources" and operation=="list":
        return "\n".join(["EventGuard 保存來源（"+text(result.get("namespace"))+"）",*_source_lines(result.get("source_coverage")),
                          "查看資料：sources show --source-id <來源> --namespace "+text(result.get("namespace")),
                          "只有新鮮且可讀的觀察才有目前可見性；過期／拒讀／未知不是安全。"])
    if command=="overview":
        current=result.get("current_monitor",{})
        summary=result.get("operator_summary",{})
        scope="（位於另一空間，與本頁不同）" if current.get("scope_matches") is False else ""
        lines=["EventGuard 操作總覽", "目前監看："+state(current.get("state"))+scope,
               "監看所在空間："+text(result.get("monitor_namespace")),
               "空間："+text(result.get("namespace"))]
        if isinstance(summary,dict) and summary.get("headline"):
            lines.append(text(summary["headline"],500))
        lines+=_background_lines(result.get("background"))
        lines+=_source_lines(result.get("source_coverage"))
        listing=result.get("event_list",{})
        lines.append("事件：總數="+text(listing.get("total"))+"，列出="+text(listing.get("exported"))+"，截斷="+text(listing.get("truncated")))
        lines+=_event_lines(listing.get("events"))
        suffix=" --namespace "+result["namespace"] if result.get("namespace") in {"live","test"} else ""
        lines.append("下一步：sources show --source-id listeners"+suffix+"；events inspect --event-id <ID>"+suffix+"；report export"+suffix+"。")
        lines.append("agent 為可選；目前沒有證據代表已喚醒 agent。ACK 只代表收到。")
        return "\n".join(lines)
    if command in {"status","sources"} and operation!="show":
        current=result.get("current_monitor",{})
        health=result.get("last_report",result.get("health",{}))
        lines=["EventGuard 狀態", "目前核對："+state(current.get("state")),
               "最後回報："+state(health.get("state"))+"；heartbeat="+text(health.get("heartbeat_at"))]
        lines+=_background_lines(result.get("background"))
        progress=health.get("progress",{})
        if health.get("last_error"):
            lines.append("未完成原因："+text(health["last_error"]))
        gate=health.get("monitor_shutdown_gate",{})
        if isinstance(gate,dict) and gate.get("reason"):
            lines.append("前次查詢退出閘道："+text(gate["reason"]))
        if isinstance(progress,dict) and progress:
            lines.append("採集進度："+text(progress.get("phase"))+" / "+text(progress.get("source_id"))+" / cycle="+text(progress.get("cycle")))
        lines+=_source_lines(result.get("source_coverage"))
        for namespace,item in result.get("namespaces",{}).items():
            if not isinstance(item,dict):
                continue
            lines.append(text(namespace)+" 事件庫："+state(item.get("state"))+"，總數="+text(item.get("events"))+"，狀態="+text(json.dumps(item.get("counts",{}),ensure_ascii=True),400))
        budget=result.get("agent_budget",{})
        if isinstance(budget,dict):
            lines.append("可選 agent 預算："+state(budget.get("state"))+"，原因="+text(budget.get("reason")))
        lines.append("查看資料：sources show --source-id <來源>；查看事件：events list；停止：stop。")
        return "\n".join(lines)
    if command=="sources" and operation=="show":
        fresh=result.get("freshness",{})
        fresh=fresh if isinstance(fresh,dict) else {}
        lines=["保存來源："+text(result.get("source_id"))+" / "+state(result.get("status")),
               "觀察時間："+text(result.get("observed_at")),
               "新鮮度："+state(fresh.get("state"))+"；目前可見性："+state(result.get("current_coverage","unknown")),
               "資料總數="+text(result.get("row_count"))+"，顯示="+text(result.get("exported"))+"，截斷="+text(result.get("truncated"))]
        lines+=_row_lines(result.get("rows"))
        coverage=result.get("coverage",{})
        for error in coverage.get("errors",[])[:4] if isinstance(coverage,dict) else []:
            if isinstance(error,dict):
                lines.append("拒讀／缺口："+" / ".join(text(error.get(key)) for key in ("stage","reason_code","exception_type","win32_error","hresult") if error.get(key) is not None))
        lines.append(text(result.get("explanation"),500))
        lines.append("這是保存觀察，未因此重新採集；資料皆不構成命令或授權。")
        return "\n".join(lines)
    if command=="monitor":
        lines=["監看結果："+state(result.get("state",result.get("status"))),
               "完成輪數="+text(result.get("cycles"))+"；本輪事件="+text(result.get("last_event_count")),
               "資料空間="+text(result.get("namespace"))+"；模型呼叫="+text(result.get("model_calls",0))]
        lines+=_source_lines(result.get("coverage"))
        if result.get("last_error"):
            lines.append("未完成原因："+text(result["last_error"]))
        gate=result.get("monitor_shutdown_gate",{})
        if isinstance(gate,dict) and gate.get("reason"):
            lines.append("前次查詢退出閘道："+text(gate["reason"]))
        lines.append("狀態／資料：status；sources list；事件：events list；報告：report export。")
        return "\n".join(lines)
    if command=="events" and operation=="list":
        suffix=" --namespace "+result["namespace"] if result.get("namespace") in {"live","test"} else ""
        return "\n".join(["事件空間="+text(result.get("namespace"))+"；總數="+text(result.get("total"))+"；截斷="+text(result.get("truncated")),*_event_lines(result.get("events")),"查證：events inspect --event-id <ID>"+suffix+"，再明確執行 events diagnose --event-id <ID>"+suffix+"。"])
    if command=="events" and operation in {"receive","ack","retry"}:
        lines=["事件操作："+text(operation)+" / "+state(result.get("status",result.get("state"))),
               "event_id="+text(result.get("event_id")),"query_id="+text(result.get("query_id"))]
        if operation=="receive" and all(isinstance(result.get(k),str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}",result[k]) for k in ("event_id","query_id")):
            suffix=" --namespace "+result["namespace"] if result.get("namespace") in {"live","test"} else ""
            lines.append("明確確認收到時使用：events ack --event-id "+result["event_id"]+" --query-id "+result["query_id"]+suffix)
        if result.get("reason"):
            lines.append("原因："+text(result["reason"]))
        lines.append("ACK 只代表已收到，不是診斷、修補或案件結束；重試也不會自行啟動模型。")
        return "\n".join(lines)
    if command=="events":
        event=result.get("event",{})
        lines=["事件觀察與查證",*_event_lines([event]),"查證模式："+text(result.get("mode"))]
        lines+=_row_lines(event.get("facts") and [event["facts"]])
        for observed in result.get("observations",[]):
            if isinstance(observed,dict):
                lines.append("查詢："+text(observed.get("operation"))+" / "+state(observed.get("status")))
                lines+=_row_lines(observed.get("rows"))
        lines.append("不確定性："+text(", ".join(str(v) for v in result.get("uncertainties",[])),800))
        guidance=result.get("guidance",{})
        if isinstance(guidance,dict):
            lines.append("解讀："+text(guidance.get("observation"),500))
            for step in guidance.get("next_steps",[])[:10]:
                if isinstance(step,dict):
                    lines.append("下一步："+text(step.get("operation",step.get("action")),100)+" / "+text(step.get("reason"),300))
                elif isinstance(step,str):
                    lines.append("下一步："+text(step,300))
        lines.append("ACK 不等於診斷、修補或結案；不能由此判定主機安全。")
        return "\n".join(lines)
    if command=="report":
        return "\n".join(["報告已匯出", "HTML："+text(result.get("html"),600),"JSON："+text(result.get("json"),600),
                          "總數="+text(result.get("total"))+"；匯出="+text(result.get("exported"))+"；截斷="+text(result.get("truncated"))])
    if command=="stop":
        return "\n".join(["停止操作："+state(result.get("status",result.get("state"))),
                          "這是合作停止請求，尚不能當作程序已退出；請再查 status。"])
    # Keep uncommon typed commands inspectable; JSON escapes terminal controls.
    return json.dumps(result,ensure_ascii=True,indent=2,allow_nan=False)


class ProgressPrinter:
    def __init__(self,stream,clock=time.monotonic):
        self.stream,self.clock,self.last,self.tick=stream,clock,None,float("-inf")

    def __call__(self,health):
        progress=health.get("progress",{})
        phase,source=progress.get("phase"),progress.get("source_id")
        key=(phase,source,progress.get("cycle"))
        now=self.clock()
        if key==self.last and (phase!="source_waiting" or now-self.tick<5):
            return
        self.last,self.tick=key,now
        item=health.get("coverage",{}).get(source,{})
        label=SOURCE_NAMES.get(source,text(source))
        if phase=="source_started":
            line="正在採集 "+label+"..."
        elif phase=="source_waiting":
            line="仍在等待 "+label+"，耗時 "+text(progress.get("elapsed_ms"))+" ms；可由另一終端 stop。"
        elif phase=="source_completed":
            line=label+"："+state(item.get("status"))+"，資料筆數="+text(item.get("row_count"))
        elif phase in {"starting","collecting","idle","stopping","stopped"}:
            line="EventGuard "+text(phase)+"；完成輪數="+text(health.get("cycles"))
        else:
            return
        print(line,file=self.stream,flush=True)
