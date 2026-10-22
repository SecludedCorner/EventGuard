"""Safe fixtures only: no sockets, system changes or actual diagnostic queries."""
from datetime import datetime, timezone
import uuid


def make_synthetic(scenario="listener"):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    episode = "test-" + uuid.uuid4().hex
    mapping = {
        "listener":("listener.changed","pb-listener-change",{"protocol":"TCP","port":18080,"binding_scope":"all_interfaces"}),
        "defender":("protection.changed","pb-protection-change",{"property":"RealTimeProtectionEnabled","current":False}),
        "startup":("persistence.changed","pb-persistence-change",{"kind":"startup","count":1,"name_hash":"synthetic-name-only"}),
        "coverage":("coverage.degraded","pb-monitor-fault",{"source":"synthetic_collector","status":"denied"}),
    }
    if scenario not in mapping:
        raise ValueError("unknown_synthetic_scenario")
    kind, rule, evidence = mapping[scenario]
    return {"schema_version":"2.0","event_id":"evt-"+uuid.uuid4().hex,"host_id":"synthetic-host",
            "episode_id":episode,"correlation_id":episode,"sequence":1,"event_type":kind,
            "detector":{"id":"synthetic-"+scenario,"version":"1.0.0"},"rule_ref":{"rule_id":rule,"version":"1.0.0"},
            "transition":"new","severity":"warning","synthetic":True,"observed_at":now,"window":{"start":now,"end":now},
            "persisted_at":now,"baseline_version":"synthetic","evidence":evidence,
            "inference":{"summary":"Synthetic test only; no actual security finding.","compromise_conclusion":"undetermined"},
            "coverage":{"status":"ok","source":"synthetic_fixture"},"privacy":{"profile":"minimal-v1","redacted":True},"evidence_refs":[]}


def mock_diagnostic(event):
    if event.get("synthetic") is not True:
        raise ValueError("mock_diagnostics_reject_real_event")
    return {"schema_version":"1.0","request_id":"mock-"+event["event_id"],"status":"ok",
            "source":"synthetic_fixture","rows":[{"synthetic":True,"result":"controlled_test_only"}],
            "coverage":{"status":"ok"},"system_query_executed":False,"real_agent_woken":False}
