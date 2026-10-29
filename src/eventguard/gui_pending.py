"""Validate bounded pending-page replies before changing the Tk list mode."""
import re

from .events.catalog import STATUSES, SEVERITIES
from .events.schema import IDENTIFIER


def page(value, *, namespace, offset):
    """None is unknown; an available empty page is a distinct verified result."""
    try:
        total, requests, rows = value['total'], value['request_total'], value['events']
        if (value['state'] != 'available' or value['namespace'] != namespace
                or type(offset) is not int or not 0 <= offset <= 128
                or type(value['offset']) is not int or value['offset'] != offset
                or type(value['requested_offset']) is not int or value['requested_offset'] != offset
                or type(value['limit']) is not int or value['limit'] != 100
                or type(total) is not int or not 0 <= total <= 128
                or type(requests) is not int or not total <= requests <= min(128, total*4)
                or type(rows) is not list or len(rows) != min(100, max(0, total-offset))
                or type(value['has_more']) is not bool or value['has_more'] != (offset+len(rows) < total)
                or type(value['model_calls']) is not int or value['model_calls'] != 0
                or value['ack_performed'] is not False or value['data_trust'] != 'untrusted_data'):
            return None
        ids, count = [], 0
        for row in rows:
            identity, digest, status = row['event_id'], row['payload_hash'], row['status']
            if (type(identity) is not str or not IDENTIFIER.fullmatch(identity) or row['id'] != identity
                    or type(digest) is not str or re.fullmatch(r'[a-f0-9]{64}', digest) is None
                    or type(status) is not str or status not in STATUSES or row['handling_status'] != status
                    or type(row['severity']) is not str or row['severity'] not in SEVERITIES
                    or row['delivery_status'] not in ('pending', 'retry', 'ack', 'failed')
                    or type(row['pending_request_count']) is not int or not 1 <= row['pending_request_count'] <= 4):
                return None
            ids.append(identity)
            count += row['pending_request_count']
        if ids != sorted(set(ids)) or count > requests or (offset == 0 and len(rows) == total and count != requests):
            return None
        return {'events': [dict(row) for row in rows], 'total': total, 'request_total': requests,
                'offset': offset, 'has_more': value['has_more']}
    except (KeyError, ValueError, TypeError):
        return None
