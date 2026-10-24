"""CLI config contract only. No subprocess, model, or MCP connection."""
from pathlib import Path
import tempfile
import tomllib
import unittest

from eventguard.agent_dispatch import command


class CliTransportConfigTests(unittest.TestCase):
    def test_disabled_servers_have_valid_inert_stdio_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = command("codex.exe", "python.exe", root / "source", root / "inbox",
                           "evt-synthetic", root / "evidence", root=root)
        values = [args[index + 1] for index, value in enumerate(args) if value == "-c"]
        config = tomllib.loads("\n".join(values))
        servers = config["mcp_servers"]
        self.assertEqual(set(servers), {"eventguard_inbox", "eventguard_test", "eventguard", "eventguard-app"})
        for name in ("eventguard_test", "eventguard", "eventguard-app"):
            self.assertEqual(servers[name], {"enabled": False, "command": "python.exe", "args": []})
        self.assertEqual(servers["eventguard_inbox"]["command"], "python.exe")
        self.assertIn("--ignore-user-config", args)
        self.assertIn("features.shell_tool=false", values)


if __name__ == "__main__":
    unittest.main()
