from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, List, Optional

from io_utils import ensure_parent_dir, write_json_atomic


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _is_failed_observation(event: Dict[str, Any]) -> bool:
    if not isinstance(event, dict):
        return False
    if str(event.get("kind") or "") != "observation":
        return False
    if event.get("ok") is False:
        return True
    if event.get("error"):
        return True
    output = event.get("output")
    if isinstance(output, dict):
        if output.get("ok") is False:
            return True
        if output.get("error"):
            return True
    return False


def _collect_events(
    events_path: str,
    *,
    run_id: str,
    event_seq_start: int,
    event_seq_end: int,
) -> List[Dict[str, Any]]:
    if not events_path or not os.path.exists(events_path):
        return []
    items: List[Dict[str, Any]] = []
    with open(events_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue
            if not isinstance(event, dict):
                continue
            seq = _safe_int(event.get("seq"), -1)
            if seq < 0:
                continue
            if event_seq_start > 0 and seq < event_seq_start:
                continue
            if event_seq_end > 0 and seq > event_seq_end:
                continue
            refs = event.get("refs") if isinstance(event.get("refs"), dict) else {}
            ref_run_id = str(refs.get("run_id") or "")
            if run_id and ref_run_id and ref_run_id != run_id:
                continue
            items.append(event)
    items.sort(key=lambda item: _safe_int(item.get("seq"), 0))
    return items


def _extract_tool_paths(event: Dict[str, Any]) -> Dict[str, str]:
    keys = (
        "tool_stdout_path",
        "tool_stderr_path",
        "tool_error_path",
        "stdout_path",
        "stderr_path",
        "error_path",
    )
    output = event.get("output") if isinstance(event.get("output"), dict) else {}
    meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}
    paths: Dict[str, str] = {}
    for key in keys:
        value = output.get(key)
        if not value:
            value = meta.get(key)
        if isinstance(value, str) and value.strip():
            paths[key] = value.strip()
    raw_from_meta = meta.get("raw_output_paths")
    if isinstance(raw_from_meta, dict):
        for key in ("tool_stdout_path", "tool_stderr_path", "tool_error_path"):
            value = raw_from_meta.get(key)
            if isinstance(value, str) and value.strip() and key not in paths:
                paths[key] = value.strip()
    return paths


def _derive_failure_code(event: Dict[str, Any], fallback_failure_code: str) -> str:
    if fallback_failure_code:
        return fallback_failure_code
    output = event.get("output") if isinstance(event.get("output"), dict) else {}
    for key in ("failure_code", "error_code"):
        value = output.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    err = event.get("error")
    if isinstance(err, str) and err.strip():
        return err.strip()
    output_err = output.get("error")
    if isinstance(output_err, str) and output_err.strip():
        return output_err.strip()
    return "UNKNOWN_FAILURE"


def _build_hop3(event: Dict[str, Any]) -> Dict[str, Any]:
    output = event.get("output") if isinstance(event.get("output"), dict) else {}
    paths = _extract_tool_paths(event)
    if paths:
        return {
            "source": "artifact_paths",
            "tool": output.get("tool") or event.get("name") or "",
            "paths": paths,
        }
    output_error = output.get("error")
    if isinstance(output_error, str) and output_error.strip():
        return {
            "source": "event_output",
            "tool": output.get("tool") or event.get("name") or "",
            "error": output_error.strip(),
        }
    event_error = event.get("error")
    if isinstance(event_error, str) and event_error.strip():
        return {
            "source": "event_error",
            "tool": output.get("tool") or event.get("name") or "",
            "error": event_error.strip(),
        }
    return {
        "source": "none",
        "tool": output.get("tool") or event.get("name") or "",
        "error": "No raw output captured",
    }


def build_failure_hops(
    events_path: str,
    *,
    run_id: str,
    event_seq_start: int,
    event_seq_end: int,
    fallback_failure_code: str = "",
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "generated_at": _utc_now_iso(),
        "event_span": {
            "seq_start": event_seq_start,
            "seq_end": event_seq_end,
        },
        "ready": True,
        "has_failure": False,
        "failure_code": fallback_failure_code or "",
        "failure_event_seq": None,
        "hop1_phase": None,
        "hop2_evidence": None,
        "hop3_tool_output": None,
    }

    events = _collect_events(
        events_path,
        run_id=run_id,
        event_seq_start=event_seq_start,
        event_seq_end=event_seq_end,
    )
    failed_events = [event for event in events if _is_failed_observation(event)]
    if not failed_events:
        return payload

    failure_event = failed_events[-1]
    failure_seq = _safe_int(failure_event.get("seq"), 0)
    refs = failure_event.get("refs") if isinstance(failure_event.get("refs"), dict) else {}

    related_action_seq: Optional[int] = None
    failure_name = str(failure_event.get("name") or "")
    for event in reversed(events):
        seq = _safe_int(event.get("seq"), 0)
        if seq >= failure_seq:
            continue
        if str(event.get("kind") or "") != "action":
            continue
        if failure_name and str(event.get("name") or "") != failure_name:
            continue
        related_action_seq = seq
        break

    payload["has_failure"] = True
    payload["failure_event_seq"] = failure_seq
    payload["failure_code"] = _derive_failure_code(failure_event, fallback_failure_code)
    payload["hop1_phase"] = {
        "phase": refs.get("phase") or "unknown",
        "seq": failure_seq,
        "actor": failure_event.get("actor") or "",
        "name": failure_event.get("name") or "",
        "summary": failure_event.get("summary") or "",
    }
    payload["hop2_evidence"] = {
        "task_id": refs.get("task_id"),
        "task_fingerprint": refs.get("task_fingerprint"),
        "run_id": refs.get("run_id") or run_id,
        "pm_iteration": refs.get("pm_iteration"),
        "director_iteration": refs.get("director_iteration"),
        "trajectory_path": refs.get("trajectory_path"),
        "evidence_path": refs.get("evidence_path"),
        "files": refs.get("files") if isinstance(refs.get("files"), list) else [],
        "related_action_seq": related_action_seq,
        "failure_event_seq": failure_seq,
    }
    payload["hop3_tool_output"] = _build_hop3(failure_event)
    return payload


def write_failure_index(run_dir: str, payload: Dict[str, Any]) -> str:
    if not run_dir:
        return ""
    output_path = os.path.join(run_dir, "failure_hops.json")
    ensure_parent_dir(output_path)
    write_json_atomic(output_path, payload)
    return output_path
