"""Synthetic, bounded tests. No live Windows inventory is collected."""
import io
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eventguard.collectors.runner import Runner, MAX_OUTPUT_BYTES
from eventguard.collectors.windows import WindowsCollectors, SCRIPTS, COMMON, SECTION_IDS, LIMITS, classify_address
from eventguard.diagnostics.api import DiagnosticAPI


class Child:
    def __init__(self, output=b'{"status":"ok","rows":[]}', code=0, gate=None):
        self.stdout = io.BytesIO(output)
        self.stderr = io.BytesIO(b"")
        self.code, self.gate = code, gate

    def wait(self):
        if self.gate:
            self.gate.wait(2)
        return self.code

    def kill(self):
        raise AssertionError("must never terminate a process")

    terminate = kill


class FakeRunner:
    pending = False

    def __init__(self, status="ok", rows=None, source_status="ok", truncated=False):
        self.response = {"status":status,"data":{"status":source_status,"rows":rows or [],"truncated":truncated}}
        self.calls = []

    def run(self, script, **kwargs):
        self.calls.append((script, kwargs))
        return self.response


class RunnerTests(unittest.TestCase):
    def test_fixed_arguments_and_json(self):
        calls = []
        def factory(args, **kwargs):
            calls.append((args, kwargs))
            return Child()
        result = Runner(factory).run("STATIC")
        self.assertEqual(result["status"], "ok")
        args, kwargs = calls[0]
        self.assertFalse(kwargs["shell"])
        self.assertIn("-NoProfile", args)
        self.assertNotIn("-ExecutionPolicy", args)
        self.assertNotIn("-Verb", args)

    def test_timeout_cannot_accumulate_or_terminate_children(self):
        gate, calls = threading.Event(), []
        def factory(*args, **kwargs):
            calls.append(1)
            return Child(gate=gate)
        runner = Runner(factory)
        try:
            self.assertEqual(runner.run("STATIC", timeout=.001)["status"], "timeout")
            self.assertTrue(runner.pending)
            self.assertEqual(runner.run("STATIC")["status"], "busy")
            self.assertEqual(len(calls), 1)
        finally:
            gate.set()
        self.assertTrue(runner._active["done"].wait(1))
        self.assertFalse(runner.pending)

    def test_cancel_and_late_output(self):
        gate, cancel = threading.Event(), threading.Event()
        runner = Runner(lambda *a, **k: Child(gate=gate))
        timer = threading.Timer(.01, cancel.set)
        timer.start()
        try:
            self.assertEqual(runner.run("STATIC", cancel=cancel)["status"], "cancelled")
        finally:
            gate.set()
            timer.join()
        self.assertTrue(runner._active["done"].wait(1))
        self.assertEqual(runner.run("STATIC", cancel=cancel)["status"], "cancelled")

    def test_nonzero_invalid_json_schema_and_limit(self):
        children = [Child(code=1), Child(b"bad"), Child(b"[]"), Child(b'{"rows":null}'), Child(b"a"*(MAX_OUTPUT_BYTES+1))]
        for child in children:
            self.assertEqual(Runner(lambda *a, child=child, **k: child).run("STATIC")["status"], "error")
        combined = Child(b"a"*(MAX_OUTPUT_BYTES//2+1))
        combined.stderr = io.BytesIO(b"b"*(MAX_OUTPUT_BYTES//2+1))
        self.assertEqual(Runner(lambda *a, **k: combined).run("STATIC")["note"], "query_output_limit_exceeded")

    def test_launch_gaps_and_input_limits(self):
        for error, status in [(PermissionError(),"denied"),(FileNotFoundError(),"not_applicable"),(OSError(),"error")]:
            def factory(*args, error=error, **kwargs):
                raise error
            self.assertEqual(Runner(factory).run("STATIC")["status"], status)
        runner = Runner(lambda *a, **k: self.fail("invalid request spawned child"))
        for timeout in (True,0,-1,61,"15"):
            self.assertEqual(runner.run("STATIC",timeout=timeout)["status"], "error")
        self.assertEqual(runner.run("")["status"], "error")


class CollectorTests(unittest.TestCase):
    def test_all_empty_success_and_runner_gaps(self):
        for section in SECTION_IDS:
            result = WindowsCollectors(FakeRunner()).collect(section)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["rows"], [])
            self.assertEqual(result["coverage"]["scope"], "local_metadata_only")
        for status in ("denied","unknown","not_applicable","timeout","cancelled","busy","error"):
            self.assertEqual(WindowsCollectors(FakeRunner(status=status)).collect("defender")["status"], status)

    def test_payload_invalid_does_not_look_empty_success(self):
        runner = FakeRunner()
        for data in (None,[],{"status":"ok","rows":None},{"status":"surprise","rows":[]},{"status":"ok","rows":["raw"]}):
            runner.response["data"] = data
            self.assertEqual(WindowsCollectors(runner).collect("services")["status"], "error")

    def test_minimization_and_process_identity(self):
        rows = [{"pid":42,"name":"example.exe","path":r"C:\Users\private\program.exe","path_status":"ok","created_at":"2026-10-22T00:00:00+00:00","status":"ok","command_line":"DO NOT LEAK","Message":"DO NOT LEAK","password":"DO NOT LEAK"}]
        result = WindowsCollectors(FakeRunner(rows=rows)).collect("processes")
        row = result["rows"][0]
        self.assertEqual(row["path"], r"%USER_HOME%\program.exe")
        self.assertTrue(row["process_instance_ref"].startswith("proc-"))
        self.assertNotIn("DO NOT LEAK", json.dumps(result))
        other = dict(rows[0], created_at="2026-10-22T01:00:00+00:00")
        ref = WindowsCollectors(FakeRunner(rows=[other])).collect("processes")["rows"][0]["process_instance_ref"]
        self.assertNotEqual(row["process_instance_ref"], ref)

    def test_empty_paths_or_identity_are_unknown_not_denied(self):
        result = WindowsCollectors(FakeRunner(rows=[{"pid":1,"name":"protected","path":"","path_status":"unknown","created_at":None,"status":"ok"}])).collect("processes")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["rows"][0]["status"], "unknown")
        self.assertIsNone(result["rows"][0]["process_instance_ref"])

    def test_optional_absence_is_complete_but_denied_is_gap(self):
        missing = {"source":"CurrentUser\\RunOnce","name":"(key absent)","kind":"registry_missing","status":"not_applicable"}
        result = WindowsCollectors(FakeRunner(rows=[missing])).collect("startup")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["rows"][0]["status"], "not_applicable")
        for row in [dict(missing,status="denied"),dict(missing,kind="folder_skipped",status="unknown")]:
            self.assertEqual(WindowsCollectors(FakeRunner(rows=[missing,row])).collect("startup")["status"], "partial")

    def test_truncation_and_invalid_endpoint_are_partial(self):
        rows = [{"name":"service-"+str(n),"status":"ok"} for n in range(LIMITS["services"]+1)]
        result = WindowsCollectors(FakeRunner(rows=rows)).collect("services")
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["coverage"]["truncated"])
        self.assertEqual(len(result["rows"]), 500)
        bad = WindowsCollectors(FakeRunner(rows=[{"protocol":"TCP","address":None,"port":None,"status":"ok"}])).collect("listeners")
        self.assertEqual(bad["status"], "partial")

    def test_false_is_observation_not_unknown_or_infection(self):
        result = WindowsCollectors(FakeRunner(rows=[{"item":"RealTimeProtectionEnabled","value":False,"status":"ok"}])).collect("defender")
        self.assertIs(result["rows"][0]["value"],False)
        self.assertEqual(result["status"], "ok")

    def test_address_scope_never_infers_reachability(self):
        cases = {"127.12.0.1":"localhost","::1":"localhost","::ffff:127.0.0.2":"localhost","0.0.0.0":"all_interfaces","::":"all_interfaces","192.168.1.1":"lan","172.18.0.1":"lan","10.2.3.4":"lan","fc00::1":"lan","fe80::1%3":"link_local","169.254.1.2":"link_local","8.8.8.8":"global","invalid":"unknown"}
        for address, expected in cases.items():
            self.assertEqual(classify_address(address), expected)

    def test_scripts_are_static_metadata_and_bounded(self):
        joined = "\n".join(SCRIPTS.values())
        for text in ("CommandLine","PathName",".Message",".ToXml",".Actions","Get-MpThreat","Set-MpPreference","Stop-Process","Invoke-WebRequest","-ExecutionPolicy"):
            self.assertNotIn(text, joined)
        self.assertIn("$rows.ToArray()", COMMON)
        self.assertIn("GetValueNames()", SCRIPTS["startup"])
        self.assertNotIn("GetValue(", SCRIPTS["startup"])
        self.assertIn("CmdletizationQuery_NotFound_State,", SCRIPTS["listeners"])
        self.assertIn("ReparsePoint", COMMON)
        self.assertIn("-First 501", SCRIPTS["services"])
        self.assertIn("-First 301", SCRIPTS["tasks"])
        self.assertNotIn("Test-Path", SCRIPTS["versions"])
        self.assertLess(SCRIPTS["versions"].rfind("Test-LocalFixedPath"), SCRIPTS["versions"].index("[Diagnostics.FileVersionInfo]"))
        self.assertIn("SpecialFolderOption]::DoNotVerify", SCRIPTS["startup"])
        self.assertTrue(all(len(script)<24000 for script in SCRIPTS.values()))


