import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


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


def build_utf8_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    if extra:
        env.update(extra)
    return env


SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PROMPT_PROFILE_ENV = "HARBORPILOT_PROMPT_PROFILE"
DEFAULT_DIRECTOR_SUBPROCESS_LOG = "state/ollama/DIRECTOR_SUBPROCESS.log"
DEFAULT_DIRECTOR_STATUS = "state/ollama/DIRECTOR_STATUS.json"
REQUIRED_MODULE_FILES = (
    "decision.py",
    "codex_utils.py",
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

try:
    from io_utils import (
        append_jsonl,
        build_cache_root,
        ensure_parent_dir,
        ensure_codex_available,
        ensure_ollama_available,
        emit_dialogue,
        flush_jsonl_buffers,
        read_file_safe,
        resolve_artifact_path,
        resolve_ramdisk_root,
        resolve_workspace_path,
        stop_flag_path,
        stop_requested,
        write_json_atomic,
        write_text_atomic,
    )
    from prompt_loader import current_profile, get_template, render_template
    from codex_utils import invoke_codex
    from ollama_utils import invoke_ollama
    from shared import strip_ansi
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def format_json_for_prompt(payload: Any, max_chars: int = 2000) -> str:
    if payload is None:
        return "none"
    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        text = str(payload)
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars] + "..."
    return text


def build_pm_prompt(
    requirements: str,
    plan_text: str,
    gap_report: str,
    last_qa: str,
    last_tasks: Any,
    director_result: Any,
    pm_state: Any,
) -> str:
    profile = current_profile().strip().lower()
    if profile in ("generic", "portable", "default"):
        intro = "You are the project manager for a software project repo."
    else:
        intro = "You are the project manager for a naval MMO repo."
    template = get_template("pm_prompt")
    return render_template(
        template,
        {
            "pm_intro": intro,
            "requirements": requirements,
            "plan_text": plan_text,
            "gap_report": gap_report,
            "last_qa": last_qa,
            "last_tasks": format_json_for_prompt(last_tasks),
            "director_result": format_json_for_prompt(director_result),
            "pm_state": format_json_for_prompt(pm_state),
        },
    )


def resolve_director_path(director_path: str, workspace_full: str) -> str:
    if os.path.isabs(director_path):
        return director_path
    candidate = os.path.join(PROJECT_ROOT, director_path)
    if os.path.isfile(candidate):
        return candidate
    return os.path.join(workspace_full, director_path)


def append_director_log(log_path: str, text: str) -> None:
    if not log_path:
        return
    ensure_parent_dir(log_path)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(text)


def write_director_status(path: str, payload: Dict[str, Any]) -> None:
    if not path:
        return
    try:
        ensure_parent_dir(path)
        write_json_atomic(path, payload)
    except Exception:
        pass


def run_director_once(args: argparse.Namespace, workspace_full: str, iteration: int, log_path: str = "") -> int:
    director_path = args.director_path or "loops/loop-director.py"
    director_path = resolve_director_path(director_path, workspace_full)
    if not os.path.isfile(director_path):
        return 1

    cmd = [sys.executable, director_path, "--iterations", "1"]
    if args.director_result_path:
        cmd.extend(["--director-result-path", args.director_result_path])
    if args.director_show_output:
        cmd.append("--show-output")
    if args.director_model:
        cmd.extend(["--model", args.director_model])
    if args.director_timeout and args.director_timeout > 0:
        cmd.extend(["--timeout", str(args.director_timeout)])
    if getattr(args, "prompt_profile", None):
        cmd.extend(["--prompt-profile", args.prompt_profile])

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if log_path:
        append_director_log(log_path, f"\n## {stamp} (iteration {iteration}) - start\n")
        append_director_log(log_path, "[cmd] " + " ".join(cmd) + "\n")

    try:
        result = subprocess.run(
            cmd,
            cwd=workspace_full,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=build_utf8_env(),
        )
        output = result.stdout or ""
        if log_path:
            if output:
                append_director_log(log_path, output if output.endswith("\n") else output + "\n")
            append_director_log(log_path, f"[exit] {result.returncode}\n")
        return result.returncode
    except Exception as exc:
        if log_path:
            append_director_log(log_path, f"[error] {exc}\n")
        return 1


