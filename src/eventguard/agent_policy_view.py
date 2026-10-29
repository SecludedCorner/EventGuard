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


def text(value, event_id):
    reasons = {'severity_not_selected': '嚴重度未被預設政策選中',
               'event_type_not_selected': '事件類型未被預設政策選中',
               'human_status_not_selected': '人工狀態未被預設政策選中',
               'delivery_not_pending': '投遞狀態不是待接收或重試'}
    unknown = ['Agent 預設政策條件：未知；快照缺失或無法核對，不代表安全或已喚醒。']
    if (type(value) is not dict or set(value) != {'state', 'event_id', 'reasons', 'scope', 'model_calls', 'ack_performed'}
            or type(event_id) is not str or value.get('event_id') != event_id or value.get('scope') != SCOPE
            or type(value.get('model_calls')) is not int or value['model_calls'] != 0 or value.get('ack_performed') is not False):
        return unknown
    codes = value['reasons']
    if (type(codes) is not list or len(codes) > 4 or any(type(code) is not str or code not in reasons for code in codes)
            or len(set(codes)) != len(codes)):
        return unknown
    if value['state'] == 'conditions_met' and not codes:
        lines = ['Agent 預設政策條件：符合；這不是啟動授權或喚醒證據。']
    elif value['state'] == 'conditions_not_met' and codes:
        lines = ['Agent 預設政策條件：不符合。', *['• ' + reasons[code] for code in codes]]
    else:
        return unknown
    return [*lines, '這是讀取詳情時的預設條件快照；自訂 dispatcher、重試時間／lease、接收權限與啟動同意需另核對。',
            '符合不代表 agent 已喚醒、ACK 或防守成功；查看不會啟動模型或改變門檻。']
