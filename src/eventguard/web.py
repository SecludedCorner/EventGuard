"""Loopback-only product views. No remote assets, shell, models or OS queries."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
from urllib.parse import parse_qs, unquote, urlsplit


HTML = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="csrf" content="__TOKEN__"><title>EventGuard 本機資安監看</title><link rel="stylesheet" href="/app.css"></head>
<body><header><div><h1>EventGuard</h1><p>本機採集。規則比對。事件保存。無模型。</p></div><span id="run-state">正在讀取狀態</span></header>
<main><p id="error" role="alert" hidden></p><p id="notice" role="status" hidden></p>
<nav aria-label="頁面"><button data-tab="events" aria-pressed="true">事件</button><button data-tab="sources">來源狀態</button><button data-tab="rules">規則</button></nav>
<section id="events"><h2>事件</h2><form id="filters">
<label>嚴重度<select name="severity"><option value="">全部</option><option value="critical">嚴重</option><option value="high">高</option><option value="warning">警告</option><option value="info">資訊</option></select></label>
<label>來源<select name="source"><option value="">全部</option><option value="defender">Defender</option><option value="listeners">監聽端點</option><option value="processes">程序</option><option value="startup">啟動項</option><option value="services">服務</option><option value="tasks">排程工作</option><option value="versions">版本</option><option value="monitor">監看程式</option><option value="unknown">未知</option></select></label>
<label>處置狀態<select name="status"><option value="">全部</option><option value="new">新增</option><option value="read">已讀</option><option value="handled">已處理</option><option value="ignored">忽略</option></select></label><button type="submit">篩選</button></form>
<p id="count"></p><div class="table-wrap"><table><thead><tr><th>嚴重度</th><th>事件</th><th>來源</th><th>時間</th><th>處置狀態</th><th>詳情</th></tr></thead><tbody id="event-rows"></tbody></table></div>
<p><button id="prev">上一頁</button> <button id="next">下一頁</button></p>
<article id="detail" hidden><h2>事件詳情</h2><p id="detail-summary"></p><p id="detail-id"></p><p>處置狀態只記錄人的決定。它不會 ACK，也不會修改系統。</p>
<div id="status-buttons"><button data-status="new">新增</button><button data-status="read">已讀</button><button data-status="handled">已處理</button><button data-status="ignored">忽略</button></div>
<h3>觀察與建議</h3><div id="guidance"></div><details><summary>結構化資料</summary><pre id="detail-json"></pre></details></article></section>
<section id="sources" hidden><h2>七個來源</h2><p>只顯示已保存的採集結果。未知、拒讀或過期都不代表安全。</p><div id="source-cards"></div></section>
<section id="rules" hidden><h2>規則</h2><p>編輯專案的 config/rules.json。下一輪採集會讀取。規則不執行命令。</p><div id="rule-cards"></div></section>
<footer>僅供本機使用。高嚴重度事件會顯示本頁提示。系統通知狀態：<span id="notification-state">未知</span>。<br>關閉此頁不會停止程式。回到執行終端，按 Ctrl+C 停止。</footer></main><script src="/app.js" defer></script></body></html>"""

CSS = """:root{color-scheme:light;font:16px system-ui,'Microsoft JhengHei',sans-serif;color:#183044;background:#f1f5f7}*{box-sizing:border-box}body{margin:0}header{background:#153d50;color:white;padding:24px max(24px,calc((100vw - 1180px)/2));display:flex;justify-content:space-between;gap:24px;align-items:center}h1{margin:0;font-size:29px}header p{margin-bottom:0;color:#d5e6ed}main{max-width:1180px;margin:auto;padding:24px}nav,form,#status-buttons{display:flex;gap:12px;flex-wrap:wrap;align-items:end}button,select{font:inherit;padding:9px 12px;border:1px solid #9badb9;border-radius:6px;background:white;color:#183044}button{cursor:pointer}button:hover,button[aria-pressed=true]{background:#d9eaf0}button:disabled{opacity:.45;cursor:default}label{display:grid;gap:5px}section,article{background:white;border:1px solid #dce4e9;border-radius:10px;margin-top:20px;padding:22px}article{background:#f7fafb}h2{margin-top:0}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;border-bottom:1px solid #e3e9ed;padding:12px 9px;vertical-align:top}th{white-space:nowrap;color:#506472}td:first-child{font-weight:700}.high,.critical{color:#a12822}.warning{color:#855c04}.source-card,.rule-card{padding:16px 0;border-bottom:1px solid #dce4e9}.source-card h3,.rule-card h3{margin:0 0 10px}.reason{font:13px ui-monospace,monospace;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px ui-monospace,monospace}#notice{padding:15px;border-left:5px solid #a12822;background:#fff0eb}#error{padding:15px;background:#ffe3df;color:#7b1e19}footer{font-size:13px;line-height:1.8;color:#566d7c;margin-top:24px}[hidden]{display:none!important}@media(max-width:650px){header{display:block}main{padding:12px}section{padding:14px}form label{flex:1;min-width:130px}}"""

