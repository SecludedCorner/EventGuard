"""Foreground headless scheduler. No service, model, external transport or daemon install."""
from __future__ import annotations
import copy
import math
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
        self._on_progress = None

    def _publish(self, health, phase=None, source_id=None, **progress):
        if phase is not None:
            previous = health.get("progress", {})
            health["progress"] = {**previous, **progress, "phase": phase, "source_id": source_id,
                                  "updated_at": utc_now()}
        health["heartbeat_at"] = utc_now()
        health["coverage"] = copy.deepcopy(self.coverage)
        self.runtime.save_health(health)
        if self._on_progress is not None:
            try:
                self._on_progress(copy.deepcopy(health))
            except Exception:
                # Display callbacks cannot turn a completed observation into a failure.
                health["progress_observer_failed"] = True

    def _collect(self, source_id, cancel, progress):
        """Adapt old injected collectors once, without retrying after TypeError."""
        from .collectors.progress import invoke_with_progress
        return invoke_with_progress(self.collectors.collect, source_id, cancel=cancel, progress=progress)

    def _record(self, section, health, namespace, instance_id):
        from .collectors.windows import coverage_metadata
        key = section.get("id")
        if key not in self.coverage:
            raise ValueError("invalid_section_identity")
        status = section.get("status", "unknown")
        rows = section.get("rows", [])
        old = self.coverage[key]
        duration = section.get("elapsed_ms")
        self.coverage[key] = {**coverage_metadata(section), "status": status,
                              "observed_at": section.get("observed_at"),
                              "last_success": utc_now() if status in SUCCESS else old.get("last_success"),
                              "row_count": len(rows), "usable_row_count": sum(
                                  row.get("status") in ("ok", "partial") and any(
                                      value is not None for field, value in row.items() if field != "status") for row in rows),
                              "elapsed_ms": duration if type(duration) is int and duration >= 0 else None,
                              "observation_saved": False, "last_persisted_at": old.get("last_persisted_at"),
                              "evaluation_status": "not_evaluated"}
        health["healthy"] = (all(value["status"] in SUCCESS for value in self.coverage.values())
                             and not health.get("persistence_failure", False))
        try:
            saved = self.runtime.save_observation(section, namespace, instance_id)
            self.coverage[key].update(observation_saved=True, last_persisted_at=saved["saved_at"],
                                      saved_row_count=saved["exported"], observation_truncated=saved["truncated"])
        except (OSError, ValueError, TypeError):
            health.update(healthy=False, last_error="observation_persistence_failed", persistence_failure=True)
            self.coverage[key]["observation_error"] = "observation_persistence_failed"

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
        if runner and getattr(runner, "last_process", None):
            health["query_shutdown"] = runner.last_process
        if health.get("state") in {"blocked_monitor_gap", "blocked_previous_query"}:
            health.update(monitoring=False, healthy=False)
            self._publish(health, "blocked", cycle=cycles)
            return

        def unconfirmed(reason=None):
            health.update(state="shutdown_unconfirmed", monitoring=False, healthy=False)
            if reason:
                health["last_error"] = reason
            # Persist the barrier before releasing the singleton or returning.
            health["monitor_shutdown_gate"] = self.runtime.block_monitor_shutdown(health)
            self._publish(health, "stopping", cycle=cycles)
        if runner and runner.pending:
            health.update(state="stopping_pending_query",monitoring=False,heartbeat_at=utc_now(),cycles=cycles)
            try:
                self._publish(health, "stopping", cycle=cycles)
            except (OSError,ValueError):
                health["persistence_failure"]=True
            heartbeat=self.clock()
            if hasattr(runner, "shutdown"):
                try:
                    receipt = runner.shutdown()
                except (OSError, ValueError, RuntimeError):
                    unconfirmed("owned_query_shutdown_failed")
                    return
                health["query_shutdown"] = receipt
                if receipt.get("managed"):
                    if receipt.get("child_exited") is not True or type(receipt.get("remaining_owned_processes")) is not int or receipt["remaining_owned_processes"] != 0:
                        unconfirmed()
                        return
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
        receipt = health.get("query_shutdown", {})
        if receipt.get("managed") and (receipt.get("child_exited") is not True or type(receipt.get("remaining_owned_processes")) is not int or receipt["remaining_owned_processes"] != 0):
            unconfirmed()
            return
        health.update(state="stopped",monitoring=False,stopped_at=utc_now(),heartbeat_at=utc_now(),cycles=cycles)
        self._publish(health, "stopped", cycle=cycles)
        self.runtime.log("monitor_stopped",{"namespace":namespace,"count":cycles})

    def run(self,max_cycles=None,fixture=None,fixture_interval=0.1,on_cycle=None,max_seconds=None,deadline_monotonic=None,on_progress=None):
        from .events.store import EventStore
        from .transport.adapters import DisabledAdapter
        from .rules.detector import evaluate
        if max_cycles is not None and (type(max_cycles) is not int or not 1<=max_cycles<=100000):
            raise ValueError("invalid_max_cycles")
        if max_seconds is not None and (type(max_seconds) not in (int,float)
                or not math.isfinite(max_seconds) or not 1<=max_seconds<=3600):
            raise ValueError("invalid_max_seconds")
        deadline=self.clock()+max_seconds if max_seconds is not None else None
        if deadline_monotonic is not None:
            if type(deadline_monotonic) not in (int,float) or not math.isfinite(deadline_monotonic):
                raise ValueError("invalid_deadline")
            deadline=min(deadline,deadline_monotonic) if deadline is not None else deadline_monotonic
        if fixture and (max_cycles is None or not 0.05<=fixture_interval<=5):
            raise ValueError("fixture_requires_bounded_cycles")
        config=self.runtime.config()
        self._on_progress = on_progress
        namespace="test" if fixture else "live"
        frames=self._load_fixture(fixture) if fixture else None
        lock=InstanceLock(self.runtime)
        if not lock.acquire():
            return {"status":"busy","reason":"single_instance_lock_held","cycles":0}
        health={"state":"starting","monitoring":True,"namespace":namespace,"instance_id":lock.instance_id,
                "pid":os.getpid(), "process_created_at":lock.process_identity.get("created_at") if lock.process_identity else None,
                "started_at":utc_now(),"heartbeat_at":utc_now(),"last_success":None,"last_attempt":None,
                "healthy":None,"coverage":copy.deepcopy(self.coverage),"real_agent_connected":False,
                "delivery":"unconfigured: local events only; no real agent ingress", "model_calls":0,"synthetic":bool(fixture),"cycles":0,
                "progress":{"phase":"starting","source_id":None,"cycle":0,"completed_sources":[],"due_sources":[],
                            "started_at":utc_now(),"updated_at":utc_now(),"elapsed_ms":0}}
        if max_seconds is not None:
            health["max_seconds"]=max_seconds
        cycles=0
        try:
            previous_query = self.runtime.monitor_shutdown_gate(recover=True)
            health["monitor_shutdown_gate"] = previous_query
            if previous_query.get("state") != "clear":
                health.update(state="blocked_previous_query", monitoring=False, healthy=False,
                              last_error=previous_query.get("reason", "previous_query_exit_unconfirmed"))
                return health
            host_id=self.runtime.identity()
            if fixture:
                host_id="fixture-"+host_id
            limits=config.get("outbox",{})
            store=EventStore(self.runtime.data_dir(namespace), **limits)
            store.maintain()
            try:
                from .monitor_gap import persist
                health["monitor_gap"] = persist(self.runtime, namespace, host_id, store)
            except (OSError, ValueError, RuntimeError) as error:
                health.update(state="blocked_monitor_gap", healthy=False, last_error="monitor_gap_persistence_failed")
                return health
            self._publish(health, "starting", cycle=0)
            monitor = self
            class QueryCancel:
                def is_set(self):
                    return monitor.cancel.is_set() or lock.stop_requested() or (deadline is not None and monitor.clock() >= deadline)
            query_cancel = QueryCancel()
            state=store.load_detector_state()
            if self.collectors is None and not fixture:
                from .collectors.windows import WindowsCollectors
                self.collectors=WindowsCollectors(timeout=config.get("query_timeout_seconds",15))
            health["priority"]=self._own_low_priority()
            self.runtime.log("monitor_started",{"namespace":namespace,"instance_id":lock.instance_id})
            next_heartbeat=self.clock()
            while not self.cancel.is_set() and not lock.stop_requested():
                stamp=self.clock()
                if deadline is not None and stamp>=deadline:
                    health["stop_reason"]="duration_limit"
                    break
                due=list(SECTIONS) if fixture else [key for key in SECTIONS if stamp>=self.not_before.get(key,0) and (key not in self.last or stamp-self.last[key]>=config["interval_seconds"][key])]
                if due:
                    health["last_attempt"]=utc_now()
                    round_start=self.clock()
                    duration_limit=False
                    health["last_event_count"] = 0
                    health["state"] = "running"
                    evaluation_blocked = False
                    completed = []
                    fixture_sections = copy.deepcopy(frames[min(cycles,len(frames)-1)]["sections"]) if fixture else None
                    selected = [item.get("id") for item in fixture_sections] if fixture else due
                    self._publish(health, "collecting", cycle=cycles+1, due_sources=selected,
                                  completed_sources=[], started_at=utc_now(), elapsed_ms=0)

                    def commit_section(section):
                        nonlocal state, evaluation_blocked
                        self._record(section, health, namespace, lock.instance_id)
                        key = section["id"]
                        if not evaluation_blocked:
                            try:
                                new_state, events = evaluate([section], state, host_id=host_id,
                                                             cooldown=config.get("cooldown_seconds", 300))
                                for event in events:
                                    event["synthetic"] = bool(fixture)
                                store.commit_evaluation(new_state, events)
                                state = new_state
                                delivery = store.pump(DisabledAdapter())
                                health["last_event_count"] += len(events)
                                health["outbox"] = store.stats()
                                health["delivery_attempts_this_round"] = delivery.get("attempted", 0)
                                self.coverage[key]["evaluation_status"] = "committed"
                            except Exception as error:
                                # Preserve this baseline for replay, and do not let another
                                # section mask a failed transaction with a later success.
                                evaluation_blocked = True
                                health["healthy"] = False
                                health["last_error"] = ("queue_capacity_or_storage_failure" if
                                    type(error).__name__ in ("CapacityError", "StoreError") else "event_evaluation_failed")
                                self.runtime.log(health["last_error"], {"namespace": namespace})
                        if evaluation_blocked:
                            health["healthy"] = False
                            self.coverage[key]["evaluation_status"] = "blocked"
                        completed.append(key)
                        self._publish(health, "source_completed", key, completed_sources=list(completed),
                                      elapsed_ms=section.get("elapsed_ms", 0),
                                      round_elapsed_ms=max(0, int((self.clock()-round_start)*1000)))

                    if fixture:
                        for section in fixture_sections:
                            commit_section(section)
                    else:
                        for key in due:
                            if deadline is not None and self.clock()>=deadline:
                                duration_limit=True
                                break
                            if self.cancel.is_set() or lock.stop_requested():
                                self.cancel.set()
                                break
                            source_start = self.clock()
                            self._publish(health, "source_started", key, started_at=utc_now(), elapsed_ms=0)

                            def source_progress(value):
                                # Only source identifiers and numeric timing are accepted;
                                # backend payloads can never become UI text or commands.
                                phase = value.get("phase") if isinstance(value, dict) else None
                                if phase not in ("launch", "waiting", "completed"):
                                    return
                                try:
                                    self._publish(health, "source_waiting",
                                                  key, elapsed_ms=max(0, int((self.clock()-source_start)*1000)))
                                except (OSError, ValueError):
                                    health.update(persistence_failure=True, healthy=False,
                                                  last_error="progress_persistence_failed")
                                    self.cancel.set()

                            if self.clock()-round_start>=45:
                                section={"id":key,"status":"busy","rows":[],"observed_at":utc_now(),"coverage":{"status":"busy","reason":"round_budget"}}
                                self.not_before[key]=self.clock()+30
                            else:
                                self.last[key]=stamp
                                self.not_before.pop(key,None)
                                try:
                                    section=self._collect(key, query_cancel, source_progress)
                                    if (not isinstance(section, dict) or section.get("id") != key
                                            or not isinstance(section.get("rows"), list)
                                            or any(not isinstance(row, dict) for row in section["rows"])):
                                        raise ValueError("invalid_section_output")
                                except Exception:
                                    section={"id":key,"status":"error","rows":[],"observed_at":utc_now(),"coverage":{"status":"error","reason":"collector_exception"}}
                            if "elapsed_ms" not in section:
                                section["elapsed_ms"] = max(0, int((self.clock()-source_start)*1000))
                            # A stop does not erase facts already returned by a source.
                            commit_section(section)
                    if not evaluation_blocked and not health.get("persistence_failure"):
                        health["healthy"] = all(value["status"] in SUCCESS for value in self.coverage.values())
                        health["last_error"] = None
                        if health["healthy"]:
                            health["last_success"] = utc_now()
                    cycles+=1
                    health.update(state="running",cycles=cycles)
                    self._publish(health, "idle", cycle=cycles)
                    if on_cycle:
                        on_cycle(copy.deepcopy(health))
                    if self.cancel.is_set() or lock.stop_requested():
                        self.cancel.set()
                        health["stop_reason"] = "cooperative_stop"
                        break
                    if duration_limit or (deadline is not None and self.clock()>=deadline):
                        health["stop_reason"]="duration_limit"
                        break
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
