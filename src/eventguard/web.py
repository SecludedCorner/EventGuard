"""Loopback-only product views. No remote assets, shell, models or OS queries."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hmac
import re
import secrets
import threading
from urllib.parse import parse_qs, unquote, urlsplit


HTML = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="csrf" content="__TOKEN__"><title>EventGuard 本機資安監看</title><link rel="stylesheet" href="/app.css"></head>
<body><header><div><h1>EventGuard</h1><p>本機採集。規則比對。事件保存。正常採集不呼叫模型。</p></div><span id="run-state" class="state-badge tone-red" role="status" aria-live="polite">? 狀態尚未確認</span></header>
<main><p id="scope-notice">__SCOPE_NOTICE__</p><p id="error" role="alert" hidden></p><p id="notice" role="status" hidden></p>
<section id="monitor-control" data-tone="red" aria-labelledby="monitor-heading"><h2 id="monitor-heading">本機資安監看</h2><p>停止採集後，網頁與 MCP 仍可使用。關閉程式才會關閉本機介面。這些操作不會啟動 agent。</p>
<p id="monitor-summary" role="status">正在取得後端狀態。控制暫不可用。</p><div id="monitor-buttons"><button id="monitor-start" disabled>開始採集</button><button id="monitor-pause" disabled>暫停採集</button><button id="monitor-resume" disabled>恢復採集</button><button id="monitor-stop" disabled>停止採集</button></div>
<p id="monitor-last-action">最近動作：尚無紀錄。</p><p id="monitor-revision" class="reason">狀態版本尚未確認。</p><p id="monitor-result" role="status">尚未送出操作。</p><div id="shutdown-controls"><button id="monitor-shutdown" class="danger" disabled>關閉程式</button><span>提出關閉要求不代表已退出。回條與連線狀態會分開顯示。</span></div></section>
<nav aria-label="頁面"><button data-tab="events" aria-pressed="true">事件</button><button data-tab="sources">來源狀態</button><button data-tab="advisories">資安公告</button><button data-tab="rules">規則</button><button data-tab="agent">Agent 派送</button></nav>
<section id="events"><h2>事件</h2><p id="source-gap-summary" role="status">來源狀態尚未確認。這不代表主機安全。</p><p id="filter-url-error" role="alert" hidden>網址篩選無效。請重新選擇篩選條件。</p><form id="filters">
<label>嚴重度<select name="severity"><option value="">全部</option><option value="critical">嚴重</option><option value="high">高</option><option value="warning">警告</option><option value="info">資訊</option></select></label>
<label>來源<select name="source"><option value="">全部</option><option value="defender">Defender</option><option value="listeners">監聽端點</option><option value="processes">程序</option><option value="startup">啟動項</option><option value="services">服務</option><option value="tasks">排程工作</option><option value="versions">版本</option><option value="monitor">監看程式</option><option value="advisories">資安公告</option><option value="unknown">未知</option></select></label>
<label>處置狀態<select name="status"><option value="">全部</option><option value="new">新增</option><option value="read">已讀</option><option value="handled">已處理</option><option value="ignored">忽略</option></select></label><button type="submit">篩選</button></form>
<p id="count"></p><div class="table-wrap"><table><thead><tr><th>嚴重度</th><th>事件</th><th>來源</th><th>時間</th><th>處置狀態</th><th>詳情</th></tr></thead><tbody id="event-rows"></tbody></table></div>
<p><button id="prev">上一頁</button> <button id="next">下一頁</button></p>
<article id="detail" hidden><h2>事件詳情</h2><button id="return-to-list" type="button">返回事件清單</button><p id="detail-summary"></p><p id="detail-id"></p><p>處置狀態只記錄人的決定。它不會 ACK，也不會修改系統。</p>
<div id="status-buttons"><button data-status="new">新增</button><button data-status="read">已讀</button><button data-status="handled">已處理</button><button data-status="ignored">忽略</button></div><h3>處置歷程</h3><div id="handling-history"></div>
<h3>觀察與建議</h3><div id="guidance"></div><h3>事件調查</h3><p>僅關聯已保存 metadata；不查主機、不啟動模型、不 ACK。時間接近不代表因果或攻擊鏈。</p><button id="investigate">建立／更新保存的調查</button><div id="investigation-view"></div><h3>投遞證據</h3><p>落盤、收件、結果與 ACK 分開記錄。缺少證據顯示未知。CLI 啟動只代表程序啟動；實際收件、回合與退出另行核對。</p><pre id="delivery-json"></pre><details><summary>結構化資料</summary><pre id="detail-json"></pre></details></article></section>
<section id="sources" hidden><h2>七個來源</h2><p>只顯示已保存的採集結果。未知、拒讀或過期都不代表安全。</p><div id="source-cards"></div></section>
<section id="advisories" hidden><h2>資安公告與本機適用性</h2><p>只讀取已保存資料。公告文字是不可信資料。未知、過期與不適用都不代表主機安全。此頁不抓網站、不啟動模型。</p><p id="advisory-summary"></p><div id="advisory-cards"></div><h3>公告來源狀態</h3><div id="advisory-source-cards"></div></section>
<section id="rules" hidden><h2>規則</h2><p>編輯專案的 config/rules.json。下一輪採集會讀取。規則不執行命令。</p><div id="rule-cards"></div></section>
<section id="agent" hidden><h2>Agent 派送</h2><p>這是選配的短期專用任務。無事件由普通程式等待。此頁不會啟動模型。ACK 不是風險結案。</p><p id="agent-summary"></p><button id="agent-pause">暫停新派送</button> <button id="agent-stop">停止派送程序</button><p>恢復需在終端明確執行 agent resume --execute。採集及原事件不受這兩個按鈕影響。</p><pre id="agent-json"></pre></section>
<footer>僅供本機使用。高嚴重度事件會顯示本頁提示。系統通知狀態：<span id="notification-state">未知</span>。<br>關閉瀏覽器頁籤不會停止程式。停止採集保留網頁與 MCP。請用「關閉程式」結束應用，或回到執行終端按 Ctrl+C。Agent 派送有獨立控制。</footer></main><script src="/app.js" defer></script></body></html>"""

