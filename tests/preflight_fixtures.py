"""Synthetic CLI probe evidence, never real startup or human approval."""
from eventguard import codex_preflight as preflight
from eventguard.acceptance_control import write_json
from eventguard.acceptance_process import launch_hash
from eventguard.codex_runtime import inventory


def seed_preflight(executable):
    directory = executable.parent/'preflight'
    directory.mkdir()
    runtime = inventory(executable)
    write_json(directory/'bundle-before.json', runtime)
    outputs = {'version': 'codex-cli 0.0.0-fixture\n',
        'help': 'Usage: codex exec --ignore-user-config --ephemeral --json --sandbox',
        'host-help': 'Usage: codex-code-mode-host.exe --listen stdio', 'host-stdio': ''}
    for number, (name, argv) in enumerate(preflight.probes(executable).items(), 1):
        stage = directory/name
        stage.mkdir()
        token, stamp = f'{number:032x}', '2026-10-30T00:00:00+00:00'
        write_json(stage/'capture-launch-intent.json', dict(kind='eventguard-capture-launch-intent-v1',
            attempt_id=token, launch_hash=launch_hash(argv, '')))
        write_json(stage/'capture-start.json', dict(attempt_id=token, codex_pid=number, created_at=stamp))
        write_json(stage/'capture-exit.json', dict(attempt_id=token, codex_pid=number, capture_complete=True,
            codex_exit_code=0, stdout_truncated=False, stderr_truncated=False, forcibly_terminated=False,
            child_exited=True, stop_reason='descendants_remaining',
            process=dict(managed=True, pid=number, created_at=stamp, child_exited=True, exit_code=0,
                remaining_owned_processes=0, forcibly_terminated=False, reason='natural_exit',
                shutdown_requested_reason='descendants_remaining')))
        (stage/'codex.jsonl').write_text(outputs[name], encoding='utf-8')
        (stage/'codex.stderr.txt').write_bytes(b'')
    write_json(directory/'verification.json', preflight.inspect(executable, directory, runtime))
