"""Local structured diagnosis. No arbitrary commands, paths, or model calls."""
from __future__ import annotations

from datetime import datetime
import re
import time
import uuid

from ..collectors.windows import WindowsCollectors, SECTION_IDS, FIELDS, STATUSES, redact, utc_now, coverage_metadata

MAX_ROWS = 100
OPERATIONS = {
    "health": {"keys": set(), "section": None},
    "query_listener": {"keys": {"protocol", "port"}, "section": "listeners"},
    "query_process": {"keys": {"pid", "created_at", "process_instance_ref"}, "section": "processes"},
    "query_defender": {"keys": {"view"}, "section": "defender"},
    "query_persistence_diff": {"keys": {"kind"}, "section": None},
    "query_version": {"keys": {"product_id"}, "section": "versions"},
}


def valid_iso(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


class DiagnosticAPI:
    def __init__(self, collectors=None):
        self.collectors = collectors or WindowsCollectors()

    def capabilities(self):
        return {"schema_version": "1.0", "read_only": True, "external_transport": False,
                "model_calls": False, "arbitrary_commands": False, "query_deadline_seconds": 15,
                "max_rows": MAX_ROWS, "sections": list(SECTION_IDS),
                "operations": {key: {"arguments": sorted(value["keys"] | {"max_rows", "request_id"})} for key, value in OPERATIONS.items()},
                "limitations": ["No threat history or active-infection verdict", "Persistence operation is current_only; no baseline comparison", "Version inventory covers fixed local Python runtime only", "Signature verification not implemented in this version", "No raw event contents or network probes", "Process identity requires creation timestamp or opaque instance reference"]}

    def query(self, operation, args=None, cancel=None):
        started = time.monotonic()
        request_id = uuid.uuid4().hex
        result = {"schema_version": "1.0", "request_id": request_id, "status": "unknown", "source": "none",
                  "observed_at": utc_now(), "coverage": {"status": "unknown"}, "rows": [],
                  "truncated": False, "error_code": None, "elapsed_ms": 0}

        def finish(status=None, code=None):
            if status:
                result["status"] = status
            if code:
                result["error_code"] = code
            result["coverage"]["status"] = result["status"]
            result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            return result

        if not isinstance(operation, str) or operation not in OPERATIONS or (args is not None and not isinstance(args, dict)):
            return finish("error", "invalid_request")
        args = dict(args or {})
        supplied_id = args.pop("request_id", request_id)
        if not isinstance(supplied_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", supplied_id):
            return finish("error", "invalid_request")
        result["request_id"] = supplied_id
        max_rows = args.pop("max_rows", MAX_ROWS)
        if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS or set(args) - OPERATIONS[operation]["keys"]:
            return finish("error", "invalid_request")
        section = OPERATIONS[operation]["section"]
        if operation == "query_listener":
            if args.get("protocol") not in ("TCP", "UDP") or type(args.get("port")) is not int or not 1 <= args["port"] <= 65535:
                return finish("error", "invalid_request")
        elif operation == "query_process":
            ref = args.get("process_instance_ref")
            by_ref = isinstance(ref, str) and re.fullmatch(r"proc-[a-f0-9]{24}", ref)
            by_pid = type(args.get("pid")) is int and 0 <= args["pid"] <= 2 ** 32 - 1 and valid_iso(args.get("created_at"))
            if not (by_ref or by_pid) or (ref is not None and not by_ref) or ("pid" in args and not by_pid) or (ref is not None and ("pid" in args or "created_at" in args)):
                return finish("error", "process_instance_required")
        elif operation == "query_defender":
            if args.get("view", "settings") != "settings":
                return finish("not_applicable", "operation_view_not_supported")
        elif operation == "query_persistence_diff":
            if args.get("kind") not in ("startup", "services", "tasks"):
                return finish("error", "invalid_request")
            section = args["kind"]
            result["coverage"]["mode"] = "current_only"
            result["coverage"]["baseline_comparison"] = "not_implemented"
        elif operation == "query_version":
            if args.get("product_id", "python_runtime") != "python_runtime":
                return finish("not_applicable", "product_not_allowlisted")
        if cancel is not None and cancel.is_set():
            return finish("cancelled", "cancelled_before_query")
        if operation == "health":
            runner = getattr(self.collectors, "runner", None)
            result["source"] = "tool_capabilities"
            result["rows"] = [{"name": "runner_pending", "value": bool(getattr(runner, "pending", False))},
                              {"name": "agent_receiver_connected", "value": False}]
            return finish("ok")
        try:
            sample = self.collectors.collect(section, cancel=cancel)
            if not isinstance(sample, dict) or sample.get("status") not in STATUSES or not isinstance(sample.get("rows"), list):
                raise ValueError()
            result["source"] = section
            result["observed_at"] = sample.get("observed_at") if valid_iso(sample.get("observed_at")) else result["observed_at"]
            result["status"] = sample["status"]
            result["coverage"].update(coverage_metadata(sample))
            result["coverage"]["source_status"] = sample["status"]
            result["coverage"]["source_scope"] = "local_metadata_only"
            safe_rows = []
            for row in sample["rows"]:
                if not isinstance(row, dict):
                    raise ValueError()
                safe_rows.append({key: redact(value) for key, value in row.items() if key in FIELDS[section] and isinstance(value, (str, int, float, bool, type(None)))})
            rows = safe_rows
            if sample["status"] not in ("ok", "partial"):
                result["rows"] = rows[:max_rows]
                result["truncated"] = len(rows) > max_rows
                return finish(code="source_" + sample["status"])
            if operation == "query_listener":
                rows = [row for row in rows if row.get("protocol") == args["protocol"] and row.get("port") == args["port"]]
            elif operation == "query_process":
                if args.get("process_instance_ref"):
                    rows = [row for row in rows if row.get("process_instance_ref") == args["process_instance_ref"]]
                else:
                    matching_pid = [row for row in rows if row.get("pid") == args["pid"]]
                    wanted = datetime.fromisoformat(args["created_at"].replace("Z", "+00:00"))
                    rows = [row for row in matching_pid if valid_iso(row.get("created_at"))
                            and datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) == wanted]
                    if matching_pid and not rows:
                        result["rows"] = []
                        return finish("unknown", "stale_process_instance")
                if not rows:
                    return finish("unknown", "process_not_observed")
            result["rows"] = rows[:max_rows]
            result["truncated"] = len(rows) > max_rows or (sample.get("coverage", {}).get("truncated") is True)
            if result["truncated"] and result["status"] == "ok":
                result["status"] = "partial"
            if result["status"] not in ("ok", "partial"):
                result["error_code"] = "source_" + result["status"]
            return finish()
        except Exception:
            result["rows"] = []
            return finish("error", "diagnostic_failed_without_raw_error")
