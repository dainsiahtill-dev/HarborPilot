import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

# --- Logic extracted from loop-director.py for testing ---

def parse_json_payload(text: str) -> Optional[Dict[str, Any]]:
    """Safe JSON parser that handles markdown code blocks."""
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
        candidate = candidate.strip()
    try:
        return json.loads(candidate)
    except Exception:
        pass
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except Exception:
            return None
    return None


def parse_acceptance(qa_text: str) -> Optional[bool]:
    """Parse acceptance decision from QA output with strict format."""
    if not qa_text:
        return None

    payload = parse_json_payload(qa_text)
    if isinstance(payload, dict) and "acceptance" in payload:
        value = payload.get("acceptance")
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized == "PASS":
                return True
            if normalized == "FAIL":
                return False
        if isinstance(value, bool):
            return value

    # Look for a specific marker line
    lines = qa_text.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith("ACCEPTANCE_DECISION:"):
            decision = line.split(":", 1)[1].strip().upper()
            if decision == "PASS":
                return True
            elif decision == "FAIL":
                return False
        elif line.startswith("ACCEPTANCE:"):
            decision = line.split(":", 1)[1].strip().upper()
            if decision == "PASS":
                return True
            elif decision == "FAIL":
                return False

    # Fallback to old logic for backward compatibility
    lower = qa_text.lower()
    for line in lower.splitlines():
        if "acceptance decision" in line:
            if "fail" in line:
                return False
            if "pass" in line:
                return True
    if "acceptance decision" in lower:
        if "fail" in lower and "pass" not in lower:
            return False
        if "pass" in lower and "fail" not in lower:
            return True
    if "fail" in lower and "pass" not in lower:
        return False
    if "pass" in lower and "fail" not in lower:
        return True
    return None


def _truncate_text(text: str, max_chars: int) -> str:
    if not text:
        return ""
    if max_chars is None or max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"


def _compact_str(value: Any, max_chars: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return _truncate_text(value.strip(), max_chars)


def _compact_list(values: Any, max_items: int, max_str_chars: int) -> List[str]:
    items: List[str] = []
    if isinstance(values, list):
        for item in values:
            if isinstance(item, str) and item.strip():
                items.append(_truncate_text(item.strip(), max_str_chars))
    elif isinstance(values, str) and values.strip():
        items.append(_truncate_text(values.strip(), max_str_chars))
    if max_items > 0 and len(items) > max_items:
        items = items[:max_items]
    return items


def compact_pm_payload(pm_payload: Optional[Dict[str, Any]], max_chars: int) -> Dict[str, Any]:
    """Compacts PM payload to fit into context window."""
    if not isinstance(pm_payload, dict):
        return {}

    def build(task_limit: int, list_limit: int, str_limit: int, include_evidence: bool) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if "overall_goal" in pm_payload:
            payload["overall_goal"] = _compact_str(pm_payload.get("overall_goal"), str_limit)
        if "focus" in pm_payload:
            payload["focus"] = _compact_str(pm_payload.get("focus"), str_limit)
        if "notes" in pm_payload:
            payload["notes"] = _compact_str(pm_payload.get("notes"), str_limit)
        tasks_out: List[Dict[str, Any]] = []
        tasks = pm_payload.get("tasks")
        if isinstance(tasks, list):
            for task in tasks[: max(task_limit, 0)]:
                if not isinstance(task, dict):
                    continue
                compact_task = {
                    "id": _compact_str(task.get("id"), 120),
                    "title": _compact_str(task.get("title"), str_limit),
                    "goal": _compact_str(task.get("goal"), str_limit),
                    "target_files": _compact_list(task.get("target_files"), list_limit, 200),
                    "context_files": _compact_list(task.get("context_files"), list_limit, 200),
                    "constraints": _compact_list(task.get("constraints"), list_limit, str_limit),
                    "acceptance": _compact_list(task.get("acceptance"), list_limit, str_limit),
                    "stop_conditions": _compact_list(task.get("stop_conditions"), list_limit, str_limit),
                }
                if include_evidence:
                    compact_task["required_evidence"] = task.get("required_evidence")
                    compact_task["policy_overrides"] = task.get("policy_overrides")
                tasks_out.append(compact_task)
        payload["tasks"] = tasks_out
        return payload

    candidate = build(task_limit=3, list_limit=8, str_limit=320, include_evidence=True)
    if max_chars > 0 and len(json.dumps(candidate, ensure_ascii=False)) > max_chars:
        candidate = build(task_limit=2, list_limit=6, str_limit=240, include_evidence=True)
    if max_chars > 0 and len(json.dumps(candidate, ensure_ascii=False)) > max_chars:
        candidate = build(task_limit=1, list_limit=4, str_limit=180, include_evidence=False)
    if max_chars > 0 and len(json.dumps(candidate, ensure_ascii=False)) > max_chars:
        task_ids = []
        tasks = pm_payload.get("tasks")
        if isinstance(tasks, list):
            for task in tasks[:2]:
                if isinstance(task, dict) and task.get("id"):
                    task_ids.append(_compact_str(task.get("id"), 120))
        summary_limit = 240
        if max_chars > 0:
            summary_limit = min(summary_limit, max_chars)
        candidate = {
            "summary": _compact_str(pm_payload.get("focus") or pm_payload.get("overall_goal") or "pm_tasks", summary_limit),
            "task_ids": task_ids,
        }
    if max_chars > 0 and len(json.dumps(candidate, ensure_ascii=False)) > max_chars:
        summary = candidate.get("summary") if isinstance(candidate, dict) else ""
        if not isinstance(summary, str):
            summary = str(summary)
        candidate = {"summary": summary}
        overhead = len(json.dumps({"summary": ""}, ensure_ascii=False))
        allowed = max_chars - overhead
        if allowed < 0:
            allowed = 0
        summary = summary[:allowed] if allowed > 0 else ""
        candidate = {"summary": summary}
        while summary and len(json.dumps(candidate, ensure_ascii=False)) > max_chars:
            summary = summary[:-1]
            candidate = {"summary": summary}
    return candidate


def validate_files_to_edit(files: List[str], workspace: str) -> Tuple[bool, List[str], List[str]]:
    """
    Ensure files are readable before edits.
    Returns: (is_valid, missing_files, unreadable_files)
    """
    if not files:
        return True, [], []
    
    missing: List[str] = []
    unreadable: List[str] = []
    
    for path in files:
        full_path = os.path.join(workspace, path)
        if not os.path.exists(full_path):
            missing.append(path)
            continue
        try:
            with open(full_path, "r", encoding="utf-8") as handle:
                handle.read(1)
        except Exception as exc:
            unreadable.append(f"{path} ({exc})")
            
    is_valid = len(unreadable) == 0
    return is_valid, missing, unreadable


def extract_required_evidence(pm_payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(pm_payload, dict):
        return {}
    if isinstance(pm_payload.get("required_evidence"), dict):
        return pm_payload.get("required_evidence")  # type: ignore
    tasks = pm_payload.get("tasks")
    if isinstance(tasks, list):
        for item in tasks:
            if isinstance(item, dict) and isinstance(item.get("required_evidence"), dict):
                return item.get("required_evidence")  # type: ignore
    return {}