def read_json_file(path: str) -> Any:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def normalize_str_list(value: Any) -> List[str]:
    items: List[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                items.append(item.strip())
    elif isinstance(value, str) and value.strip():
        items.append(value.strip())
    return items


def normalize_tasks(raw_tasks: Any, iteration: int) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    if not isinstance(raw_tasks, list):
        return tasks
    index = 1
    for item in raw_tasks:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        goal = str(item.get("goal") or "").strip()
        if not title and not goal:
            continue
        task_id = str(item.get("id") or "")
        priority = item.get("priority")
        try:
            priority = int(priority)
        except Exception:
            priority = index
        context_files = normalize_str_list(item.get("context_files") or item.get("files"))
        target_files = normalize_str_list(item.get("target_files") or item.get("files"))
        constraints = normalize_str_list(item.get("constraints"))
        acceptance = normalize_str_list(item.get("acceptance"))
        required_evidence = item.get("required_evidence")
        stop_conditions = normalize_str_list(item.get("stop_conditions"))
        fingerprint_source = "|".join(
            [
                title.lower(),
                goal.lower(),
                ",".join(sorted(target_files)).lower(),
                ",".join(sorted(acceptance)).lower(),
            ]
        ).strip()
        fingerprint = hashlib.sha1(fingerprint_source.encode("utf-8")).hexdigest() if fingerprint_source else ""
        if not task_id:
            task_id = f"PM-{fingerprint[:8] or f'{iteration:04d}-{index}'}"
        tasks.append(
            {
                "id": task_id,
                "fingerprint": fingerprint,
                "priority": priority,
                "title": title,
                "goal": goal,
                "context_files": context_files,
                "target_files": target_files,
                "constraints": constraints,
                "acceptance": acceptance,
                "required_evidence": required_evidence if isinstance(required_evidence, dict) else None,
                "stop_conditions": stop_conditions,
            }
        )
        index += 1
        if len(tasks) >= 3:
            break
    return tasks


def normalize_pm_payload(raw_payload: Dict[str, Any], iteration: int, timestamp: str) -> Dict[str, Any]:
    overall_goal = str(raw_payload.get("overall_goal") or raw_payload.get("focus") or "Advance global requirements").strip()
    focus = str(raw_payload.get("focus") or "").strip()
    notes = str(raw_payload.get("notes") or "").strip()
    tasks = normalize_tasks(raw_payload.get("tasks"), iteration)
    return {
        "pm_iteration": iteration,
        "timestamp": timestamp,
        "overall_goal": overall_goal,
        "focus": focus,
        "tasks": tasks,
        "notes": notes,
    }


def build_run_dir(workspace: str, iteration: int) -> str:
    return os.path.join(workspace, "state", "ollama", "runs", f"pm-{iteration:05d}")


def archive_if_exists(src: str, dest: str) -> None:
    if not src or not os.path.exists(src):
        return
    ensure_parent_dir(dest)
    try:
        with open(src, "r", encoding="utf-8") as handle:
            content = handle.read()
        write_text_atomic(dest, content)
    except Exception:
        pass


def wait_for_director_result(path: str, expected_task_id: str, since_ts: float, timeout_s: int) -> Dict[str, Any]:
    deadline = time.time() + max(timeout_s, 1)
    while time.time() < deadline:
        data = read_json_file(path)
        if isinstance(data, dict):
            task_id = str(data.get("task_id") or "")
            ts = data.get("timestamp") or ""
            try:
                ts_epoch = datetime.fromisoformat(ts).timestamp() if ts else 0
            except Exception:
                ts_epoch = 0
            if task_id and expected_task_id and task_id == expected_task_id and ts_epoch >= since_ts:
                return data
        time.sleep(1)
    return {"status": "blocked", "error_code": "DIRECTOR_NO_RESULT"}


def match_director_result(result: Any, expected_task_id: str, since_ts: float) -> Optional[Dict[str, Any]]:
    if not isinstance(result, dict):
        return None
    task_id = str(result.get("task_id") or "")
    if not task_id or not expected_task_id or task_id != expected_task_id:
        return None
    ts = result.get("timestamp") or ""
    try:
        ts_epoch = datetime.fromisoformat(ts).timestamp() if ts else 0
    except Exception:
        ts_epoch = 0
    if ts_epoch < since_ts:
        return None
    return result


def run_once(args: argparse.Namespace, iteration: int = 1) -> int:
    backend = str(getattr(args, "pm_backend", "ollama") or "ollama").strip().lower()
    if backend == "codex":
        ensure_codex_available()
    else:
        ensure_ollama_available()
    workspace_full = resolve_workspace_path(args.workspace)
    ramdisk_root = resolve_ramdisk_root(getattr(args, "ramdisk_root", None))
    cache_root_full = build_cache_root(ramdisk_root, workspace_full) or ""
    plan_full = os.path.join(workspace_full, args.plan_path)
    gap_full = os.path.join(workspace_full, args.gap_report_path)
    qa_full = os.path.join(workspace_full, args.qa_path)
    req_full = os.path.join(workspace_full, args.requirements_path)
    pm_out_full = os.path.join(workspace_full, args.pm_out)
    pm_report_full = os.path.join(workspace_full, args.pm_report)
    pm_state_full = os.path.join(workspace_full, args.state_path)
    pm_history_full = os.path.join(workspace_full, args.task_history_path)
    director_result_full = os.path.join(workspace_full, args.director_result_path)
    stop_flag_full = stop_flag_path(workspace_full)
    dialogue_full = resolve_artifact_path(workspace_full, cache_root_full, args.dialogue_path) if args.dialogue_path else ""
    pm_last_full = os.path.join(workspace_full, args.pm_last_message_path)
    pm_history_full = resolve_artifact_path(workspace_full, cache_root_full, args.task_history_path)
    director_log_full = ""
    director_status_full = resolve_artifact_path(workspace_full, cache_root_full, DEFAULT_DIRECTOR_STATUS)
    if getattr(args, "director_log_path", None):
        director_log_full = resolve_artifact_path(workspace_full, cache_root_full, args.director_log_path)

    requirements = read_file_safe(req_full) or ""
    plan_text = read_file_safe(plan_full) or ""
    gap_report = read_file_safe(gap_full) or ""
    last_qa = read_file_safe(qa_full) or ""
    last_tasks = read_json_file(pm_out_full)
    director_result = read_json_file(director_result_full)
    pm_state = read_json_file(pm_state_full) or {}

    last_signature = str(pm_state.get("last_task_fingerprint") or pm_state.get("last_task_signature") or "").strip()
    consecutive_failures = int(pm_state.get("consecutive_failures") or 0)
    consecutive_blocked = int(pm_state.get("consecutive_blocked") or 0)
    last_director_status = ""
    last_director_task_id = ""
    last_director_task_title = ""
    last_director_task_fingerprint = ""
    if isinstance(director_result, dict):
        last_director_status = str(director_result.get("status") or "").strip().lower()
        last_director_task_id = str(director_result.get("task_id") or "").strip()
        last_director_task_title = str(director_result.get("task_title") or "").strip()
        last_director_task_fingerprint = str(director_result.get("task_fingerprint") or "").strip()
        signature = last_director_task_fingerprint or last_director_task_id or last_director_task_title
        if last_director_status == "fail":
            if signature and signature == last_signature:
                consecutive_failures += 1
            else:
                consecutive_failures = 1
            consecutive_blocked = 0
        elif last_director_status == "blocked":
            if signature and signature == last_signature:
                consecutive_blocked += 1
            else:
                consecutive_blocked = 1
            # blocked does not count as failure
            consecutive_failures = 0
        elif last_director_status == "success":
            consecutive_failures = 0
            consecutive_blocked = 0

    pm_state.update(
        {
            "last_director_status": last_director_status,
            "last_director_task_id": last_director_task_id,
            "last_director_task_title": last_director_task_title,
            "last_director_task_fingerprint": last_director_task_fingerprint,
            "consecutive_failures": consecutive_failures,
            "consecutive_blocked": consecutive_blocked,
        }
    )

    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pm_state["last_updated_ts"] = start_timestamp
    if stop_requested(workspace_full):
        ensure_parent_dir(pm_report_full)
        with open(pm_report_full, "a", encoding="utf-8") as handle:
            handle.write(
                f"\n## {start_timestamp} (iteration {iteration}) - halted\n"
                f"Status: stop requested ({stop_flag_full}).\n"
            )
        pm_state["pm_iteration"] = iteration
        pm_state["last_updated_ts"] = start_timestamp
        write_json_atomic(pm_state_full, pm_state)
        return 3
    if args.max_failures and consecutive_failures >= args.max_failures:
        ensure_parent_dir(pm_report_full)
        with open(pm_report_full, "a", encoding="utf-8") as handle:
            handle.write(
                f"\n## {start_timestamp} (iteration {iteration}) - halted\n"
                f"Status: halted after {consecutive_failures} consecutive failures.\n"
            )
        pm_state["pm_iteration"] = iteration
        pm_state["last_updated_ts"] = start_timestamp
        write_json_atomic(pm_state_full, pm_state)
        return 2
    if args.max_blocked and consecutive_blocked >= args.max_blocked:
        ensure_parent_dir(pm_report_full)
        with open(pm_report_full, "a", encoding="utf-8") as handle:
            handle.write(
                f"\n## {start_timestamp} (iteration {iteration}) - halted\n"
                f"Status: halted after {consecutive_blocked} consecutive blocked results.\n"
            )
        pm_state["pm_iteration"] = iteration
        pm_state["last_updated_ts"] = start_timestamp
        write_json_atomic(pm_state_full, pm_state)
        return 2
    if args.loop or (args.max_iterations and args.max_iterations > 1):
        ensure_parent_dir(pm_report_full)
        with open(pm_report_full, "a", encoding="utf-8") as handle:
            handle.write(f"\n\n## {start_timestamp} (iteration {iteration}) - start\n")
            handle.write("Status: running\n")
    if args.json_log:
        json_log_full = resolve_artifact_path(workspace_full, cache_root_full, args.json_log)
        ensure_parent_dir(json_log_full)
        start_record = {
            "timestamp": start_timestamp,
            "iteration": iteration,
            "status": "started",
        }
        with open(json_log_full, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(start_record, ensure_ascii=False) + "\n")

    prompt = build_pm_prompt(requirements, plan_text, gap_report, last_qa, last_tasks, director_result, pm_state)
    show_output = bool(getattr(args, "pm_show_output", False))
    if backend == "codex":
        output = invoke_codex(
            prompt,
            pm_last_full,
            workspace_full,
            show_output,
            args.codex_full_auto,
            args.codex_dangerous,
            args.codex_profile,
            args.timeout,
            None,
        )
    else:
        output = invoke_ollama(prompt, args.model, workspace_full, show_output, args.timeout)
    exit_code = 0

    try:
        payload = json.loads(strip_ansi(output))
    except Exception:
        payload = {"focus": "parse_failed", "tasks": [], "notes": "PM JSON parse failed."}
    normalized = normalize_pm_payload(payload, iteration, start_timestamp)
    write_json_atomic(pm_out_full, normalized)

    run_id = f"pm-{iteration:05d}"
    primary_task = None
    tasks_for_dialogue = normalized.get("tasks") if isinstance(normalized, dict) else []
    if isinstance(tasks_for_dialogue, list) and tasks_for_dialogue:
        primary_task = tasks_for_dialogue[0] if isinstance(tasks_for_dialogue[0], dict) else None
    if primary_task:
        task_id = str(primary_task.get("id") or "")
        acc = primary_task.get("acceptance") or []
        acc_summary = ", ".join(acc[:3]) if isinstance(acc, list) else ""
        emit_dialogue(
            dialogue_full,
            speaker="PM",
            type="handoff",
            text=f"I am assigning tasks. Priority: {task_id}. Acceptance: {acc_summary}",
            summary=f"Dispatch: {task_id}",
            run_id=run_id,
            pm_iteration=iteration,
            refs={"task_id": task_id, "phase": "handoff", "files": ["PM_TASKS.json"]},
        )

    ensure_parent_dir(pm_report_full)
    clean_output = strip_ansi(output).strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if args.loop or (args.max_iterations and args.max_iterations > 1):
        with open(pm_report_full, "a", encoding="utf-8") as handle:
            handle.write(f"\n\n## {timestamp} (iteration {iteration}) - output\n{clean_output}\n")
            handle.write(f"\nHeartbeat: iteration={iteration} exit=0\n")
    else:
        with open(pm_report_full, "w", encoding="utf-8") as handle:
            handle.write(clean_output + "\n")

    if args.run_director:
        director_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        director_start_epoch = time.time()
        write_director_status(
            director_status_full,
            {
                "running": True,
                "started_at": director_start_epoch,
                "updated_at": time.time(),
                "mode": "pm",
                "pm_iteration": iteration,
                "log_path": director_log_full or DEFAULT_DIRECTOR_SUBPROCESS_LOG,
            },
        )
        if primary_task:
            task_id = str(primary_task.get("id") or "")
            emit_dialogue(
                dialogue_full,
                speaker="PM",
                type="say",
                text=f"Starting execution for task {task_id}.",
                summary=f"Start: {task_id}",
                run_id=run_id,
                pm_iteration=iteration,
                refs={"task_id": task_id},
            )
        if args.loop or (args.max_iterations and args.max_iterations > 1):
            with open(pm_report_full, "a", encoding="utf-8") as handle:
                handle.write(f"\n## {director_timestamp} (iteration {iteration}) - director start\n")
        run_dir = build_run_dir(workspace_full, iteration)
        archive_if_exists(pm_out_full, os.path.join(run_dir, "PM_TASKS.json"))
        archive_if_exists(pm_report_full, os.path.join(run_dir, "PM_REPORT.md"))
        director_exit: Optional[int] = None
        try:
            director_exit = run_director_once(args, workspace_full, iteration, director_log_full)
        finally:
            write_director_status(
                director_status_full,
                {
                    "running": False,
                    "started_at": director_start_epoch,
                    "ended_at": time.time(),
                    "updated_at": time.time(),
                    "mode": "pm",
                    "pm_iteration": iteration,
                    "exit_code": director_exit,
                    "log_path": director_log_full or DEFAULT_DIRECTOR_SUBPROCESS_LOG,
                },
            )
        expected_task_id = ""
        tasks_for_director = normalized.get("tasks") if isinstance(normalized, dict) else []
        if isinstance(tasks_for_director, list) and tasks_for_director:
            primary = tasks_for_director[0] if isinstance(tasks_for_director[0], dict) else {}
            expected_task_id = str(primary.get("id") or "")
        matched_result: Optional[Dict[str, Any]] = None
        if expected_task_id:
            director_check = wait_for_director_result(
                director_result_full,
                expected_task_id,
                director_start_epoch,
                args.director_result_timeout,
            )
            matched_result = match_director_result(director_check, expected_task_id, director_start_epoch)
        latest_result = read_json_file(director_result_full)
        latest_match = match_director_result(latest_result, expected_task_id, director_start_epoch)
        if latest_match is not None:
            matched_result = latest_match
        if expected_task_id and matched_result is None:
            pm_state["last_director_status"] = "blocked"
            pm_state["last_director_error_code"] = "DIRECTOR_NO_RESULT"
            write_json_atomic(pm_state_full, pm_state)
            emit_dialogue(
                dialogue_full,
                speaker="PM",
                type="warning",
                text="Director result missing. Marked as blocked.",
                summary="Director result missing",
                run_id=run_id,
                pm_iteration=iteration,
                refs={"task_id": expected_task_id or None, "files": ["DIRECTOR_RESULT.json"]},
                meta={"error_code": "DIRECTOR_NO_RESULT"},
            )
        if isinstance(latest_result, dict):
            status = str(latest_result.get("status") or "").upper()
            error_code = latest_result.get("error_code")
            changed_files = latest_result.get("changed_files") or []
            emit_dialogue(
                dialogue_full,
                speaker="PM",
                type="result",
                text=f"Result: {status}. {error_code or 'OK'}",
                summary=f"Result: {status}",
                run_id=run_id,
                pm_iteration=iteration,
                refs={"task_id": latest_result.get("task_id"), "phase": "done", "files": ["DIRECTOR_RESULT.json"]},
                meta={
                    "error_code": error_code,
                    "changed_files_count": len(changed_files) if isinstance(changed_files, list) else 0,
                },
            )
            if matched_result is not None:
                pm_state["last_director_status"] = str(latest_result.get("status") or "").strip().lower()
                pm_state["last_director_task_id"] = str(latest_result.get("task_id") or "").strip()
                pm_state["last_director_task_title"] = str(latest_result.get("task_title") or "").strip()
                pm_state["last_director_task_fingerprint"] = str(latest_result.get("task_fingerprint") or "").strip()
                pm_state.pop("last_director_error_code", None)
                write_json_atomic(pm_state_full, pm_state)
        archive_if_exists(director_result_full, os.path.join(run_dir, "DIRECTOR_RESULT.json"))
        archive_if_exists(os.path.join(workspace_full, "scripts", "state", "ollama", "PLANNER_RESPONSE.md"), os.path.join(run_dir, "PLANNER_RESPONSE.md"))
        archive_if_exists(os.path.join(workspace_full, "scripts", "state", "ollama", "OLLAMA_RESPONSE.md"), os.path.join(run_dir, "OLLAMA_RESPONSE.md"))
        archive_if_exists(os.path.join(workspace_full, "scripts", "state", "ollama", "QA_RESPONSE.md"), os.path.join(run_dir, "QA_RESPONSE.md"))
        archive_if_exists(os.path.join(workspace_full, "scripts", "state", "ollama", "RUNLOG.md"), os.path.join(run_dir, "RUNLOG.md"))
        if args.loop or (args.max_iterations and args.max_iterations > 1):
            with open(pm_report_full, "a", encoding="utf-8") as handle:
                handle.write(f"Director exit: {director_exit}\n")

    if args.json_log:
        json_log_full = resolve_artifact_path(workspace_full, cache_root_full, args.json_log)
        log_record = {
            "timestamp": timestamp,
            "iteration": iteration,
            "exit_code": exit_code,
            "status": "completed",
            "focus": normalized.get("focus"),
            "task_count": len(normalized.get("tasks", [])) if isinstance(normalized.get("tasks"), list) else 0,
            "notes": normalized.get("notes"),
        }
        append_jsonl(json_log_full, log_record)

    tasks = normalized.get("tasks") if isinstance(normalized, dict) else []
    new_signature = ""
    if isinstance(tasks, list) and tasks:
        primary = tasks[0] if isinstance(tasks[0], dict) else {}
        new_signature = str(primary.get("fingerprint") or primary.get("id") or "").strip()
    same_task_count = int(pm_state.get("same_task_count") or 0)
    if new_signature and new_signature == last_signature:
        same_task_count += 1
    else:
        same_task_count = 1 if new_signature else 0
    pm_state.update(
        {
            "pm_iteration": iteration,
            "last_task_signature": new_signature,
            "last_task_fingerprint": new_signature,
            "same_task_count": same_task_count,
            "last_updated_ts": timestamp,
        }
    )
    if args.max_same_task:
        pm_state["force_switch"] = same_task_count >= args.max_same_task
        pm_state["max_same_task"] = args.max_same_task
    write_json_atomic(pm_state_full, pm_state)
    if pm_history_full:
        history_record = {
            "timestamp": timestamp,
            "pm_iteration": iteration,
            "focus": normalized.get("focus"),
            "tasks": tasks,
        }
        append_jsonl(pm_history_full, history_record)

    if args.max_same_task and same_task_count >= args.max_same_task:
        ensure_parent_dir(pm_report_full)
        with open(pm_report_full, "a", encoding="utf-8") as handle:
            handle.write(
                f"\n## {timestamp} (iteration {iteration}) - warning\n"
                f"Status: same task repeated {same_task_count} times. PM should rotate focus.\n"
            )

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="PM wrapper for Ollama loop")
    parser.add_argument("--workspace", "-Workspace", default=os.getcwd())
    parser.add_argument("--model", "-Model", default="modelscope.cn/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:latest")
    parser.add_argument("--pm-backend", default="codex", choices=["codex", "ollama"])
    parser.add_argument("--timeout", "-Timeout", type=int, default=0)
    parser.add_argument("--plan-path", "-PlanPath", default="state/ollama/PLAN.md")
    parser.add_argument("--gap-report-path", "-GapReportPath", default="state/ollama/GAP_REPORT.md")
    parser.add_argument("--qa-path", "-QaPath", default="state/ollama/QA_RESPONSE.md")
    parser.add_argument("--requirements-path", "-RequirementsPath", default="docs/product/requirements.md")
    parser.add_argument("--pm-out", "-PmOut", default="state/ollama/PM_TASKS.json")
    parser.add_argument("--pm-report", "-PmReport", default="state/ollama/PM_REPORT.md")
    parser.add_argument("--state-path", "-StatePath", default="state/ollama/PM_STATE.json")
    parser.add_argument("--task-history-path", "-TaskHistoryPath", default="state/ollama/PM_TASK_HISTORY.jsonl")
    parser.add_argument("--director-result-path", "-DirectorResultPath", default="state/ollama/DIRECTOR_RESULT.json")
    parser.add_argument("--loop", action="store_true", help="Run continuously until interrupted.")
    parser.add_argument("--interval", type=int, default=20, help="Seconds to wait between iterations.")
    parser.add_argument("--max-iterations", type=int, default=0, help="Stop after N iterations (0 = infinite).")
    parser.add_argument("--max-failures", type=int, default=5, help="Stop after N consecutive director failures (0 disables).")
    parser.add_argument("--max-blocked", type=int, default=5, help="Stop after N consecutive blocked results (0 disables).")
    parser.add_argument("--max-same-task", type=int, default=3, help="Warn after repeating the same task N times (0 disables).")
    parser.add_argument("--stop-on-failure", action=argparse.BooleanOptionalAction, default=True, help="Stop loop if run_once returns non-zero.")
    parser.add_argument("--heartbeat", action="store_true", help="Print a status line each iteration.")
    parser.add_argument("--json-log", default="", help="Append JSONL status records to this path.")
    parser.add_argument("--pm-show-output", action=argparse.BooleanOptionalAction, default=False, help="Stream PM backend output to stdout.")
    parser.add_argument("--run-director", action=argparse.BooleanOptionalAction, default=False, help="Run director once after PM output.")
    parser.add_argument("--director-path", default="loops/loop-director.py")
    parser.add_argument("--director-log-path", default=DEFAULT_DIRECTOR_SUBPROCESS_LOG)
    parser.add_argument("--director-model", default="")
    parser.add_argument("--director-timeout", type=int, default=0)
    parser.add_argument("--director-show-output", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--director-result-timeout", type=int, default=60, help="Seconds to wait for director result.")
    parser.add_argument("--dialogue-path", default="state/ollama/DIALOGUE.jsonl")
    parser.add_argument("--prompt-profile", default="demo_ming_armada", help="Prompt profile (e.g. demo_ming_armada, generic).")
    parser.add_argument("--pm-last-message-path", default="state/ollama/PM_LAST_RESPONSE.md")
    parser.add_argument("--ramdisk-root", default="", help="Optional RAM-disk root (Windows default: X:). High-frequency artifacts will be written here.")
    parser.add_argument("--codex-profile", default="")
    parser.add_argument("--codex-full-auto", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--codex-dangerous", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args()

    try:
        if args.prompt_profile:
            os.environ[PROMPT_PROFILE_ENV] = str(args.prompt_profile).strip()
        iterations = 0
        if args.loop:
            state_full = os.path.join(resolve_workspace_path(args.workspace), args.state_path)
            state_data = read_json_file(state_full)
            if isinstance(state_data, dict):
                last_iter = state_data.get("pm_iteration")
                try:
                    iterations = int(last_iter) if last_iter is not None else 0
                except Exception:
                    iterations = 0
        if not args.loop and args.max_iterations <= 1:
            return run_once(args, 1)

        while True:
            iterations += 1
            exit_code = run_once(args, iterations)
            if args.heartbeat:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[loop-pm] {timestamp} iteration={iterations} exit={exit_code}")
            if exit_code != 0 and args.stop_on_failure:
                return exit_code
            if args.max_iterations and iterations >= args.max_iterations:
                return exit_code
            time.sleep(max(args.interval, 1))
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        return 1
    finally:
        try:
            flush_jsonl_buffers(force=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
