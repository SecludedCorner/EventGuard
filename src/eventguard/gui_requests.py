"""Validate an inert Catalog view before recovering explicit human retry keys."""
import re

from .desktop_requests import MAX_PENDING, _valid
from .events.disposition_history import IDENTIFIER


def recover(value):
    """None means unknown/blocked, distinct from an available empty journal."""
    try:
        event_id = value['event']['event_id']
        namespace, digest = value['namespace'], value['payload_hash']
        view = value['pending_handling_requests']
        if (type(event_id) is not str or not IDENTIFIER.fullmatch(event_id) or value['event_id'] != event_id
                or type(namespace) is not str or namespace not in ('live', 'test')
                or type(digest) is not str or re.fullmatch(r'[a-f0-9]{64}', digest) is None
                or view['state'] != 'available' or view['event_id'] != event_id
                or view['namespace'] != namespace or view['payload_hash'] != digest
                or type(view['requests']) is not list or len(view['requests']) > MAX_PENDING):
            return None
        result, ids = {}, set()
        for raw in view['requests']:
            item = _valid(raw)
            key = (event_id, item['status'])
            if (item['namespace'] != namespace or item['event_id'] != event_id or item['payload_hash'] != digest
                    or key in result or item['operation_id'] in ids):
                return None
            result[key] = item['operation_id']
            ids.add(item['operation_id'])
        return result
    except (ValueError, KeyError, TypeError):
        return None