CSS = """:root{color-scheme:light;font:16px system-ui,'Microsoft JhengHei',sans-serif;color:#183044;background:#f1f5f7}*{box-sizing:border-box}body{margin:0}header{background:#153d50;color:white;padding:24px max(24px,calc((100vw - 1180px)/2));display:flex;justify-content:space-between;gap:24px;align-items:center}h1{margin:0;font-size:29px}header p{margin-bottom:0;color:#d5e6ed}main{max-width:1180px;margin:auto;padding:24px}nav,form,#status-buttons,#monitor-buttons,#shutdown-controls{display:flex;gap:12px;flex-wrap:wrap;align-items:center}button,select{font:inherit;padding:9px 12px;border:1px solid #9badb9;border-radius:6px;background:white;color:#183044}button{cursor:pointer}button:hover,button[aria-pressed=true]{background:#d9eaf0}button:disabled{opacity:.45;cursor:default}.danger{border-color:#a12822;color:#8d241f}#shutdown-controls{border-top:1px solid #dce4e9;margin-top:18px;padding-top:16px}#shutdown-controls span{font-size:14px;color:#566d7c}.state-badge{display:inline-flex;align-items:center;gap:8px;padding:10px 14px;border-radius:8px;font-weight:700;white-space:normal;max-width:380px}.tone-green{background:#d1fae5;color:#065f46}.tone-amber{background:#fef3c7;color:#92400e}.tone-gray{background:#e5e7eb;color:#374151}.tone-blue{background:#dbeafe;color:#1e40af}.tone-red{background:#fee2e2;color:#991b1b}#monitor-control{border-left:6px solid #b91c1c}#monitor-control[data-tone=green]{border-left-color:#047857}#monitor-control[data-tone=amber]{border-left-color:#b45309}#monitor-control[data-tone=gray]{border-left-color:#6b7280}#monitor-control[data-tone=blue]{border-left-color:#2563eb}.result-unknown{color:#991b1b}label{display:grid;gap:5px}section,article{background:white;border:1px solid #dce4e9;border-radius:10px;margin-top:20px;padding:22px}article{background:#f7fafb}h2{margin-top:0}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;border-bottom:1px solid #e3e9ed;padding:12px 9px;vertical-align:top}th{white-space:nowrap;color:#506472}td:first-child{font-weight:700}.high,.critical{color:#a12822}.warning{color:#855c04}.source-card,.rule-card{padding:16px 0;border-bottom:1px solid #dce4e9}.source-card h3,.rule-card h3{margin:0 0 10px}.reason{font:13px ui-monospace,monospace;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px ui-monospace,monospace}#notice{padding:15px;border-left:5px solid #a12822;background:#fff0eb}#error{padding:15px;background:#ffe3df;color:#7b1e19}footer{font-size:13px;line-height:1.8;color:#566d7c;margin-top:24px}[hidden]{display:none!important}@media(max-width:650px){header{display:block}.state-badge{margin-top:18px}main{padding:12px}section{padding:14px}form label{flex:1;min-width:130px}}"""

