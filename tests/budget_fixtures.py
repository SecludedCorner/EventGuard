"""Explicit isolated test installation; never a production CLI bypass switch."""
from contextlib import contextmanager, ExitStack
from pathlib import Path
import sys
from unittest.mock import patch

from eventguard.agent_budget import BudgetAuthority
from eventguard.acceptance_process import capture, launch_hash
from eventguard.processes import spawn


@contextmanager
def isolated_budget(root):
    authority = BudgetAuthority(Path(root) / "test-installation" / "authority.sqlite3")
    authority.initialize(known_used=0)  # New, explicitly fake installation only.
    wrapper = '''import sys
sys.path.insert(0,sys.argv.pop(1))
from unittest.mock import patch
from eventguard.agent_budget import BudgetAuthority
from eventguard.agent_dispatch import main
authority=BudgetAuthority.open_existing(sys.argv[1])
with patch("eventguard.acceptance_process.open_authority",return_value=authority):
 raise SystemExit(main(sys.argv[2:]))
'''
    def fixture_spawn(args, **kwargs):
        args = list(args)
        if len(args) >= 4 and Path(args[2]).name == "eventguard_agent.py" and args[3] == "_capture":
            args = [sys.executable, "-B", "-c", wrapper, str(Path(__file__).resolve().parents[1]/"src"), str(authority.path), *args[3:]]
        return spawn(args, **kwargs)
    with ExitStack() as stack:
        for module in ("acceptance_process", "agent_dispatch", "delivery_validation"):
            stack.enter_context(patch("eventguard." + module + ".open_authority", return_value=authority))
        stack.enter_context(patch("eventguard.agent_dispatch.spawn", side_effect=fixture_spawn))
        yield authority


def reserve_capture(authority, argv, directory, token, prompt):
    import hashlib
    return authority.reserve(token, "fixture-" + token, "test", hashlib.sha256(token.encode()).hexdigest(),
                             "acceptance", launch_hash=launch_hash(argv, prompt))


def capture_fixture(argv, directory, token, prompt, **kwargs):
    with isolated_budget(Path(directory) / "budget-fixture") as authority:
        reserve_capture(authority, argv, directory, token, prompt)
        return capture(argv, directory, token, prompt, **kwargs)
