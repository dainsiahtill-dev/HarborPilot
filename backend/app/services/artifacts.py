import os
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from ..config import (
    DEFAULT_WORKSPACE, DEFAULT_PM_OUT, DEFAULT_PM_REPORT, DEFAULT_PM_LOG,
    DEFAULT_PM_SUBPROCESS_LOG, DEFAULT_DIRECTOR_SUBPROCESS_LOG, DEFAULT_DIALOGUE,
    DEFAULT_PLANNER, DEFAULT_OLLAMA, DEFAULT_QA, DEFAULT_RUNLOG, DEFAULT_DIRECTOR_STATUS,
    AGENTS_DRAFT_REL, AGENTS_FEEDBACK_REL, ARTIFACT_ROOT, ARTIFACT_NAMESPACE,
    LEGACY_ARTIFACT_NAMESPACE
)
from ..state import AppState
from ..utils import (
    build_cache_root, workspace_has_docs, read_workspace_status, resolve_artifact_path,
    select_latest_artifact, read_json, read_file_head, format_mtime, build_file_status,
    get_git_status, build_runtime_issues
)

def build_memory_payload(workspace: str, cache_root: str) -> Optional[Dict[str, Any]]:
    path = select_latest_artifact(workspace, cache_root, ".harborpilot/runtime/memory/last_state.json")
    if not path:
        return None
    # We need read_file_tail but utils imports read_file_tail
    # Wait, read_file_tail was in utils in my implementation.
    from ..utils import read_file_tail
    content = read_file_tail(path, max_lines=200, max_chars=20000)
    return {"content": content, "mtime": format_mtime(path)}

def build_success_stats_payload(workspace: str, cache_root: str) -> Dict[str, Any]:
    path = select_latest_artifact(workspace, cache_root, ".harborpilot/runtime/DIRECTOR_RESULT.json")
    result = read_json(path) if path else None
    
    # helper for compute_success_stats is not in utils?
    # I verified utils.py content, compute_success_stats was NOT in it.
    # It was in server.py around line 750. I missed it in utils.py.
    # I should add it to utils.py or defining it here.
    # It seems general enough, but only used here. Defining here is fine.
    return compute_success_stats_local(result)

