"""Four-tool trace cross-check; protocol proof is not independent model provenance."""
from datetime import datetime

from .acceptance_evidence import _tool_result
from .agent_investigation import TOOLS, digest, report, result_id


def assess(trace, record, identity, exit_code, acknowledged):
    try:
        _check(trace, record, identity, exit_code, acknowledged)
        return dict(passed=True, event_id=identity, query_id=record['query_id'],
            result_id=record['result']['result_id'], completed_tools=list(TOOLS),
            scope='cli_protocol_evidence_not_independent_model_provenance',
            investigation_saved=True, outbox_acknowledged=True, evidence_errors=[])
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        return dict(passed=False, evidence_errors=['investigation_trace_or_durable_evidence_mismatch'])


def _check(trace, record, identity, exit_code, acknowledged):
    def require(condition):
        if not condition:
            raise ValueError()
    require(type(exit_code) is int and exit_code == 0 and acknowledged is True)
    require(type(trace) is list and len(trace) <= 4096)
    calls, starts, threads, turns = [], [], [], 0
    for row in trace:
        require(type(row) is dict and row.get('type') not in {'turn.failed', 'error'})
        typ = row.get('type')
        if typ == 'thread.started':
            threads.append(row.get('thread_id'))
        if typ == 'turn.completed':
            turns += 1
        if typ in {'item.started', 'item.updated', 'item.completed'}:
            item = row['item']
            require(type(item) is dict and item.get('type') in {'mcp_tool_call', 'agent_message', 'reasoning', 'todo_list'})
            if item.get('type') == 'mcp_tool_call':
                require(item.get('server') == 'eventguard_inbox' and item.get('tool') in TOOLS)
                if typ == 'item.started':
                    starts.append(item['id'])
                if typ == 'item.completed':
                    calls.append(item)
    require(turns == 1 and len(threads) == 1 and type(threads[0]) is str and bool(threads[0]))
    require(len(calls) == 4 and [call['tool'] for call in calls] == list(TOOLS))
    require(starts == [call['id'] for call in calls] and len(set(starts)) == 4)
    result, observed = record['result'], record['saved_evidence']
    query_id = record['query_id']
    require(record['event_id'] == identity == observed['event_id'] == result['event_id'])
    require(observed['payload_hash'] == record['payload_hash'])
    require(observed['evidence_hash'] == digest({k: v for k, v in observed.items() if k != 'evidence_hash'}))
    value = calls[2]['arguments']['report']
    saved = report(value, observed, query_id)
    require(result['investigation'] == saved and result['query_id'] == query_id)
    require(result['status'] == 'review_recorded' and result['decision'] == 'needs_more_evidence')
    require(result['incident_conclusion'] == 'not_assessed' and result['real_agent_wake_verified'] is False)
    require(result['result_id'] == result_id(identity, record['payload_hash'], query_id, 'needs_more_evidence', saved))
    stamps = [datetime.fromisoformat(record[k]) for k in ('received_at', 'queried_at')]
    stamps.append(datetime.fromisoformat(result['recorded_at']))
    require(all(stamp.utcoffset() is not None for stamp in stamps) and stamps == sorted(stamps))
    args = [{}, dict(event_id=identity), dict(event_id=identity, query_id=query_id, report=value),
            dict(event_id=identity, query_id=query_id, decision='needs_more_evidence')]
    replies = [dict(status='event_available', event_id=identity, snapshot=record['snapshot'], received_at=record['received_at']),
        dict(status='stored_minimal_snapshot', event_id=identity, query_id=query_id, snapshot=record['snapshot'],
             snapshot_only=True, system_query_executed=False, saved_evidence=observed),
        dict(result, outbox_acknowledged=False), dict(result, outbox_acknowledged=True)]
    for call, arguments, expected in zip(calls, args, replies):
        require(call.get('status') == 'completed' and call.get('error') is None)
        require(type(call.get('result')) is dict and call['result'].get('isError', call['result'].get('is_error', False)) is False)
        require(call['arguments'] == arguments and _tool_result(call) == expected)
