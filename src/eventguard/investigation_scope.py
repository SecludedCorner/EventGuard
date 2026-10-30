"""Run-bound, single-use human model scope; preparing never starts a process."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

from .acceptance_control import read_json, write_json
from .acceptance_process import launch_hash
from .agent_dispatch import command, ROOT
from .agent_investigation import PROFILE, PROMPT, TOOLS, digest
from .codex_runtime import inventory
from .codex_preflight import verified as verified_preflight
from .events.store import event_payload_hash
from .local_paths import _guard


def file_hash(path):
    with _guard(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def scope(root, manifest, codex):
    root, codex = _guard(root), _guard(codex)
    runtime = inventory(codex)
    preflight = verified_preflight(codex, runtime)
    events = manifest['events']
    if manifest['case'] != 'investigation' or len(events) != 1 or events[0]['synthetic'] is not True:
        raise ValueError('single_synthetic_investigation_required')
    sources = {str(path.relative_to(ROOT)): file_hash(path)
               for folder in ('src', 'scripts') for path in sorted((ROOT/folder).rglob('*.py'))}
    identity = events[0]['event_id']
    args = command(codex, sys.executable, root/'source', root/'inbox', identity,
                   root/'stage-1', investigation=True)
    body = dict(kind=PROFILE, root=str(root), event_id=identity, event_hash=event_payload_hash(events[0]),
        codex_executable=str(codex), codex_sha256=file_hash(codex), runtime_bundle=runtime, python=sys.version.split()[0],
        runtime_preflight=preflight, source_hash=digest(sources), launch_hash=launch_hash(args, PROMPT), tasks=1, events=1,
        timeout_seconds=180, expected_tools=list(TOOLS), native_queries=0, remediation=False,
        model='existing CLI default; one ephemeral task, no guaranteed token/cost cap', retries=0)
    return dict(body, scope_hash=digest(body))


def prepare(root, manifest, codex):
    """A changed source/binary/launch needs a new reviewed scope; never approve it."""
    root = _guard(root)
    bound = scope(root, manifest, codex)
    target = root/'investigation-scope.json'
    if target.exists() and read_json(target) != bound:
        raise ValueError('investigation_scope_changed_new_directory_required')
    write_json(target, bound)
    approval = root/'human-approval.json'
    if not approval.exists():
        write_json(approval, dict(approved=False, scope_hash=bound['scope_hash'], approved_at=None, user_instruction=None))
    text = ('# 單事件真模型調查批准請求\n\n'
        f"事件：{bound['event_id']}；profile：{PROFILE}；Python：{bound['python']}。\n\n"
        f"CLI：{bound['codex_executable']}；SHA256：{bound['codex_sha256']}。\n\n"
        f"版本：{preflight_version(bound)}；四檔完整清單／SHA及無模型預檢證據hash見investigation-scope.json。\n\n"
        '預檢僅證明CLI與host啟動／stdio EOF，不保證模型至MCP協定成功；不得關閉code mode或放寬驗收。\n\n'
        f"source hash：{bound['source_hash']}；scope hash：{bound['scope_hash']}。\n\n"
        '僅一件自有合成 listener、一個短期 CLI 任務、180 秒，預期 receive/query/save_investigation/ACK 各一次；'
        '使用 CLI 既有預設模型，模型內部請求數與token／費用無硬上限保證。失敗不重試。\n\n'
        '只傳固定合成 metadata、事件／query／hash與有界分析。無原生查詢、shell、瀏覽器、其他工具或處置；'
        '不更改全域設定／帳戶。成功須保存分析、來源 ACK、四步原始trace、CLI與MCP私有Job自然退出／無殘留／無強停。'
        '錯序／工具錯誤／證據不符即失敗；逾時合作停止，只可清理自有Job，保留pending與實際結果。\n\n'
        '預期產物：manifest、source SQLite、inbox completed、stage-1 trace／capture／MCP HANDLE退出、validation。'
        '執行前須把本次人類批准原文、UTC時間與scope hash寫入human-approval.json；目前未批准／未啟動模型。\n')
    (root/'AUTHORIZATION_REQUEST.md').write_text(text, encoding='utf-8')
    return bound


def preflight_version(bound):
    return bound['runtime_preflight'].get('version', 'unknown')


def require_approval(root, manifest, codex):
    root = _guard(root)
    bound = scope(root, manifest, codex)
    saved = read_json(root/'investigation-scope.json')
    approval = read_json(root/'human-approval.json')
    if (saved != bound or approval.get('approved') is not True or approval.get('scope_hash') != bound['scope_hash']
            or type(approval.get('user_instruction')) is not str or not 1 <= len(approval['user_instruction']) <= 8000):
        raise ValueError('current_investigation_human_approval_required')
    stamp = datetime.fromisoformat(approval['approved_at'])
    if stamp.utcoffset() is None or not 0 <= (datetime.now(timezone.utc)-stamp).total_seconds() <= 86400:
        raise ValueError('current_investigation_human_approval_required')
    if manifest['stages'] or manifest['enqueued']:
        raise ValueError('single_use_investigation_scope_consumed')
    return bound
