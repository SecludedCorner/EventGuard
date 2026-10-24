"""Human app controls must show evidence, not imply completed shutdown."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from eventguard.cli import main
from eventguard.presentation import render


class ApplicationCLITextTests(unittest.TestCase):
    def result(self):
        return {"namespace":"test", "instance_id":"a"*32, "state_revision":4,
                "monitor_state":"stopped", "local_url":"http://127.0.0.1:8765", "model_calls":0,
                "monitor_controls":{"available":True, "transition":None, "can_start":True,
                                    "can_stop":False, "can_shutdown":True},
                "last_action":{"action":"stop", "source":"cli", "state":"stopped",
                               "result_code":"monitor_stop_events_preserved", "operation_id":"test-stop"}}

    def test_text_cli_reads_the_same_app_without_creating_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            proxy=Mock()
            proxy.status.return_value=self.result()
            output=io.StringIO()
            with patch("eventguard.application_host.RemoteApplication", return_value=proxy), redirect_stdout(output):
                code=main(["--format","text","app","status","--namespace","test"],root=root)
            self.assertEqual(code,0)
            shown=output.getvalue()
            self.assertIn("採集已停止，應用仍開啟",shown)
            self.assertIn("來源：CLI",shown)
            self.assertIn("狀態版本：4",shown)
            self.assertIn("目前可用：開始採集、關閉程式",shown)
            self.assertIn("http://127.0.0.1:8765",shown)
            self.assertNotIn('"monitor_state"',shown)
            proxy.monitor_control.assert_not_called()
            self.assertEqual(list(root.iterdir()),[])

    def test_missing_app_stays_blocked_and_never_looks_stopped(self):
        shown=render({"state":"blocked", "reason":"application_not_running",
                      "namespace":"test", "instance_id":"unbound", "model_calls":0},"app","status")
        self.assertIn("application_not_running",shown)
        self.assertIn("採集狀態未確認",shown)
        self.assertNotIn("採集已停止",shown)
        self.assertIn("沒有已確認可用",shown)

    def test_shutdown_receipt_is_distinct_from_actual_exit(self):
        value=self.result()
        value.update(state="shutdown_requested",reason="monitor_application_shutdown_requested")
        shown=render(value,"app","shutdown")
        self.assertIn("不代表程式已退出",shown)
        self.assertIn("需另核對退出結果",shown)
        self.assertNotIn("已成功關閉",shown)
        self.assertIn("停止採集保留介面",render(self.result(),"app","stop"))

    def test_replayed_old_receipt_shows_current_state_without_repeating_operation(self):
        value=self.result()
        value.update(state="running",monitor_state="paused",replayed=True)
        value["monitor_controls"]["transition"]="resume"
        shown=render(value,"app","start")
        self.assertIn("採集已暫停",shown)
        self.assertIn("沒有再次執行",shown)
        self.assertIn("沒有已確認可用",shown)

    def test_terminal_control_characters_are_inert_and_source_is_fixed(self):
        value=self.result()
        value.update(reason="untrusted\x1b[31m\nSHUTDOWN",state="unknown")
        value["last_action"].update(source="mcp\nexecute",result_code="fake\u202eACK")
        shown=render(value,"app","stop")
        self.assertNotIn("\x1b",shown)
        self.assertNotIn("\u202e",shown)
        self.assertIn("來源：未知",shown)
        self.assertIn("\\u001b",shown)
        self.assertIn("\\u202e",shown)
        self.assertNotIn("來源：mcp",shown)

    def test_malformed_enum_data_stays_unknown_without_an_exception(self):
        value=self.result()
        value["monitor_state"]={"running":True}
        value["last_action"].update(source=["mcp"],action={"shutdown":True})
        shown=render(value,"app","status")
        self.assertIn("採集狀態未確認",shown)
        self.assertIn("來源：未知",shown)
        self.assertIn("其他操作",shown)


if __name__=="__main__":
    unittest.main()
