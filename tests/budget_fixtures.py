"""Explicit isolated launch fixtures; never a production CLI bypass switch.

The application has no daily model quota. These fixtures move the short
OS-create gate into a temporary directory and fence the historical budget:
any capture, dispatch, acceptance or host read of it fails the test.
"""
from contextlib import contextmanager, ExitStack
from pathlib import Path
import sys
from unittest.mock import patch

from eventguard import acceptance_process, agent_budget
from eventguard.acceptance_process import capture
from eventguard.processes import spawn

SRC = Path(__file__).resolve().parents[1] / "src"
TESTS = Path(__file__).resolve().parent
LEGACY_SENTINEL = b"SYNTHETIC_HISTORICAL_BUDGET_NOT_READ_OR_CHANGED\x00"
WORKER = """import sys
sys.path[:0] = [sys.argv.pop(1), sys.argv.pop(1)]
from budget_fixtures import fenced
from eventguard.agent_dispatch import main
with fenced(sys.argv.pop(1), sys.argv.pop(1)):
    code = main(sys.argv[1:])
raise SystemExit(code)
"""


def _refuse_budget(*args, **kwargs):
    raise AssertionError("communication_path_must_not_open_historical_budget")


def _refuse_launch(*args, **kwargs):
    raise AssertionError("model_launch_requested")


def _fence_budget(stack):
    stack.enter_context(patch.object(acceptance_process, "open_authority", side_effect=_refuse_budget))
    stack.enter_context(patch.object(agent_budget, "public_status", side_effect=_refuse_budget))
    for name in ("open_existing", "__init__"):
        stack.enter_context(patch.object(agent_budget.BudgetAuthority, name, side_effect=_refuse_budget))


@contextmanager
def fenced(lock, legacy):
    """One process: temporary launch gate, refused historical budget."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(acceptance_process, "LAUNCH_LOCK", Path(lock)))
        stack.enter_context(patch.object(agent_budget, "AUTHORITY_PATH", Path(legacy)))
        _fence_budget(stack)
        yield


@contextmanager
def launch_forbidden():
    """Fail on any OS-create gate, worker spawn or historical budget read."""
    with ExitStack() as stack:
        for target in ("eventguard.acceptance_process.launch_gate", "eventguard.acceptance_process.spawn",
                       "eventguard.agent_dispatch.spawn"):
            stack.enter_context(patch(target, side_effect=_refuse_launch))
        _fence_budget(stack)
        yield


class LaunchFixture:
    """Temporary gate and a synthetic historical budget sentinel."""
    def __init__(self, root):
        self.lock = Path(root) / "launch-gate" / "launch.lock"
        self.legacy = Path(root) / "historical-budget" / "authority.sqlite3"
        self.lock.parent.mkdir(parents=True, exist_ok=True)
        self.legacy.parent.mkdir(parents=True, exist_ok=True)
        if not self.legacy.exists():
            self.legacy.write_bytes(LEGACY_SENTINEL)
        self.before = self._legacy_state()

    def _legacy_state(self):
        return self.legacy.read_bytes(), self.legacy.stat().st_mtime_ns

    def legacy_untouched(self):
        return self._legacy_state() == self.before

    def gate_entered(self):
        # FileLease keeps its file after release; absence means no OS-create gate.
        return self.lock.exists()


@contextmanager
def isolated_launch(root):
    fixture = LaunchFixture(root)

    def fixture_spawn(args, **kwargs):
        args = list(args)
        if len(args) >= 4 and Path(args[2]).name == "eventguard_agent.py" and args[3] == "_capture":
            args = [sys.executable, "-B", "-c", WORKER, str(SRC), str(TESTS),
                    str(fixture.lock), str(fixture.legacy), *args[3:]]
        return spawn(args, **kwargs)

    with fenced(fixture.lock, fixture.legacy), \
            patch("eventguard.agent_dispatch.spawn", side_effect=fixture_spawn):
        yield fixture
    if not fixture.legacy_untouched():
        raise AssertionError("historical_budget_changed")


def capture_fixture(argv, directory, token, prompt, **kwargs):
    with isolated_launch(Path(directory) / "launch-fixture"):
        return capture(argv, directory, token, prompt, **kwargs)
