"""Read-only default policy conditions, independent of authorization or launch."""
from .dispatch_policy import load_policy
from .events.schema import validate_event

SCOPE = 'default_policy_conditions_only'


def snapshot(event, human_status):
    result = {'state': 'unknown', 'event_id': None, 'reasons': [], 'scope': SCOPE,
              'model_calls': 0, 'ack_performed': False}
    try:
        clean = validate_event(event)
        if human_status not in {'new', 'read', 'handled', 'ignored'}:
            return result
        delivery = event.get('delivery_status')
        if delivery not in {'pending', 'retry', 'ack', 'failed'}:
            return result
        policy = load_policy()
        reasons = []
        for field, value, code in (('severities', clean['severity'], 'severity_not_selected'),
                ('event_types', clean['event_type'], 'event_type_not_selected'),
                ('human_statuses', human_status, 'human_status_not_selected')):
            if value not in policy[field]:
                reasons.append(code)
        if delivery not in {'pending', 'retry'}:
            reasons.append('delivery_not_pending')
        return dict(result, event_id=clean['event_id'], reasons=reasons,
                    state='conditions_not_met' if reasons else 'conditions_met')
    except (ValueError, TypeError, KeyError):
        return result
