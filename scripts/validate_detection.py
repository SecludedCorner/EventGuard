"""Fixed synthetic detector -> SQLite -> dispatch qualification; no agent launch."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from eventguard.dispatch_policy import DEFAULT_POLICY, select_pending
from eventguard.events.store import EventStore, _guard
from eventguard.queue_inbox import QueueInbox
from eventguard.rules.configured import DEFAULT_RULES, apply_rules
from eventguard.rules.detector import evaluate

CORPUS = ROOT / 'tests/fixtures/detection-sentry.json'


def run(root):
    root = _guard(root)
    if not root.is_relative_to(ROOT / 'reports'):
        raise ValueError('detection_report_root_required')
    raw = CORPUS.read_bytes()
    corpus = json.loads(raw)
    cases = corpus['cases']
    identities = [case['id'] for case in cases]
    if len(set(identities)) != len(cases) or any(re.fullmatch(r'[a-z0-9-]{1,64}', item) is None for item in identities):
        raise ValueError('detection_case_identity_invalid')
    root.mkdir(exist_ok=False)
    results, totals = [], Counter()
    for case in cases:
        store = EventStore(root / case['id'] / 'source')
        state, emitted = None, []
        for index, sections in enumerate(case['stages']):
            state, events = evaluate(sections, state, now=1000 + index, host_id='synthetic-sentry')
            for event in events:
                event['synthetic'] = True  # The pure detector defaults to native provenance.
            events = apply_rules(events, DEFAULT_RULES)
            store.commit_evaluation(state, events)
            emitted.extend(events)
        actual = Counter((event['event_type'], event['severity']) for event in emitted)
        expected = Counter(tuple(item) for item in case['expect'])
        before = store.path.read_bytes()
        chosen = select_pending(QueueInbox(store.directory, root / case['id'] / 'inbox'), policy=DEFAULT_POLICY)
        preserved = store.path.read_bytes() == before
        eligible = chosen is not None
        observed = case['observable'] is True
        if observed:
            totals.update(tp=sum((actual & expected).values()), fp=sum((actual - expected).values()),
                          fn=sum((expected - actual).values()), tn=int(not actual and not expected))
        else:
            totals['unobserved'] += 1
        passed = actual == expected and eligible == case['eligible'] and preserved
        totals['passed'] += int(passed)
        results.append({'id': case['id'], 'observable': observed, 'passed': passed,
                        'events': [list(item) for item in actual.elements()], 'policy_eligible': eligible,
                        'source_unchanged_by_selection': preserved,
                        'pending': store.stats()['pending'], 'receipt_count': store.stats()['receipt_count']})
    report = {'schema_version': '1.0', 'scope': corpus['scope'],
              'corpus_sha256': hashlib.sha256(raw).hexdigest(), 'case_count': len(cases), 'policy': DEFAULT_POLICY,
              'metrics': dict(totals), 'cases': results, 'limitations': corpus['limitations'],
              'model_calls': 0, 'real_agent_woken': False, 'machine_scan_executed': False,
              'passed': totals['passed'] == len(cases)}
    (root / 'detection-summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    result = run(args.root)
    print(json.dumps({key: result[key] for key in ('passed', 'case_count', 'metrics', 'scope')}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
