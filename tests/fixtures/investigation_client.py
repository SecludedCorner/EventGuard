"""FAKE CLI client: actual synthetic stdio calls, never a model or human approval."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from eventguard.acceptance_evidence import _tool_result
from eventguard.processes import spawn, finish

source, state, identity, directory, project = sys.argv[1:]
child = spawn([sys.executable, '-B', str(ROOT/'scripts/eventguard_inbox_mcp.py'),
    '--source-dir', source, '--state-dir', state, '--event-id', identity,
    '--startup-evidence-dir', directory, '--project-root', project, '--investigation', '--exit-after-ack'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
messages = queue.Queue()
def reader():
    for line in child.stdout: messages.put(json.loads(line))
    child.stdout.close()
def errors():
    while child.stderr.read(4096): pass
    child.stderr.close()
readers = [threading.Thread(target=reader, daemon=True), threading.Thread(target=errors, daemon=True)]
for thread in readers: thread.start()
def rpc(number, method, params):
    child.stdin.write(json.dumps(dict(jsonrpc='2.0', id=number, method=method, params=params)).encode()+b'\n')
    child.stdin.flush()
    reply = messages.get(timeout=20)
    assert reply.get('id') == number and 'error' not in reply
    return reply['result']
def tool(number, name, args):
    item = dict(id='fake-'+name, type='mcp_tool_call', server='eventguard_inbox', tool=name, arguments=args)
    print(json.dumps(dict(type='item.started', item=item)), flush=True)
    raw = rpc(number, 'tools/call', dict(name=name, arguments=args))
    assert raw.get('isError', False) is False
    print(json.dumps(dict(type='item.completed', item=dict(item, status='completed', error=None, result=raw))), flush=True)
    return _tool_result(dict(result=raw))
try:
    print(json.dumps(dict(type='thread.started', thread_id='FAKE-CLI-NO-MODEL')), flush=True)
    rpc(1, 'initialize', dict(protocolVersion='2024-11-05', capabilities={}, clientInfo=dict(name='fake-cli-fixture', version='1')))
    child.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'); child.stdin.flush()
    rpc(2, 'tools/list', {})
    deadline = time.monotonic()+10
    while not (Path(directory)/'mcp-process-start.json').exists():
        if time.monotonic() >= deadline: raise RuntimeError('fixture_observer_not_bound')
        time.sleep(.02)
    tool(3, 'receive_event', {})
    query = tool(4, 'query_evidence', dict(event_id=identity))
    report = dict(summary='FAKE fixture: saved synthetic listener requires follow-up; host unverified.',
        finding='metadata_requires_followup', fact_keys=list(query['saved_evidence']['facts']),
        limitations=query['saved_evidence']['limitations'], next_step='request_authorized_evidence')
    tool(5, 'save_investigation', dict(event_id=identity, query_id=query['query_id'], report=report))
    tool(6, 'ack_event', dict(event_id=identity, query_id=query['query_id'], decision='needs_more_evidence'))
    assert child.wait(timeout=15) == 0
    print(json.dumps(dict(type='turn.completed')), flush=True)
finally:
    if not child.stdin.closed: child.stdin.close()
    receipt = finish(child, 'descendants_remaining', grace=2, request_stop=True)
    for thread in readers: thread.join(timeout=2)
    assert receipt['remaining_owned_processes'] == 0 and receipt['forcibly_terminated'] is False
