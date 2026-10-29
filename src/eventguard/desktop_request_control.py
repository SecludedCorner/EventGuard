"""Persist before a human operation; resolve only after its outer receipt."""
from .events.catalog import EventCatalog
from .events.disposition_history import OPERATION, STATUSES
from .events.store import EventStore, StoreError


def save(controller, event_id, status, operation_id):
    if type(operation_id) is not str or OPERATION.fullmatch(operation_id) is None:
        raise ValueError('invalid_history_identity')
    if type(status) is not str or status not in STATUSES:
        raise ValueError('invalid_event_status')
    with controller._lock:
        catalog = EventCatalog(controller.root, 'live')
        view = catalog.detail(event_id)['pending_handling_requests']
        if view['state'] != 'available':
            return {'state': 'blocked', 'reason': 'desktop_request_journal_unavailable',
                    'operation_started': False, 'request_pending': None, 'model_calls': 0}
        intent = {'namespace': 'live', 'event_id': event_id, 'status': status,
                  'operation_id': operation_id, 'payload_hash': view['payload_hash']}
        store = EventStore(catalog.directory)
        try:
            store._prepare_desktop_request(intent, namespace='live')
        except (OSError, ValueError, StoreError):
            return {'state': 'blocked', 'reason': 'desktop_request_prepare_unconfirmed',
                    'operation_started': False, 'request_pending': None, 'model_calls': 0}
        # This decorated method includes activity.begin AND activity.complete.
        value = controller._set_status_bound(event_id, status, operation_id, intent['payload_hash'])
        confirmed = (isinstance(value, dict) and value.get('state') == 'event_status_updated'
                     and value.get('event_id') == event_id and value.get('namespace') == 'live'
                     and value.get('status') in STATUSES and value.get('ack_performed') is False)
        if not confirmed:
            value = value if isinstance(value, dict) else {'state': 'error', 'reason': 'desktop_result_invalid'}
            return dict(value, request_pending=True, request_operation_id=operation_id)
        try:
            store._complete_desktop_request(intent, namespace='live')
        except (OSError, ValueError, StoreError):
            return {'state': 'error', 'reason': 'desktop_request_completion_unconfirmed',
                    'operation_may_have_completed': True, 'automatic_retry_allowed': False,
                    'request_pending': True, 'request_operation_id': operation_id, 'model_calls': 0}
        return dict(value, request_pending=False, request_operation_id=operation_id)