JS = """'use strict';
const $=id=>document.getElementById(id), severity={critical:'嚴重',high:'高',warning:'警告',info:'資訊'}, handling={new:'新增',read:'已讀',handled:'已處理',ignored:'忽略'};
const sourceNames={defender:'Defender',listeners:'監聽端點',processes:'程序',startup:'啟動項',services:'服務',tasks:'排程工作',versions:'版本',monitor:'監看程式',unknown:'未知'};
const states={ok:'成功',partial:'部分成功',denied:'拒讀',unknown:'未知',not_applicable:'不適用',not_requested:'尚未採集',not_observed:'尚未採集',not_collected:'尚未採集',stale:'資料過期',error:'失敗',timeout:'逾時',cancelled:'已取消',busy:'忙碌',started:'監看中',running:'監看中',stopped:'已停止',blocked:'受阻',blocked_rules:'規則檔錯誤',backoff:'等待重試',shutdown_unconfirmed:'退出未確認',enabled_not_running:'目前未採集',disabled:'已停用'};
const eventNames={'listener.changed':'監聽端點變化','protection.changed':'防護狀態變化','persistence.changed':'啟動與服務變化','coverage.degraded':'來源可見性降低','monitor_gap':'監看缺口'};
let offset=0, selected=null, tab='events', busy=false;
function node(tag,text,cls){const e=document.createElement(tag);e.textContent=text??'';if(cls)e.className=cls;return e;}
function when(s){if(!s)return '尚無紀錄';const d=new Date(s);return Number.isNaN(+d)?'時間未知':d.toLocaleString('zh-TW',{hour12:false});}
async function api(path,options={}){const r=await fetch(path,{cache:'no-store',...options});const data=await r.json();if(!r.ok)throw Error(data.error_code||'操作失敗');return data;}
function fail(error){$('error').textContent='無法完成操作：'+error.message;$('error').hidden=false;}
async function events(){const q=new URLSearchParams(new FormData($('filters')));for(const [k,v] of [...q])if(!v)q.delete(k);q.set('limit','50');q.set('offset',offset);const data=await api('/api/events?'+q);$('event-rows').replaceChildren();for(const e of data.events){const tr=node('tr');tr.append(node('td',severity[e.severity]||e.severity,e.severity),node('td',eventNames[e.event_type]||e.event_type),node('td',sourceNames[e.source]||e.source),node('td',when(e.observed_at)),node('td',handling[e.status]||e.status));const td=node('td'),b=node('button','查看');b.addEventListener('click',()=>detail(e.event_id).catch(fail));td.append(b);tr.append(td);$('event-rows').append(tr);}if(!data.events.length){const tr=node('tr'),td=node('td','沒有符合條件的事件。這不代表主機安全。');td.colSpan=6;tr.append(td);$('event-rows').append(tr);}$('count').textContent='符合條件 '+data.total+' 件。本頁 '+data.events.length+' 件。';$('prev').disabled=offset===0;$('next').disabled=!data.has_more;}
async function detail(id){const d=await api('/api/events/'+encodeURIComponent(id));selected=id;$('detail').hidden=false;$('detail-summary').textContent=(severity[d.severity]||d.severity)+' / '+(sourceNames[d.source]||d.source)+' / '+(handling[d.status]||d.status)+' / '+when(d.observed_at);$('detail-id').textContent=id;$('detail-json').textContent=JSON.stringify(d,null,2);$('guidance').replaceChildren();if(d.guidance){$('guidance').append(node('p',d.guidance.observation));for(const step of d.guidance.next_steps||[])$('guidance').append(node('p',typeof step==='string'?step:JSON.stringify(step)));}for(const b of $('status-buttons').querySelectorAll('button'))b.disabled=b.dataset.status===d.status;}
async function sources(){const d=await api('/api/sources');$('source-cards').replaceChildren();for(const s of d.sources){const a=node('article',null,'source-card');a.append(node('h3',s.name||sourceNames[s.source_id]||s.source_id),node('p','最後採集：'+when(s.last_collected_at)+'。結果：'+(states[s.saved_status]||s.saved_status)+'。目前：'+(states[s.status]||s.status)+'。'));for(const reason of s.reasons||[])a.append(node('p',JSON.stringify(reason), 'reason'));a.append(node('p',s.suggestion));$('source-cards').append(a);}}
async function rules(){const d=await api('/api/rules');$('rule-cards').replaceChildren();for(const r of d.rules){const a=node('article',null,'rule-card');a.append(node('h3',r.name),node('p','嚴重度：'+(severity[r.severity]||r.severity)+'。'+(r.enabled===false?'已停用':'已啟用')+'。'),node('pre',JSON.stringify(r.conditions,null,2)));$('rule-cards').append(a);}}
async function state(){const d=await api('/api/status');$('run-state').textContent=states[d.monitor_state]||d.monitor_state||'狀態未知';const n=d.notifications||{};const noticeLabels={disabled:'已關閉',waiting:'等待新事件',no_high_severity_events:'等待新事件',already_notified:'沒有待通知事件',notification_requested:'已送出系統通知要求',notification_display_cooldown:'等待下一則通知'};const noticeCode=n.reason||n.status||n.state;$('notification-state').textContent=noticeLabels[noticeCode]||(n.status==='failed'?'系統通知不可用。本頁提示仍有效。原因：'+noticeCode:noticeCode)||'等待新事件';if(d.config_error){$('error').textContent='規則檔錯誤：'+d.config_error+'。請檢查 config/rules.json。';$('error').hidden=false;}const fresh=await api('/api/events?severity=high&status=new&limit=1');const critical=await api('/api/events?severity=critical&status=new&limit=1');const count=fresh.total+critical.total;$('notice').hidden=count===0;$('notice').textContent='有 '+count+' 件新增的高嚴重度事件。請查看事件並記錄處置狀態。';}
async function refresh(){if(busy)return;busy=true;$('error').hidden=true;try{await state();if(tab==='events')await events();if(tab==='sources')await sources();if(tab==='rules')await rules();}catch(e){fail(e);}finally{busy=false;}}
$('filters').addEventListener('submit',e=>{e.preventDefault();offset=0;refresh();});$('prev').addEventListener('click',()=>{offset=Math.max(0,offset-50);refresh();});$('next').addEventListener('click',()=>{offset+=50;refresh();});
for(const b of document.querySelectorAll('nav button'))b.addEventListener('click',()=>{tab=b.dataset.tab;for(const s of ['events','sources','rules'])$(s).hidden=s!==tab;for(const x of document.querySelectorAll('nav button'))x.setAttribute('aria-pressed',String(x===b));refresh();});
for(const b of $('status-buttons').querySelectorAll('button'))b.addEventListener('click',async()=>{if(!selected)return;b.disabled=true;try{await api('/api/events/'+encodeURIComponent(selected)+'/status',{method:'POST',headers:{'Content-Type':'application/json','X-EventGuard-CSRF':document.querySelector('meta[name=csrf]').content},body:JSON.stringify({status:b.dataset.status})});await detail(selected);await refresh();}catch(e){fail(e);b.disabled=false;}});
refresh();setInterval(refresh,5000);
"""


