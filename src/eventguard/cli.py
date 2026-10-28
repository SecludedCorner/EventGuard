"""Typed local CLI. There is no shell-execution, remediation or external endpoint option."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from .runtime import Runtime, read_json
from .operations import OperatorAPI, store as _store, status, export_report


def parser():
    p=argparse.ArgumentParser(prog="eventguard",description="EventGuard 本機資安監看。run 啟動採集、事件頁與通知。")
    p.add_argument("--format",choices=("auto","json","text"),default="auto",
                   help="auto: 終端可讀文字、管線JSON；text: 人類摘要；json: 機器介面")
    sub=p.add_subparsers(dest="command",required=True)
    agents=sub.add_parser("agent",help="選配的事件派送。無事件不呼叫模型。預設只檢查。")
    agentsub=agents.add_subparsers(dest="agent_command",required=True)
    agent_start=agentsub.add_parser("start",help="檢查專用CLI派送。加--execute才啟動背景並允許模型。")
    agent_start.add_argument("--codex-executable",required=True,help="既有原生codex.exe；不接受包裝腳本")
    agent_start.add_argument("--namespace",choices=("live","test"),default="live")
    agent_start.add_argument("--execute",action="store_true")
    for action in ("status","pause","stop","resume","capabilities"):
        command=agentsub.add_parser(action)
        if action=="resume":
            command.add_argument("--execute",action="store_true",help="明確解除暫停，允許事件使用模型額度")
    for action in ("inspect","export"):
        command=agentsub.add_parser(action,help="唯讀投遞階段" if action=="inspect" else "唯讀匯出CloudEvents七欄封裝")
        command.add_argument("--event-id",required=True)
        command.add_argument("--namespace",choices=("live","test"),default="live")
        if action=="export":
            command.add_argument("--producer-id",required=True,help="不含主機或使用者資訊的固定UUID")
    intelligence=sub.add_parser("advisories",help="本機公告追蹤與靜態適用性比對。不呼叫模型。")
    intel_sub=intelligence.add_subparsers(dest="advisory_command",required=True)
    for action in ("start","check"):
        command=intel_sub.add_parser(action,help="手動啟動背景追蹤" if action=="start" else "只執行一輪擷取及比對")
        command.add_argument("--config",type=Path,help="專案config目錄內的設定檔")
    intel_sub.add_parser("status",help="來源新鮮度、待收事件、共用預算及進度")
    stop_intel=intel_sub.add_parser("stop",help="合作停止本工具的公告背景程序")
    stop_intel.add_argument("--grace-seconds",type=float,default=15)
    cases=intel_sub.add_parser("cases",help="查閱本機公告及適用性證據。不送給模型。")
    case_selector=cases.add_mutually_exclusive_group()
    case_selector.add_argument("--case-id")
    case_selector.add_argument("--event-id")
    host=intel_sub.add_parser("_serve",help=argparse.SUPPRESS)
    host.add_argument("--host-root",type=Path,required=True)
    host.add_argument("--run-id",required=True)
    host.add_argument("--job-name",required=True)
    run=sub.add_parser("run",help="前景啟動採集、本機Web與通知。按Ctrl+C停止。不呼叫模型。")
    run.add_argument("--port",type=int,default=8765)
    run.add_argument("--max-seconds",type=float,help="選填。有限試跑秒數（1..3600）。")
    run.add_argument("--fixture",help="選填。只讀tests/fixtures合成資料。")
    run.add_argument("--max-cycles",type=int,help="fixture必填。限制合成採集輪數。")
    run.add_argument("--no-notifications",action="store_true",help="關閉系統通知。本機頁面仍顯示高嚴重度事件。")
    run.add_argument("--idle",action="store_true",help="只開控制介面。等待明確開始採集。")
    run.add_argument("--no-mcp",action="store_true",help="不開選配MCP listener。Web仍可使用。")
    run.add_argument("--event-source",type=Path,help="選填。綁定專案內既有的合成事件source；需--fixture與--idle，不採集、不通知。")
    application=sub.add_parser("app",help="操作已啟動的同一個 App。未啟動時回報 blocked，不建立新程序。")
    appsub=application.add_subparsers(dest="app_command",required=True)
    for action in ("status","start","pause","resume","stop","shutdown"):
        command=appsub.add_parser(action,help="關閉 App" if action=="shutdown" else "只操作 App 的採集狀態")
        command.add_argument("--namespace",choices=("live","test"),default="live")
        if action!="status":
            command.add_argument("--operation-id",help="選填。重送相同操作時沿用此識別。")
    mcp=sub.add_parser("mcp",help="本機應用MCP observer。只連既有 App。斷線不關 App。不呼叫模型。")
    mcp.add_argument("--allow-live",action="store_true",help="明確允許正式資料範圍。不會自動採集。")
    mcp.add_argument("--fixture",help="只用tests/fixtures合成資料。")
    mcp.add_argument("--max-cycles",type=int,help=argparse.SUPPRESS)
    mcp.add_argument("--port",type=int,default=0,help=argparse.SUPPRESS)
    mcp.add_argument("--max-seconds",type=float,help=argparse.SUPPRESS)
    sub.add_parser("capabilities")
    sub.add_parser("status")
    activity=sub.add_parser("activity",help="查看EventGuard操作進度與歷史；不啟動採集或模型")
    activity.add_argument("--namespace",choices=("live","test"),default="live")
    activity.add_argument("--limit",type=int,default=100)
    background=sub.add_parser("background",help="長期背景唯讀監看；無模型、耐久手動停止")
    backgroundsub=background.add_subparsers(dest="background_command",required=True)
    backgroundsub.add_parser("start",help="明確啟用並啟動；不建立排程或啟動模型")
    backgroundsub.add_parser("status",help="核對背景 owner、心跳與保存的啟停意圖")
    background_stop=backgroundsub.add_parser("stop",help="耐久停用背景與合作停止；不碰其他程序")
    background_stop.add_argument("--grace-seconds",type=float,default=10)
    background_serve=backgroundsub.add_parser("serve",help="供已批准排程同步執行；只恢復已明確啟用的監看")
    background_serve.add_argument("--fixture",help=argparse.SUPPRESS)
    background_serve.add_argument("--max-cycles",type=int,help=argparse.SUPPRESS)
    background_host=backgroundsub.add_parser("_serve",help=argparse.SUPPRESS)
    background_host.add_argument("--host-root",type=Path,required=True)
    background_host.add_argument("--run-id",required=True)
    background_host.add_argument("--job-name",required=True)
    background_host.add_argument("--fixture",help=argparse.SUPPRESS)
    background_host.add_argument("--max-cycles",type=int,help=argparse.SUPPRESS)
    overview=sub.add_parser("overview",help="監看、來源與事件的操作總覽；不重掃")
    overview.add_argument("--namespace",choices=("live","test"),default="live")
    overview.add_argument("--limit",type=int,default=20)
    sources=sub.add_parser("sources",help="查看已保存的七來源觀察；不重新查Windows")
    sourcesub=sources.add_subparsers(dest="source_command",required=True)
    source_list=sourcesub.add_parser("list")
    source_list.add_argument("--namespace",choices=("live","test"),default="live")
    source_show=sourcesub.add_parser("show")
    source_show.add_argument("--namespace",choices=("live","test"),default="live")
    source_show.add_argument("--source-id",choices=("defender","listeners","processes","startup","services","tasks","versions"),required=True)
    source_show.add_argument("--limit",type=int,default=20)
    budget=sub.add_parser("budget",help="本安裝共用耐久預算；不啟動模型")
    budgetsub=budget.add_subparsers(dest="budget_command",required=True)
    budgetsub.add_parser("status")
    initialize=budgetsub.add_parser("initialize",help="明示一次初始化；未知當日用量會阻擋當日")
    initialize.add_argument("--known-used",type=int,choices=range(6),default=None,
                            help="僅限已核實的當日受管用量；不會查私人 sessions")
    reconcile=budgetsub.add_parser("reconcile",help="以已保存且匹配的 Job 退出回條解除未解閘道")
    reconcile.add_argument("--attempt-dir",type=Path,required=True)
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
    listing.add_argument("--offset",type=int,default=0)
    listing.add_argument("--severity",choices=("info","warning","high","critical"))
    listing.add_argument("--source",choices=("defender","listeners","processes","startup","services","tasks","versions","monitor","advisories","unknown"))
    listing.add_argument("--status",choices=("new","read","handled","ignored"))
    listing.add_argument("--event-source",type=Path,help="選填。test範圍內既有的合成事件source。")
    detail=eventsub.add_parser("detail",help="查看事件詳情與處置狀態。不採集、不ACK。")
    detail.add_argument("--namespace",choices=("live","test"),default="live")
    detail.add_argument("--event-id",required=True)
    detail.add_argument("--event-source",type=Path,help="選填。test範圍內既有的合成事件source。")
    investigation=eventsub.add_parser("investigate",help="保存既有metadata的關聯時間線；不採集、不呼叫模型、不ACK。")
    investigation.add_argument("--namespace",choices=("live","test"),default="live")
    investigation.add_argument("--event-id",required=True)
    investigation.add_argument("--event-source",type=Path)
    handling=eventsub.add_parser("set-status",help="保存處置狀態。不ACK、不修改系統。")
    handling.add_argument("--namespace",choices=("live","test"),default="live")
    handling.add_argument("--event-id",required=True)
    handling.add_argument("--status",choices=("new","read","handled","ignored"),required=True)
    handling.add_argument("--event-source",type=Path,help="選填。test範圍內既有的合成事件source。")
    history_backup=eventsub.add_parser("backup-history",help="明確保存歷程快照到 reports；不清理、不 ACK。")
    history_backup.add_argument("--namespace",choices=("live","test"),default="live")
    history_backup.add_argument("--name",required=True,help="history-backup-<名稱>.json；已有檔案不覆寫")
    history_backup.add_argument("--event-source",type=Path,help="選填。僅 test 範圍既有合成事件 source。")
    history_preview=eventsub.add_parser("preview-history",help="從標準輸入唯讀預檢備份身分；不還原、不刪除。")
    history_preview.add_argument("--namespace",choices=("live","test"),default="live")
    history_preview.add_argument("--event-source",type=Path,help="選填。僅 test 範圍既有合成事件 source。")
    rules=sub.add_parser("rules",help="查看或檢查config/rules.json。不採集。")
    rules.add_argument("action",choices=("list","validate"),default="list",nargs="?")
    for name in ("inspect", "diagnose", "receive", "retry"):
        event_operation=eventsub.add_parser(name,help="查看已存事件／明確執行事件綁定唯讀查證；不 ACK")
        event_operation.add_argument("--namespace",choices=("live","test"),default="live")
        event_operation.add_argument("--event-id",required=True)
    acknowledge=eventsub.add_parser("ack",help="確認同event/query已收到；不是修補或結案")
    acknowledge.add_argument("--namespace",choices=("live","test"),default="live")
    acknowledge.add_argument("--event-id",required=True)
    acknowledge.add_argument("--query-id",required=True)
    acknowledge.add_argument("--decision",choices=("reviewed_metadata","needs_more_evidence"),default="reviewed_metadata")
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


def execute(args,runtime,progress=None):
    if args.command=="app":
        from .application_host import RemoteApplication
        application=RemoteApplication(runtime.root,args.namespace)
        if args.app_command=="status":
            return application.status()
        import uuid
        return application.monitor_control(args.app_command,source="cli",
            operation_id=args.operation_id if args.operation_id is not None else uuid.uuid4().hex)
    if args.command=="agent":
        from . import agent_service, event_ingress
        action=args.agent_command
        if action=="start":
            return agent_service.start(runtime.root,codex_executable=args.codex_executable,
                                       allow_live=args.namespace=="live",execute=args.execute)
        if action=="resume":
            return agent_service.resume(runtime.root,execute=args.execute)
        if action in {"status","pause","stop"}:
            return getattr(agent_service,action)(runtime.root)
        if action=="capabilities":
            return event_ingress.capabilities()
        source=runtime.path("data/"+args.namespace)
        inbox=runtime.path("data/agent-delivery" if args.namespace=="live" else "data/agent-delivery-test")
        if action=="export":
            return event_ingress.export_event(source,inbox,args.event_id,
                allow_live=args.namespace=="live",producer_id=args.producer_id)
        return event_ingress.inspect_delivery(source,inbox,args.event_id,allow_live=args.namespace=="live",root=runtime.root)
    if args.command=="advisories":
        from .intelligence import engine, service
        if args.advisory_command=="start":
            return service.start(runtime.root,args.config)
        if args.advisory_command=="status":
            return service.status(runtime.root)
        if args.advisory_command=="stop":
            return service.stop(runtime.root,grace_seconds=args.grace_seconds)
        if args.advisory_command=="check":
            return engine.cycle(runtime.root,args.config)
        if args.advisory_command=="_serve":
            return service.serve(args.host_root,args.run_id,args.job_name)
        from .intelligence.store import IntelligenceStore
        path=runtime.path("data/advisories/intelligence.sqlite3")
        if not path.exists():
            return {"cases":[],"state":"not_started","model_calls":0}
        store=IntelligenceStore(path,readonly=True)
        if args.event_id:
            return store.event_case(args.event_id) or {"state":"unknown","reason":"event_case_not_found"}
        return store.advisory(args.case_id) if args.case_id else {"cases":store.cases(),"model_calls":0}
    operator=OperatorAPI(runtime.root)
    if args.command=="run":
        if not args.fixture and args.max_cycles is not None:
            raise ValueError("max_cycles_requires_fixture")
        from .application import run
        return run(runtime.root,port=args.port,fixture=args.fixture,max_cycles=args.max_cycles,
                   notifications=not args.no_notifications and args.event_source is None,max_seconds=args.max_seconds,
                   auto_start=not args.idle,mcp_enabled=not args.no_mcp,event_source=args.event_source)
    if args.command=="rules":
        from .rules.configured import load_rules
        values=load_rules(runtime.root)
        return {"rules":values,"valid":True,"model_calls":0,"config_file":"config/rules.json"}
    if args.command=="background":
        if args.background_command=="start":
            return operator.call("background_start")
        if args.background_command=="status":
            return operator.call("background_status")
        if args.background_command=="stop":
            return operator.call("background_stop",args.grace_seconds)
        from . import background
        options={"fixture":args.fixture,"max_cycles":args.max_cycles}
        if args.background_command=="_serve":
            return background.serve(args.host_root,run_id=args.run_id,job_name=args.job_name,**options)
        return background.serve(runtime.root,**options)
    if args.command=="budget":
        from .agent_budget import BudgetAuthority, BudgetError, public_status
        try:
            if args.budget_command=="status":
                return public_status()
            if args.budget_command=="initialize":
                return BudgetAuthority().initialize(known_used=args.known_used)
            from .acceptance_control import read_json as read_receipt
            from .local_paths import _guard
            directory=_guard(args.attempt_dir)
            installation=Path(__file__).resolve().parents[2]
            if not any(directory.is_relative_to(installation/name) for name in ("data","logs","reports")):
                raise ValueError("owned_evidence_directory_required")
            started=read_receipt(directory/"capture-start.json")
            receipt=read_receipt(directory/"capture-exit.json")
            return BudgetAuthority.open_existing().finalize(started["attempt_id"],receipt,started)
        except BudgetError as error:
            return {"status":"error","state":"blocked","reason":error.code,"model_started":False}
    if args.command=="capabilities":
        return operator.call("capabilities")
    if args.command=="status":
        return operator.call("status")
    if args.command=="activity":
        return operator.call("activity",args.namespace,args.limit)
    if args.command=="overview":
        return operator.call("overview",args.namespace,args.limit)
    if args.command=="sources":
        if args.source_command=="list":
            from .source_status import source_status
            return source_status(runtime.root,args.namespace)
        return operator.call("observation",args.source_id,args.namespace,args.limit)
    if args.command=="stop":
        return operator.call("stop",args.namespace)
    if args.command=="monitor":
        return operator.call("monitor",max_cycles=args.max_cycles,fixture=args.fixture,fixture_interval=args.fixture_interval,
                             max_seconds=args.max_seconds,on_progress=progress)
    if args.command=="query":
        if len(args.args.encode("utf-8"))>8192:
            raise ValueError("query_input_limit")
        values=json.loads(args.args)
        if not isinstance(values,dict):
            raise ValueError("query_args_must_be_object")
        from .diagnostics.api import DiagnosticAPI
        return DiagnosticAPI(query_admission=runtime.query_launch).query(args.operation,values)
    if args.command=="events":
        if args.event_command in {"list","detail","set-status","investigate","backup-history","preview-history"}:
            from .events.catalog import EventCatalog
            catalog=EventCatalog(runtime.root,args.namespace,directory=args.event_source)
            if args.event_command=="list":
                return catalog.list(severity=args.severity,source=args.source,status=args.status,
                                    limit=args.limit,offset=args.offset)
            if args.event_command=="detail":
                return catalog.detail(args.event_id)
            if args.event_command=="investigate":
                return catalog.investigate(args.event_id)
            if args.event_command=="backup-history":
                from .events.disposition_history_backup_file import write_backup
                return write_backup(runtime.root,args.name,catalog.handling_history_snapshot())
            if args.event_command=="preview-history":
                from .events.disposition_history_backup import MAX_EXPORT_BYTES
                stream=getattr(sys.stdin,"buffer",sys.stdin)
                if stream.isatty():
                    raise ValueError("history_backup_stdin_required")
                content=stream.read(MAX_EXPORT_BYTES+1025)
                if len(content)>MAX_EXPORT_BYTES+1024:
                    raise ValueError("history_backup_bytes_limit")
                return catalog.preview_handling_history(json.loads(content))
            return catalog.set_status(args.event_id,args.status,source="cli")
        if args.event_command=="receive":
            return operator.call("receive_event",args.event_id,args.namespace)
        if args.event_command=="ack":
            return operator.call("ack_event",args.event_id,args.query_id,args.decision,args.namespace)
        if args.event_command=="retry":
            return operator.call("retry_event",args.event_id,args.namespace)
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


def _format_args(argv):
    # Accept this presentation option before or after a subcommand. There is no
    # shell interpretation or arbitrary command tail in this CLI.
    values=list(sys.argv[1:] if argv is None else argv)
    options,remaining=[],[]
    i=0
    while i<len(values):
        value=values[i]
        if value=="--format" and i+1<len(values):
            options=["--format",values[i+1]]
            i+=2
        elif value.startswith("--format="):
            options=[value]
            i+=1
        else:
            remaining.append(value)
            i+=1
    return options+remaining


def main(argv=None,root=None):
    # Windows pipes otherwise inherit the locale code page. Keep CLI text and
    # redirected startup messages UTF-8. Native console streams retain their
    # normal Unicode console handling; in-memory test streams stay injectable.
    for stream in (sys.stdout,sys.stderr):
        if stream is not None and hasattr(stream,"reconfigure") and not stream.isatty():
            stream.reconfigure(encoding="utf-8",errors="backslashreplace")
    args=parser().parse_args(_format_args(argv))
    root=Path(root) if root else Path(__file__).resolve().parents[2]
    if args.command=="mcp":
        # stdout belongs exclusively to MCP JSON-RPC, including startup failure.
        try:
            if not args.fixture and args.max_cycles is not None:
                raise ValueError("max_cycles_requires_fixture")
            from .application_host import serve_stdio
            return serve_stdio(root,allow_live=args.allow_live,fixture=args.fixture,
                max_cycles=args.max_cycles,port=args.port,max_seconds=args.max_seconds)
        except (OSError,ValueError,TypeError,RuntimeError,ImportError):
            if sys.stderr is not None:
                print("EventGuard MCP: startup_or_shutdown_unconfirmed",file=sys.stderr,flush=True)
            return 4
    human=args.format=="text" or args.format=="auto" and bool(getattr(sys.stdout,"isatty",lambda:False)())
    def show(value):
        if sys.stdout is None:  # Existing pythonw.exe scheduled/background host.
            return  # Structured status/exit receipts are persisted by its owner.
        if human:
            from .presentation import render
            operation=getattr(args,"app_command",getattr(args,"agent_command",getattr(args,"background_command",getattr(args,"event_command",getattr(args,"source_command","")))))
            print(render(value,args.command,operation))
        else:
            print(json.dumps(value,ensure_ascii=True,allow_nan=False))
    try:
        from .presentation import ProgressPrinter
        result=execute(args,Runtime(root),ProgressPrinter(sys.stderr) if human and args.command=="monitor" else None)
        show(result)
        if isinstance(result,dict):
            if args.command in {"app","background","run","advisories","agent"} or args.command=="stop" and "desired_enabled" in result:
                state=result.get("state")
                if state=="busy":
                    return 3
                if state in {"blocked","startup_failed","stop_not_persisted","conflict"}:
                    return 2
                if state in {"unknown","shutdown_unconfirmed"}:
                    return 5
                if args.command=="advisories" and state in {"partial","error"}:
                    return 5
            if result.get("valid") is False or result.get("status") in {"invalid_request","invalid_playbooks","invalid_event","conflict"} or result.get("error_code") in {"invalid_request","process_instance_required","product_not_allowlisted"}:
                return 2
            if result.get("status")=="busy":
                return 3
            if result.get("status")=="blocked":
                return 3 if "busy" in str(result.get("reason","")) else 2
            if result.get("status")=="error":
                return 4
            if result.get("status") in {"partial","denied","unknown","timeout"} or result.get("healthy") is False:
                return 5
        return 0
    except (ValueError,TypeError,json.JSONDecodeError) as error:
        from .rules.configured import RulesValidationError
        from .event_ingress import EventIngressError
        if isinstance(error,EventIngressError):
            show({"status":"invalid_request","error_code":str(error),"raw_error_omitted":True})
            return 2
        if isinstance(error,RulesValidationError):
            show({"status":"invalid_request","error_code":str(error),"config_file":"config/rules.json"})
            return 2
        show({"status":"invalid_request","error_code":"input_or_config_validation_failed","raw_error_omitted":True})
        return 2
    except Exception as error:
        show({"status":"error","error_code":"capacity_or_storage_failure" if type(error).__name__ in ("CapacityError","StoreError") else "operation_failed","raw_error_omitted":True})
        return 4
