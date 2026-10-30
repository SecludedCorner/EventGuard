"""Explicit, bounded CLI/host startup probes; never submit a model prompt."""
import re
import uuid

from .acceptance_control import read_json, write_json
from .acceptance_process import capture, launch_hash
from .capture_receipt import validate_receipt
from .codex_runtime import file_hash, inventory
from .local_paths import _guard

LIMIT = 64 * 1024
ARTIFACTS = ('capture-launch-intent.json', 'capture-start.json', 'capture-exit.json',
             'codex.jsonl', 'codex.stderr.txt')


def probes(executable):
    host = executable.parent/'codex-code-mode-host.exe'
    return {'version': [executable, '--version'], 'help': [executable, 'exec', '--help'],
            'host-help': [host, '--help'], 'host-stdio': [host, '--listen', 'stdio']}


def checked_probe(directory, name, argv):
    directory = _guard(directory)
    intent = read_json(directory/'capture-launch-intent.json')
    start = read_json(directory/'capture-start.json')
    receipt = read_json(directory/'capture-exit.json')
    if (intent.get('kind') != 'eventguard-capture-launch-intent-v1'
            or intent.get('launch_hash') != launch_hash(argv, '')
            or validate_receipt(receipt, start, intent.get('attempt_id'), require_success=True)):
        raise ValueError('codex_preflight_process_not_verified')
    outputs = []
    for filename in ('codex.jsonl', 'codex.stderr.txt'):
        with _guard(directory/filename).open('rb') as stream:
            data = stream.read(LIMIT+1)
        if len(data) > LIMIT:
            raise ValueError('codex_preflight_output_capacity')
        outputs.append(data.decode('utf-8'))
    output, errors = outputs
    valid = {'version': bool(re.fullmatch(r'codex-cli [0-9][0-9A-Za-z.+-]{0,80}\r?\n', output)),
        'help': all(value in output for value in ('Usage: codex exec', '--ignore-user-config',
                                                 '--ephemeral', '--json', '--sandbox')),
        'host-help': all(value in output for value in ('Usage: codex-code-mode-host', '--listen', 'stdio')),
        'host-stdio': output == ''}
    if errors or not valid[name]:
        raise ValueError('codex_preflight_output_not_verified')
    return {filename: file_hash(directory/filename) for filename in ARTIFACTS}, output.strip()


def inspect(executable, directory, runtime):
    executable, directory = _guard(executable), _guard(directory)
    if read_json(directory/'bundle-before.json') != runtime:
        raise ValueError('codex_preflight_bundle_changed')
    artifacts, version = {}, None
    for name, argv in probes(executable).items():
        artifacts[name], output = checked_probe(directory/name, name, argv)
        if name == 'version':
            version = output
    return dict(kind='eventguard-codex-no-model-preflight-v1', runtime_bundle=runtime,
                version=version, artifacts=artifacts, model_calls=0, probe_timeout_seconds=10,
                limitations=['startup/EOF only; model-to-MCP protocol remains unverified'])


def verified(executable, runtime=None):
    executable = _guard(executable)
    directory = executable.parent/'preflight'
    result = inspect(executable, directory, runtime if runtime is not None else inventory(executable))
    if read_json(directory/'verification.json') != result:
        raise ValueError('codex_preflight_evidence_changed')
    return result


def run(executable):
    executable = _guard(executable)
    before = inventory(executable)
    directory = executable.parent/'preflight'
    directory.mkdir(exist_ok=False)
    write_json(directory/'bundle-before.json', before)
    for name, argv in probes(executable).items():
        stage = directory/name
        stage.mkdir()
        if capture(argv, stage, uuid.uuid4().hex, '', limit=LIMIT, timeout_seconds=10) != 0:
            raise ValueError('codex_preflight_capture_failed')
        checked_probe(stage, name, argv)
    result = inspect(executable, directory, inventory(executable))
    write_json(directory/'verification.json', result)
    return verified(executable)