def compute_success_stats_local(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {"successes": None, "total": None, "rate": None}
    if isinstance(result.get("results"), list):
        total = len(result["results"])
        successes = len([r for r in result["results"] if str(r.get("status") or "").lower() == "success"])
        rate = successes / total if total > 0 else None
        return {"successes": successes, "total": total, "rate": rate}
    if isinstance(result.get("successes"), (int, float)) and isinstance(result.get("total"), (int, float)):
        total_val = int(result["total"])
        successes_val = int(result["successes"])
        rate_val = result.get("success_rate")
        if not isinstance(rate_val, (int, float)) and total_val > 0:
            rate_val = successes_val / total_val
        return {"successes": successes_val, "total": total_val, "rate": rate_val}
    return {"successes": None, "total": None, "rate": None}

def build_snapshot(state: AppState) -> Dict[str, Any]:
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
    docs_present = workspace_has_docs(workspace)
    workspace_status = read_workspace_status(workspace)
    if not docs_present and not workspace_status:
        workspace_status = {
            "status": "NEEDS_DOCS_INIT",
            "reason": "docs/ directory not found",
            "actions": ["INIT_DOCS_WIZARD"],
            "workspace_path": os.path.abspath(workspace),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    if docs_present and workspace_status and workspace_status.get("status") == "NEEDS_DOCS_INIT":
        workspace_status = None

    pm_out = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_OUT)
    pm_report = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_REPORT)
    pm_log = resolve_artifact_path(workspace, cache_root, state.settings.json_log_path or DEFAULT_PM_LOG)
    pm_subprocess_log = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
    director_subprocess_log = resolve_artifact_path(workspace, cache_root, DEFAULT_DIRECTOR_SUBPROCESS_LOG)
    dialogue_path = resolve_artifact_path(workspace, cache_root, DEFAULT_DIALOGUE)
    pm_state_path = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/PM_STATE.json")
    director_state_path = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/memory/last_state.json")
    plan_path = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/PLAN.md")
    planner_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PLANNER)
    ollama_path = resolve_artifact_path(workspace, cache_root, DEFAULT_OLLAMA)
    qa_path = resolve_artifact_path(workspace, cache_root, DEFAULT_QA)
    runlog_path = resolve_artifact_path(workspace, cache_root, DEFAULT_RUNLOG)
    agents_draft_path = resolve_artifact_path(workspace, cache_root, AGENTS_DRAFT_REL)
    agents_feedback_path = resolve_artifact_path(workspace, cache_root, AGENTS_FEEDBACK_REL)
    agents_draft_actual = select_latest_artifact(workspace, cache_root, AGENTS_DRAFT_REL) or agents_draft_path
    agents_feedback_actual = select_latest_artifact(workspace, cache_root, AGENTS_FEEDBACK_REL) or agents_feedback_path
    agents_target_path = os.path.join(workspace, "AGENTS.md")
    runtime_issues = build_runtime_issues(state.settings, workspace)

    def _extract_goals(md_text: str) -> List[str]:
        if not md_text:
            return []
        lines = md_text.splitlines()
        goals: List[str] = []
        in_goals = False
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                heading = line.lstrip("#").strip().lower()
                if ("goal" in heading) or ("??" in heading):
                    in_goals = True
                    continue
                if in_goals:
                    break
            if not in_goals:
                lowered = line.lower()
                if lowered.startswith("goal:") or lowered.startswith("goals:"):
                    item = line.split(":", 1)[1].strip()
                    if item:
                        goals.append(item)
                elif line.startswith("??"):
                    parts = line.split("?", 1) if "?" in line else line.split(":", 1)
                    if len(parts) > 1:
                        item = parts[1].strip()
                        if item:
                            goals.append(item)
                continue
            if line.startswith(("-", "*")):
                item = line[1:].strip()
                if item:
                    goals.append(item)
                continue
            if line[0].isdigit() and "." in line:
                parts = line.split(".", 1)
                item = parts[1].strip() if len(parts) > 1 else ""
                if item:
                    goals.append(item)
                continue
            if line:
                goals.append(line)
        return goals

    def _load_goals() -> List[str]:
        candidates = [
            os.path.join(workspace, "docs", "00_overview.md"),
            os.path.join(workspace, "docs", "product", "requirements.md"),
        ]
        for candidate in candidates:
            text = read_file_head(candidate, max_chars=20000)
            goals = _extract_goals(text)
            if goals:
                return goals
        return []

    goals = _load_goals()

    file_entries = [
        ("PM_TASKS.json", pm_out),
        ("PM_REPORT.md", pm_report),
        ("PM_LOG.jsonl", pm_log),
        ("PM_SUBPROCESS.log", pm_subprocess_log),
        ("DIRECTOR_SUBPROCESS.log", director_subprocess_log),
        ("PM_STATE.json", pm_state_path),
        ("last_state.json", director_state_path),
        ("PM_TASK_HISTORY.jsonl", resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/PM_TASK_HISTORY.jsonl")),
        ("PLANNER_RESPONSE.md", planner_path),
        ("OLLAMA_RESPONSE.md", ollama_path),
        ("QA_RESPONSE.md", qa_path),
        ("RUNLOG.md", runlog_path),
        ("DIRECTOR_RESULT.json", resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/DIRECTOR_RESULT.json")),
        ("DIALOGUE.jsonl", dialogue_path),
    ]

    agents_review: Optional[Dict[str, Any]] = None
    has_agents = os.path.isfile(agents_target_path)
    has_draft = os.path.isfile(agents_draft_actual) if agents_draft_actual else False
    has_feedback = os.path.isfile(agents_feedback_actual) if agents_feedback_actual else False
    if (not has_agents) or has_draft or has_feedback:
        draft_failed = False
        if has_draft:
            preview = read_file_head(agents_draft_actual, max_chars=2000)
            lowered = preview.lower()
            draft_failed = ("generation failed" in lowered) or ("failed to write last message file" in lowered)
        agents_review = {
            "needs_review": not has_agents,
            "has_agents": has_agents,
            "draft_path": AGENTS_DRAFT_REL if has_draft else None,
            "feedback_path": AGENTS_FEEDBACK_REL if has_feedback else None,
            "draft_mtime": format_mtime(agents_draft_actual) if has_draft else None,
            "feedback_mtime": format_mtime(agents_feedback_actual) if has_feedback else None,
            "draft_failed": draft_failed,
        }

    payload = read_json(pm_out)
    if payload is None:
        payload = state.last_pm_payload or {}
    else:
        state.last_pm_payload = payload

    tasks = payload.get("tasks") if isinstance(payload, dict) else []
    if not goals and isinstance(payload, dict):
        overall_goal = str(payload.get("overall_goal") or "").strip()
        if overall_goal:
            goals = [overall_goal]
    pm_state_data = read_json(pm_state_path) or {}
    director_state_data = read_json(director_state_path) or {}
    git_status = get_git_status(workspace)
    plan_actual = select_latest_artifact(workspace, cache_root, ".harborpilot/runtime/PLAN.md") or plan_path
    plan_text = read_file_head(plan_actual, max_chars=20000)
    plan_mtime = format_mtime(plan_actual)

    return {
        "focus": str(payload.get("focus") or "").strip() if isinstance(payload, dict) else "",
        "notes": str(payload.get("notes") or "").strip() if isinstance(payload, dict) else "",
        "tasks": tasks if isinstance(tasks, list) else [],
        "goals": goals,
        "plan_text": plan_text,
        "plan_mtime": plan_mtime,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_status": build_file_status(file_entries),
        "file_paths": [f"{label}: {path}" for label, path in file_entries],
        "pm_state": pm_state_data,
        "director_state": director_state_data,
        "git": git_status,
        "agents_review": agents_review,
        "runtime_issues": runtime_issues,
        "workspace_status": workspace_status,
        "docs_present": docs_present,
    }

def read_director_status(workspace: str, cache_root: str) -> Optional[Dict[str, Any]]:
    # This was implicitly missing in utils too?
    # I verified utils.py and didn't see read_director_status.
    # It was in server.py lines 671-710.
    # I'll implement it here.
    from ..utils import _cache_join_double, _cache_join, legacy_artifact_rel_path, ARTIFACT_ROOT, LEGACY_ARTIFACT_ROOT

    candidates = []
    cache_path = resolve_artifact_path(workspace, cache_root, DEFAULT_DIRECTOR_STATUS)
    double_cache_path = _cache_join_double(cache_root, DEFAULT_DIRECTOR_STATUS) if cache_root else ""
    workspace_path = os.path.join(workspace, DEFAULT_DIRECTOR_STATUS)
    legacy_rel = legacy_artifact_rel_path(DEFAULT_DIRECTOR_STATUS)
    legacy_cache_path = _cache_join(cache_root, legacy_rel) if cache_root and legacy_rel else ""
    legacy_workspace_path = os.path.join(workspace, legacy_rel) if legacy_rel else ""
    state_rel = ""
    if legacy_rel:
        state_rel = legacy_rel.replace(f"{ARTIFACT_ROOT}/", f"{LEGACY_ARTIFACT_ROOT}/")
    state_cache_path = _cache_join(cache_root, state_rel) if cache_root and state_rel else ""
    state_workspace_path = os.path.join(workspace, state_rel) if state_rel else ""
    for path in (
        cache_path,
        double_cache_path,
        workspace_path,
        legacy_cache_path,
        legacy_workspace_path,
        state_cache_path,
        state_workspace_path,
    ):
        if not path:
            continue
        if path in candidates:
            continue
        if os.path.isfile(path):
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                mtime = 0.0
            candidates.append((mtime, path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, best_path = candidates[0]
    data = read_json(best_path)
    if isinstance(data, dict):
        data.setdefault("path", best_path)
    return data
