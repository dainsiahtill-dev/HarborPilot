import hashlib
import json
import os
from typing import Any, Dict, Optional

from io_utils import ensure_parent_dir, write_json_atomic


def _hash_payload(payload: Dict[str, Any]) -> str:
    try:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    except Exception:
        raw = str(payload)
    return "sha1:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()


def write_trajectory(
    state: Any,
    *,
    run_id: str,
    task_id: str,
    task_fingerprint: str,
    pm_iteration: Optional[int],
    director_iteration: int,
    result_payload: Dict[str, Any],
    policy_effective: Dict[str, Any],
    evidence_path: str,
    event_seq_start: int,
    event_seq_end: int,
) -> str:
    base_root = getattr(state, "cache_root_full", "") or getattr(state, "workspace_full", "")
    runs_dir = os.path.join(base_root, "state", "ollama", "runs", run_id)
    ensure_parent_dir(os.path.join(runs_dir, "trajectory.json"))

    span_start = event_seq_start if event_seq_start > 0 else event_seq_end
    span_end = event_seq_end
    if event_seq_end < event_seq_start:
        count = 0
    else:
        count = event_seq_end - event_seq_start + 1

    payload: Dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "task": {
            "task_id": task_id,
            "task_fingerprint": task_fingerprint,
            "pm_iteration": pm_iteration,
            "director_iteration": director_iteration,
        },
        "inputs": {
            "pm_tasks_path": getattr(state, "pm_task_path", ""),
            "policy_path": getattr(state, "policy_path", ""),
            "policy_effective_hash": _hash_payload(policy_effective),
            "required_evidence_present": bool(evidence_path),
        },
        "artifacts": {
            "director_result_path": getattr(state, "director_result_full", ""),
            "qa_response_path": getattr(state, "qa_full", ""),
            "planner_response_path": getattr(state, "planner_full", ""),
            "ollama_response_path": getattr(state, "ollama_full", ""),
            "reviewer_response_path": getattr(state, "reviewer_full", ""),
            "evidence_path": evidence_path,
            "events_path": getattr(state, "events_full", ""),
        },
        "event_span": {
            "seq_start": span_start,
            "seq_end": span_end,
            "count": count,
        },
        "summary": {
            "status": result_payload.get("status"),
            "error_code": result_payload.get("error_code"),
            "tool_rounds": result_payload.get("tool_rounds"),
            "total_lines_read": result_payload.get("total_lines_read"),
            "repair_attempts": result_payload.get("repair_attempts"),
            "risk_score": (result_payload.get("patch_risk") or {}).get("score"),
        },
    }
    write_json_atomic(os.path.join(runs_dir, "trajectory.json"), payload)
    return os.path.join(runs_dir, "trajectory.json")