class FixtureCollectors:
    runner = FakeRunner()

    def __init__(self, sections=None):
        self.sections = sections or {}
        self.calls = []

    def collect(self, section_id, cancel=None):
        self.calls.append(section_id)
        return self.sections.get(section_id,{"id":section_id,"status":"ok","rows":[],"observed_at":"2026-10-22T00:00:00+00:00","coverage":{}})


class DiagnosticTests(unittest.TestCase):
    def test_capabilities_are_actual_read_only_contract(self):
        caps = DiagnosticAPI(FixtureCollectors()).capabilities()
        self.assertTrue(caps["read_only"])
        self.assertFalse(caps["external_transport"])
        self.assertEqual(caps["max_rows"],100)
        self.assertIn("query_process",caps["operations"])

    def test_invalid_operation_and_injected_fields_never_collect(self):
        collectors=FixtureCollectors(); api=DiagnosticAPI(collectors)
        for op,args in [("shell",{}),("query_listener",{"protocol":"TCP","port":80,"command":"bad"}),("query_listener",{"protocol":"TCP","port":True}),("query_listener",{"protocol":"TCP","port":80,"max_rows":10000}),("query_defender",{"request_id":"../secret"}),("query_process",{"pid":42})]:
            self.assertEqual(api.query(op,args)["status"],"error")
        self.assertEqual(collectors.calls,[])

    def test_query_listener_filters_minimizes_and_truncates(self):
        rows=[{"protocol":"TCP","port":80,"address":"127.0.0.1","status":"ok","secret":"bad"},{"protocol":"UDP","port":80,"status":"ok"},{"protocol":"TCP","port":80,"address":"0.0.0.0","status":"ok"}]
        collectors=FixtureCollectors({"listeners":{"status":"ok","rows":rows,"coverage":{}}})
        result=DiagnosticAPI(collectors).query("query_listener",{"protocol":"TCP","port":80,"max_rows":1})
        self.assertEqual(len(result["rows"]),1)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["status"],"partial")
        self.assertNotIn("secret",json.dumps(result))
        self.assertEqual(collectors.calls,["listeners"])

    def test_pid_reuse_does_not_return_different_instance(self):
        rows=[{"pid":42,"created_at":"2026-10-22T01:00:00+00:00","path":"sensitive","status":"ok","process_instance_ref":"proc-"+"a"*24}]
        api=DiagnosticAPI(FixtureCollectors({"processes":{"status":"ok","rows":rows,"coverage":{}}}))
        stale=api.query("query_process",{"pid":42,"created_at":"2026-10-22T00:00:00+00:00"})
        self.assertEqual(stale["error_code"],"stale_process_instance")
        self.assertEqual(stale["rows"],[])
        found=api.query("query_process",{"process_instance_ref":"proc-"+"a"*24})
        self.assertEqual(len(found["rows"]),1)
        conflicting=api.query("query_process",{"process_instance_ref":"proc-"+"a"*24,"pid":42,"created_at":"2026-10-22T00:00:00+00:00"})
        self.assertEqual(conflicting["status"],"error")

    def test_process_source_denial_not_relabelled_missing_pid(self):
        collectors=FixtureCollectors({"processes":{"status":"denied","rows":[{"status":"denied"}],"coverage":{}}})
        result=DiagnosticAPI(collectors).query("query_process",{"pid":42,"created_at":"2026-10-22T00:00:00+00:00"})
        self.assertEqual(result["status"],"denied")
        self.assertEqual(result["error_code"],"source_denied")

    def test_unsupported_threat_view_and_version_do_not_scan(self):
        collectors=FixtureCollectors(); api=DiagnosticAPI(collectors)
        self.assertEqual(api.query("query_defender",{"view":"threat_history"})["status"],"not_applicable")
        self.assertEqual(api.query("query_version",{"product_id":"arbitrary"})["status"],"not_applicable")
        self.assertEqual(collectors.calls,[])

    def test_persistence_is_explicit_current_only(self):
        result=DiagnosticAPI(FixtureCollectors()).query("query_persistence_diff",{"kind":"tasks"})
        self.assertEqual(result["coverage"]["mode"],"current_only")
        self.assertEqual(result["coverage"]["baseline_comparison"],"not_implemented")

    def test_health_and_cancel_do_not_query_sources(self):
        collectors=FixtureCollectors(); api=DiagnosticAPI(collectors)
        self.assertEqual(api.query("health")["status"],"ok")
        cancel=threading.Event();cancel.set()
        self.assertEqual(api.query("query_defender",cancel=cancel)["status"],"cancelled")
        self.assertEqual(collectors.calls,[])

    def test_source_denied_stays_denied_and_raw_errors_not_leaked(self):
        collectors=FixtureCollectors({"defender":{"status":"denied","rows":[],"coverage":{},"note":"PRIVATE STDERR"}})
        result=DiagnosticAPI(collectors).query("query_defender")
        self.assertEqual(result["status"],"denied")
        self.assertEqual(result["error_code"],"source_denied")
        self.assertNotIn("PRIVATE",json.dumps(result))


if __name__=="__main__":
    unittest.main()
