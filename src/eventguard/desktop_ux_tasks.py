"""Six synthetic tasks and exclusive, unverified operator-entered metrics."""
from datetime import datetime, timezone
import json
import math
import os

from .runtime import Runtime, read_json

TASKS = (
    ('U1', '查看七來源：辨認目前拒讀／部分／未知／過期，並區分歷史成功時間。'),
    ('U2', '查看 synthetic-ux-listener：找出觀察事實、未知與限制；判斷能否據此宣稱主機安全。'),
    ('U3', '將該事件標已讀再標已處理：核對人工歷程與接收狀態，說明兩者差異。'),
    ('U4', '使用人工狀態與接收篩選、清除並返回原事件：核對選取及保存狀態。'),
    ('U5', '查看另存查證：辨認歷史拒讀／截斷，說明不能支持的目前結論。'),
    ('U6', '備份並核對剛才備份，查看時間／轉換／未知範圍，再返回原事件。'),
)


def task_plan():
    return {'kind': 'desktop-synthetic-ux-plan-v1', 'synthetic': True, 'human_participation_verified': False,
            'tasks': [{'id': key, 'instruction': text, 'reported_metrics': None} for key, text in TASKS]}


def instructions():
    return ('合成固定情境，非主機實測；採集、模型、設定與ACK已停用。\n'
            '請依實際操作記錄步數、秒數與錯誤；程序不自填真人結果。\n\n'
            + '\n\n'.join(key+'：'+text for key, text in TASKS)
            + '\n\n只做真人準備；跨產品比較仍需相同條件、參與者與合法帳戶。')


def _write_new(path, value):
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False).encode('ascii')
    if len(encoded) > 8192:
        raise ValueError('desktop_task_bytes_limit')
    with path.open('xb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != encoded:
        raise ValueError('desktop_task_write_unconfirmed')


def prepare_tasks(root):
    _write_new(Runtime(root).path('tasks.json'), task_plan())


def record_task(root, task_id, steps, elapsed_seconds, errors, outcome):
    if task_id not in {key for key, _ in TASKS} or outcome not in ('completed', 'failed', 'unresolved'):
        raise ValueError('desktop_task_choice_invalid')
    if (any(type(n) is not int or not 0 <= n <= 1000 for n in (steps, errors))
            or type(elapsed_seconds) not in (int, float) or not math.isfinite(elapsed_seconds)
            or not 0 <= elapsed_seconds <= 900):
        raise ValueError('desktop_task_metrics_invalid')
    runtime = Runtime(root)
    if read_json(runtime.path('tasks.json'), limit=8192) != task_plan():
        raise ValueError('desktop_task_plan_invalid')
    value = {'kind': 'desktop-synthetic-ux-report-v1', 'synthetic': True, 'task_id': task_id,
        'steps': steps, 'elapsed_seconds': elapsed_seconds, 'errors': errors, 'outcome': outcome,
        'entry_source': 'operator_self_report_unverified', 'human_participation_verified': False,
        'recorded_at': datetime.now(timezone.utc).isoformat()}
    _write_new(runtime.path('task-'+task_id+'.json'), value)
    return value