class LocalWeb:
    def __init__(self, root, namespace="live", *, port=8765, status_provider=None):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("invalid_local_port")
        from .events.catalog import EventCatalog
        self.root, self.namespace = root, namespace
        self.catalog = EventCatalog(root, namespace)
        self.token = secrets.token_hex(32)
        self.status_provider = status_provider or (lambda: {"monitor_state": "unknown", "model_calls": 0})
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
                    query = parse_qs(route.query, max_num_fields=8, strict_parsing=True) if route.query else {}
                    if any(len(v) != 1 for v in query.values()):
                        raise ValueError("duplicate_filter")
                    if route.path == "/" and not query:
                        return self.reply(200, HTML.replace("__TOKEN__", app.token), "text/html; charset=utf-8")
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
                    if route.path.startswith("/api/events/") and not query:
                        event_id = unquote(route.path.removeprefix("/api/events/"), errors="strict")
                        return self.reply(200, app.catalog.detail(event_id))
                    if route.path == "/api/sources" and not query:
                        from .source_status import source_status
                        return self.reply(200, source_status(app.root, app.namespace))
                    if route.path == "/api/rules" and not query:
                        from .rules.configured import load_rules
                        return self.reply(200, {"rules": load_rules(app.root), "model_calls": 0})
                    if route.path == "/api/status" and not query:
                        return self.reply(200, app.status_provider())
                    self.error(404, "route_not_found")
                except ValueError:
                    self.error(400, "invalid_request_or_rules")
                except (OSError, RuntimeError):
                    self.error(503, "local_storage_unavailable")

            def do_POST(self):
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
                    if len(parts) != 5 or parts[:3] != ["", "api", "events"] or parts[4] != "status":
                        return self.error(404, "route_not_found")
                    data = json.loads(self.rfile.read(size))
                    if not isinstance(data, dict) or set(data) != {"status"}:
                        raise ValueError("invalid_status_request")
                    return self.reply(200, app.catalog.set_status(unquote(parts[3], errors="strict"), data["status"]))
                except (ValueError, UnicodeError):
                    self.error(400, "invalid_status_request")
                except (OSError, RuntimeError):
                    self.error(503, "local_storage_unavailable")

        self.server = Server(("127.0.0.1", port), Handler)
        self.host = "127.0.0.1:" + str(self.server.server_port)
        self.url = "http://" + self.host
        self.thread = None

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