JS = """'use strict';
const $=id=>document.getElementById(id), severity={critical:'嚴重',high:'高',warning:'警告',info:'資訊'}, handling={new:'新增',read:'已讀',handled:'已處理',ignored:'忽略'};
const sourceNames={defender:'Defender',listeners:'監聽端點',processes:'程序',startup:'啟動項',services:'服務',tasks:'排程工作',versions:'版本',monitor:'監看程式',advisories:'資安公告',unknown:'未知'};
const states={ok:'成功',partial:'部分成功',denied:'拒讀',unknown:'未知',not_applicable:'不適用',not_requested:'尚未採集',not_observed:'尚未採集',not_collected:'尚未採集',stale:'資料過期',error:'失敗',timeout:'逾時',cancelled:'已取消',busy:'忙碌',started:'監看中',running:'監看中',paused:'已暫停',pausing:'正在暫停',resuming:'正在恢復採集',stopping:'正在停止採集',closing:'正在關閉',stopped:'採集已停止',blocked:'受阻',blocked_rules:'規則檔錯誤',backoff:'等待重試',shutdown_unconfirmed:'退出未確認',enabled_not_running:'目前未採集',disabled:'已停用'};
const eventNames={'listener.changed':'監聽端點變化','protection.changed':'防護狀態變化','persistence.changed':'啟動與服務變化','coverage.degraded':'來源可見性降低','monitor_gap':'監看缺口','advisory.changed':'資安公告與適用性變化'};
const APP_STATE_PRESENTATION = {"running":{"tone":"green","icon":"●","label":"監看中（後端已確認）"},"paused":{"tone":"amber","icon":"Ⅱ","label":"採集已暫停"},"stopped":{"tone":"gray","icon":"■","label":"採集已停止，應用仍開啟"},"processing":{"tone":"blue","icon":"↻","label":"操作處理中，等待後端確認"},"closing":{"tone":"blue","icon":"↻","label":"關閉要求處理中，退出尚未確認"},"blocked":{"tone":"red","icon":"!","label":"監看受阻"},"unknown":{"tone":"red","icon":"?","label":"目前狀態未確認"},"failed":{"tone":"red","icon":"!","label":"最近操作失敗，請查看結果"},"offline":{"tone":"red","icon":"!","label":"連線中斷，目前狀態未確認"},"stale":{"tone":"red","icon":"!","label":"狀態回覆過期，目前狀態未確認"},"invalid":{"tone":"red","icon":"?","label":"狀態資料不完整，控制暫不可用"},"reloading":{"tone":"blue","icon":"↻","label":"程式實例已變更，正在重新連線"}};
const MONITOR_ACTIONS=['start','pause','resume','stop','shutdown'], CAPABILITY_FIELDS=['available','paused','stopped','can_start','can_pause','can_resume','can_stop','can_shutdown'];
const actionLabels={start:'開始採集',pause:'暫停採集',resume:'恢復採集',stop:'停止採集',shutdown:'關閉程式',set_event_status:'變更事件處置狀態'}, sourceLabels={cli:'CLI',gui:'GUI',mcp:'MCP',startup:'啟動流程',system:'系統'}, actionStates={processing:'處理中',succeeded:'成功',busy:'忙碌，要求未執行',failed:'失敗',unknown:'未確認',running:'採集運作中',paused:'採集已暫停',stopped:'採集已停止',event_status_updated:'事件處置已保存',shutdown_requested:'關閉要求已接受，退出待確認',shutdown_unconfirmed:'退出未確認',blocked:'操作受阻',conflict:'操作識別衝突'};
const STATUS_TIMEOUT_MS=4000, CONTROL_TIMEOUT_MS=30000, STATUS_POLL_MS=1000, STATUS_STALE_MS=5000;
let offset=0, selected=null, tab='events', busy=false, refreshQueued=false, sourceGapSequence=0, eventSequence=0, filterUrlValid=true, controlFlight=null, statusFlight=null, clientSeq=0, statusTimer=null, detailSequence=0, deliverySequence=0;
let currentStatus=null, instanceId=null, stateRevision=-1, lastAppliedSeq=-1, lastPollSuccessAt=0, connectionHealthy=false, reloadPending=false;
function node(tag,text,cls){const e=document.createElement(tag);e.textContent=text??'';if(cls)e.className=cls;return e;}
function when(s){if(!s)return '尚無紀錄';const d=new Date(s);return Number.isNaN(+d)?'時間未知':d.toLocaleString('zh-TW',{hour12:false});}
function sourceSuccess(s){
  if(s.last_success_state!=='known'||typeof s.last_success_at!=='string')return '未知／尚無成功紀錄';
  const time=Date.parse(s.last_success_at);
  return Number.isFinite(time)&&time<=Date.now()?when(s.last_success_at):'未知／尚無成功紀錄';
}
function sourceFreshness(s){const labels={fresh:'新鮮',stale:'已過期',unknown:'未知'};return Object.prototype.hasOwnProperty.call(labels,s.freshness)?labels[s.freshness]:'未知';}
function renderHandlingHistory(value){
  const target=$('handling-history');target.replaceChildren();
  if(!value||!['available','not_recorded'].includes(value.state)||!Array.isArray(value.entries)){target.append(node('p','處置歷程無法確認。此前狀態變化未知。','result-unknown'));return;}
  target.append(node('p','此前狀態變化未記錄或未知。來源僅表示操作通道，並非已驗證操作者；處置不等於 ACK。'));
  if(!value.entries.length)target.append(node('p','尚無可顯示的處置紀錄。'));
  const list=node('ol');for(const item of value.entries){const transition=(handling[item.previous_status]||'未知')+' → '+(handling[item.status]||'未知');list.append(node('li',when(item.at)+' / '+transition+(item.changed?'':'（無變更）')+' / 來源：'+(sourceLabels[item.source]||'未知')));}target.append(list);
  target.append(node('p',value.count_capacity==='full'?'紀錄數量已達上限；新處置會被拒絕。':value.count_capacity==='available'?'紀錄數量未達上限；實際儲存空間仍可能不足。':'紀錄數量容量未知。'));
}
function renderInvestigation(value){
  const target=$('investigation-view');target.replaceChildren();if(!value){target.append(node('p','尚未建立調查。查看事件不會自動保存。'));return;}
  const c=value.case,correlation=c.correlation||{};
  const evidence=value.evidence_status==='saved_snapshot'?'成員與保存雜湊相符':'未知，原事件缺失或已變更';
  const freshness={ok:'未判過期',stale:'已過期',unknown:'未知'};
  target.append(node('h4','保存的調查快照'),node('p','案件 '+c.case_id+'。錨定事件：'+c.anchor_event_id+'。保存時間：'+when(c.as_of)+'。'),
    node('p','證據狀態：'+evidence+'。快照新鮮度：'+(freshness[value.snapshot_freshness]||'未知')+'。'+(c.status==='limited'?'證據有缺口。':c.status==='related_metadata_only'?'僅確認 metadata 關聯。':'調查狀態未知。')),
    node('p','保存成員：'+c.timeline.length+'。檢視候選：'+correlation.examined+'。缺口：'+c.gaps.length+'。截斷：'+(correlation.truncated===true?'是':correlation.truncated===false?'否':'未知')+'。主機安全與入侵狀態未判定。'));
  target.append(node('p','關聯依據：同主機範圍、同來源、穩定程序實例或持久項目；時間範圍前後15分鐘。'));
  const labels={stable_entity_missing:'缺少穩定實體綁定，不能關聯',source_unknown:'來源未知',source_incomplete:'來源觀測不完整',saved_observation_stale:'保存觀測已過期',observation_in_future:'觀測時間在未來',simultaneous_metadata_conflict:'同時間／序號 metadata 矛盾',sequence_time_conflict:'序號與時間順序矛盾',candidate_or_member_limit:'候選或案件事件達上限，關聯不完整',diagnostic_not_saved:'沒有保存診斷',diagnostic_incomplete:'診斷資料不完整',diagnostic_result_missing:'缺少診斷結果',diagnostic_stale:'保存診斷已過期',diagnostic_in_future:'診斷時間在未來'};
  const list=node('ol');for(const item of c.timeline){
    const li=node('li');li.dataset.eventId=item.event_id;
    const basis=item.event_id===c.anchor_event_id?'錨定事件':correlation.basis==='same_host_source_stable_entity'?'同主機範圍、同來源、相同穩定身分；僅 metadata 關聯':'關聯依據未知';
    li.append(node('p',when(item.observed_at)+' / '+item.event_id+' / '+(eventNames[item.event_type]||item.event_type)+' / '+item.transition+' / '+(states[item.coverage_status]||item.coverage_status)),node('p','關聯依據：'+basis+'。'));
    for(const gap of c.gaps.filter(entry=>entry.event_id===item.event_id))li.append(node('p','此觀測缺口：'+(labels[gap.reason]||gap.reason),'result-unknown'));
    if(value.missing_event_ids.includes(item.event_id))li.append(node('p','原事件缺失，證據未知。','result-unknown'));
    if(value.changed_event_ids.includes(item.event_id))li.append(node('p','原事件內容已變，證據未知。','result-unknown'));
    li.append(node('pre',JSON.stringify(item.facts,null,2)));list.append(li);
  }target.append(node('h4','已保存觀測時間線'),list);
  const gaps=node('ul');for(const gap of c.gaps)gaps.append(node('li',(labels[gap.reason]||gap.reason)+'：'+gap.event_id));target.append(node('h4','缺失／過期／矛盾證據'),gaps);if(!c.gaps.length)target.append(node('p','此快照未發現上述 metadata 缺口；不代表主機安全。'));
  if(value.evidence_status==='unknown')target.append(node('p','原事件缺失或內容已變，證據目前為 UNKNOWN：'+[...value.missing_event_ids,...value.changed_event_ids].join(', '),'result-unknown'));
  const diagnosticLabels={missing:'沒有已保存診斷',matched:'保存hash相符',changed:'診斷已變，原快照不改寫',not_bound:'舊案件未綁定診斷'};
  if(c.diagnostic_context){const d=c.diagnostic_context;target.append(node('h4','已保存的查證依據'),node('p',(diagnosticLabels[value.diagnostic_evidence_status]||'未知')+'。觀測時間：'+when(d.observed_at)+'。'+(d.review_hash?'hash '+d.review_hash:'缺少診斷結果。')));for(const observation of d.observations)target.append(node('p',observation.operation+' / '+(sourceNames[observation.source]||observation.source)+' / '+(states[observation.status]||observation.status)+' / 保存列數 '+observation.row_count+' / '+when(observation.observed_at)));target.append(node('p','這裡只讀既有診斷摘要，沒有重新查詢。之後的觀測不能證明過去已恢復。'));}
  target.append(node('p','作業系統帳戶 owner：UNKNOWN（未保存）；沒有推定跨帳戶因果。'));
  target.append(node('p','下一步：人工檢閱保存事實；需要新觀測時先取得該來源的採集批准。允許處置清單為空；此頁不執行隔離、終止或修復。'));
}
function isStatusSnapshot(value){
  if(!value||typeof value!=='object'||Array.isArray(value)||typeof value.instance_id!=='string'||!/^[A-Za-z0-9_.:-]{1,160}$/.test(value.instance_id)||!Number.isSafeInteger(value.state_revision)||value.state_revision<0||!['running','paused','stopped','blocked','unknown','closing'].includes(value.monitor_state))return false;
  const c=value.monitor_controls;
  if(!c||typeof c!=='object'||Array.isArray(c)||!CAPABILITY_FIELDS.every(key=>typeof c[key]==='boolean')||!(c.transition===null||(typeof c.transition==='string'&&c.transition.length>0&&c.transition.length<=64)))return false;
  if(!Object.prototype.hasOwnProperty.call(value,'last_action'))return false;
  const a=value.last_action;
  return a===null||(a&&typeof a==='object'&&!Array.isArray(a)&&typeof a.action==='string'&&a.action.length<=128&&Object.prototype.hasOwnProperty.call(sourceLabels,a.source)&&Object.prototype.hasOwnProperty.call(actionStates,a.state)&&typeof a.result_code==='string'&&a.result_code.length<=160&&typeof a.operation_id==='string'&&a.operation_id.length<=128&&typeof a.at==='string'&&a.at.length<=80&&Number.isSafeInteger(a.revision)&&a.revision>=0&&a.revision<=value.state_revision);
}
function acceptStatusDecision(current,value,sequence,expectedInstance=null){
  if(!isStatusSnapshot(value)||!Number.isSafeInteger(sequence)||sequence<0)return 'invalid';
  if(current.instanceId!==null&&value.instance_id!==current.instanceId){
    if(sequence<current.lastAppliedSeq||(expectedInstance!==null&&expectedInstance!==current.instanceId))return 'ignore';
    return 'reload';
  }
  if(value.state_revision<current.stateRevision||(value.state_revision===current.stateRevision&&sequence<current.lastAppliedSeq))return 'ignore';
  return 'apply';
}
function deriveApplicationView(value,options={}){
  const fresh=options.fresh===true, connected=options.connected===true;
  let key=!connected?'offline':!fresh?'stale':!isStatusSnapshot(value)?'invalid':value.monitor_state;
  if(connected&&fresh&&isStatusSnapshot(value)){
    const c=value.monitor_controls,a=value.last_action;
    if(value.monitor_state==='closing')key='closing';
    else if(c.transition!==null||(a&&a.state==='processing')||options.requestPending===true)key='processing';
    else if(a&&['failed','blocked','conflict'].includes(a.state))key='failed';
    else if(a&&['unknown','shutdown_unconfirmed'].includes(a.state))key='unknown';
    else if((value.monitor_state==='running'&&(c.paused||c.stopped))||(value.monitor_state==='paused'&&!c.paused)||(value.monitor_state==='stopped'&&!c.stopped))key='unknown';

  }
  if(options.reloading===true)key='reloading';
  const presentation=APP_STATE_PRESENTATION[key]||APP_STATE_PRESENTATION.unknown;
  const capable=isStatusSnapshot(value)&&connected&&fresh&&!options.requestPending&&!options.reloading&&value.monitor_controls.available===true&&value.monitor_controls.transition===null&&(!value.last_action||value.last_action.state!=='processing');
  const permissions={};for(const action of MONITOR_ACTIONS)permissions[action]=Boolean(capable&&value.monitor_controls['can_'+action]);
  return {...presentation,key,permissions};
}
window.EventGuardUI=Object.freeze({APP_STATE_PRESENTATION,deriveApplicationView,acceptStatusDecision,isStatusSnapshot});
async function api(path,options={},timeoutMs=6000){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeoutMs);
  try{const reply=await fetch(path,{cache:'no-store',...options,signal:controller.signal});const data=await reply.json();if(!reply.ok){const error=Error(typeof data.error_code==='string'?data.error_code:'request_failed');error.code=error.message;error.httpStatus=reply.status;throw error;}return data;}
  catch(error){if(error.name==='AbortError'){const timeout=Error('request_timeout');timeout.code='request_timeout';throw timeout;}throw error;}finally{clearTimeout(timer);}
}
function fail(error){$('error').textContent='無法完成操作：'+error.message;$('error').hidden=false;}
function renderApplication(){
  const fresh=lastPollSuccessAt>0&&performance.now()-lastPollSuccessAt<=STATUS_STALE_MS;
  const view=deriveApplicationView(currentStatus,{fresh,connected:connectionHealthy,requestPending:controlFlight!==null,reloading:reloadPending});
  $('run-state').textContent=view.icon+' '+view.label;$('run-state').className='state-badge tone-'+view.tone;$('monitor-control').dataset.tone=view.tone;
  for(const action of MONITOR_ACTIONS)$('monitor-'+action).disabled=!view.permissions[action];
  const transition=currentStatus&&currentStatus.monitor_controls.transition;
  $('monitor-summary').textContent=view.label+(transition?'。階段：'+(states[transition]||transition)+'。':'。')+(view.key==='offline'||view.key==='stale'?' 不推定採集已停止。將自動重試連線。':'');
  const a=currentStatus&&currentStatus.last_action;
  $('monitor-last-action').textContent=a?'最近動作：'+(actionLabels[a.action]||a.action)+'。來源：'+sourceLabels[a.source]+'。結果：'+actionStates[a.state]+'。原因：'+a.result_code+'。時間：'+when(a.at)+'。':'最近動作：尚無紀錄。';
  $('monitor-revision').textContent=instanceId?'狀態版本：'+stateRevision+'。實例：'+instanceId+'。':'狀態版本尚未確認。';
}
function updateSavedStatus(value){
  const n=value.notifications||{},labels={disabled:'已關閉',waiting:'等待新事件',no_high_severity_events:'等待新事件',already_notified:'沒有待通知事件',notification_requested:'已送出系統通知要求',notification_display_cooldown:'等待下一則通知',notification_submission_unconfirmed:'上次通知結果未確認。為避免重複，不自動重送。事件仍保存在事件頁。',notification_receipt_failed:'通知要求已送出，但回條未保存。不自動重送。',notification_intent_not_saved:'通知尚未送出：無法保存通知意圖。事件仍保留。'};
  const uncertain=Number.isSafeInteger(n.unconfirmed_count)&&n.unconfirmed_count>0;const code=n.reason||n.status||n.state;$('notification-state').textContent=labels[code]||(n.status==='failed'?'系統通知不可用。原因：'+code:code)||'等待新事件';if(uncertain)$('notification-state').textContent+=' 未確認 '+n.unconfirmed_count+' 件。事件未 ACK。';$('notification-state').className=uncertain?'result-unknown':'';
  if(value.config_error){$('error').textContent=value.config_error==='saved_health_unavailable'?'已保存狀態暫時無法讀取。不推定規則檔損壞。':'規則檔錯誤：'+value.config_error+'。請檢查 config/rules.json。';$('error').dataset.statusError='true';$('error').hidden=false;}
  else if($('error').dataset.statusError==='true'){$('error').hidden=true;delete $('error').dataset.statusError;}
}
function applyServerState(value,sequence,expectedInstance,fromPoll){
  const decision=acceptStatusDecision({instanceId,stateRevision,lastAppliedSeq},value,sequence,expectedInstance);
  if(decision==='reload'){reloadPending=true;renderApplication();window.location.reload();return decision;}
  if(decision!=='apply')return decision;
  instanceId=value.instance_id;stateRevision=value.state_revision;lastAppliedSeq=sequence;
  currentStatus={...(currentStatus||{}),...value};
  if(fromPoll){lastPollSuccessAt=performance.now();connectionHealthy=true;}
  updateSavedStatus(currentStatus);renderApplication();return decision;
}
async function pollStatus(){
  if(statusFlight!==null||reloadPending)return statusFlight;
  const sequence=++clientSeq,expectedInstance=instanceId;
  statusFlight=(async()=>{try{const value=await api('/api/status',{},STATUS_TIMEOUT_MS);const decision=applyServerState(value,sequence,expectedInstance,true);if(decision==='invalid'){connectionHealthy=false;renderApplication();}}catch(error){if(sequence>=lastAppliedSeq){connectionHealthy=false;renderApplication();}}})();
  try{await statusFlight;}finally{statusFlight=null;}
}
function scheduleStatusPoll(){if(reloadPending)return;statusTimer=setTimeout(async()=>{await pollStatus();scheduleStatusPoll();},STATUS_POLL_MS);}
async function monitorAction(action){
  const fresh=lastPollSuccessAt>0&&performance.now()-lastPollSuccessAt<=STATUS_STALE_MS;
  const view=deriveApplicationView(currentStatus,{fresh,connected:connectionHealthy,requestPending:controlFlight!==null,reloading:reloadPending});
  if(controlFlight!==null||!view.permissions[action])return;
  if(!window.crypto||typeof window.crypto.randomUUID!=='function'){$('monitor-result').textContent='無法建立操作識別。要求未送出。';$('monitor-result').className='result-unknown';return;}
  const request={action,operationId:window.crypto.randomUUID(),sequence:++clientSeq,expectedInstance:instanceId};
  controlFlight=request;$('monitor-result').textContent='正在送出「'+actionLabels[action]+'」。尚未確認完成。';$('monitor-result').className='';renderApplication();
  try{
    const value=await api('/api/monitor/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-EventGuard-CSRF':document.querySelector('meta[name=csrf]').content},body:JSON.stringify({operation_id:request.operationId})},CONTROL_TIMEOUT_MS);
    if(controlFlight!==request)return;
    if(value.operation_id!==request.operationId||value.instance_id!==request.expectedInstance){connectionHealthy=false;$('monitor-result').textContent='操作回條身分不符。結果未確認。';$('monitor-result').className='result-unknown';}
    else{
      const decision=applyServerState(value,request.sequence,request.expectedInstance,false);
      const code=typeof value.reason==='string'?value.reason:(value.last_action&&value.last_action.result_code)||'receipt_received';
      $('monitor-result').textContent='操作回條：'+actionLabels[action]+'。原因：'+code+'。識別：'+request.operationId+'。'+(action==='shutdown'?'這是關閉要求的回條，不能單獨證明程序已退出。':'真實狀態以上方後端狀態為準。');
      if(decision==='invalid'){$('monitor-result').textContent+=' 回條狀態格式未確認。';$('monitor-result').className='result-unknown';connectionHealthy=false;}
    }
  }catch(error){
    if(controlFlight===request){connectionHealthy=false;$('monitor-result').textContent='要求回覆未確認：'+(error.code||'connection_failed')+'。不自動重送。將繼續查詢後端狀態。';$('monitor-result').className='result-unknown';}
  }finally{if(controlFlight===request)controlFlight=null;renderApplication();await pollStatus();}
}
const SOURCE_IDS=['defender','listeners','processes','startup','services','tasks','versions'];
async function sourceGap(){
  const target=$('source-gap-summary'),sequence=++sourceGapSequence;target.textContent='來源狀態正在確認。這不代表主機安全。';
  try{
    const data=await api('/api/sources'),rows=data&&data.sources;if(sequence!==sourceGapSequence)return;
    if(!Array.isArray(rows)||rows.length!==SOURCE_IDS.length)throw Error('invalid_sources');
    const indexed=new Map();
    for(const row of rows){if(!row||!SOURCE_IDS.includes(row.source_id)||indexed.has(row.source_id))throw Error('invalid_sources');indexed.set(row.source_id,row);}
    const gaps=SOURCE_IDS.filter(id=>indexed.get(id).status!=='ok'||indexed.get(id).freshness!=='fresh');
    target.textContent=gaps.length?'來源缺口 '+gaps.length+'／7：'+gaps.map(id=>sourceNames[id]+'（'+(states[indexed.get(id).status]||'未知')+'，'+sourceFreshness(indexed.get(id))+'）').join('、')+'。請查看來源狀態；不代表主機安全。':'七個來源最近觀測成功且未過期；不代表主機安全。';
  }catch(error){if(sequence===sourceGapSequence)target.textContent='來源狀態無法確認，請查看來源狀態；不代表主機安全。';}
}
function invalidateEventList(){eventSequence++;detailSequence++;deliverySequence++;selected=null;$('detail').hidden=true;$('event-rows').replaceChildren();$('count').textContent='正在讀取事件。';$('prev').disabled=true;$('next').disabled=true;}
function writeFilterUrl(){
  const params=new URLSearchParams(),form=$('filters');for(const name of ['severity','source','status'])if(form.elements[name].value)params.set(name,form.elements[name].value);
  if(offset)params.set('page',String(offset/50));const query=params.toString();history.pushState(null,'',location.pathname+(query?'?'+query:''));
}
function restoreFilterUrl(){
  const params=new URLSearchParams(location.search),form=$('filters'),names=['severity','source','status'];
  let valid=[...params.keys()].every(name=>[...names,'page'].includes(name)&&params.getAll(name).length===1);
  for(const name of names){const value=params.get(name)||'';if(![...form.elements[name].options].some(option=>option.value===value))valid=false;}
  const page=params.get('page')||'0';if(!/^(0|[1-9][0-9]{0,4})$/.test(page)||Number(page)>10000)valid=false;
  for(const name of names)form.elements[name].value=valid?(params.get(name)||''):'';
  offset=valid?Number(page)*50:0;filterUrlValid=valid;$('filter-url-error').hidden=valid;invalidateEventList();
}
async function events(){const sequence=++eventSequence;if(!filterUrlValid){$('count').textContent='網址篩選無效，無法顯示事件。';return;}const q=new URLSearchParams(new FormData($('filters')));for(const [k,v] of [...q])if(!v)q.delete(k);q.set('limit','50');q.set('offset',offset);const data=await api('/api/events?'+q);if(sequence!==eventSequence)return;const focused=document.activeElement&&document.activeElement.dataset.eventId;$('event-rows').replaceChildren();for(const e of data.events){const tr=node('tr');tr.append(node('td',severity[e.severity]||e.severity,e.severity),node('td',eventNames[e.event_type]||e.event_type),node('td',sourceNames[e.source]||e.source),node('td',when(e.observed_at)),node('td',handling[e.status]||e.status));const td=node('td'),b=node('button','查看');b.dataset.eventId=e.event_id;b.addEventListener('click',async()=>{try{await detail(e.event_id);if(selected===e.event_id)$('return-to-list').focus();}catch(error){fail(error);}});td.append(b);tr.append(td);$('event-rows').append(tr);}if(!data.events.length){const tr=node('tr'),td=node('td','沒有符合條件的事件。這不代表主機安全。');td.colSpan=6;tr.append(td);$('event-rows').append(tr);}$('count').textContent='符合條件 '+data.total+' 件。本頁 '+data.events.length+' 件。';$('prev').disabled=offset===0;$('next').disabled=!data.has_more||offset>=500000;if(focused){const button=[...$('event-rows').querySelectorAll('button')].find(item=>item.dataset.eventId===focused);if(button)button.focus();}}
async function detail(id){selected=id;const sequence=++detailSequence;const d=await api('/api/events/'+encodeURIComponent(id));if(sequence!==detailSequence||selected!==id)return;$('detail').hidden=false;$('detail-summary').textContent=(severity[d.severity]||d.severity)+' / '+(sourceNames[d.source]||d.source)+' / '+(handling[d.status]||d.status)+' / '+when(d.observed_at);$('detail-id').textContent=id;$('detail-json').textContent=JSON.stringify(d,null,2);renderHandlingHistory(d.handling_history);renderInvestigation(d.investigation);$('guidance').replaceChildren();if(d.guidance){$('guidance').append(node('p',d.guidance.observation));for(const step of d.guidance.next_steps||[])$('guidance').append(node('p',typeof step==='string'?step:JSON.stringify(step)));}for(const b of $('status-buttons').querySelectorAll('button'))b.disabled=b.dataset.status===d.status;}
async function sources(){const d=await api('/api/sources');$('source-cards').replaceChildren();for(const s of d.sources){const a=node('article',null,'source-card');a.append(node('h3',s.name||sourceNames[s.source_id]||s.source_id),node('p','最後採集：'+when(s.last_collected_at)+'。結果：'+(states[s.saved_status]||s.saved_status)+'。目前：'+(states[s.status]||s.status)+'。'),node('p','最後成功：'+sourceSuccess(s)+'。新鮮度：'+sourceFreshness(s)+'。'),node('p','觀測列數：'+(Number.isSafeInteger(s.row_count)&&s.row_count>=0?s.row_count:'未知')+'。'));for(const reason of s.reasons||[])a.append(node('p',JSON.stringify(reason),'reason'));a.append(node('p',s.suggestion));$('source-cards').append(a);}}
async function rules(){const d=await api('/api/rules');$('rule-cards').replaceChildren();for(const r of d.rules){const a=node('article',null,'rule-card');a.append(node('h3',r.name),node('p','嚴重度：'+(severity[r.severity]||r.severity)+'。'+(r.enabled===false?'已停用':'已啟用')+'。'),node('pre',JSON.stringify(r.conditions,null,2)));$('rule-cards').append(a);}}
const advisoryStates={not_started:'尚未啟用',ready:'資料可讀',partial:'資料不完整',blocked:'讀取受阻',possible:'需要調查',not_applicable:'目前條件不適用',unknown:'未知',success:'成功',not_modified:'未變更',failed:'失敗',fresh:'未過期',stale:'已過期'};
function advisorySource(s){const a=node('article',null,'source-card');a.append(node('h3',s.source_id||'未知來源'),node('p','狀態：'+(advisoryStates[s.status]||'未知')+'。新鮮度：'+(advisoryStates[s.freshness]||'未知')+'。'),node('p','來源 URL：'+(s.source_url||'未確認'),'reason'),node('p','發布：'+when(s.published_at)+'。更新：'+when(s.updated_at)+'。擷取：'+when(s.fetched_at)+'。最後成功：'+when(s.last_success_at)+'。'));if(s.partial||s.reason_code||(s.item_errors||[]).length)a.append(node('pre',JSON.stringify({partial:s.partial,reason:s.reason_code,item_errors:s.item_errors},null,2)));return a;}
async function advisories(){const d=await api('/api/advisories?limit=50');$('advisory-summary').textContent=(advisoryStates[d.state]||'未知')+'。共 '+d.total+' 案。本頁 '+d.advisories.length+' 案。'+(d.has_more?'其餘案件請用 CLI 篩選查看。':'')+'未評估是否已遭入侵。'+(d.reason_codes||[]).join(' / ');$('advisory-cards').replaceChildren();for(const c of d.advisories){const a=node('article',null,'source-card'),v=c.current_assessment||{};a.append(node('h3',c.title||'未提供標題'),node('p',(c.aliases||[]).join(' / '),'reason'),node('p','適用性：'+(advisoryStates[v.status]||'未知')+'。信心：'+c.confidence+'。資料不完整：'+(c.partial?'是':'否')+'。'),node('p','原因：'+(v.reason_codes||[]).join(' / '),'reason'));for(const s of c.sources||[])a.append(advisorySource(s));$('advisory-cards').append(a);}if(!d.advisories.length)$('advisory-cards').append(node('p','尚無可顯示的公告案件。這不代表沒有風險。'));$('advisory-source-cards').replaceChildren();for(const s of d.sources||[])$('advisory-source-cards').append(advisorySource(s));}
function mcpExitSummary(value){const m=value&&typeof value==='object'?value:{},verified=m.status==='verified'&&m.exit_code===0&&m.ack_flushed===true&&m.reason==='mcp_natural_exit_verified',code=Number.isInteger(m.exit_code)&&m.exit_code>=-2147483648&&m.exit_code<=4294967295?m.exit_code:'未知';return (verified?'MCP退出已驗證':'MCP退出未驗證')+'。退出碼：'+code+'。ACK回應已flush：'+(verified?'是':'未知')+'。';}
async function agent(){const d=await api('/api/agent'),task=d.dispatcher||{},failed=Number.isInteger(task.codex_exit_code)&&task.codex_exit_code!==0;$('agent-summary').textContent='程序：'+(d.host_liveness||'未知')+'。狀態：'+(d.state||d.host_state||'未知')+'。待收：'+(d.pending_events??'未知')+'。最後進度：'+(d.last_progress||d.heartbeat_at||'未知')+'。原因：'+(d.reason||d.blocked_reason||'無')+'。'+mcpExitSummary(d.mcp_lifecycle)+(failed?' 上次 CLI 任務失敗。退出碼：'+task.codex_exit_code+'。事件：'+(task.pending_event_id||'未知')+'。Attempt：'+(task.active_attempt_id||'未知')+'。接收／查證／ACK 請核對下方 delivery_progress；程序已退出不代表事件已收到。':'');$('agent-json').textContent=JSON.stringify(d,null,2);}
const showDetail=detail;detail=async function(id){const sequence=++deliverySequence;await showDetail(id);if(selected!==id||sequence!==deliverySequence)return;$('delivery-json').textContent='正在讀取保存證據…';try{const d=await api('/api/events/'+encodeURIComponent(id)+'/delivery');if(selected===id&&sequence===deliverySequence)$('delivery-json').textContent=JSON.stringify(d,null,2);}catch(e){if(selected===id&&sequence===deliverySequence)$('delivery-json').textContent='投遞證據不可用：'+e.message;}};
$('return-to-list').addEventListener('click',()=>{const id=selected;selected=null;detailSequence++;deliverySequence++;$('detail').hidden=true;const button=[...$('event-rows').querySelectorAll('button')].find(item=>item.dataset.eventId===id);(button||$('filters').querySelector('button')).focus();});
$('investigate').addEventListener('click',async()=>{if(!selected)return;const id=selected;$('investigate').disabled=true;try{const value=await api('/api/events/'+encodeURIComponent(id)+'/investigation',{method:'POST',headers:{'Content-Type':'application/json','X-EventGuard-CSRF':document.querySelector('meta[name=csrf]').content},body:'{}'});if(selected===id){renderInvestigation(value);await detail(id);}}catch(error){fail(error);}finally{$('investigate').disabled=false;}});
function openNoticeSeverity(value){
  const form=$('filters');form.elements.severity.value=value;form.elements.source.value='';form.elements.status.value='new';offset=0;filterUrlValid=true;$('filter-url-error').hidden=true;invalidateEventList();writeFilterUrl();
  document.querySelector('nav button[data-tab="events"]').click();
}
async function refreshNotice(){
  const high=await api('/api/events?severity=high&status=new&limit=1'),critical=await api('/api/events?severity=critical&status=new&limit=1');
  if(![high.total,critical.total].every(n=>Number.isSafeInteger(n)&&n>=0))throw Error('invalid_event_totals');
  const target=$('notice');target.hidden=high.total+critical.total===0;
  if(target.dataset.high===String(high.total)&&target.dataset.critical===String(critical.total))return;
  target.dataset.high=String(high.total);target.dataset.critical=String(critical.total);target.replaceChildren(node('span','新增事件（兩次獨立讀取，時間可能不同）： '));
  for(const [key,count] of [['high',high.total],['critical',critical.total]])if(count){const button=node('button',severity[key]+' '+count+' 件');button.type='button';button.addEventListener('click',()=>openNoticeSeverity(key));target.append(button,node('span',' '));}
}
async function refresh(){if(reloadPending)return;if(busy){refreshQueued=true;return;}busy=true;try{if(tab==='events')await sourceGap();await refreshNotice();if(tab==='events'){await events();if(selected)await detail(selected);}if(tab==='sources')await sources();if(tab==='advisories')await advisories();if(tab==='rules')await rules();if(tab==='agent')await agent();}catch(error){fail(error);}finally{busy=false;if(refreshQueued){refreshQueued=false;queueMicrotask(refresh);}}}
$('filters').addEventListener('submit',event=>{event.preventDefault();offset=0;filterUrlValid=true;$('filter-url-error').hidden=true;invalidateEventList();writeFilterUrl();refresh();});$('prev').addEventListener('click',()=>{offset=Math.max(0,offset-50);invalidateEventList();writeFilterUrl();refresh();});$('next').addEventListener('click',()=>{if(offset>=500000)return;offset+=50;invalidateEventList();writeFilterUrl();refresh();});window.addEventListener('popstate',()=>{restoreFilterUrl();refresh();});
for(const button of document.querySelectorAll('nav button'))button.addEventListener('click',()=>{sourceGapSequence++;$('source-gap-summary').textContent='來源狀態尚未確認。這不代表主機安全。';tab=button.dataset.tab;for(const name of ['events','sources','advisories','rules','agent'])$(name).hidden=name!==tab;for(const item of document.querySelectorAll('nav button'))item.setAttribute('aria-pressed',String(item===button));refresh();});
for(const action of ['pause','stop'])$('agent-'+action).addEventListener('click',async()=>{const button=$('agent-'+action);button.disabled=true;try{await api('/api/agent/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-EventGuard-CSRF':document.querySelector('meta[name=csrf]').content},body:'{}'});await agent();}catch(error){fail(error);}finally{button.disabled=false;}});
for(const action of MONITOR_ACTIONS)$('monitor-'+action).addEventListener('click',()=>monitorAction(action));
for(const button of $('status-buttons').querySelectorAll('button'))button.addEventListener('click',async()=>{if(!selected)return;if(!window.crypto||typeof window.crypto.randomUUID!=='function'){fail(Error('operation_id_unavailable'));return;}const id=selected,status=button.dataset.status,operationId=window.crypto.randomUUID();button.disabled=true;try{const result=await api('/api/events/'+encodeURIComponent(id)+'/status',{method:'POST',headers:{'Content-Type':'application/json','X-EventGuard-CSRF':document.querySelector('meta[name=csrf]').content},body:JSON.stringify({status,operation_id:operationId})});if((result.state&&result.state!=='event_status_updated')||result.status!==status)throw Error(result.reason||'event_status_unconfirmed');if(selected===id){await detail(id);await refresh();}}catch(error){const labels={event_status_capacity:'處置紀錄容量不足，狀態未變更',operation_id_conflict:'操作識別衝突，狀態未變更'};fail(Error(labels[error.message]||error.message));button.disabled=false;}});
restoreFilterUrl();renderApplication();pollStatus();scheduleStatusPoll();refresh();setInterval(refresh,5000);setInterval(renderApplication,500);
"""


