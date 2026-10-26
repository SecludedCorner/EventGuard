"""Synthetic Scheduler definitions and mocked subprocesses; no task registration."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from eventguard import schedule


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "scripts").mkdir()
        (self.root / "scripts/eventguard.py").write_text("# synthetic task action\n", encoding="utf-8")
        for name in schedule.ACTION_SOURCES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("{}\n" if path.suffix == ".json" else "# Synthetic installation fixture; never executed.\n", encoding="utf-8")
        self.sid = "S-1-5-21-101-202-303-1001"
        self.python = Path(sys.executable)
        self.xml = schedule.build_task_xml(self.root, self.python, self.sid)
        self._original_query = schedule.query_task
        self.query = patch("eventguard.schedule.query_task", return_value={"status": "absent", "hresult": "80070002"}).start()
        self.addCleanup(patch.stopall)
        patch("eventguard.schedule.current_user_sid", return_value=self.sid).start()

    def plan(self, action="install", observed=None, start_now=False):
        return schedule.make_plan(self.root, action, executable=self.python, sid=self.sid, observed=observed, start_now=start_now)

    def matching(self):
        # The executable picker can prefer pythonw in the same installation.
        plan, xml, _ = self.plan()
        return {"status": "present", "xml": xml.decode("utf-16")}

    def test_definition_is_least_privilege_one_user_logon_and_unlimited(self):
        root = ET.fromstring(self.xml)
        ns = {"t": schedule.NS}
        get = lambda path: root.findtext(path, namespaces=ns)
        self.assertEqual(get("t:Principals/t:Principal/t:UserId"), self.sid)
        self.assertEqual(get("t:Principals/t:Principal/t:LogonType"), "InteractiveToken")
        self.assertEqual(get("t:Principals/t:Principal/t:RunLevel"), "LeastPrivilege")
        self.assertEqual(get("t:Triggers/t:LogonTrigger/t:UserId"), self.sid)
        self.assertIsNone(root.find("t:Triggers/t:BootTrigger", ns))
        self.assertEqual(get("t:Settings/t:ExecutionTimeLimit"), "PT0S")
        self.assertEqual(get("t:Settings/t:MultipleInstancesPolicy"), "IgnoreNew")
        self.assertEqual(get("t:Settings/t:RestartOnFailure/t:Count"), "3")
        self.assertEqual(get("t:Settings/t:RestartOnFailure/t:Interval"), "PT1M")
        for path in ("t:Settings/t:RunOnlyIfIdle", "t:Settings/t:StopIfGoingOnBatteries", "t:Settings/t:IdleSettings/t:StopOnIdleEnd", "t:Settings/t:AllowHardTerminate"):
            self.assertEqual(get(path), "false")
        self.assertEqual(get("t:Actions/t:Exec/t:Command"), str(self.python.resolve()))
        self.assertEqual(get("t:Actions/t:Exec/t:WorkingDirectory"), str(self.root.resolve()))
        self.assertTrue(get("t:Actions/t:Exec/t:Arguments").endswith("--format json background serve"))

    def test_digest_binds_user_root_action_and_immediate_run_scope(self):
        plan, _, blocked = self.plan()
        self.assertFalse(blocked)
        self.assertEqual(plan, self.plan()[0])
        self.assertNotEqual(plan["plan_sha256"], self.plan(start_now=True)[0]["plan_sha256"])
        self.assertNotEqual(plan["plan_sha256"], self.plan("uninstall")[0]["plan_sha256"])
        other, _, _ = schedule.make_plan(self.root, sid=self.sid + "1", executable=self.python, observed={"status": "absent"})
        self.assertNotEqual(plan["task_name"], other["task_name"])
        self.assertEqual(plan["model_calls"], 0)
        self.assertIn("not_before_login", plan["recovery_scope"])

    def test_exported_unicode_xml_and_known_generated_defaults_match(self):
        original = schedule.definition_digest(self.xml)
        parsed = ET.fromstring(self.xml)
        info = parsed.find(f"{{{schedule.NS}}}RegistrationInfo")
        ET.SubElement(info, f"{{{schedule.NS}}}Date").text = "2026-10-23T00:00:00"
        settings = parsed.find(f"{{{schedule.NS}}}Settings")
        ET.SubElement(settings, f"{{{schedule.NS}}}UseUnifiedSchedulingEngine").text = "false"
        ET.SubElement(settings, f"{{{schedule.NS}}}DisallowStartOnRemoteAppSession").text = "false"
        self.assertEqual(original, schedule.definition_digest(ET.tostring(parsed, encoding="unicode")))
        self.assertEqual(original, schedule.definition_digest(self.xml.decode("utf-16")))

    def test_changed_action_user_marker_and_extra_trigger_are_not_owned(self):
        for old, new in (("background serve", "background start"), (self.sid, self.sid + "2"), (schedule.SOURCE, "Other.Tool"), ("PT0S", "PT72H"), ("LeastPrivilege", "HighestAvailable")):
            with self.subTest(change=old):
                changed = self.xml.decode("utf-16").replace(old, new)
                _, _, blocked = self.plan(observed={"status": "present", "xml": changed})
                self.assertTrue(blocked)
        parsed = ET.fromstring(self.xml)
        ET.SubElement(parsed.find(f"{{{schedule.NS}}}Triggers"), f"{{{schedule.NS}}}BootTrigger")
        self.assertTrue(self.plan(observed={"status": "present", "xml": ET.tostring(parsed)})[2])

    def test_unknown_denied_and_invalid_xml_remain_blocked(self):
        for observed in ({"status": "denied", "hresult": "80070005"}, {"status": "unknown", "reason": "scheduler_timeout"}, {"status": "present", "xml": "<wrong/>"}):
            with self.subTest(state=observed["status"]):
                self.assertTrue(self.plan(observed=observed)[2])

    def test_foreign_identity_is_blocked_without_reading_definition(self):
        with patch("eventguard.schedule.definition_digest", wraps=schedule.definition_digest) as digest:
            plan, _, blocked = self.plan(observed={"status": "present", "ownership": "foreign_or_changed_identity"})
            self.assertTrue(blocked)
            self.assertEqual(plan["observed"]["reason"], "task_identity_not_owned")
            self.assertEqual(digest.call_count, 1, "Only our generated definition is parsed")

    def test_query_checks_fixed_identity_before_requesting_full_xml(self):
        powershell = self.root / "System32/WindowsPowerShell/v1.0/powershell.exe"
        powershell.parent.mkdir(parents=True)
        powershell.write_bytes(b"synthetic-placeholder-never-executed")
        # Patch only this module's os binding; no platform-wide os.name mutation.
        fake_os = SimpleNamespace(name="nt", environ={"SystemRoot": str(self.root)})
        response = {"status": "present", "ownership": "foreign_or_changed_identity", "stage": "definition", "parent_folder_confirmed": True}
        with patch("eventguard.schedule.os", fake_os), patch("eventguard.schedule._owned_run", return_value={"status": "completed", "exit_code": 0, "stdout": json.dumps(response).encode()}) as run:
            # The setUp mock must be bypassed for this script-construction contract.
            # Resolve the original function from the patcher without running COM.
            function = self._original_query
            value = function(schedule.task_name(self.root.resolve(), self.sid), root=self.root, sid=self.sid)
            self.assertEqual(value, response)
            script = run.call_args.args[0][-1]
            for field in ("$r.Source", "$r.URI", "$r.Description", "$p.UserId", "foreign_or_changed_identity"):
                self.assertLess(script.index(field), script.index("$t.Xml"))
            self.assertNotIn("$d.Actions", script)
            for stage in schedule.QUERY_STAGES:
                self.assertIn("$stage='" + stage + "'", script)
            self.assertLess(script.index("$f=$s.GetFolder"), script.index("$folderKnown=$true"))
            self.assertLess(script.index("$folderKnown=$true"), script.index("$t=$f.GetTask"))

    def test_not_found_is_absent_only_at_get_task_in_confirmed_parent(self):
        for code in ("80070002", "80070003"):
            with self.subTest(hresult=code):
                result = schedule._query_error("get_task", code, True)
                self.assertEqual(result["status"], "absent")
                self.assertEqual(result["reason"], "task_not_found_in_confirmed_folder")
                self.assertEqual(schedule._query_error("get_task", code, False)["status"], "unknown")
                for stage in schedule.QUERY_STAGES - {"get_task"}:
                    self.assertEqual(schedule._query_error(stage, code, True)["status"], "unknown")

    def test_query_denied_and_failure_preserve_precise_stage_hresult(self):
        for stage in schedule.QUERY_STAGES:
            with self.subTest(stage=stage):
                denied = schedule._query_error(stage, "80070005", stage != "get_folder")
                self.assertEqual(denied["status"], "denied")
                self.assertEqual(denied["stage"], stage)
                self.assertEqual(denied["hresult"], "80070005")
        observed = schedule._query_error("get_folder", "80070003", False)
        plan, _, blocked = self.plan(observed=observed)
        self.assertTrue(blocked)
        self.assertEqual(plan["blocked_reason"], "scheduler_query_failed")
        self.assertEqual(plan["observed"]["stage"], "get_folder")

    def test_xml_entities_rejected_in_utf8_and_utf16(self):
        for xml in ('<!DOCTYPE Task [<!ENTITY a "x">]><Task/>', '<!DOCTYPE Task><Task/>'.encode("utf-16"), b"x" * (schedule.MAX_XML + 1)):
            with self.assertRaises(ValueError):
                schedule.definition_digest(xml)

    def test_plan_artifacts_inside_reports_are_immutable_and_bind_exact_xml(self):
        plan, xml, _ = self.plan()
        directory = schedule.write_plan(self.root, plan, xml)
        self.assertEqual(directory, schedule.write_plan(self.root, plan, xml))
        self.assertEqual((directory / "task.xml").read_bytes(), xml)
        self.assertEqual(json.loads((directory / "plan.json").read_text()), plan)
        self.assertEqual(schedule._hash(xml), plan["task_xml_sha256"])
        with self.assertRaisesRegex(ValueError, "different_content"):
            schedule.write_plan(self.root, {**plan, "model_calls": 1}, xml, directory)
        for path in (self.root, self.root / "reports", self.root / "reports/../../other-plan"):
            with self.assertRaisesRegex(ValueError, "inside_reports|path_outside_project"):
                schedule.write_plan(self.root, plan, xml, path)

    def test_internal_redirect_chain_is_rejected_before_resolve(self):
        plan, xml, _ = self.plan()
        alias = self.root / "reports/alias"
        real_is_symlink = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path == alias or real_is_symlink(path)):
            with self.assertRaisesRegex(ValueError, "redirected_runtime_path"):
                schedule.write_plan(self.root, plan, xml, alias / "review")
        self.assertFalse((self.root / "reports").exists())

    def test_default_install_and_uninstall_are_dry_run_without_mutation(self):
        with patch("eventguard.schedule._owned_run") as run:
            for action in ("install", "uninstall"):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(schedule.main([action], root=self.root), 0)
                value = json.loads(output.getvalue())
                self.assertEqual(value["status"], "dry_run")
                self.assertFalse(value["executed"])
                self.assertTrue(value["requires_approval"])
            run.assert_not_called()

    def test_execute_without_approved_digest_never_queries_or_mutates(self):
        self.query.reset_mock()
        with patch("eventguard.schedule._owned_run") as run:
            for approved in (None, "bad", "A" * 64):
                value = schedule.execute_plan(self.root, "install", approved)
                self.assertEqual(value["status"], "approval_required")
            self.query.assert_not_called()
            run.assert_not_called()

    def test_changed_plan_digest_denies_mutation(self):
        plan, _, _ = self.plan()
        with patch("eventguard.schedule._owned_run") as run:
            result = schedule.execute_plan(self.root, "install", plan["plan_sha256"], start_now=True)
            self.assertEqual(result["reason"], "plan_changed_or_digest_mismatch")
            run.assert_not_called()

    def test_changed_action_source_requires_new_approval(self):
        plan, _, _ = self.plan()
        (self.root / "scripts/eventguard.py").write_text("# changed synthetic task action\n", encoding="utf-8")
        with patch("eventguard.schedule._owned_run") as run:
            result = schedule.execute_plan(self.root, "install", plan["plan_sha256"])
            self.assertEqual(result["reason"], "plan_changed_or_digest_mismatch")
            run.assert_not_called()

    def test_missing_bound_monitor_source_blocks_even_with_approved_digest(self):
        (self.root / "src/eventguard/background.py").unlink()
        plan, _, blocked = self.plan()
        self.assertTrue(blocked)
        self.assertEqual(plan["blocked_reason"], "monitor_installation_incomplete")
        self.assertEqual(plan["missing_action_sources"], ["src/eventguard/background.py"])
        with patch("eventguard.schedule._owned_run") as run:
            result = schedule.execute_plan(self.root, "install", plan["plan_sha256"])
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason"], "monitor_installation_incomplete")
            self.assertFalse(result["executed"])
            run.assert_not_called()

    def test_changed_imported_cli_collector_and_playbook_require_new_approval(self):
        for name in ("src/eventguard/cli.py", "src/eventguard/collectors/windows.py", "playbooks/default.json"):
            with self.subTest(source=name):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n" if path.suffix == ".json" else "# Synthetic imported source before review.\n", encoding="utf-8")
                plan, _, _ = self.plan()
                self.assertEqual(plan["action_source_sha256"][name], schedule._hash(path.read_bytes()))
                path.write_text('{"synthetic_changed":true}\n' if path.suffix == ".json" else "# Synthetic imported source changed after review.\n", encoding="utf-8")
                with patch("eventguard.schedule._owned_run") as run:
                    result = schedule.execute_plan(self.root, "install", plan["plan_sha256"])
                    self.assertEqual(result["reason"], "plan_changed_or_digest_mismatch")
                    self.assertFalse(result["executed"])
                    run.assert_not_called()

    def test_new_and_removed_installed_core_sources_change_approval_digest(self):
        before, _, _ = self.plan()
        module = self.root / "src/eventguard/diagnostics/new_query.py"
        module.parent.mkdir(parents=True)
        module.write_text("# Synthetic imported module, never executed.\n", encoding="utf-8")
        added, _, _ = self.plan()
        self.assertNotEqual(before["plan_sha256"], added["plan_sha256"])
        self.assertIn("src/eventguard/diagnostics/new_query.py", added["action_source_sha256"])
        module.unlink()
        self.assertEqual(before["plan_sha256"], self.plan()[0]["plan_sha256"])

    def test_existing_matching_install_is_noop_and_does_not_run(self):
        self.query.return_value = self.matching()
        plan, _, blocked = self.plan()
        self.assertFalse(blocked)
        with patch("eventguard.schedule._owned_run") as run:
            result = schedule.execute_plan(self.root, "install", plan["plan_sha256"])
            self.assertEqual(result["status"], "already_installed")
            self.assertFalse(result["executed"])
            self.assertFalse((self.root / "reports").exists())
            run.assert_not_called()

    def test_pythonw_selection_is_only_from_same_existing_installation(self):
        executable = self.root / "python.exe"
        executable.write_bytes(b"synthetic-placeholder-never-executed")
        self.assertEqual(schedule._python(executable), executable.resolve())
        windowless = self.root / "pythonw.exe"
        windowless.write_bytes(b"synthetic-placeholder-never-executed")
        self.assertEqual(schedule._python(executable), windowless.resolve())

    def test_foreign_task_cannot_be_deleted_even_with_current_digest(self):
        self.query.return_value = {"status": "present", "xml": "<Other/>"}
        plan, _, _ = self.plan("uninstall")
        with patch("eventguard.schedule._owned_run") as run:
            result = schedule.execute_plan(self.root, "uninstall", plan["plan_sha256"])
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["executed"])
            run.assert_not_called()

    def test_mocked_approved_create_has_no_force_and_no_run_by_default(self):
        plan, _, _ = self.plan()
        scheduler = self.root / "schtasks.exe"
        scheduler.write_bytes(b"synthetic-placeholder-never-executed")
        present = self.matching()
        self.query.side_effect = [{"status": "absent", "hresult": "80070002"}, present]
        with patch("eventguard.schedule._scheduler_executable", return_value=scheduler), patch("eventguard.schedule._owned_run", return_value={"status": "completed", "exit_code": 0}) as run:
            result = schedule.execute_plan(self.root, "install", plan["plan_sha256"])
            self.assertEqual(result["status"], "installed")
            self.assertEqual(run.call_count, 1)
            argv = run.call_args.args[0]
            self.assertEqual(argv[1], "/Create")
            self.assertNotIn("/F", argv)
            self.assertNotIn("/Run", argv)
            self.assertFalse(result["task_started"])
            self.assertFalse(result["task_start_requested"])

    def test_mocked_immediate_run_requires_definition_verified_after_create(self):
        plan, _, _ = self.plan(start_now=True)
        scheduler = self.root / "schtasks.exe"
        scheduler.write_bytes(b"synthetic-placeholder-never-executed")
        self.query.side_effect = [{"status": "absent", "hresult": "80070002"}, {"status": "present", "xml": "<Foreign/>"}]
        with patch("eventguard.schedule._scheduler_executable", return_value=scheduler), patch("eventguard.schedule._owned_run", return_value={"status": "completed", "exit_code": 0}) as run:
            result = schedule.execute_plan(self.root, "install", plan["plan_sha256"], start_now=True)
            self.assertEqual(result["status"], "unconfirmed")
            self.assertEqual(run.call_count, 1)
            self.assertFalse(result["start_request_accepted"])

    def test_mocked_delete_targets_only_matching_task_registration(self):
        self.query.return_value = self.matching()
        plan, _, _ = self.plan("uninstall")
        scheduler = self.root / "schtasks.exe"
        scheduler.write_bytes(b"synthetic-placeholder-never-executed")
        self.query.side_effect = [self.query.return_value, {"status": "absent", "hresult": "80070002"}]
        with patch("eventguard.schedule._scheduler_executable", return_value=scheduler), patch("eventguard.schedule._owned_run", return_value={"status": "completed", "exit_code": 0}) as run:
            result = schedule.execute_plan(self.root, "uninstall", plan["plan_sha256"])
            self.assertEqual(result["status"], "uninstalled")
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0], [str(scheduler), "/Delete", "/TN", plan["task_name"], "/F"])
            self.assertFalse(result["task_started"])
            self.assertIn("without_stopping_monitor", plan["approval_scope"])

    def test_mocked_start_request_is_not_claimed_running_monitor(self):
        plan, _, _ = self.plan(start_now=True)
        scheduler = self.root / "schtasks.exe"
        scheduler.write_bytes(b"synthetic-placeholder-never-executed")
        present = self.matching()
        self.query.side_effect = [{"status": "absent", "hresult": "80070002"}, present]
        with patch("eventguard.schedule._scheduler_executable", return_value=scheduler), patch("eventguard.schedule._owned_run", return_value={"status": "completed", "exit_code": 0}) as run:
            result = schedule.execute_plan(self.root, "install", plan["plan_sha256"], start_now=True)
            self.assertTrue(result["start_request_accepted"])
            self.assertFalse(result["task_started"])
            self.assertEqual(run.call_args.args[0][1], "/Run")

    def test_unconfirmed_mutation_retains_attempt_and_does_not_query_or_run_again(self):
        plan, _, _ = self.plan(start_now=True)
        scheduler = self.root / "schtasks.exe"
        scheduler.write_bytes(b"synthetic-placeholder-never-executed")
        self.query.reset_mock()
        with patch("eventguard.schedule._scheduler_executable", return_value=scheduler), patch("eventguard.schedule._owned_run", return_value={"status": "unknown", "reason": "scheduler_timeout"}) as run:
            result = schedule.execute_plan(self.root, "install", plan["plan_sha256"], start_now=True)
            self.assertEqual(result["status"], "unconfirmed")
            self.assertTrue(result["executed"])
            self.assertEqual(run.call_count, 1)
            self.assertEqual(self.query.call_count, 1)
            result = schedule.execute_plan(self.root, "install", plan["plan_sha256"], start_now=True)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason"], "execution_receipt_already_exists")
            self.assertEqual(run.call_count, 1)

    def test_status_is_read_only_without_artifacts_or_scheduler_mutation(self):
        with patch("eventguard.schedule._owned_run") as run:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(schedule.main(["status"], root=self.root), 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "absent")
            self.assertFalse((self.root / "reports").exists())
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
