"""Typed local CLI. There is no shell-execution, remediation or external endpoint option."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from .runtime import Runtime, read_json
from .operations import OperatorAPI, store as _store, status, export_report


def parser():
    p=argparse.ArgumentParser(prog="eventguard",description="EventGuard 本機唯讀 headless 監看；有界 agent 接線另用 eventguard_watch.py")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("capabilities")
    sub.add_parser("status")
    stopping=sub.add_parser("stop")
    stopping.add_argument("--namespace",choices=("live","test"),help="選填：只停止該 namespace 的已核對 monitor")
    monitor=sub.add_parser("monitor",help="前景持續監看；Ctrl+C 或另一終端 stop")
    monitor.add_argument("--max-cycles",type=int)
    monitor.add_argument("--max-seconds",type=int,help="停止後續採集的總秒數（1..3600）；本工具 Job 先寬限再有界清理；未確認退出會明示")
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
    for name in ("inspect", "diagnose"):
        event_operation=eventsub.add_parser(name,help="查看已存事件／明確執行事件綁定唯讀查證；不 ACK")
        event_operation.add_argument("--namespace",choices=("live","test"),default="live")
        event_operation.add_argument("--event-id",required=True)
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


def execute(args,runtime):
    operator=OperatorAPI(runtime.root)
    if args.command=="capabilities":
        return operator.call("capabilities")
    if args.command=="status":
        return operator.call("status")
    if args.command=="stop":
        return operator.call("stop",args.namespace)
    if args.command=="monitor":
        return operator.call("monitor",max_cycles=args.max_cycles,fixture=args.fixture,fixture_interval=args.fixture_interval,max_seconds=args.max_seconds)
    if args.command=="query":
        if len(args.args.encode("utf-8"))>8192:
            raise ValueError("query_input_limit")
        values=json.loads(args.args)
        if not isinstance(values,dict):
            raise ValueError("query_args_must_be_object")
        from .diagnostics.api import DiagnosticAPI
        return DiagnosticAPI().query(args.operation,values)
    if args.command=="events":
        if args.event_command=="inspect":
            return operator.call("inspect_event",args.event_id,args.namespace)
        if args.event_command=="diagnose":
            return operator.call("diagnose_event",args.event_id,args.namespace)
        return operator.call("events",args.namespace,args.limit)
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
        return operator.call("report",args.namespace)
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