class LocalWeb:
    def __init__(self, root, namespace="live", *, port=8765, status_provider=None, monitor_control=None,
                 operator_call=None, event_status_control=None, event_source=None):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("invalid_local_port")
        if monitor_control is not None and not callable(monitor_control):
            raise ValueError("invalid_monitor_control")
        if any(value is not None and not callable(value) for value in (operator_call, event_status_control)):
            raise ValueError("invalid_application_callback")
        from .events.catalog import EventCatalog
        self.root, self.namespace = root, namespace
        self.catalog = EventCatalog(root, namespace, directory=event_source)
        self.event_source = None if event_source is None else self.catalog.directory
        self.token = secrets.token_hex(32)
        self.status_provider = status_provider or (lambda: {"monitor_state": "unknown", "model_calls": 0})
        self.monitor_control = monitor_control
        self.operator_call, self.event_status_control = operator_call, event_status_control
        app = self

        class Server(ThreadingHTTPServer):
            daemon_threads = False
            block_on_close = True
            allow_reuse_address = False
            request_queue_size = 8

            def __init__(self, *args):
                self.slots = threading.BoundedSemaphore(8)
                super().__init__(*args)

            def process_request(self, request, client_address):
                if not self.slots.acquire(blocking=False):
                    self.shutdown_request(request)
                    return
                try:
                    super().process_request(request, client_address)
                except Exception:
                    self.slots.release()
                    raise

            def process_request_thread(self, request, client_address):
                try:
                    super().process_request_thread(request, client_address)
                finally:
                    self.slots.release()

        class Handler(BaseHTTPRequestHandler):
            server_version = "EventGuard"
            sys_version = ""

            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def log_message(self, *_args):
                pass  # No query values or event content in HTTP logs.

            def reply(self, code, data, mime="application/json; charset=utf-8"):
                body = data.encode("utf-8") if isinstance(data, str) else json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (OSError, TimeoutError):
                    pass
                self.close_connection = True

            def local_request(self):
                # Exact Host also rejects a DNS-rebinding name resolved to loopback.
                return self.headers.get_all("Host", []) == [app.host] and len(self.path) <= 2048

            def error(self, code, reason):
                self.reply(code, {"status": "error", "error_code": reason})

            def do_GET(self):
                if not self.local_request():
                    return self.error(403, "local_host_required")
                try:
                    route = urlsplit(self.path)
                    if route.path == "/":
                        return self.reply(200, HTML.replace("__TOKEN__", app.token).replace("__SCOPE_NOTICE__", app.scope_notice()), "text/html; charset=utf-8")
                    query = parse_qs(route.query, max_num_fields=8, strict_parsing=True) if route.query else {}
                    if any(len(v) != 1 for v in query.values()):
                        raise ValueError("duplicate_filter")
                    if route.path in {"/app.js", "/app.css"} and not query:
                        return self.reply(200, JS if route.path.endswith(".js") else CSS,
                                          "text/javascript; charset=utf-8" if route.path.endswith(".js") else "text/css; charset=utf-8")
                    if route.path == "/api/events":
                        if set(query) - {"severity", "source", "status", "limit", "offset"}:
                            raise ValueError("unknown_filter")
                        args = {k: v[0] for k, v in query.items()}
                        for k in ("limit", "offset"):
                            if k in args:
                                args[k] = int(args[k])
                        return self.reply(200, app.catalog.list(**args))
                    if route.path.startswith("/api/events/") and route.path.endswith("/delivery") and not query:
                        from .event_ingress import inspect_delivery
                        from .runtime import Runtime
                        runtime = Runtime(app.root)
                        event_id = unquote(route.path[len("/api/events/"):-len("/delivery")], errors="strict")
                        if app.event_source is not None:
                            state = app.bound_delivery_state()
                            if state is None:
                                return self.reply(200, {"state": "unknown", "reason": "delivery_state_not_bound_to_event_source",
                                                        "event_id": event_id, "model_calls": 0})
                            return self.reply(200, inspect_delivery(app.event_source, state, event_id,
                                                                    allow_live=False, root=runtime.root))
                        state = "data/agent-delivery" if app.namespace == "live" else "data/agent-delivery-test"
                        return self.reply(200, inspect_delivery(runtime.path("data/"+app.namespace),
                            runtime.path(state), event_id, allow_live=app.namespace == "live", root=runtime.root))
                    if route.path.startswith("/api/events/") and not query:
                        event_id = unquote(route.path.removeprefix("/api/events/"), errors="strict")
                        return self.reply(200, app.catalog.detail(event_id))
                    if route.path == "/api/sources" and not query:
                        from .source_status import source_status
                        return self.reply(200, source_status(app.root, app.namespace))
                    if route.path == "/api/advisories":
                        if set(query) - {"limit"}:
                            raise ValueError("unknown_advisory_filter")
                        from .intelligence.views import public_advisories
                        return self.reply(200, public_advisories(app.root, app.namespace,
                            limit=int(query.get("limit", ["50"])[0])))
                    if route.path == "/api/rules" and not query:
                        from .rules.configured import load_rules
                        return self.reply(200, {"rules": load_rules(app.root), "model_calls": 0})
                    if route.path == "/api/status" and not query:
                        return self.reply(200, app.status())
                    if route.path == "/api/agent" and not query:
                        from .agent_service import status
                        return self.reply(200, status(app.root))
                    self.error(404, "route_not_found")
                except ValueError:
                    self.error(400, "invalid_request_or_rules")
                except (OSError, RuntimeError):
                    self.error(503, "local_storage_unavailable")

            def do_POST(self):
                if self.path == "/api/operator":
                    return self.operator_request()
                if (not self.local_request() or self.headers.get_all("Origin", []) != [app.url]
                        or self.headers.get_all("X-EventGuard-CSRF", []) != [app.token]):
                    return self.error(403, "same_origin_required")
                try:
                    if (self.headers.get("Content-Type") != "application/json" or self.headers.get("Transfer-Encoding")
                            or len(self.headers.get_all("Content-Length", [])) != 1):
                        raise ValueError("invalid_body")
                    size = int(self.headers["Content-Length"])
                    if not 1 <= size <= 256:
                        raise ValueError("invalid_body_size")
                    parts = self.path.split("/")
                    if parts[:3] == ["", "api", "monitor"] and len(parts) == 4 and parts[3] in {"start", "pause", "resume", "stop", "shutdown"}:
                        body = self.json_body(size)
                        if type(body) is not dict or set(body) - {"operation_id"}:
                            raise ValueError("invalid_monitor_control")
                        self.operation_id(body)
                        if app.monitor_control is None:
                            return self.error(503, "monitor_control_unavailable")
                        try:
                            result = app.monitor_control(parts[3], **body)
                            if type(result) is not dict:
                                raise ValueError("invalid_monitor_control_result")
                            json.dumps(result, ensure_ascii=False, allow_nan=False)
                        except Exception:
                            return self.error(503, "monitor_control_failed")
                        return self.reply(200, result)
                    if parts[:3] == ["", "api", "agent"] and len(parts) == 4 and parts[3] in {"pause", "stop"}:
                        if json.loads(self.rfile.read(size)) != {}:
                            raise ValueError("invalid_agent_control")
                        from . import agent_service
                        result = (agent_service.pause(app.root) if parts[3] == "pause" else
                                  agent_service.stop(app.root, grace_seconds=5))
                        return self.reply(200, result)
                    if len(parts) == 5 and parts[:3] == ["", "api", "events"] and parts[4] == "investigation":
                        if self.json_body(size) != {}:
                            raise ValueError("invalid_investigation_request")
                        return self.reply(200, app.catalog.investigate(parts[3]))
                    if len(parts) != 5 or parts[:3] != ["", "api", "events"] or parts[4] != "status":
                        return self.error(404, "route_not_found")
                    data = self.json_body(size)
                    if not isinstance(data, dict) or set(data) - {"status", "operation_id"} or "status" not in data:
                        raise ValueError("invalid_status_request")
                    self.operation_id(data)
                    event_id = unquote(parts[3], errors="strict")
                    from .events.disposition_history_store import HistoryConflictError
                    from .events.store import CapacityError
                    try:
                        result = (app.event_status_control(event_id, **data) if app.event_status_control is not None
                                  else app.catalog.set_status(event_id, data["status"], source="gui", operation_id=data.get("operation_id")))
                    except HistoryConflictError:
                        return self.error(409, "operation_id_conflict")
                    except CapacityError:
                        return self.error(503, "event_status_capacity")
                    return self.reply(200, result)
                except (ValueError, UnicodeError):
                    self.error(400, "invalid_status_request")
                except (OSError, RuntimeError):
                    self.error(503, "local_storage_unavailable")

            @staticmethod
            def operation_id(body):
                if "operation_id" in body and (type(body["operation_id"]) is not str or
                        re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", body["operation_id"]) is None):
                    raise ValueError("invalid_operation_id")

            def json_body(self, size):
                def pairs(values):
                    result = {}
                    for key, value in values:
                        if key in result:
                            raise ValueError("duplicate_json_key")
                        result[key] = value
                    return result
                def constant(_value):
                    raise ValueError("nonfinite_json")
                return json.loads(self.rfile.read(size), object_pairs_hook=pairs, parse_constant=constant)

            def operator_request(self):
                # A typed stdio adapter attaches to this existing application.
                # It does not create a second control owner or accept shell text.
                origin = self.headers.get_all("Origin", [])
                authorization = self.headers.get_all("Authorization", [])
                if (not self.local_request() or origin not in ([], [app.url]) or len(authorization) != 1
                        or not hmac.compare_digest(authorization[0].encode("latin-1"), ("Bearer " + app.token).encode("ascii"))):
                    return self.error(403, "application_token_required")
                try:
                    if (self.headers.get_all("Content-Type", []) != ["application/json"]
                            or self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1):
                        raise ValueError("invalid_body")
                    size = int(self.headers["Content-Length"])
                    if not 1 <= size <= 8192:
                        raise ValueError("invalid_body_size")
                    body = self.json_body(size)
                    if (type(body) is not dict or set(body) - {"instance_id", "name", "arguments", "source"}
                            or not {"instance_id", "name", "arguments"}.issubset(body)
                            or type(body.get("source", "mcp")) is not str or body.get("source", "mcp") not in {"mcp", "cli"}):
                        raise ValueError("invalid_operator_request")
                    current = app.status_provider()
                    if body["instance_id"] != current.get("instance_id"):
                        return self.error(409, "application_instance_changed")
                    if app.operator_call is None:
                        return self.error(503, "application_operator_unavailable")
                    return self.reply(200, app.operator_call(body["name"], body["arguments"], source=body["source"])
                                      if "source" in body else app.operator_call(body["name"], body["arguments"]))
                except (ValueError, TypeError, UnicodeError):
                    self.error(400, "invalid_operator_request")
                except (OSError, RuntimeError):
                    self.error(503, "application_operator_unavailable")

        self.server = Server(("127.0.0.1", port), Handler)
        self.host = "127.0.0.1:" + str(self.server.server_port)
        self.url = "http://" + self.host
        self.thread = None

    def status(self):
        """Missing or malformed control state must leave the page disabled."""
        saved = self.status_provider()
        if type(saved) is not dict:
            raise ValueError("invalid_local_status")
        controls = {"available": False, "paused": False, "stopped": False, "transition": None,
                    "can_start": False, "can_pause": False, "can_resume": False, "can_stop": False, "can_shutdown": False}
        supplied = saved.get("monitor_controls")
        if (type(supplied) is dict and set(supplied) == set(controls)
                and all(type(supplied.get(key)) is bool for key in controls if key != "transition")
                and (supplied.get("transition") is None
                     or type(supplied.get("transition")) is str and 1 <= len(supplied["transition"]) <= 64)):
            controls = {**supplied, "available": supplied["available"] and callable(self.monitor_control)}
            for key in controls:
                if key.startswith("can_"):
                    controls[key] = controls[key] and controls["available"]
        return {**saved, "monitor_controls": controls}

    def scope_notice(self):
        if self.event_source is not None:
            from html import escape
            from .runtime import Runtime
            relative = self.event_source.relative_to(Runtime(self.root).root).as_posix()
            return "合成驗收資料。事件來自綁定的自訂 source：" + escape(relative) + "。此頁不採集，也未查詢主機資安來源。"
        return "合成驗收資料。此頁未查詢主機資安來源。" if self.namespace == "test" else "本機保存資料。未知、拒讀與過期都不代表安全。"

    def bound_delivery_state(self):
        """Delivery state of the agent service only when it names this source."""
        import os
        from pathlib import Path
        from .agent_service import status
        try:
            agent = status(self.root)
        except (OSError, ValueError, RuntimeError, TypeError):
            return None
        source, state = agent.get("source_dir"), agent.get("state_dir")
        if not isinstance(source, str) or not isinstance(state, str):
            return None
        same = os.path.normcase(str(Path(source).absolute())) == os.path.normcase(str(self.event_source))
        return Path(state) if same else None

    def start(self):
        if self.thread is not None:
            raise RuntimeError("web_already_started")
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .1}, name="eventguard-web")
        self.thread.start()

    def close(self):
        if self.thread is not None:
            self.server.shutdown()
            self.thread.join(timeout=6)
        self.server.server_close()
        return {"web_thread_exited": self.thread is None or not self.thread.is_alive()}
