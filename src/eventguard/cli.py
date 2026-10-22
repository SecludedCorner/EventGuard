"""Typed local CLI. There is no shell-execution, remediation or external endpoint option."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sqlite3
import sys
import uuid

from . import __version__
from .runtime import Runtime, read_json, utc_now


def parser():
    p=argparse.ArgumentParser(prog="eventguard",description="EventGuard 本機唯讀 headless 監看；正式 agent 尚未接通")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("capabilities")
    sub.add_parser("status")
    sub.add_parser("stop")
    monitor=sub.add_parser("monitor",help="前景持續監看；Ctrl+C 或另一終端 stop")
    monitor.add_argument("--max-cycles",type=int)
    monitor.add_argument("--fixture",help="僅 tests/fixtures 內的合成資料")
    monitor.add_argument("--fixture-interval",type=float,default=0.1)
    query=sub.add_parser("query")
    query.add_argument("operation")
    query.add_argument("--args",default="{}",help="型別化 JSON，不能是 shell 指令")
    events=sub.add_parser("events")
    eventsub=events.add_subparsers(dest="event_command",required=True)
    listing=eventsub.add_parser("list")
    listing.add_argument("--namespace",choices=("live","test"),default="live")
    listing.add_argument("--limit",type=int,default=100)
    synth=sub.add_parser("synthetic")
    synthsub=synth.add_subparsers(dest="synthetic_command",required=True)
    emit=synthsub.add_parser("emit")
    emit.add_argument("--scenario",choices=("listener","defender","startup","coverage"),default="listener")
    deliver=sub.add_parser("deliver")
    deliver.add_argument("--adapter",choices=("disabled","mock"),default="disabled")
    deliver.add_argument("--namespace",choices=("live","test"))
    mock=sub.add_parser("mock")
    mocksub=mock.add_subparsers(dest="mock_command",required=True)
    process=mocksub.add_parser("process")
    process.add_argument("--event-id",required=True)
    mocksub.add_parser("status")
    playbook=sub.add_parser("playbook")
    playsub=playbook.add_subparsers(dest="playbook_command",required=True)
    playsub.add_parser("validate")
    simulate=playsub.add_parser("simulate")
    simulate.add_argument("--event-id",required=True)
    simulate.add_argument("--namespace",choices=("live","test"),default="test")
    report=sub.add_parser("report")
    reportsub=report.add_subparsers(dest="report_command",required=True)
    export=reportsub.add_parser("export")
    export.add_argument("--namespace",choices=("live","test"),default="live")
    return p


def _store(runtime,namespace):
    from .events.store import EventStore
    config=runtime.config().get("outbox",{})
    return EventStore(runtime.data_dir(namespace),max_events=config.get("max_events",1000),max_bytes=config.get("max_bytes",8388608))


def _readonly_stats(runtime,namespace):
    path=runtime.data_dir(namespace,create=False)/"eventguard.sqlite3"
    runtime.path(path.relative_to(runtime.root))
    if not path.is_file():
        return {"state":"not_created","events":0}
    with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=1) as connection:
        rows=connection.execute("SELECT delivery_status,COUNT(*) FROM events GROUP BY delivery_status").fetchall()
    return {"state":"available","counts":dict(rows),"events":sum(row[1] for row in rows)}


def status(runtime):
    health=runtime.health()
    stamp=health.get("heartbeat_at")
    age=None
    if isinstance(stamp,str):
        try:
            age=max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(stamp.replace("Z","+00:00"))).total_seconds())
        except (ValueError,TypeError):
            pass
    # The last report is not proof of liveness after a crash; do not claim a watchdog.
    return {"tool_version":__version__,"health":health,"heartbeat_age_seconds":age,
            "liveness":"last_report_only; no independent watchdog",
            "namespaces":{name:_readonly_stats(runtime,name) for name in ("live","test")},
            "agent_ingress":"not_configured","real_agent_woken":False}


def export_report(runtime,namespace):
    events=_store(runtime,namespace).list_events(limit=1000)
    document={"schema_version":"1.0","tool_version":__version__,"exported_at":utc_now(),"namespace":namespace,
              "real_agent_connected":False,"note":"本機事件與投遞狀態；ACK 不代表 agent 已處理，也不是安全結論。","events":events}
    runtime.ensure()
    prefix="eventguard-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
    json_path=runtime.path("reports/"+prefix+".json")
    html_path=runtime.path("reports/"+prefix+".html")
    with json_path.open("x",encoding="utf-8") as stream:
        json.dump(document,stream,ensure_ascii=False,indent=2)
    escaped=html.escape(json.dumps(document,ensure_ascii=False,indent=2),quote=True)
    page='<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>EventGuard 本機報告</title><style>body{font:15px sans-serif;max-width:1100px;margin:32px auto;padding:16px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>EventGuard 本機事件報告</h1><p>事件不等於入侵結論。mock 不等於真正 agent 喚醒。</p><pre>'+escaped+'</pre></html>'
    with html_path.open("x",encoding="utf-8") as stream:
        stream.write(page)
    return {"json":str(json_path),"html":str(html_path),"event_count":len(events)}


def execute(args,runtime):
    if args.command=="capabilities":
        from .diagnostics.api import DiagnosticAPI
        return {"tool_version":__version__,"diagnostics":DiagnosticAPI().capabilities(),
                "monitor":"foreground, cooperative stop, singleton", "transport":["disabled","synthetic-only local mock"],
                "remediation":[],"gui":False,"model_calls":0,"real_agent_ingress":"not_configured"}
    if args.command=="status":
        return status(runtime)
    if args.command=="stop":
        return runtime.request_stop()
    if args.command=="monitor":
        from .monitor import Monitor
        return Monitor(runtime.root).run(max_cycles=args.max_cycles,fixture=args.fixture,fixture_interval=args.fixture_interval)
    if args.command=="query":
        if len(args.args.encode("utf-8"))>8192:
            raise ValueError("query_input_limit")
        values=json.loads(args.args)
        if not isinstance(values,dict):
            raise ValueError("query_args_must_be_object")
        from .diagnostics.api import DiagnosticAPI
        return DiagnosticAPI().query(args.operation,values)
    if args.command=="events":
        if not 1<=args.limit<=1000:
            raise ValueError("event_limit_out_of_bounds")
        return {"namespace":args.namespace,"events":_store(runtime,args.namespace).list_events(limit=args.limit)}
    if args.command=="synthetic":
        from .synthetic import make_synthetic
        event=make_synthetic(args.scenario)
        inserted=_store(runtime,"test").enqueue(event)
        return {"namespace":"test","event_id":event["event_id"],"inserted":inserted,"synthetic":True,"real_agent_woken":False}
    if args.command=="deliver":
        from .transport.adapters import DisabledAdapter,MockReceiverAdapter
        namespace=args.namespace or ("test" if args.adapter=="mock" else "live")
        if args.adapter=="mock" and namespace!="test":
            raise ValueError("mock_adapter_requires_test_namespace")
        adapter=MockReceiverAdapter(runtime.data_dir("test")) if args.adapter=="mock" else DisabledAdapter()
        return {"namespace":namespace,"adapter":args.adapter,"delivery":_store(runtime,namespace).pump(adapter),"real_agent_woken":False}
    if args.command=="mock":
        from .transport.adapters import MockReceiverAdapter
        receiver=MockReceiverAdapter(runtime.data_dir("test"))
        if args.mock_command=="status":
            return {"receiver":receiver.status(),"cases":receiver.list_cases(),"real_agent_woken":False}
        from .synthetic import mock_diagnostic
        return receiver.process_mock(args.event_id,mock_diagnostic)
    if args.command=="playbook":
        from .rules.playbooks import validate_playbooks,simulate
        path=runtime.path("playbooks/default.json")
        findings=validate_playbooks(path)
        if args.playbook_command=="validate":
            return {"valid":not findings,"findings":findings,"system_actions_executed":False}
        if findings:
            return {"valid":False,"findings":findings,"system_actions_executed":False}
        events=_store(runtime,args.namespace).list_events(limit=1000)
        event=next((value for value in events if value.get("event_id")==args.event_id),None)
        if event is None:
            raise ValueError("event_not_found")
        return simulate(event,read_json(path,1024*1024))
    if args.command=="report":
        return export_report(runtime,args.namespace)
    raise ValueError("unknown_command")


def main(argv=None,root=None):
    args=parser().parse_args(argv)
    root=Path(root) if root else Path(__file__).resolve().parents[2]
    try:
        result=execute(args,Runtime(root))
        print(json.dumps(result,ensure_ascii=True,allow_nan=False))
        if isinstance(result,dict):
            if result.get("valid") is False or result.get("status") in {"invalid_request","invalid_playbooks","invalid_event","conflict"} or result.get("error_code") in {"invalid_request","process_instance_required","product_not_allowlisted"}:
                return 2
            if result.get("status")=="busy":
                return 3
            if result.get("status")=="error":
                return 4
            if result.get("status") in {"partial","denied","unknown","timeout"} or result.get("healthy") is False:
                return 5
        return 0
    except (ValueError,TypeError,json.JSONDecodeError):
        print(json.dumps({"status":"invalid_request","error_code":"input_or_config_validation_failed","raw_error_omitted":True}))
        return 2
    except Exception as error:
        print(json.dumps({"status":"error","error_code":"capacity_or_storage_failure" if type(error).__name__ in ("CapacityError","StoreError") else "operation_failed","raw_error_omitted":True}))
        return 4
