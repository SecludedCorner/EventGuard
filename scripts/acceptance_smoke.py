"""Finite, synthetic CLI contract and cross-process cooperative-stop checks."""
from datetime import datetime,timezone
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"src"))
from eventguard.cli import main
from eventguard.events.store import EventStore


def call(root,*args):
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):
        code=main(list(args),root=root)
    value=json.loads(stream.getvalue())
    if code:
        raise AssertionError({"arguments":args,"exit":code,"result":value})
    return value


def main_smoke():
    steps=[]
    with tempfile.TemporaryDirectory(prefix="eventguard-smoke-") as directory:
        root=Path(directory)
        for relative in ("config/default.json","playbooks/default.json","tests/fixtures/normal.json"):
            target=root/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/relative,target)
        normal=call(root,"monitor","--fixture","tests/fixtures/normal.json","--max-cycles","2","--fixture-interval","0.05")
        assert normal["last_event_count"]==0 and normal["outbox"]["total"]==0
        steps.append({"step":"normal_monitor","cycles":2,"new_events":0,"model_calls":0,"stopped":not normal["monitoring"]})
        event=call(root,"synthetic","emit","--scenario","listener")
        event_id=event["event_id"]
        steps.append({"step":"persisted","event_id":event_id,"namespace":"test"})
        disabled=call(root,"deliver","--adapter","disabled","--namespace","test")
        assert disabled["delivery"]["attempted"]==0
        steps.append({"step":"disabled_adapter","attempted":0})
        delivered=call(root,"deliver","--adapter","mock")
        assert delivered["delivery"]["acknowledged"]==1
        steps.append({"step":"local_mock_receiver_ack","event_id":event_id,"acknowledged":1,"real_agent_woken":False})
        plan=call(root,"playbook","simulate","--event-id",event_id,"--namespace","test")
        assert plan["status"]=="planned" and not plan["authorization_granted"]
        processed=call(root,"mock","process","--event-id",event_id)
        assert processed["case_state"]=="mock_closed" and processed["agent_processed"] is False
        steps.append({"step":"mock_diagnosis_and_closure","event_id":event_id,"case_id":processed["case_id"],"case_state":processed["case_state"],"real_agent_woken":False,"system_actions_executed":[]})
        repeated=call(root,"mock","process","--event-id",event_id)
        assert repeated["case_id"]==processed["case_id"]
        assert call(root,"deliver","--adapter","mock")["delivery"]["attempted"]==0
        assert EventStore(root/"data/test").get_event(event_id)["delivery_status"]=="ack"
        report=call(root,"report","export","--namespace","test")
        assert Path(report["json"]).is_file() and Path(report["html"]).is_file()
        assert not (root/"data/live").exists()
        steps.append({"step":"restart_dedup_and_exports","duplicate_delivery_attempts":0,"live_namespace_created":False,"json_html_written":True})

        # Actual separate CLI processes, still only a copied synthetic fixture.
        # Temporary project imports the tested source; no system collection runs.
        wrapper=root/"run.py"
        wrapper.write_text("import sys\nfrom pathlib import Path\nsys.path.insert(0,"+repr(str(ROOT/"src"))+")\nfrom eventguard.cli import main\nraise SystemExit(main(root=Path(__file__).parent))\n",encoding="utf-8")
        flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        child=subprocess.Popen([sys.executable,"-B",str(wrapper),"monitor","--fixture","tests/fixtures/normal.json","--max-cycles","12","--fixture-interval","0.1"],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
        deadline=time.monotonic()+5
        while not (root/"data/monitor-owner.json").exists() and child.poll() is None and time.monotonic()<deadline:
            time.sleep(.02)
        second=subprocess.Popen([sys.executable,"-B",str(wrapper),"monitor","--fixture","tests/fixtures/normal.json","--max-cycles","1"],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
        second_out,second_err=second.communicate(timeout=10)
        assert second.returncode==3,(second.returncode,second_out,second_err)
        stop=call(root,"stop")
        assert stop["status"]=="stop_requested"
        stdout,stderr=child.communicate(timeout=15)
        assert child.returncode==0,(child.returncode,stdout,stderr)
        stopped=json.loads(stdout.decode("utf-8"))
        assert stopped["state"]=="stopped" and not (root/"data/monitor-owner.json").exists()
        steps.append({"step":"cross_process_singleton_and_stop","second_exit":3,"first_exit":0,"stop":"cooperative","child_exited":child.poll() is not None,"process_signal_sent":False})
    summary={"verified_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),"passed":True,"steps":steps,
             "machine_scan_executed":False,"external_transport":False,"model_calls":0,"real_agent_woken":False,
             "remaining_test_processes":0,"note":"Local synthetic receiver contract only; no actual Codex/dot ingress was exercised."}
    (ROOT/"reports").mkdir(exist_ok=True)
    (ROOT/"reports/acceptance-smoke.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary))


if __name__=="__main__":
    main_smoke()
