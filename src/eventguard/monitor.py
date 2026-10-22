"""Foreground headless scheduler. No service, model, external transport or daemon install."""
from __future__ import annotations
import copy
import os
from pathlib import Path
import threading
import time

from .runtime import Runtime, InstanceLock, read_json, utc_now, safe_child

SECTIONS = ("defender","listeners","processes","startup","services","tasks","versions")
SUCCESS = {"ok","not_applicable"}


class Monitor:
    def __init__(self, root, collectors=None, clock=time.monotonic, wait=None):
        self.runtime = Runtime(root)
        self.collectors = collectors
        self.clock = clock
        self.cancel = threading.Event()
        self.wait = wait or self.cancel.wait
        self.last = {}
        self.not_before = {}
        self.coverage = {key:{"status":"not_requested","last_success":None} for key in SECTIONS}

    def _load_fixture(self, relative):
        path = safe_child(self.runtime.root, relative)
        allowed = self.runtime.path("tests/fixtures")
        if not path.is_relative_to(allowed):
            raise ValueError("fixture_must_be_in_tests_fixtures")
        data = read_json(path, 1024*1024)
        frames = data.get("frames",[data]) if isinstance(data,dict) else []
        if not frames or len(frames)>100 or not all(isinstance(x,dict) and isinstance(x.get("sections"),list) for x in frames):
            raise ValueError("invalid_fixture")
        return frames

    @staticmethod
    def _own_low_priority():
        if os.name != "nt":
            return "platform_default"
        try:
            import ctypes
            kernel=ctypes.WinDLL("kernel32",use_last_error=True)
            kernel.GetCurrentProcess.restype=ctypes.c_void_p
            kernel.SetPriorityClass.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
            return "below_normal" if kernel.SetPriorityClass(kernel.GetCurrentProcess(),0x4000) else "unchanged"
        except (OSError,AttributeError):
            return "unchanged"

    def _finish(self,health,cycles,namespace):
        runner=getattr(self.collectors,"runner",None) if self.collectors else None
        if runner and runner.pending:
            health.update(state="stopping_pending_query",monitoring=False,heartbeat_at=utc_now(),cycles=cycles)
            try:
                self.runtime.save_health(health)
            except (OSError,ValueError):
                health["persistence_failure"]=True
            print('{"status":"stopping_pending_query","monitoring":false,"note":"Waiting for the existing read-only query to exit naturally; singleton lock remains held."}',flush=True)
            heartbeat=self.clock()
            while runner.pending:
                try:
                    time.sleep(.25)
                except KeyboardInterrupt:
                    pass
                if self.clock()-heartbeat>=30:
                    health["heartbeat_at"]=utc_now()
                    try:
                        self.runtime.save_health(health)
                    except (OSError,ValueError):
                        health["persistence_failure"]=True
                    heartbeat=self.clock()
        health.update(state="stopped",monitoring=False,stopped_at=utc_now(),heartbeat_at=utc_now(),cycles=cycles)
        self.runtime.save_health(health)
        self.runtime.log("monitor_stopped",{"namespace":namespace,"count":cycles})

    def run(self,max_cycles=None,fixture=None,fixture_interval=0.1,on_cycle=None):
        from .events.store import EventStore
        from .transport.adapters import DisabledAdapter
        from .rules.detector import evaluate
        if max_cycles is not None and (type(max_cycles) is not int or not 1<=max_cycles<=100000):
            raise ValueError("invalid_max_cycles")
        if fixture and (max_cycles is None or not 0.05<=fixture_interval<=5):
            raise ValueError("fixture_requires_bounded_cycles")
        config=self.runtime.config()
        namespace="test" if fixture else "live"
        frames=self._load_fixture(fixture) if fixture else None
        lock=InstanceLock(self.runtime)
        if not lock.acquire():
            return {"status":"busy","reason":"single_instance_lock_held","cycles":0}
        health={"state":"starting","monitoring":True,"namespace":namespace,"instance_id":lock.instance_id,
                "started_at":utc_now(),"heartbeat_at":utc_now(),"last_success":None,"last_attempt":None,
                "healthy":None,"coverage":copy.deepcopy(self.coverage),"real_agent_connected":False,
                "delivery":"unconfigured: local events only; no real agent ingress", "model_calls":0,"synthetic":bool(fixture),"cycles":0}
        cycles=0
        try:
            host_id=self.runtime.identity()
            if fixture:
                host_id="fixture-"+host_id
            limits=config.get("outbox",{})
            store=EventStore(self.runtime.data_dir(namespace),max_events=limits.get("max_events",1000),max_bytes=limits.get("max_bytes",8388608))
            state=store.load_detector_state()
            if self.collectors is None and not fixture:
                from .collectors.windows import WindowsCollectors
                self.collectors=WindowsCollectors()
            health["priority"]=self._own_low_priority()
            self.runtime.log("monitor_started",{"namespace":namespace,"instance_id":lock.instance_id})
            next_heartbeat=self.clock()
            while not self.cancel.is_set() and not lock.stop_requested():
                stamp=self.clock()
                due=list(SECTIONS) if fixture else [key for key in SECTIONS if stamp>=self.not_before.get(key,0) and (key not in self.last or stamp-self.last[key]>=config["interval_seconds"][key])]
                if due:
                    health["last_attempt"]=utc_now()
                    round_start=self.clock()
                    sections=[]
                    if fixture:
                        sections=copy.deepcopy(frames[min(cycles,len(frames)-1)]["sections"])
                    else:
                        for key in due:
                            if self.cancel.is_set() or lock.stop_requested():
                                self.cancel.set()
                                break
                            if self.clock()-round_start>=45:
                                section={"id":key,"status":"busy","rows":[],"observed_at":utc_now(),"coverage":{"status":"busy","reason":"round_budget"}}
                                self.not_before[key]=self.clock()+30
                            else:
                                self.last[key]=stamp
                                self.not_before.pop(key,None)
                                try:
                                    section=self.collectors.collect(key,cancel=self.cancel)
                                except Exception:
                                    section={"id":key,"status":"error","rows":[],"observed_at":utc_now(),"coverage":{"status":"error","reason":"collector_exception"}}
                            sections.append(section)
                    if self.cancel.is_set():
                        break
                    for section in sections:
                        key=section.get("id")
                        if key in self.coverage:
                            status=section.get("status","unknown")
                            old=self.coverage[key].get("last_success")
                            self.coverage[key]={"status":status,"observed_at":section.get("observed_at"),"last_success":utc_now() if status in SUCCESS else old}
                    try:
                        new_state,events=evaluate(sections,state,host_id=host_id,cooldown=config.get("cooldown_seconds",300))
                        for event in events:
                            event["synthetic"]=bool(fixture)
                        commit=store.commit_evaluation(new_state,events)
                        state=new_state
                        delivery=store.pump(DisabledAdapter())
                        health["last_event_count"]=len(events)
                        health["outbox"]=store.stats()
                        health["delivery_attempts_this_round"]=delivery.get("attempted",0)
                        health["healthy"]=all(value["status"] in SUCCESS for value in self.coverage.values())
                        health["last_error"]=None
                        if health["healthy"]:
                            health["last_success"]=utc_now()
                    except Exception as error:
                        # Leave the previous committed baseline intact for replay.
                        health["healthy"]=False
                        health["last_error"]="queue_capacity_or_storage_failure" if type(error).__name__ in ("CapacityError","StoreError") else "event_evaluation_failed"
                        self.runtime.log(health["last_error"],{"namespace":namespace})
                    cycles+=1
                    health.update(state="running",cycles=cycles,coverage=copy.deepcopy(self.coverage),heartbeat_at=utc_now())
                    self.runtime.save_health(health)
                    if on_cycle:
                        on_cycle(copy.deepcopy(health))
                    if max_cycles is not None and cycles>=max_cycles:
                        break
                    if fixture:
                        self.wait(fixture_interval)
                if self.clock()>=next_heartbeat:
                    health["heartbeat_at"]=utc_now()
                    self.runtime.save_health(health)
                    next_heartbeat=self.clock()+30
                self.wait(0.2 if fixture else 0.5)
        except KeyboardInterrupt:
            self.cancel.set()
        finally:
            self.cancel.set()
            try:
                self._finish(health,cycles,namespace)
            finally:
                lock.release()
        return health
