import argparse
import datetime
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, replace


def enforce_utf8() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("LANG", "en_US.UTF-8")
    os.environ.setdefault("LC_ALL", "en_US.UTF-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


enforce_utf8()

SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PROMPT_PROFILE_ENV = "HARBORPILOT_PROMPT_PROFILE"
DEFAULT_READ_RADIUS = 80
DEFAULT_TOOL_COMMANDS = [
    "python tools.py ruff_check -- .",
    "python tools.py mypy -- .",
    "python tools.py pytest -- -q",
]
REQUIRED_MODULE_FILES = (
    "decision.py",
    "io_utils.py",
    "policy.py",
    "ollama_utils.py",
    "prompts.py",
    "shared.py",
)

def find_module_dir(base_dir: str) -> str:
    env_dir = os.environ.get("OLLAMA_LOOP_MODULE_DIR", "").strip()
    if env_dir:
        return env_dir
    candidates = [
        os.path.join(base_dir, "harborpilot-loop"),
        os.path.join(base_dir, "..", "modules", "harborpilot-loop"),
        os.path.join(base_dir, "..", "modules", "ollama-loop"),
    ]
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if not os.path.isdir(candidate):
            continue
        if all(os.path.isfile(os.path.join(candidate, filename)) for filename in REQUIRED_MODULE_FILES):
            return candidate
    for name in os.listdir(base_dir):
        candidate = os.path.join(base_dir, name)
        if not os.path.isdir(candidate):
            continue
        if all(os.path.isfile(os.path.join(candidate, filename)) for filename in REQUIRED_MODULE_FILES):
            return candidate
    return ""

MODULE_DIR = find_module_dir(SCRIPT_DIR)
if not MODULE_DIR:
    print("Shared loop modules not found. Set OLLAMA_LOOP_MODULE_DIR.")
    sys.exit(1)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

# Import from shared modules
try:
    from decision import select_backlog_target
    from io_utils import (
        build_cache_root,
        resolve_artifact_path,
        resolve_ramdisk_root,
        resolve_run_dir,
        state_to_ramdisk_enabled,
        workspace_has_docs,
        write_workspace_status,
        clear_workspace_status,
        ensure_memory_dir,
        ensure_ollama_available,
        ensure_parent_dir,
        ensure_plan_file,
        configure_jsonl_buffer,
        emit_event,
        emit_dialogue,
        flush_jsonl_buffers,
        get_event_seq,
        get_memory_summary,
        read_file_safe,
        read_memory_snapshot,
        resolve_workspace_path,
        scan_last_seq,
        set_dialogue_seq,
        set_event_seq,
        stop_requested,
        director_stop_requested,
        clear_director_stop_flag,
        update_latest_pointer,
        write_json_atomic,
        write_text_atomic,
    )
    from ollama_utils import invoke_ollama
    from policy import (
        apply_overrides,
        apply_task_overrides,
        build_base_policy,
        build_cli_overrides,
        extract_task_policy_overrides,
    )
    from director_policy_runtime import apply_policy_to_state
    from director_tooling import (
        count_tool_output_lines,
        extract_tool_budget,
        extract_tool_plan,
        normalize_tool_plan,
        _as_list,
        run_tool_plan,
    )
    from director_evidence import build_evidence_summary, summarize_tool_outputs, write_evidence_package
    from director_trajectory import write_trajectory
    from director_memory import update_memory_snapshot
    from director_exec import (
        assess_patch_risk,
        format_risk_summary,
        format_review_summary,
        restore_snapshot,
        run_ollama_apply,
        run_qa,
        run_reviewer,
        run_tool_commands,
        run_npm_commands,
        format_tool_results,
    )
    from director_gap_review import run_gap_review, render_gap_report, update_plan_with_gap_report
    from prompts import (
        build_planner_prompt,
        build_tool_planner_prompt,
        build_patch_planner_prompt,
        extract_between,
        parse_files_to_edit,
    )
    from shared import normalize_path, strip_ansi
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

@dataclass
class State:
    """State container for the loop execution."""
    workspace_full: str
    cache_root_full: str
    plan_full: str
    log_full: str
    planner_full: str
    ollama_full: str
    qa_full: str
    reviewer_full: str
    delay_seconds: int
    repair_rounds: int
    auto_repair: bool
    continue_on_error: bool
    show_output: bool
    model: str
    timeout: int
    auto_pick_target: bool
    memory_backend: str
    memory_enabled: bool
    memory_dir_full: str
    memory_snapshot_path: str
    memory_snapshot: Optional[Dict[str, Any]]
    memory_max_chars: int
    memory_store_enabled: bool
    memory_store_every: int
    memory_store_on_accept: bool
    run_npm_commands: bool
    npm_timeout: int
    gap_review_enabled: bool
    gap_report_full: str
    gap_max_headings: int
    gap_max_files: int
    gap_review_done: bool
    gap_write_plan: bool
    pm_task_path: str
    director_result_full: str
    dialogue_full: str
    events_full: str
    default_tools_enabled: bool
    reviewer_enabled: bool
    reviewer_rounds: int
    rollback_on_fail: bool
    qa_enabled: bool
    risk_block_threshold: int
    evidence_verbosity: str
    evidence_write_enabled: bool
    rag_topk: int
    rollback_on_block: bool
    budget_max_rounds: int
    budget_max_lines: int
    context_pm_tasks_max_chars: int
    context_known_files_max_chars: int
    context_last_result_max_chars: int
    context_tool_output_max_chars: int
    context_planner_output_max_chars: int
    context_ollama_output_max_chars: int
    policy_base: Dict[str, Any]
    policy_sources: Dict[str, str]
    policy_cli_overrides: Dict[str, Any]
    policy_path: str
    current_run_id: str = ""
    current_task_id: str = ""
    current_task_fingerprint: str = ""
    current_pm_iteration: Optional[int] = None
    current_director_iteration: Optional[int] = None

def write_text(path: str, text: str) -> None:
    write_text_atomic(path, text or "")


def append_log(log_path: str, text: str) -> None:
    ensure_parent_dir(log_path)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(text)


def write_director_result(state: State, payload: Dict[str, Any]) -> None:
    if not state.director_result_full:
        return
    try:
        write_json_atomic(state.director_result_full, payload)
    except Exception as exc:
        append_log(state.log_full, f"[WARN] Failed to write director result: {exc}\n")


def safe_int(value, default=-1):
    """Safely convert value to int with fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default



def parse_json_payload(text: str) -> Optional[Dict[str, Any]]:
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


def _compact_pm_payload(pm_payload: Optional[Dict[str, Any]], max_chars: int) -> Dict[str, Any]:
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


def _compact_known_files(files: List[str], max_chars: int, max_items: int = 200) -> str:
    if not files:
        return ""
    trimmed = files[: max_items if max_items > 0 else len(files)]
    text = "\n".join(trimmed)
    return _truncate_text(text, max_chars)


def _compact_tool_output_bundle(
    tool_outputs: List[Dict[str, Any]],
    tool_rounds: int,
    total_lines_read: int,
    max_chars: int,
    verbosity: str,
) -> Dict[str, Any]:
    results = build_evidence_summary(tool_outputs, verbosity)
    bundle = {"results": results, "rounds": tool_rounds, "total_lines_read": total_lines_read}
    if max_chars <= 0:
        return bundle
    while len(json.dumps(bundle, ensure_ascii=False)) > max_chars and len(results) > 1:
        results = results[:-1]
        bundle["results"] = results
    if len(json.dumps(bundle, ensure_ascii=False)) > max_chars and results:
        for item in results:
            if isinstance(item, dict):
                item.pop("sample", None)
                item.pop("content", None)
        bundle["results"] = results
    return bundle


def _compact_plan_for_event(plan: Any, max_steps: int = 6, max_chars: int = 2000) -> Any:
    if plan is None:
        return None
    if isinstance(plan, str):
        return _truncate_text(plan, max_chars)
    if isinstance(plan, dict):
        compact = dict(plan)
        steps = compact.get("steps")
        if isinstance(steps, list) and max_steps > 0 and len(steps) > max_steps:
            compact["steps"] = steps[:max_steps]
        if max_chars > 0 and len(json.dumps(compact, ensure_ascii=False)) > max_chars:
            compact.pop("steps", None)
            compact["summary"] = _compact_str(compact.get("summary"), max_chars)
        return compact
    return plan


def _truncate_for_review(state: State, planner_output: str, ollama_output: str) -> Tuple[str, str]:
    return (
        _truncate_text(planner_output, getattr(state, "context_planner_output_max_chars", 0)),
        _truncate_text(ollama_output, getattr(state, "context_ollama_output_max_chars", 0)),
    )


def parse_planner_payload(planner_text: str) -> Dict[str, Any]:
    payload = parse_json_payload(planner_text)
    if isinstance(payload, dict):
        plan_payload = payload.get("plan") if isinstance(payload.get("plan"), (dict, list, str)) else None
        act_payload = payload.get("act") if isinstance(payload.get("act"), dict) else payload
        brief = act_payload.get("brief") if isinstance(act_payload, dict) else None
        files = act_payload.get("files") if isinstance(act_payload, dict) else None
        if isinstance(brief, str) and isinstance(files, list):
            normalized_files: List[str] = []
            for item in files:
                if isinstance(item, str):
                    path = normalize_path(item)
                    if path:
                        normalized_files.append(path)
            raw_commands = act_payload.get("commands") if isinstance(act_payload, dict) else None
            commands: List[str] = []
            if isinstance(raw_commands, list):
                for cmd in raw_commands:
                    if isinstance(cmd, str) and cmd.strip():
                        commands.append(cmd.strip())
            raw_tool_commands = act_payload.get("tool_commands") if isinstance(act_payload, dict) else None
            tool_commands: List[str] = []
            if isinstance(raw_tool_commands, list):
                for cmd in raw_tool_commands:
                    if isinstance(cmd, str) and cmd.strip():
                        tool_commands.append(cmd.strip())
            return {
                "brief": brief.strip(),
                "files": normalized_files,
                "commands": commands,
                "tool_commands": tool_commands,
                "plan": plan_payload,
                "act": act_payload if isinstance(act_payload, dict) else None,
                "payload": payload,
                "source": "json",
            }
    return {
        "brief": extract_between(planner_text, "[OLLAMA_BEGIN]", "[OLLAMA_END]"),
        "files": parse_files_to_edit(planner_text),
        "commands": [],
        "tool_commands": [],
        "plan": None,
        "act": None,
        "payload": None,
        "source": "legacy",
    }


def run_tool_planner(state: State, pm_tasks_json: str, known_files: str, last_result: str) -> tuple[str, Dict[str, Any]]:
    prompt = build_tool_planner_prompt(pm_tasks_json, known_files, last_result)
    output = invoke_ollama(prompt, state.model, state.workspace_full, state.show_output, state.timeout)
    append_log(state.log_full, "[TOOL_PLANNER]\n" + strip_ansi(output) + "\n")
    payload = parse_json_payload(output) or {}
    return output, payload


def run_patch_planner(state: State, tool_output_json: str, pm_tasks_json: str) -> tuple[str, Dict[str, Any]]:
    prompt = build_patch_planner_prompt(tool_output_json, pm_tasks_json)
    output = invoke_ollama(prompt, state.model, state.workspace_full, state.show_output, state.timeout)
    write_text(state.planner_full, output)
    append_log(state.log_full, "[PATCH_PLANNER]\n" + strip_ansi(output) + "\n")
    payload = parse_json_payload(output) or {}
    return output, payload


def collect_known_files(pm_payload: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(pm_payload, dict):
        return []
    tasks = pm_payload.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
    files: List[str] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        for key in ("target_files", "context_files"):
            values = item.get(key)
            if isinstance(values, list):
                for entry in values:
                    if isinstance(entry, str) and entry.strip():
                        normalized = normalize_path(entry.strip())
                        if normalized:
                            files.append(normalized)
        required = item.get("required_evidence")
        if isinstance(required, dict):
            must_read = required.get("must_read")
            if isinstance(must_read, list):
                for entry in must_read:
                    if isinstance(entry, dict):
                        file_arg = entry.get("file") or entry.get("path")
                        if isinstance(file_arg, str) and file_arg.strip():
                            normalized = normalize_path(file_arg.strip())
                            if normalized:
                                files.append(normalized)
    required_top = pm_payload.get("required_evidence")
    if isinstance(required_top, dict):
        must_read = required_top.get("must_read")
        if isinstance(must_read, list):
            for entry in must_read:
                if isinstance(entry, dict):
                    file_arg = entry.get("file") or entry.get("path")
                    if isinstance(file_arg, str) and file_arg.strip():
                        normalized = normalize_path(file_arg.strip())
                        if normalized:
                            files.append(normalized)
    seen = set()
    unique: List[str] = []
    for path in files:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


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


def build_required_tool_plan(required: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(required, dict):
        return []
    plan: List[Dict[str, Any]] = []
    must_read = required.get("must_read")
    if isinstance(must_read, list):
        for entry in must_read:
            if not isinstance(entry, dict):
                continue
            file_arg = entry.get("file") or entry.get("path")
            if not file_arg:
                continue
            start_line = entry.get("start") or entry.get("start_line")
            end_line = entry.get("end") or entry.get("end_line")
            line_no = entry.get("line") or entry.get("around_line")
            around = entry.get("around")
            radius = entry.get("radius") or DEFAULT_READ_RADIUS
            if start_line is not None and end_line is not None:
                plan.append(
                    {"tool": "repo_read_slice", "args": {"file": file_arg, "start": start_line, "end": end_line}}
                )
            elif line_no is not None:
                plan.append(
                    {"tool": "repo_read_around", "args": {"file": file_arg, "line": line_no, "radius": radius}}
                )
            elif around:
                radius_value = safe_int(radius, DEFAULT_READ_RADIUS)
                fallback_lines = max(DEFAULT_READ_RADIUS * 2, radius_value * 2 if radius_value > 0 else 0)
                fallback_lines = min(fallback_lines, 200)
                plan.append(
                    {
                        "tool": "repo_rg",
                        "args": {"pattern": str(around), "paths": [file_arg], "max_results": 5, "radius": radius},
                        "auto_follow": True,
                        "fallback_head_lines": fallback_lines,
                    }
                )
    must_find = required.get("must_find_calls")
    if isinstance(must_find, list):
        for item in must_find:
            if isinstance(item, str) and item.strip():
                plan.append({"tool": "repo_rg", "args": {"pattern": item.strip(), "paths": ["."], "max_results": 20}})
            elif isinstance(item, dict):
                pattern = item.get("pattern") or item.get("query")
                paths = item.get("paths") or item.get("path") or ["."]
                if pattern:
                    plan.append(
                        {
                            "tool": "repo_rg",
                            "args": {"pattern": str(pattern), "paths": _as_list(paths), "max_results": 20},
                        }
                    )
    return plan


def run_planner(state: State, plan_text: str, memory_summary: str, target_note: str) -> str:
    prompt = build_planner_prompt(plan_text, memory_summary, target_note)
    output = invoke_ollama(prompt, state.model, state.workspace_full, state.show_output, state.timeout)
    write_text(state.planner_full, output)
    append_log(state.log_full, "[PLANNER]\n" + strip_ansi(output) + "\n")
    return output


def validate_files_to_edit(files: List[str], workspace: str, log_path: str) -> bool:
    """Ensure files are readable before edits; warn on missing files."""
    if not files:
        return True
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
    if missing:
        append_log(
            log_path,
            "[WARN] Files listed for edit are missing; treating as new files:\n"
            + "\n".join(f"- {path}" for path in missing)
            + "\n",
        )
    if unreadable:
        append_log(
            log_path,
            "[ERROR] Failed to read files before edit:\n"
            + "\n".join(f"- {entry}" for entry in unreadable)
            + "\n",
        )
        return False
    append_log(log_path, f"[INFO] Read {len(files) - len(missing)} file(s) before edit.\n")
    return True


def invoke_iteration(state: State, index: int, is_last: bool) -> Dict[str, Any]:
    """Execute a single iteration and return detailed results."""
    log_path = state.log_full
    run_start = time.time()
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state.current_director_iteration = index
    state.current_pm_iteration = None
    state.current_task_id = ""
    state.current_task_fingerprint = ""
    state.current_run_id = f"dir-{index:05d}"
    event_seq_start = get_event_seq() + 1
    append_log(log_path, f"\n## Run {index} - {stamp}\n")
    pm_iteration = None
    pm_task_id = ""
    pm_task_fingerprint = ""
    pm_task_title = ""
    pm_task_goal = ""

    def build_result(
        status: str,
        reason: str,
        acceptance: Optional[bool] = None,
        changed_files: Optional[List[str]] = None,
        task_id: str = "",
        task_fingerprint: str = "",
        task_title: str = "",
        task_goal: str = "",
        pm_iteration: Optional[int] = None,
        error_code: str = "",
        failure_code: str = "",
        duration: Optional[float] = None,
        repair_attempts: int = 0,
    ) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "timestamp": stamp,
            "timestamp_epoch": time.time(),
            "timestamp_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "run_id": state.current_run_id,
            "director_iteration": index,
            "pm_iteration": pm_iteration,
            "task_id": task_id,
            "task_fingerprint": task_fingerprint,
            "task_title": task_title,
            "task_goal": task_goal,
            "status": status,
            "acceptance": acceptance,
            "reason": reason,
            "error_code": error_code,
            "failure_code": failure_code,
            "duration": duration,
            "repair_attempts": repair_attempts,
            "changed_files": changed_files or [],
        }

    if director_stop_requested(state.workspace_full):
        clear_director_stop_flag(state.workspace_full)
        append_log(log_path, "[INFO] Director stop requested. Exiting before run.\n")
        run_id = f"pm-{pm_iteration:05d}" if isinstance(pm_iteration, int) else f"dir-{index:05d}"
        emit_dialogue(
            state.dialogue_full,
            speaker="System",
            type="warning",
            text="Director stop requested. Exiting.",
            summary="Director stop requested",
            run_id=run_id,
            pm_iteration=pm_iteration,
            director_iteration=index,
        )
        write_director_result(
            state,
            build_result(
                "blocked",
                "Stop requested",
                acceptance=None,
                task_id=pm_task_id,
                task_fingerprint=pm_task_fingerprint,
                task_title=pm_task_title,
                task_goal=pm_task_goal,
                pm_iteration=pm_iteration,
                error_code="STOP_REQUESTED",
                duration=0,
            ),
        )
        return {
            "ok": False,
            "acceptance": None,
            "changed_files": [],
            "error": "Stop requested",
            "duration": 0,
        }

    if stop_requested(state.workspace_full):
        append_log(log_path, "[INFO] Stop requested. Exiting before run.\n")
        run_id = f"pm-{pm_iteration:05d}" if isinstance(pm_iteration, int) else f"dir-{index:05d}"
        emit_dialogue(
            state.dialogue_full,
            speaker="System",
            type="warning",
            text="Stop requested. Director exiting.",
            summary="Director stop requested",
            run_id=run_id,
            pm_iteration=pm_iteration,
            director_iteration=index,
        )
        write_director_result(
            state,
            build_result(
                "blocked",
                "Stop requested",
                task_id=pm_task_id,
                task_fingerprint=pm_task_fingerprint,
                task_title=pm_task_title,
                task_goal=pm_task_goal,
                pm_iteration=pm_iteration,
                error_code="STOP_REQUESTED",
                duration=0,
            ),
        )
        return {
            "ok": False,
            "acceptance": None,
            "changed_files": [],
            "error": "Stop requested",
            "duration": 0,
        }

    plan_text = read_file_safe(state.plan_full).strip()
    if not plan_text:
        append_log(log_path, "Plan is empty. Aborting.\n")
        duration = time.time() - run_start
        write_director_result(
            state,
            build_result(
                "blocked",
                "Plan is empty",
                task_id=pm_task_id,
                task_fingerprint=pm_task_fingerprint,
                task_title=pm_task_title,
                task_goal=pm_task_goal,
                pm_iteration=pm_iteration,
                error_code="MISSING_PLAN",
                duration=duration,
            ),
        )
        return {
            "ok": False,
            "acceptance": None,
            "changed_files": [],
            "error": "Plan is empty",
            "duration": 0
        }

    target_note = "none"
    pm_task_note = ""
    pm_payload: Optional[Dict[str, Any]] = None
    pm_task_id = ""
    pm_task_fingerprint = ""
    pm_task_title = ""
    pm_task_goal = ""
    pm_task_acceptance: List[str] = []
    pm_iteration = None
    pm_task_path = state.pm_task_path or os.path.join(state.workspace_full, "scripts", ".harborpilot", "runtime", "PM_TASKS.json")
    try:
        if os.path.isfile(pm_task_path):
            pm_payload = parse_json_payload(read_file_safe(pm_task_path))
            if isinstance(pm_payload, dict):
                pm_iteration = pm_payload.get("pm_iteration")
                focus = str(pm_payload.get("focus") or "").strip()
                overall_goal = str(pm_payload.get("overall_goal") or "").strip()
                tasks = pm_payload.get("tasks") or []
                if isinstance(tasks, list):
                    task_lines = []
                    for item in tasks[:3]:
                        if not isinstance(item, dict):
                            continue
                        task_id = str(item.get("id") or "").strip()
                        task_fingerprint = str(item.get("fingerprint") or "").strip()
                        title = str(item.get("title") or "").strip()
                        goal = str(item.get("goal") or "").strip()
                        constraints = item.get("constraints") or []
                        target_files = item.get("target_files") or []
                        acceptance = item.get("acceptance") or []
                        if not pm_task_id and (task_id or title or goal):
                            pm_task_id = task_id
                            pm_task_fingerprint = task_fingerprint
                            pm_task_title = title
                            pm_task_goal = goal
                            if isinstance(acceptance, list):
                                pm_task_acceptance = [str(x) for x in acceptance if isinstance(x, str)]
                        head = ""
                        if task_id:
                            head = f"{task_id} "
                        if title and goal:
                            task_lines.append(f"- {head}{title}: {goal}")
                        elif title:
                            task_lines.append(f"- {head}{title}")
                        elif goal:
                            task_lines.append(f"- {head}{goal}")
                    if task_lines:
                        header_parts = []
                        if overall_goal:
                            header_parts.append(f"PM overall goal: {overall_goal}")
                        header_parts.append(f"PM focus: {focus}" if focus else "PM focus:")
                        pm_task_note = "\n".join(header_parts) + "\n" + "\n".join(task_lines)
                        if target_files:
                            pm_task_note += "\nTarget files: " + ", ".join([str(x) for x in target_files])
                        if constraints:
                            pm_task_note += "\nConstraints: " + ", ".join([str(x) for x in constraints])
                        if acceptance:
                            pm_task_note += "\nAcceptance: " + ", ".join([str(x) for x in acceptance])
    except Exception as exc:
        append_log(state.log_full, f"[WARN] Failed to read PM_TASKS.json: {exc}\n")
    policy_effective = state.policy_base
    policy_sources = state.policy_sources
    try:
        policy_overrides = extract_task_policy_overrides(pm_payload or {})
        policy_effective, policy_sources = apply_task_overrides(state.policy_base, state.policy_sources, policy_overrides)
        if state.policy_cli_overrides:
            policy_effective, policy_sources = apply_overrides(
                policy_effective,
                policy_sources,
                state.policy_cli_overrides,
                "cli",
            )
        apply_policy_to_state(state, policy_effective)
    except Exception as exc:
        append_log(state.log_full, f"[WARN] Failed to apply policy overrides: {exc}\n")
    target_index = -1
    state.current_task_id = pm_task_id
    state.current_task_fingerprint = pm_task_fingerprint
    state.current_pm_iteration = pm_iteration
    state.current_run_id = f"pm-{pm_iteration:05d}" if isinstance(pm_iteration, int) else f"dir-{index:05d}"

    # Re-bucket if run_id changed (and we were auto-bucketing)
    # We detect "auto-bucketing" by checking if current log_path contains the OLD run_id "dir-XXXXX"
    # but the NEW run_id is "pm-XXXXX".
    old_run_id = f"dir-{index:05d}"
    if state.current_run_id != old_run_id and old_run_id in state.log_full:
         run_id = state.current_run_id
         run_dir = resolve_run_dir(state.workspace_full, state.cache_root_full, run_id)
         update_latest_pointer(state.workspace_full, state.cache_root_full, run_id)
         
         state = replace(
            state,
            log_full=os.path.join(run_dir, "RUNLOG.md"),
            director_result_full=os.path.join(run_dir, "DIRECTOR_RESULT.json"),
            events_full=os.path.join(run_dir, "events.jsonl"),
            planner_full=os.path.join(run_dir, "PLANNER_RESPONSE.md"),
            ollama_full=os.path.join(run_dir, "OLLAMA_RESPONSE.md"),
            qa_full=os.path.join(run_dir, "QA_RESPONSE.md"),
            reviewer_full=os.path.join(run_dir, "REVIEWER_RESPONSE.md"),
        )
         log_path = state.log_full
         append_log(log_path, f"\n## Run {index} (Switch to {run_id}) - {stamp}\n")

    if pm_task_note:
        target_note = pm_task_note
        append_log(state.log_full, "[INFO] Using PM tasks as target note.\n")
        run_id = f"pm-{pm_iteration:05d}" if isinstance(pm_iteration, int) else f"dir-{index:05d}"
        emit_dialogue(
            state.dialogue_full,
            speaker="Director",
            type="say",
            text=f"Received task {pm_task_id}. I will follow acceptance criteria.",
            summary=f"Received: {pm_task_id}",
            run_id=run_id,
            pm_iteration=pm_iteration,
            director_iteration=index,
            refs={"task_id": pm_task_id, "task_fingerprint": pm_task_fingerprint, "phase": "receipt"},
        )
    elif state.auto_pick_target:
        last_target_index = -1
        snapshot = state.memory_snapshot or {}
        if isinstance(snapshot, dict):
            last_target_index = safe_int(snapshot.get("last_target_index"), -1)
        target_pick = select_backlog_target(plan_text, last_target_index)
        target_note = target_pick.get("item") or "none"
        target_index = target_pick.get("index", last_target_index)
        if target_note != "none":
            append_log(log_path, f"[INFO] Auto-target: {target_note}\n")

    memory_summary = (
        get_memory_summary(state.memory_snapshot, state.memory_max_chars)
        if state.memory_enabled
        else "disabled"
    )

    gap_review_ran = False
    if state.gap_review_enabled and not state.gap_review_done:
        gap_output = run_gap_review(state, log_path)
        if state.gap_write_plan and gap_output:
            report_body = render_gap_report(gap_output)
            update_plan_with_gap_report(state.plan_full, report_body)
        gap_review_ran = True
        state.gap_review_done = True

    tool_outputs: List[Dict[str, Any]] = []
    tool_rounds = 0
    total_lines_read = 0
    fsm_error = ""
    planner_output = ""
    planner_payload: Dict[str, Any] = {}
    compact_pm_payload = _compact_pm_payload(pm_payload, state.context_pm_tasks_max_chars)
    pm_tasks_json = json.dumps(compact_pm_payload, ensure_ascii=False)
    known_files = _compact_known_files(
        collect_known_files(pm_payload),
        state.context_known_files_max_chars,
    )
    last_result = ""
    if state.context_last_result_max_chars and state.context_last_result_max_chars > 0:
        last_result = _truncate_text(last_result, state.context_last_result_max_chars)
    required_evidence = extract_required_evidence(pm_payload)
    forced_tool_plan: Optional[List[Dict[str, Any]]] = build_required_tool_plan(required_evidence) or None
    required_evidence_done = False
    max_rounds = state.budget_max_rounds or 6
    max_lines = state.budget_max_lines or 1200
    tool_cache: Dict[Tuple[str, Tuple[str, ...]], Dict[str, Any]] = {}
    around_history: Dict[Tuple[str, int], Dict[str, Any]] = {}
    need_more_context_count = 0

    while True:
        if tool_rounds >= max_rounds:
            fsm_error = "Budget exceeded: max_rounds"
            break
        if total_lines_read >= max_lines:
            fsm_error = "Budget exceeded: max_total_lines"
            break
        tool_rounds += 1

        if forced_tool_plan is None:
            tool_planner_output, tool_plan_payload = run_tool_planner(state, pm_tasks_json, known_files, last_result)
            tool_plan = extract_tool_plan(tool_plan_payload)
            max_rounds, max_lines = extract_tool_budget(tool_plan_payload, max_rounds, max_lines)
            if not tool_plan:
                fsm_error = "Empty tool_plan"
                append_log(log_path, f"[ERROR] Tool planner returned empty plan. Raw:\n{tool_planner_output}\n")
                break
        else:
            tool_plan = forced_tool_plan
            forced_tool_plan = None
            if not required_evidence_done:
                required_evidence_done = True

        tool_plan = normalize_tool_plan(tool_plan, around_history, need_more_context_count)

        tool_outputs_round = run_tool_plan(state, tool_plan, log_path, tool_cache, around_history)
        tool_outputs.extend(tool_outputs_round)
        total_lines_read += sum(count_tool_output_lines(out) for out in tool_outputs_round)

        tool_output_bundle = _compact_tool_output_bundle(
            tool_outputs,
            tool_rounds,
            total_lines_read,
            state.context_tool_output_max_chars,
            state.evidence_verbosity,
        )
        planner_output, patch_payload = run_patch_planner(
            state,
            json.dumps(tool_output_bundle, ensure_ascii=False),
            pm_tasks_json,
        )
        if not isinstance(patch_payload, dict):
            fsm_error = "Patch planner returned no JSON"
            break
        if patch_payload.get("need_more_context") is True:
            need_more_context_count += 1
            forced_tool_plan = extract_tool_plan(patch_payload)
            if not forced_tool_plan:
                fallback_plan = build_required_tool_plan(required_evidence)
                if fallback_plan:
                    append_log(
                        log_path,
                        "[WARN] Patch planner requested more context but tool_plan missing; "
                        "falling back to required_evidence tool plan.\n",
                    )
                    forced_tool_plan = fallback_plan
                    required_evidence_done = True
                else:
                    append_log(
                        log_path,
                        "[WARN] Patch planner requested more context but tool_plan missing; "
                        "re-running tool planner.\n",
                    )
                    forced_tool_plan = None
                continue
            continue

        planner_payload = parse_planner_payload(planner_output)
        need_more_context_count = 0
        break

    evidence_path = None
    if state.evidence_write_enabled:
        evidence_path = write_evidence_package(
            state,
            tool_outputs,
            pm_task_id,
            pm_iteration,
            index,
            tool_rounds,
            total_lines_read,
        )

    if fsm_error:
        duration = time.time() - run_start
        write_director_result(
            state,
            build_result(
                "blocked",
                fsm_error,
                acceptance=None,
                task_id=pm_task_id,
                task_fingerprint=pm_task_fingerprint,
                task_title=pm_task_title,
                task_goal=pm_task_goal,
                pm_iteration=pm_iteration,
                error_code="FSM_BLOCKED",
                failure_code="TOOL_BUDGET_EXCEEDED" if "Budget" in fsm_error else "FSM_ERROR",
                duration=duration,
            ),
        )
        return {
            "ok": False,
            "acceptance": None,
            "changed_files": [],
            "error": fsm_error,
            "duration": duration,
        }

    def build_event_refs(phase: str, files: Optional[List[str]] = None) -> Dict[str, Any]:
        refs: Dict[str, Any] = {
            "task_id": pm_task_id,
            "task_fingerprint": pm_task_fingerprint,
            "run_id": state.current_run_id,
            "pm_iteration": pm_iteration,
            "director_iteration": index,
            "phase": phase,
        }
        if files:
            refs["files"] = files
        return refs

    brief = planner_payload.get("brief", "")
    files = planner_payload.get("files", [])
    commands = planner_payload.get("commands", [])
    tool_commands = planner_payload.get("tool_commands") or []
    plan_payload = planner_payload.get("plan")
    act_payload = planner_payload.get("act") if isinstance(planner_payload.get("act"), dict) else None
    run_id = f"pm-{pm_iteration:05d}" if isinstance(pm_iteration, int) else f"dir-{index:05d}"
    if brief:
        emit_dialogue(
            state.dialogue_full,
            speaker="Director",
            type="progress",
            text=f"Planner brief: {brief[:160]}",
            summary="Planner ready",
            run_id=run_id,
            pm_iteration=pm_iteration,
            director_iteration=index,
            refs={"task_id": pm_task_id},
        )

    if isinstance(brief, str) and brief.strip().lower().startswith("blocked:"):
        append_log(log_path, f"[ERROR] Planner returned blocked brief: {brief}\n")
        duration = time.time() - run_start
        write_director_result(
            state,
            build_result(
                "blocked",
                brief.strip(),
                acceptance=None,
                task_id=pm_task_id,
                task_fingerprint=pm_task_fingerprint,
                task_title=pm_task_title,
                task_goal=pm_task_goal,
                pm_iteration=pm_iteration,
                error_code="INSUFFICIENT_CONTEXT",
                duration=duration,
            ),
        )
        return {
            "ok": False,
            "acceptance": None,
            "changed_files": [],
            "error": brief.strip(),
            "duration": duration,
        }

    if not brief:
        if planner_payload.get("source") == "json":
            append_log(log_path, "[ERROR] Planner JSON missing brief.\n")
        else:
            append_log(log_path, "[ERROR] Planner response missing [OLLAMA_BEGIN]/[OLLAMA_END].\n")
        duration = time.time() - run_start
        write_director_result(
            state,
            build_result(
                "blocked",
                "Missing brief",
                acceptance=None,
                task_id=pm_task_id,
                task_fingerprint=pm_task_fingerprint,
                task_title=pm_task_title,
                task_goal=pm_task_goal,
                pm_iteration=pm_iteration,
                error_code="MISSING_CONTEXT",
                failure_code="PLANNER_FAILURE",
                duration=duration,
            ),
        )
        if state.continue_on_error:
            return {
                "ok": True,
                "acceptance": None,
                "changed_files": [],
                "error": "Missing brief",
                "duration": time.time() - run_start
            }

        return {
            "ok": False,
            "acceptance": None,
            "changed_files": [],
            "error": "Missing brief",
            "duration": time.time() - run_start
        }
    if not files:
        if planner_payload.get("source") == "json":
            append_log(log_path, "[ERROR] Planner JSON missing file list.\n")
        else:
            append_log(log_path, "[ERROR] Planner response missing file list.\n")
        duration = time.time() - run_start
        write_director_result(
            state,
            build_result(
                "blocked",
                "Missing file list",
                acceptance=None,
                task_id=pm_task_id,
                task_fingerprint=pm_task_fingerprint,
                task_title=pm_task_title,
                task_goal=pm_task_goal,
                pm_iteration=pm_iteration,
                error_code="MISSING_CONTEXT",
                failure_code="PLANNER_FAILURE",
                duration=duration,
            ),
        )
        if state.continue_on_error:
            return {
                "ok": True,
                "acceptance": None,
                "changed_files": [],
                "error": "Missing file list",
                "duration": time.time() - run_start
            }
        return {
            "ok": False,
            "acceptance": None,
            "changed_files": [],
            "error": "Missing file list",
            "duration": time.time() - run_start
        }

    plan_event = _compact_plan_for_event(plan_payload)
    if plan_event:
        emit_event(
            state.events_full,
            kind="action",
            actor="Director",
            name="patch_plan",
            refs=build_event_refs("patch_plan", files),
            summary="Patch plan ready",
            input={"plan": plan_event},
        )
    if files or commands or tool_commands:
        emit_event(
            state.events_full,
            kind="action",
            actor="Director",
            name="patch_act",
            refs=build_event_refs("apply", files),
            summary="Patch act ready",
            input={
                "files": files,
                "commands": commands,
                "tool_commands": tool_commands,
                "brief_preview": _truncate_text(str(brief), 300),
                "act": act_payload,
            },
        )

    if not validate_files_to_edit(files, state.workspace_full, log_path):
        duration = time.time() - run_start
        write_director_result(
            state,
            build_result(
                "blocked",
                "Failed to read files before edit",
                acceptance=None,
                task_id=pm_task_id,
                task_fingerprint=pm_task_fingerprint,
                task_title=pm_task_title,
                task_goal=pm_task_goal,
                pm_iteration=pm_iteration,
                error_code="ENV_ISSUE",
                duration=duration,
            ),
        )
        return {
            "ok": False,
            "acceptance": None,
            "changed_files": [],
            "error": "Failed to read files before edit",
            "duration": time.time() - run_start
        }

    tool_results: List[Dict[str, Any]] = []
    tool_output_summary = ""
    review_output = ""
    review_payload: Dict[str, Any] = {}
    review_summary = ""
    patch_risk: Dict[str, Any] = {}
    patch_risk_summary = ""
    base_snapshot: Dict[str, Optional[str]] = {}
    brief_for_run = brief

    result = run_ollama_apply(state, brief_for_run, files)
    ollama_output = result["output"]
    changed_files = result["changed_files"]
    base_snapshot = result.get("snapshot") or {}
    run_id = f"pm-{pm_iteration:05d}" if isinstance(pm_iteration, int) else f"dir-{index:05d}"
    if changed_files:
        preview = ", ".join(changed_files[:5])
        suffix = "..." if len(changed_files) > 5 else ""
        emit_dialogue(
            state.dialogue_full,
            speaker="Director",
            type="progress",
            text=f"Modified {len(changed_files)} files: {preview}{suffix}",
            summary=f"Modified {len(changed_files)} files",
            run_id=run_id,
            pm_iteration=pm_iteration,
            director_iteration=index,
            refs={"task_id": pm_task_id},
            meta={"changed_files_count": len(changed_files)},
        )

    patch_risk = assess_patch_risk(changed_files, base_snapshot)
    risk_score = safe_int(patch_risk.get("score"), 0)
    if state.risk_block_threshold and risk_score >= state.risk_block_threshold:
        patch_risk["threshold"] = state.risk_block_threshold
        patch_risk["gate"] = "block"
        patch_risk_summary = format_risk_summary(patch_risk)
        append_log(log_path, f"[RISK] Blocking run: {patch_risk_summary}\n")
        emit_dialogue(
            state.dialogue_full,
            speaker="System",
            type="warning",
            text=f"Risk gate blocked execution: {patch_risk_summary}",
            summary="Risk gate blocked execution",
            run_id=run_id,
            pm_iteration=pm_iteration,
            director_iteration=index,
            refs={"task_id": pm_task_id, "phase": "risk"},
            meta={"risk_score": risk_score, "risk_threshold": state.risk_block_threshold},
        )
        if state.rollback_on_block and base_snapshot:
            restore_snapshot(
                base_snapshot,
                state.workspace_full,
                log_path,
                events_path=state.events_full,
                refs=build_event_refs("rollback", list(base_snapshot.keys())),
            )
        write_director_result(
            state,
            build_result(
                "blocked",
                "Risk gate blocked execution",
                acceptance=None,
                changed_files=changed_files,
                task_id=pm_task_id,
                task_fingerprint=pm_task_fingerprint,
                task_title=pm_task_title,
                task_goal=pm_task_goal,
                pm_iteration=pm_iteration,
                error_code="RISK_BLOCKED",
                duration=time.time() - run_start,
            ),
        )
        return {
            "ok": False,
            "acceptance": None,
            "changed_files": changed_files,
            "error": "Risk gate blocked execution",
            "duration": time.time() - run_start,
        }
    patch_risk["threshold"] = state.risk_block_threshold
    patch_risk["gate"] = "pass" if state.risk_block_threshold else "n/a"
    patch_risk_summary = format_risk_summary(patch_risk)

    if state.reviewer_enabled:
        planner_output_for_review, ollama_output_for_review = _truncate_for_review(
            state, planner_output, ollama_output
        )
        review_output = run_reviewer(
            state,
            plan_text,
            memory_summary,
            target_note,
            changed_files,
            planner_output_for_review,
            ollama_output_for_review,
            tool_output_summary,
            patch_risk_summary,
        )
        review_payload = parse_json_payload(review_output) or {}
        review_summary = format_review_summary(review_payload)
        if review_summary and state.reviewer_rounds > 0:
            for review_index in range(1, state.reviewer_rounds + 1):
                if not review_summary:
                    break
                append_log(log_path, f"[REVIEWER] Applying reviewer fixes {review_index}/{state.reviewer_rounds}.\n")
                if base_snapshot:
                    restore_snapshot(
                        base_snapshot,
                        state.workspace_full,
                        log_path,
                        events_path=state.events_full,
                        refs=build_event_refs("rollback", list(base_snapshot.keys())),
                    )
                review_brief = brief + "\n\nReviewer issues to address:\n" + review_summary + "\n"
                result = run_ollama_apply(state, review_brief, files)
                brief_for_run = review_brief
                ollama_output = result["output"]
                changed_files = result["changed_files"]
                patch_risk = assess_patch_risk(changed_files, base_snapshot)
                patch_risk_summary = format_risk_summary(patch_risk)
                if review_index < state.reviewer_rounds:
                    planner_output_for_review, ollama_output_for_review = _truncate_for_review(
                        state, planner_output, ollama_output
                    )
                    review_output = run_reviewer(
                        state,
                        plan_text,
                        memory_summary,
                        target_note,
                        changed_files,
                        planner_output_for_review,
                        ollama_output_for_review,
                        tool_output_summary,
                        patch_risk_summary,
                    )
                    review_payload = parse_json_payload(review_output) or {}
                    review_summary = format_review_summary(review_payload)

    if state.run_npm_commands and commands:
        run_npm_commands(state, commands, log_path)

    if not tool_commands and state.default_tools_enabled:
        tool_commands = DEFAULT_TOOL_COMMANDS.copy()
    if tool_commands:
        tool_results = run_tool_commands(state, tool_commands, log_path)
    tool_output_summary = format_tool_results(tool_results) if tool_results else ""

    if state.qa_enabled:
        planner_output_for_qa, ollama_output_for_qa = _truncate_for_review(state, planner_output, ollama_output)
        qa_output = run_qa(
            state,
            plan_text,
            memory_summary,
            target_note,
            changed_files,
            planner_output_for_qa,
            ollama_output_for_qa,
            tool_output_summary,
            review_summary,
            patch_risk_summary,
        )
    else:
        qa_output = '{"acceptance":"PASS","summary":"QA disabled"}'
        write_text_atomic(state.qa_full, qa_output + "\n")
        append_log(state.log_full, "[QA]\n" + qa_output + "\n")
    acceptance = parse_acceptance(qa_output)

    # Handle acceptance decision
    repair_attempts = 0
    if acceptance is False and state.auto_repair:
        for round_index in range(1, state.repair_rounds + 1):
            repair_attempts += 1
            append_log(log_path, f"[OLLAMA] Acceptance failed; retrying {round_index}/{state.repair_rounds}.\n")
            if state.rollback_on_fail and base_snapshot:
                restore_snapshot(
                    base_snapshot,
                    state.workspace_full,
                    log_path,
                    events_path=state.events_full,
                    refs=build_event_refs("rollback", list(base_snapshot.keys())),
                )
            repair_brief = brief_for_run + "\n\nQA feedback to address:\n" + qa_output.strip() + "\n"
            result = run_ollama_apply(state, repair_brief, files)
            ollama_output = result["output"]
            changed_files = result["changed_files"]
            patch_risk = assess_patch_risk(changed_files, base_snapshot, state.workspace_full, policy_effective)
            patch_risk_summary = format_risk_summary(patch_risk)
            if tool_commands:
                tool_results = run_tool_commands(state, tool_commands, log_path)
            tool_output_summary = format_tool_results(tool_results) if tool_results else ""
            if state.qa_enabled:
                planner_output_for_qa, ollama_output_for_qa = _truncate_for_review(
                    state, planner_output, ollama_output
                )
                qa_output = run_qa(
                    state,
                    plan_text,
                    memory_summary,
                    target_note,
                    changed_files,
                    planner_output_for_qa,
                    ollama_output_for_qa,
                    tool_output_summary,
                    review_summary,
                    patch_risk_summary,
                )
                acceptance = parse_acceptance(qa_output)
            else:
                qa_output = '{"acceptance":"PASS","summary":"QA disabled"}'
                write_text_atomic(state.qa_full, qa_output + "\n")
                append_log(state.log_full, "[QA]\n" + qa_output + "\n")
                acceptance = True
            if acceptance is True:
                break
    if acceptance is False and state.rollback_on_fail and base_snapshot:
        restore_snapshot(
            base_snapshot,
            state.workspace_full,
            log_path,
            events_path=state.events_full,
            refs=build_event_refs("rollback", list(base_snapshot.keys())),
        )

    run_id = f"pm-{pm_iteration:05d}" if isinstance(pm_iteration, int) else f"dir-{index:05d}"
    qa_payload = parse_json_payload(qa_output)
    qa_summary = ""
    if isinstance(qa_payload, dict):
        qa_summary = str(qa_payload.get("summary") or "").strip()
    qa_status = "PASS" if acceptance is True else "FAIL" if acceptance is False else "UNKNOWN"
    if state.qa_enabled:
        emit_dialogue(
            state.dialogue_full,
            speaker="QA",
            type="result",
            text=f"QA result: {qa_status}. {qa_summary[:160]}",
            summary=f"QA: {qa_status}",
            run_id=run_id,
            pm_iteration=pm_iteration,
            director_iteration=index,
            refs={"task_id": pm_task_id, "phase": "done"},
            meta={"qa_pass": True if acceptance is True else False if acceptance is False else None},
        )

    qa_payload = parse_json_payload(qa_output)
    memory_status = update_memory_snapshot(
        state,
        qa_output=qa_output,
        qa_payload=qa_payload if isinstance(qa_payload, dict) else None,
        iteration_index=index,
        target_index=target_index,
        target_note=target_note,
        log_path=log_path,
        gap_review_ran=gap_review_ran,
        acceptance=acceptance,
    )
    memory_backend_effective = ""
    memory_warnings: List[str] = []
    if isinstance(memory_status, dict):
        memory_backend_effective = str(memory_status.get("backend_effective") or "")
        warnings = memory_status.get("warnings")
        if isinstance(warnings, list):
            memory_warnings = [str(item) for item in warnings if item]

    duration = time.time() - run_start
    append_log(log_path, f"### Run Summary\n- Duration: {duration:.1f}s\n")

    qa_next = ""
    if isinstance(qa_payload, dict):
        qa_next = str(qa_payload.get("next") or qa_payload.get("next_step") or "").strip()

    status = "success" if acceptance is True else "fail" if acceptance is False else "unknown"
    error_code = ""
    failure_code = ""
    if acceptance is False:
        error_code = "QA_FAIL"
        failure_code = "QA_FAIL"
    result_payload = build_result(
        status,
        "completed",
        acceptance=acceptance,
        changed_files=changed_files,
        task_id=pm_task_id,
        task_fingerprint=pm_task_fingerprint,
        task_title=pm_task_title,
        task_goal=pm_task_goal,
        pm_iteration=pm_iteration,
        error_code=error_code,
        failure_code=failure_code,
        duration=duration,
        repair_attempts=repair_attempts,
    )
    event_seq_end = get_event_seq()
    trajectory_path = write_trajectory(
        state,
        run_id=state.current_run_id,
        task_id=pm_task_id,
        task_fingerprint=pm_task_fingerprint,
        pm_iteration=pm_iteration,
        director_iteration=index,
        result_payload=result_payload,
        policy_effective=policy_effective,
        evidence_path=evidence_path,
        event_seq_start=event_seq_start,
        event_seq_end=event_seq_end,
    )
    tool_summary = summarize_tool_outputs(tool_outputs)
    result_payload.update(
        {
            "completion_summary": qa_summary or tool_output_summary or "",
            "commands_run": commands,
            "tool_commands_run": tool_commands,
            "planner_brief": brief,
            "patch_plan": plan_payload,
            "patch_act": {
                "files": files,
                "commands": commands,
                "tool_commands": tool_commands,
                "act": act_payload,
            },
            "reviewer_summary": review_summary,
            "reviewer_response_path": state.reviewer_full,
            "patch_risk": patch_risk,
            "qa_summary": qa_summary,
            "qa_next": qa_next,
            "acceptance_criteria": pm_task_acceptance,
            "tool_rounds": tool_rounds,
            "total_lines_read": total_lines_read,
            "rg_queries": tool_summary.get("rg_queries"),
            "evidence_refs": tool_summary.get("evidence_refs"),
            "evidence_path": evidence_path,
            "tool_results_summary": tool_output_summary,
            "events_path": state.events_full,
            "policy": {
                "auto_repair": state.auto_repair,
                "max_repair_attempts": state.repair_rounds,
                "reviewer_enabled": state.reviewer_enabled,
                "reviewer_rounds": state.reviewer_rounds,
                "risk_block_threshold": state.risk_block_threshold,
                "evidence_verbosity": state.evidence_verbosity,
                "rag_topk": state.rag_topk,
                "default_tools": state.default_tools_enabled,
                "rollback_on_fail": state.rollback_on_fail,
            },
            "policy_effective": policy_effective,
            "policy_sources": policy_sources,
            "policy_path": state.policy_path,
            "memory_backend_effective": memory_backend_effective,
            "memory_warnings": memory_warnings,
            "trajectory_path": trajectory_path,
        }
    )
    write_director_result(state, result_payload)

    # Return detailed results
    return {
        "ok": True,
        "acceptance": acceptance,
        "changed_files": changed_files,
        "error": None,
        "duration": duration
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="HarborPilot Director loop (Ollama)")
    parser.add_argument("--plan-path", "-PlanPath", default=".harborpilot/runtime/PLAN.md")
    default_auto_plan = str(os.environ.get("HARBORPILOT_AUTO_PLAN", "1")).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    parser.add_argument(
        "--auto-plan",
        dest="auto_plan",
        action="store_true",
        default=default_auto_plan,
        help="Auto-generate PLAN.md when missing and continue without manual edit.",
    )
    parser.add_argument(
        "--no-auto-plan",
        dest="auto_plan",
        action="store_false",
        help="Require manual PLAN.md; exit after generating template.",
    )
    parser.add_argument("--log-path", "-LogPath", default=".harborpilot/runtime/RUNLOG.md")
    parser.add_argument("--planner-response-path", "-PlannerResponsePath", default=".harborpilot/runtime/PLANNER_RESPONSE.md")
    parser.add_argument("--ollama-response-path", "-OllamaResponsePath", default=".harborpilot/runtime/OLLAMA_RESPONSE.md")
    parser.add_argument("--qa-response-path", "-QaResponsePath", default=".harborpilot/runtime/QA_RESPONSE.md")
    parser.add_argument("--reviewer-response-path", "-ReviewerResponsePath", default=".harborpilot/runtime/REVIEW_RESPONSE.md")
    parser.add_argument("--director-result-path", "-DirectorResultPath", default=".harborpilot/runtime/DIRECTOR_RESULT.json")
    parser.add_argument("--policy-path", default=".harborpilot/runtime/director_policy.json")
    parser.add_argument("--workspace", "-Workspace", default=os.getcwd())
    parser.add_argument("--iterations", "-Iterations", type=int, default=1)
    parser.add_argument("--delay-seconds", "-DelaySeconds", type=int, default=0)
    parser.add_argument("--repair-rounds", "-RepairRounds", type=int, default=1)
    parser.add_argument("--max-repair-attempts", type=int, default=0, help="Alias for --repair-rounds (0 keeps existing).")
    parser.add_argument("--auto-repair", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--reviewer", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--reviewer-rounds", type=int, default=1)
    parser.add_argument("--rollback-on-fail", action=argparse.BooleanOptionalAction, default=True)
    default_qa_enabled = str(os.environ.get("HARBORPILOT_QA_ENABLED", "1")).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    def _read_int_env(name: str, default: int) -> int:
        raw = os.environ.get(name)
        if raw is None:
            return default
        try:
            return int(str(raw).strip())
        except Exception:
            return default
    parser.add_argument("--qa", dest="qa_enabled", action="store_true", default=default_qa_enabled)
    parser.add_argument("--no-qa", dest="qa_enabled", action="store_false")
    parser.add_argument("--risk-block-threshold", type=int, default=0, help="Block run when patch risk score >= threshold (0 disables).")
    parser.add_argument("--evidence-verbosity", choices=["summary", "full"], default="summary")
    parser.add_argument("--rag-topk", type=int, default=5, help="Default top-k for local RAG tools.")
    parser.add_argument("--continue-on-error", "-ContinueOnError", action="store_true")
    parser.add_argument("--forever", "-Forever", action="store_true")
    parser.add_argument("--show-output", "-ShowOutput", action="store_true")
    parser.add_argument("--model", "-Model", default="modelscope.cn/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:latest")
    parser.add_argument("--timeout", "-Timeout", type=int, default=0)
    parser.add_argument("--auto-pick-target", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--memory-backend", "-MemoryBackend", default="lancedb")
    parser.add_argument("--memory-dir", "-MemoryDir", default=".harborpilot/runtime/memory")
    parser.add_argument("--memory-max-chars", "-MemoryMaxChars", type=int, default=2000)
    parser.add_argument("--run-npm", dest="run_npm", action=argparse.BooleanOptionalAction, default=False)
    default_npm_timeout = _read_int_env("HARBORPILOT_NPM_TIMEOUT", 600)
    if default_npm_timeout < 0:
        default_npm_timeout = 0
    parser.add_argument("--npm-timeout", "-NpmTimeout", type=int, default=default_npm_timeout)
    parser.add_argument("--gap-review", dest="gap_review", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--gap-report-path", "-GapReportPath", default=".harborpilot/runtime/GAP_REPORT.md")
    parser.add_argument("--gap-max-headings", "-GapMaxHeadings", type=int, default=200)
    parser.add_argument("--gap-max-files", "-GapMaxFiles", type=int, default=200)
    parser.add_argument("--gap-write-plan", dest="gap_write_plan", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--pm-task-path", "-PmTaskPath", default=".harborpilot/runtime/PM_TASKS.json")
    parser.add_argument("--dialogue-path", "-DialoguePath", default=".harborpilot/runtime/DIALOGUE.jsonl")
    parser.add_argument("--events-path", "-EventsPath", default=".harborpilot/runtime/events.jsonl")
    parser.add_argument("--prompt-profile", default="demo_ming_armada", help="Prompt profile (e.g. demo_ming_armada, generic).")
    parser.add_argument("--default-tools", dest="default_tools", action=argparse.BooleanOptionalAction, default=True, help="Run default QA tool chain (ruff/mypy/pytest) when PatchPlanner provides no tool_commands.")
    parser.add_argument("--ramdisk-root", default="", help="Optional RAM-disk root (Windows default: X:). High-frequency artifacts will be written here.")

    args = parser.parse_args()
    if args.max_repair_attempts and args.max_repair_attempts > 0:
        args.repair_rounds = args.max_repair_attempts
    if args.rag_topk and args.rag_topk > 0:
        os.environ["HARBORPILOT_RAG_TOPK"] = str(args.rag_topk)

    try:
        if args.prompt_profile:
            os.environ[PROMPT_PROFILE_ENV] = str(args.prompt_profile).strip()
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode = "forever" if args.forever else f"iterations={args.iterations}"
        print(f"[director] {stamp} start {mode}")
        sys.stdout.flush()
        workspace_full = resolve_workspace_path(args.workspace, require_docs=False)
        if not workspace_has_docs(workspace_full):
            write_workspace_status(
                workspace_full,
                status="NEEDS_DOCS_INIT",
                reason="docs/ directory not found",
                actions=["INIT_DOCS_WIZARD"],
            )
            print(f"[workspace] docs/ not found at {workspace_full}. Run docs init and retry.")
            return 2
        clear_workspace_status(workspace_full)
        ensure_ollama_available()
        os.chdir(workspace_full)

        ramdisk_root = resolve_ramdisk_root(getattr(args, "ramdisk_root", None))
        cache_root_full = build_cache_root(ramdisk_root, workspace_full) or ""

        policy_path_full = args.policy_path
        if policy_path_full and not os.path.isabs(policy_path_full):
            policy_path_full = os.path.join(workspace_full, policy_path_full)
        cli_overrides = build_cli_overrides(sys.argv[1:])
        base_policy, base_sources = build_base_policy(policy_path_full, cli_overrides)
        io_policy = base_policy.get("io", {}) if isinstance(base_policy.get("io"), dict) else {}
        configure_jsonl_buffer(
            buffered=io_policy.get("jsonl_buffered"),
            flush_interval_sec=io_policy.get("flush_interval_sec"),
            flush_batch=io_policy.get("flush_batch"),
            max_buffer=io_policy.get("max_buffer"),
        )
        rag_policy = base_policy.get("rag", {}) if isinstance(base_policy.get("rag"), dict) else {}
        if isinstance(rag_policy.get("topk"), int):
            os.environ["HARBORPILOT_RAG_TOPK"] = str(rag_policy.get("topk"))

        if state_to_ramdisk_enabled() and not cache_root_full:
            raise RuntimeError(
                "HARBORPILOT_STATE_TO_RAMDISK is enabled but no ramdisk cache root is available. "
                "Set HARBORPILOT_RAMDISK_ROOT (e.g. X:\\) or disable HARBORPILOT_STATE_TO_RAMDISK."
            )
        plan_full = resolve_artifact_path(workspace_full, cache_root_full, args.plan_path)
        log_full = resolve_artifact_path(workspace_full, cache_root_full, args.log_path)
        planner_full = resolve_artifact_path(workspace_full, cache_root_full, args.planner_response_path)
        ollama_full = resolve_artifact_path(workspace_full, cache_root_full, args.ollama_response_path)
        qa_full = resolve_artifact_path(workspace_full, cache_root_full, args.qa_response_path)
        reviewer_full = resolve_artifact_path(workspace_full, cache_root_full, args.reviewer_response_path)

        ensure_parent_dir(plan_full)
        ensure_parent_dir(log_full)
        ensure_parent_dir(planner_full)
        ensure_parent_dir(ollama_full)
        ensure_parent_dir(qa_full)
        ensure_parent_dir(reviewer_full)

        if not ensure_plan_file(plan_full, auto_continue=bool(args.auto_plan)):
            return 1

        repair_policy = base_policy.get("repair", {}) if isinstance(base_policy.get("repair"), dict) else {}
        risk_policy = base_policy.get("risk", {}) if isinstance(base_policy.get("risk"), dict) else {}
        evidence_policy = base_policy.get("evidence", {}) if isinstance(base_policy.get("evidence"), dict) else {}
        rag_policy = base_policy.get("rag", {}) if isinstance(base_policy.get("rag"), dict) else {}
        memory_policy = base_policy.get("memory", {}) if isinstance(base_policy.get("memory"), dict) else {}
        budgets_policy = base_policy.get("budgets", {}) if isinstance(base_policy.get("budgets"), dict) else {}
        qa_policy = base_policy.get("qa", {}) if isinstance(base_policy.get("qa"), dict) else {}
        context_policy = base_policy.get("context", {}) if isinstance(base_policy.get("context"), dict) else {}

        memory_backend = str(memory_policy.get("backend", args.memory_backend or "lancedb")).lower()
        memory_enabled = bool(memory_policy.get("enabled", True))
        if memory_backend in ("none", "off", "disabled", "false", "0"):
            memory_enabled = False
        memory_dir_full = resolve_artifact_path(workspace_full, cache_root_full, args.memory_dir)
        memory_snapshot_path = os.path.join(memory_dir_full, "last_state.json")
        memory_snapshot = None
        if memory_enabled:
            ensure_memory_dir(memory_dir_full)
            memory_snapshot = read_memory_snapshot(memory_snapshot_path)
        memory_store_enabled = bool(memory_policy.get("store_enabled", True))
        memory_store_every = int(memory_policy.get("store_every", 1) or 1)
        memory_store_on_accept = bool(memory_policy.get("store_on_accept", False))

        state = State(
            workspace_full=workspace_full,
            cache_root_full=cache_root_full or workspace_full,
            plan_full=plan_full,
            log_full=log_full,
            planner_full=planner_full,
            ollama_full=ollama_full,
            qa_full=qa_full,
            reviewer_full=reviewer_full,
            delay_seconds=args.delay_seconds,
            repair_rounds=int(repair_policy.get("max_attempts", args.repair_rounds)),
            auto_repair=bool(repair_policy.get("auto_repair", args.auto_repair)),
            continue_on_error=args.continue_on_error,
            show_output=args.show_output,
            model=args.model,
            timeout=args.timeout,
            auto_pick_target=args.auto_pick_target,
            memory_backend=memory_backend,
            memory_enabled=memory_enabled,
            memory_dir_full=memory_dir_full,
            memory_snapshot_path=memory_snapshot_path,
            memory_snapshot=memory_snapshot,
            memory_max_chars=args.memory_max_chars,
            memory_store_enabled=memory_store_enabled,
            memory_store_every=memory_store_every,
            memory_store_on_accept=memory_store_on_accept,
            run_npm_commands=args.run_npm,
            npm_timeout=args.npm_timeout,
            gap_review_enabled=args.gap_review,
            gap_report_full=resolve_artifact_path(workspace_full, cache_root_full, args.gap_report_path),
            gap_max_headings=args.gap_max_headings,
            gap_max_files=args.gap_max_files,
            gap_review_done=False,
            gap_write_plan=args.gap_write_plan,
        pm_task_path=resolve_artifact_path(workspace_full, cache_root_full, args.pm_task_path),
            director_result_full=resolve_artifact_path(workspace_full, cache_root_full, args.director_result_path),
            dialogue_full=resolve_artifact_path(workspace_full, cache_root_full, args.dialogue_path),
            events_full=resolve_artifact_path(workspace_full, cache_root_full, args.events_path),
            default_tools_enabled=bool(qa_policy.get("default_tools", args.default_tools)),
            reviewer_enabled=bool(repair_policy.get("reviewer_enabled", args.reviewer)),
            reviewer_rounds=int(repair_policy.get("reviewer_rounds", args.reviewer_rounds)),
            rollback_on_fail=bool(repair_policy.get("rollback_on_fail", args.rollback_on_fail)),
            qa_enabled=bool(qa_policy.get("enabled", args.qa_enabled)),
            risk_block_threshold=int(risk_policy.get("block_threshold", args.risk_block_threshold)),
            evidence_verbosity=str(evidence_policy.get("verbosity", args.evidence_verbosity)),
            evidence_write_enabled=bool(evidence_policy.get("write_enabled", True)),
            rag_topk=int(rag_policy.get("topk", args.rag_topk)),
            rollback_on_block=bool(risk_policy.get("rollback_on_block", args.rollback_on_fail)),
            budget_max_rounds=int(budgets_policy.get("max_tool_rounds", 6)),
            budget_max_lines=int(budgets_policy.get("max_total_lines_read", 1200)),
            context_pm_tasks_max_chars=int(context_policy.get("pm_tasks_max_chars", 8000)),
            context_known_files_max_chars=int(context_policy.get("known_files_max_chars", 2000)),
            context_last_result_max_chars=int(context_policy.get("last_result_max_chars", 2000)),
            context_tool_output_max_chars=int(context_policy.get("tool_output_max_chars", 9000)),
            context_planner_output_max_chars=int(context_policy.get("planner_output_max_chars", 6000)),
            context_ollama_output_max_chars=int(context_policy.get("ollama_output_max_chars", 6000)),
            policy_base=base_policy,
            policy_sources=base_sources,
            policy_cli_overrides=cli_overrides,
            policy_path=policy_path_full,
        )

        if args.forever:
            index = 1
            while True:
                # Sync sequences before each iteration in case other processes wrote to them
                if state.dialogue_full:
                    set_dialogue_seq(scan_last_seq(state.dialogue_full))
                if state.events_full:
                    set_event_seq(scan_last_seq(state.events_full))
                
                result = invoke_iteration(state, index, False)
                if not result["ok"]:
                    return 1
                index += 1
        else:
            for index in range(1, args.iterations + 1):
                # Sync sequences
                if state.dialogue_full:
                    set_dialogue_seq(scan_last_seq(state.dialogue_full))
                if state.events_full:
                    set_event_seq(scan_last_seq(state.events_full))
                    
                is_last = index >= args.iterations
                result = invoke_iteration(state, index, is_last)
                if not result["ok"]:
                    return 1

        return 0
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        try:
            flush_jsonl_buffers(force=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
