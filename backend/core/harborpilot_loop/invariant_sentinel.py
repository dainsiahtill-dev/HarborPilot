from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from io_utils import emit_event, read_file_safe, scan_last_seq
from anthropomorphic.memory_store import _has_refs


def _hash_payload(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def compute_contract_fingerprint(pm_payload: Optional[Dict[str, Any]]) -> str:
    if not isinstance(pm_payload, dict):
        return ""
    contract: Dict[str, Any] = {
        "overall_goal": pm_payload.get("overall_goal"),
        "focus": pm_payload.get("focus"),
        "tasks": [],
    }
    tasks = pm_payload.get("tasks") or []
    if isinstance(tasks, list):
        for item in tasks:
            if not isinstance(item, dict):
                continue
            contract["tasks"].append(
                {
                    "id": item.get("id"),
                    "goal": item.get("goal"),
                    "acceptance": item.get("acceptance") or item.get("acceptance_criteria"),
                }
            )
    return _hash_payload(contract)


def load_contract_fingerprint(pm_task_path: str) -> str:
    if not pm_task_path:
        return ""
    text = read_file_safe(pm_task_path)
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except Exception:
        return ""
    return compute_contract_fingerprint(payload if isinstance(payload, dict) else None)


def _check_events_append_only(
    events_path: str,
    *,
    start_seq: int = 0,
    start_size: int = 0,
) -> Optional[Dict[str, Any]]:
    if not events_path or not os.path.exists(events_path):
        return None
    end_size = 0
    try:
        end_size = os.path.getsize(events_path)
    except Exception:
        end_size = 0
    end_seq = scan_last_seq(events_path)
    if (start_size and end_size < start_size) or (start_seq and end_seq and end_seq < start_seq - 1):
        return {
            "code": "EVENTS_APPEND_ONLY",
            "message": "events.jsonl appears to shrink or rewind",
            "details": {
                "start_seq": start_seq,
                "end_seq": end_seq,
                "start_size": start_size,
                "end_size": end_size,
            },
        }
    return None


def _check_contract_immutable(
    *,
    initial_hash: str,
    pm_task_path: str,
) -> Optional[Dict[str, Any]]:
    if not initial_hash or not pm_task_path:
        return None
    current_hash = load_contract_fingerprint(pm_task_path)
    if not current_hash or current_hash == initial_hash:
        return None
    return {
        "code": "CONTRACT_IMMUTABLE",
        "message": "PM_TASKS contract fields changed during run",
        "details": {"initial_hash": initial_hash, "current_hash": current_hash, "pm_task_path": pm_task_path},
    }


def _check_memory_refs(memory_path: str, run_id: str) -> Optional[Dict[str, Any]]:
    if not memory_path or not os.path.exists(memory_path) or not run_id:
        return None
    missing: List[str] = []
    try:
        with open(memory_path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                context = data.get("context") if isinstance(data, dict) else None
                if not isinstance(context, dict):
                    continue
                if str(context.get("run_id") or "") != run_id:
                    continue
                if not _has_refs(context):
                    mem_id = str(data.get("id") or "")
                    if mem_id:
                        missing.append(mem_id)
    except Exception:
        return None
    if not missing:
        return None
    return {
        "code": "MEMORY_REFS",
        "message": "Memory items missing evidence refs",
        "details": {"missing_count": len(missing), "memory_ids": missing[:10]},
    }


def run_invariant_sentinel(
    *,
    events_path: str,
    run_id: str,
    step: int,
    pm_task_path: str = "",
    contract_fingerprint: str = "",
    events_seq_start: int = 0,
    events_size_start: int = 0,
    memory_path: str = "",
) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    contract_violation = _check_contract_immutable(
        initial_hash=contract_fingerprint,
        pm_task_path=pm_task_path,
    )
    if contract_violation:
        violations.append(contract_violation)
    events_violation = _check_events_append_only(
        events_path,
        start_seq=events_seq_start,
        start_size=events_size_start,
    )
    if events_violation:
        violations.append(events_violation)
    memory_violation = _check_memory_refs(memory_path, run_id)
    if memory_violation:
        violations.append(memory_violation)

    refs = {"run_id": run_id, "step": step, "phase": "sentinel"}
    emit_event(
        events_path,
        kind="observation",
        actor="System",
        name="invariant.check",
        refs=refs,
        summary="Invariant check " + ("PASS" if not violations else "FAIL"),
        output={"ok": not violations, "violations": violations},
    )
    for violation in violations:
        emit_event(
            events_path,
            kind="observation",
            actor="System",
            name="invariant.violation",
            refs=refs,
            summary=violation.get("message", "Invariant violation"),
            output=violation,
        )
    return {"ok": not violations, "violations": violations}
