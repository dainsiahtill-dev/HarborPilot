import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


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
DEFAULT_DIRECTOR_SUBPROCESS_LOG = ".harborpilot/runtime/DIRECTOR_SUBPROCESS.log"
DEFAULT_DIRECTOR_STATUS = ".harborpilot/runtime/DIRECTOR_STATUS.json"
AGENTS_DRAFT_REL = ".harborpilot/runtime/AGENTS.generated.md"
AGENTS_FEEDBACK_REL = ".harborpilot/runtime/AGENTS.feedback.md"
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
        ensure_plan_file,
        ensure_codex_available,
        ensure_ollama_available,
        emit_dialogue,
        emit_event,
        flush_jsonl_buffers,
        read_file_safe,
        resolve_artifact_path,
        resolve_ramdisk_root,
        resolve_run_dir,
        resolve_workspace_path,
        state_to_ramdisk_enabled,
        workspace_has_docs,
        write_workspace_status,
        clear_workspace_status,
        stop_flag_path,
        stop_requested,
        director_stop_requested,
        clear_director_stop_flag,
        update_latest_pointer,
        write_json_atomic,
        write_text_atomic,
        scan_last_seq,
        set_dialogue_seq,
    )
    from prompt_loader import current_profile, get_template, render_template
    from codex_utils import invoke_codex
    from ollama_utils import invoke_ollama
    from shared import normalize_path, strip_ansi
    from anthropomorphic.integration import get_anthropomorphic_context, get_anthropomorphic_context_v2
    from invariant_sentinel import run_invariant_sentinel
    from usage import UsageContext
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


def _use_context_engine_v2() -> bool:
    value = str(os.environ.get("HARBORPILOT_CONTEXT_ENGINE", "")).strip().lower()
    return value in ("v2", "context_v2", "engine_v2", "context-engine-v2")


def build_pm_prompt(
    requirements: str,
    plan_text: str,
    gap_report: str,
    last_qa: str,
    last_tasks: Any,
    director_result: Any,
    pm_state: Any,
    iteration: int = 0,
    run_id: str = "",
    events_path: str = "",
) -> str:
    profile = current_profile().strip().lower()
    is_zh = profile.endswith("_zh") or profile.startswith("zh") or profile in ("zh", "chinese")
    if "armada" in profile:
        intro = "你是这个海战 MMO 仓库的项目经理。" if is_zh else "You are the project manager for a naval MMO repo."
    else:
        intro = "你是这个软件项目仓库的项目经理。" if is_zh else "You are the project manager for a software project repo."
    
    query = f"{requirements}\n{plan_text}"
    if _use_context_engine_v2():
        anthro = get_anthropomorphic_context_v2(
            PROJECT_ROOT,
            "pm",
            query,
            iteration,
            run_id,
            "pm.planning",
            events_path=events_path or "",
        )
    else:
        anthro = get_anthropomorphic_context(PROJECT_ROOT, "pm", query, iteration, run_id, "pm.planning")

    if events_path:
        output = anthro["prompt_context_obj"].model_dump()
        context_pack = anthro.get("context_pack")
        if context_pack is not None:
            output["context_hash"] = getattr(context_pack, "request_hash", "")
            output["context_snapshot"] = getattr(context_pack, "snapshot_path", "")
        emit_event(
            events_path,
            kind="observation",
            actor="PM",
            name="prompt_context",
            refs={"run_id": run_id, "step": iteration},
            summary="Prompt Context Injection",
            output=output
        )

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
            "persona_instruction": anthro["persona_instruction"],
            "anthropomorphic_context": anthro["anthropomorphic_context"],
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


def run_director_once(
    args: argparse.Namespace,
    workspace_full: str,
    iteration: int,
    subprocess_log_path: str = "",
    director_log_path: str = "",
    status_path: str = "",
    status_payload: Optional[Dict[str, Any]] = None,
    pid_holder: Optional[Dict[str, int]] = None,
) -> int:
    director_path = args.director_path or "loops/loop-director.py"
    director_path = resolve_director_path(director_path, workspace_full)
    if not os.path.isfile(director_path):
        return 1

    cmd = [sys.executable, director_path, "--iterations", "1"]
    if args.director_result_path:
        cmd.extend(["--director-result-path", args.director_result_path])
    if director_log_path:
        cmd.extend(["--log-path", director_log_path])
    if args.director_events_path:
        cmd.extend(["--events-path", args.director_events_path])
    if args.pm_task_path:
        cmd.extend(["--pm-task-path", args.pm_task_path])
    
    # Pass response paths if they are in the run directory
    if args.planner_response_path:
        cmd.extend(["--planner-response-path", args.planner_response_path])
    if args.ollama_response_path:
        cmd.extend(["--ollama-response-path", args.ollama_response_path])
    if args.qa_response_path:
        cmd.extend(["--qa-response-path", args.qa_response_path])
    if args.reviewer_response_path:
        cmd.extend(["--reviewer-response-path", args.reviewer_response_path])

    if args.director_show_output:
        cmd.append("--show-output")
    if args.director_model:
        cmd.extend(["--model", args.director_model])
    if args.director_timeout and args.director_timeout > 0:
        cmd.extend(["--timeout", str(args.director_timeout)])
    if getattr(args, "prompt_profile", None):
        cmd.extend(["--prompt-profile", args.prompt_profile])

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if subprocess_log_path:
        append_director_log(subprocess_log_path, f"\n## {stamp} (iteration {iteration}) - start\n")
        append_director_log(subprocess_log_path, "[cmd] " + " ".join(cmd) + "\n")

    def _terminate_process(proc: subprocess.Popen) -> None:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=3)
            except Exception:
                pass

    log_handle = None
    try:
        timeout_sec = 0
        if args.director_timeout and args.director_timeout > 0:
            timeout_sec = int(args.director_timeout) + 30
        else:
            try:
                timeout_sec = int(str(os.environ.get("HARBORPILOT_DIRECTOR_RUN_TIMEOUT", "3600")).strip())
            except Exception:
                timeout_sec = 3600
        timeout_val = timeout_sec if timeout_sec and timeout_sec > 0 else None
        extra_env: Dict[str, str] = {}
        if "HARBORPILOT_AUTO_PLAN" not in os.environ:
            extra_env["HARBORPILOT_AUTO_PLAN"] = "1"
        stdout_target = subprocess.DEVNULL
        if subprocess_log_path:
            ensure_parent_dir(subprocess_log_path)
            log_handle = open(subprocess_log_path, "a", encoding="utf-8", errors="ignore")
            stdout_target = log_handle
        process = subprocess.Popen(
            cmd,
            cwd=workspace_full,
            stdout=stdout_target,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=build_utf8_env(extra_env),
        )
        if pid_holder is not None:
            pid_holder["pid"] = process.pid
        if status_path and isinstance(status_payload, dict):
            payload = dict(status_payload)
            payload["pid"] = process.pid
            payload["running"] = True
            payload["updated_at"] = time.time()
            write_director_status(status_path, payload)
        start = time.time()
        stopped = False
        while True:
            if director_stop_requested(workspace_full):
                clear_director_stop_flag(workspace_full)
                stopped = True
                if subprocess_log_path:
                    append_director_log(subprocess_log_path, "[stop] Director stop requested; terminating\n")
                _terminate_process(process)
                break
            if timeout_val is not None and timeout_val > 0 and time.time() - start > timeout_val:
                if subprocess_log_path:
                    append_director_log(subprocess_log_path, "[error] director subprocess timeout\n")
                _terminate_process(process)
                return 124
            exit_code = process.poll()
            if exit_code is not None:
                if subprocess_log_path:
                    append_director_log(subprocess_log_path, f"[exit] {exit_code}\n")
                return exit_code
            time.sleep(0.5)
        exit_code = process.poll()
        if exit_code is None:
            exit_code = 1
        if subprocess_log_path and not stopped:
            append_director_log(subprocess_log_path, f"[exit] {exit_code}\n")
        return 130 if stopped else exit_code
    except Exception as exc:
        if subprocess_log_path:
            append_director_log(subprocess_log_path, f"[error] {exc}\n")
        return 1
    finally:
        if log_handle is not None:
            try:
                log_handle.close()
            except Exception:
                pass


def read_json_file(path: str) -> Any:
    if not path or not os.path.exists(path):
        if not path:
            return None
        legacy_dot = path.replace(
            f"{os.sep}.harborpilot{os.sep}runtime{os.sep}",
            f"{os.sep}.harborpilot{os.sep}ollama{os.sep}",
        )
        legacy_state = path.replace(
            f"{os.sep}.harborpilot{os.sep}runtime{os.sep}",
            f"{os.sep}state{os.sep}ollama{os.sep}",
        )
        if legacy_dot != path and os.path.exists(legacy_dot):
            path = legacy_dot
        elif legacy_state != path and os.path.exists(legacy_state):
            path = legacy_state
        else:
            return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def truncate_text_block(text: str, max_chars: int = 4000) -> str:
    if not text:
        return ""
    text = text.strip("\n")
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars].rstrip() + "\n...[truncated]"
    return text


def maybe_generate_agents_draft(
    workspace_full: str,
    cache_root_full: str,
    timestamp: str,
    args: argparse.Namespace,
) -> Optional[str]:
    def _is_failed_draft(text: str) -> bool:
        if not text:
            return True
        lowered = text.lower()
        if "generation failed" in lowered:
            return True
        if "failed to write last message file" in lowered:
            return True
        return False

    def _build_fallback(docs_text: str, root_text: str, feedback_text: str, error_hint: str = "") -> str:
        sections: List[str] = []
        if error_hint:
            sections.append(f"## Generation Status\n- error: {error_hint}\n")
        if docs_text:
            sections.append("## docs/agent/README.md (excerpt)\n" + truncate_text_block(docs_text))
        if root_text:
            sections.append("## README.md (excerpt)\n" + truncate_text_block(root_text))
        if feedback_text:
            sections.append("## User Feedback (apply before adopting)\n" + truncate_text_block(feedback_text))

        body = "\n\n".join([s for s in sections if s.strip()]).strip()
        content = (
            "# AGENTS (Draft)\n"
            f"> Generated by HarborPilot PM at {timestamp}\n"
            "> 请人工审阅并决定是否复制到 workspace/AGENTS.md\n\n"
            "<INSTRUCTIONS>\n"
            "- Use docs/agent/README.md as the documentation index.\n"
            "- Check docs/product/requirements.md for global requirements (if present).\n"
            "- Keep state artifacts in .harborpilot/runtime/ (ramdisk may be enabled).\n"
            "- Always use UTF-8 when reading/writing text files.\n"
            "</INSTRUCTIONS>\n\n"
            + (body + "\n" if body else "")
        )
        return content

    workspace_agents = os.path.join(workspace_full, "AGENTS.md")
    if os.path.exists(workspace_agents):
        return None
    draft_full = resolve_artifact_path(workspace_full, cache_root_full, AGENTS_DRAFT_REL)
    feedback_full = resolve_artifact_path(workspace_full, cache_root_full, AGENTS_FEEDBACK_REL)
    feedback_text = read_file_safe(feedback_full).strip() if feedback_full else ""
    if os.path.exists(draft_full):
        existing = read_file_safe(draft_full) or ""
        if _is_failed_draft(existing):
            try:
                os.remove(draft_full)
            except Exception:
                pass
        else:
            if feedback_text and os.path.exists(feedback_full):
                try:
                    if os.path.getmtime(feedback_full) <= os.path.getmtime(draft_full):
                        return draft_full
                except Exception:
                    return draft_full
            else:
                return draft_full

    docs_readme = os.path.join(workspace_full, "docs", "README.md")
    root_readme = os.path.join(workspace_full, "README.md")
    docs_text = read_file_safe(docs_readme) or ""
    root_text = read_file_safe(root_readme) or ""
    if not docs_text and not root_text and not feedback_text:
        print("[pm] generating AGENTS.md draft using fallback (no README/feedback found)")
        sys.stdout.flush()
        content = _build_fallback(docs_text, root_text, feedback_text, "no README/feedback available")
        write_text_atomic(draft_full, content)
        return draft_full

    docs_context = ""
    if docs_text:
        docs_context += f"## docs/agent/README.md\n{truncate_text_block(docs_text)}\n\n"
    if root_text:
        docs_context += f"## README.md\n{truncate_text_block(root_text)}\n\n"

    try:
        template = get_template("agents_prompt")
        prompt = render_template(
            template,
            {
                "docs_context": docs_context,
                "feedback": feedback_text or "(none)",
            },
        )
        
        backend = str(getattr(args, "pm_backend", "ollama") or "ollama").strip().lower()
        print(f"[pm] generating AGENTS.md draft using {backend}...")
        sys.stdout.flush()
        
        if backend == "codex":
            codex_output = resolve_artifact_path(
                workspace_full,
                cache_root_full,
                ".harborpilot/runtime/AGENTS.codex.last_message.md",
            )
            output = invoke_codex(
                prompt,
                codex_output,
                workspace_full,
                bool(getattr(args, "pm_show_output", False)),
                args.codex_full_auto,
                args.codex_dangerous,
                args.codex_profile,
                args.timeout,
                None,
            )
        else:
            output = invoke_ollama(prompt, args.model, workspace_full, bool(getattr(args, "pm_show_output", False)), args.timeout)
            
        content = strip_ansi(output).strip()
        if not content:
            content = _build_fallback(docs_text, root_text, feedback_text, "empty model output")
             
        write_text_atomic(draft_full, content)
        return draft_full
    except Exception as e:
        print(f"[pm] error generating AGENTS.md: {e}")
        content = _build_fallback(docs_text, root_text, feedback_text, str(e))
        write_text_atomic(draft_full, content)
        return draft_full


def wait_for_agents_confirmation(
    workspace_full: str,
    cache_root_full: str,
    pm_state_full: str,
    pm_state: Dict[str, Any],
    pm_report_full: str,
    dialogue_full: str,
    run_id: str,
    pm_iteration: int,
    timestamp: str,
    args: argparse.Namespace,
    poll_sec: float = 2.0,
) -> bool:
    agents_path = os.path.join(workspace_full, "AGENTS.md")
    if os.path.isfile(agents_path):
        pm_state["awaiting_agents"] = False
        pm_state.pop("awaiting_agents_since", None)
        write_json_atomic(pm_state_full, pm_state)
        return True

    draft_path = maybe_generate_agents_draft(workspace_full, cache_root_full, timestamp, args)
    feedback_path = resolve_artifact_path(workspace_full, cache_root_full, AGENTS_FEEDBACK_REL)
    last_feedback_mtime = 0.0
    if feedback_path and os.path.isfile(feedback_path):
        try:
            last_feedback_mtime = os.path.getmtime(feedback_path)
        except Exception:
            last_feedback_mtime = 0.0
    pm_state["awaiting_agents"] = True
    pm_state["awaiting_agents_since"] = timestamp
    write_json_atomic(pm_state_full, pm_state)

    if dialogue_full:
        emit_dialogue(
            dialogue_full,
            speaker="PM",
            type="warning",
            text="AGENTS.md missing. Please review AGENTS.generated.md and adopt it before PM continues.",
            summary="AGENTS.md missing",
            run_id=run_id,
            pm_iteration=pm_iteration,
            refs={"files": ["AGENTS.generated.md", "AGENTS.md"], "phase": "agents"},
            meta={"error_code": "AGENTS_MISSING"},
        )

    ensure_parent_dir(pm_report_full)
    with open(pm_report_full, "a", encoding="utf-8") as handle:
        handle.write(
            f"\n## {timestamp} (iteration {pm_iteration}) - paused\n"
            "Status: waiting for AGENTS.md approval.\n"
            f"Draft: {draft_path or AGENTS_DRAFT_REL}\n"
        )

    while not os.path.isfile(agents_path):
        if stop_requested(workspace_full):
            return False
        if feedback_path and os.path.isfile(feedback_path):
            try:
                current_mtime = os.path.getmtime(feedback_path)
            except Exception:
                current_mtime = last_feedback_mtime
            if current_mtime > last_feedback_mtime + 0.0001:
                last_feedback_mtime = current_mtime
                updated = maybe_generate_agents_draft(workspace_full, cache_root_full, timestamp, args)
                if updated and dialogue_full:
                    emit_dialogue(
                        dialogue_full,
                        speaker="PM",
                        type="note",
                        text="收到反馈，已重新生成 AGENTS 草稿，请再次确认。",
                        summary="AGENTS draft updated",
                        run_id=run_id,
                        pm_iteration=pm_iteration,
                        refs={"files": ["AGENTS.generated.md"]},
                    )
        time.sleep(max(poll_sec, 0.5))

    pm_state["awaiting_agents"] = False
    pm_state.pop("awaiting_agents_since", None)
    write_json_atomic(pm_state_full, pm_state)
    return True


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
    run_id = f"pm-{iteration:05d}"
    return {
        "run_id": run_id,
        "pm_iteration": iteration,
        "timestamp": timestamp,
        "overall_goal": overall_goal,
        "focus": focus,
        "tasks": tasks,
        "notes": notes,
    }


def _is_docs_path(path: str) -> bool:
    if not path:
        return False
    normalized = normalize_path(str(path)).lstrip("/")
    lowered = normalized.lower()
    return lowered == "docs" or lowered.startswith("docs/")


def split_director_tasks(tasks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    director_tasks: List[Dict[str, Any]] = []
    docs_only_tasks: List[Dict[str, Any]] = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        target_files = task.get("target_files") or []
        normalized_targets = [
            normalize_path(str(item))
            for item in target_files
            if isinstance(item, str) and normalize_path(str(item))
        ]
        if normalized_targets and all(_is_docs_path(path) for path in normalized_targets):
            docs_only_tasks.append(task)
            continue
        if normalized_targets and any(_is_docs_path(path) for path in normalized_targets):
            filtered_targets = [path for path in normalized_targets if not _is_docs_path(path)]
            if not filtered_targets:
                docs_only_tasks.append(task)
                continue
            task_copy = dict(task)
            task_copy["target_files"] = filtered_targets
            constraints = task_copy.get("constraints") if isinstance(task_copy.get("constraints"), list) else []
            task_copy["constraints"] = [*constraints, "Do not modify docs/ (PM-only)."]
            director_tasks.append(task_copy)
            continue
        director_tasks.append(task)
    return director_tasks, docs_only_tasks


def build_run_dir(workspace: str, cache_root: str, iteration: int) -> str:
    rel = os.path.join(".harborpilot", "runtime", "runs", f"pm-{iteration:05d}")
    return resolve_artifact_path(workspace, cache_root, rel)


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
    ts_epoch = result_timestamp_epoch(result)
    if since_ts and ts_epoch < since_ts - 1.0:
        return None
    return result


def match_director_result_any(result: Any, expected_task_ids: List[str], since_ts: float) -> Optional[Dict[str, Any]]:
    if not isinstance(result, dict):
        return None
    task_id = str(result.get("task_id") or "").strip()
    if expected_task_ids and (not task_id or task_id not in expected_task_ids):
        return None
    ts_epoch = result_timestamp_epoch(result)
    if since_ts and ts_epoch < since_ts - 1.0:
        return None
    return result


def result_timestamp_epoch(result: Dict[str, Any]) -> float:
    raw_epoch = result.get("timestamp_epoch")
    if isinstance(raw_epoch, (int, float)):
        try:
            return float(raw_epoch)
        except Exception:
            return 0
    ts = str(result.get("timestamp_iso") or "").strip()
    if ts:
        try:
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            return datetime.fromisoformat(ts).timestamp()
        except Exception:
            pass
    ts = result.get("timestamp") or ""
    try:
        return datetime.fromisoformat(ts).timestamp() if ts else 0
    except Exception:
        return 0


def build_director_fallback_result(
    *,
    task_id: str,
    task_title: str,
    run_id: str,
    error_code: str,
    reason: str,
) -> Dict[str, Any]:
    now = datetime.now()
    return {
        "schema_version": 1,
        "timestamp": now.isoformat(),
        "timestamp_epoch": now.timestamp(),
        "status": "blocked",
        "acceptance": False,
        "error_code": error_code,
        "reason": reason,
        "task_id": task_id,
        "task_title": task_title,
        "run_id": run_id,
        "changed_files": [],
    }


def normalize_match_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in ("latest", "any", "strict", "run_id"):
        return mode
    return "latest"


def is_qa_enabled() -> bool:
    raw = str(os.environ.get("HARBORPILOT_QA_ENABLED", "1")).strip().lower()
    return raw not in ("0", "false", "no", "off")


def compact_text(text: str, max_len: int = 360) -> str:
    if not text:
        return ""
    text = " ".join(str(text).split())
    if max_len > 0 and len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def build_director_response(result: Dict[str, Any], task_title: str) -> str:
    status = str(result.get("status") or "").strip().upper()
    acceptance = result.get("acceptance")
    error_code = str(result.get("error_code") or "").strip()
    summary = str(result.get("completion_summary") or "").strip()
    if not summary:
        summary = str(result.get("qa_summary") or result.get("reason") or "").strip()
    if not summary:
        summary = "已完成本次执行。"
    summary = compact_text(summary, 280)
    changed_files = result.get("changed_files") or []
    changed_count = len(changed_files) if isinstance(changed_files, list) else 0
    qa_summary = compact_text(str(result.get("qa_summary") or "").strip(), 160)
    qa_next = compact_text(str(result.get("qa_next") or "").strip(), 160)
    reviewer = compact_text(str(result.get("reviewer_summary") or "").strip(), 160)
    acceptance_text = "PASS" if acceptance is True else "FAIL" if acceptance is False else "UNKNOWN"
    parts = []
    if task_title:
        parts.append(f"任务《{task_title}》执行结果：{acceptance_text}/{status or 'UNKNOWN'}。")
    else:
        parts.append(f"执行结果：{acceptance_text}/{status or 'UNKNOWN'}。")
    parts.append(f"摘要：{summary}")
    if changed_count:
        parts.append(f"改动文件数：{changed_count}")
    if error_code:
        parts.append(f"错误码：{error_code}")
    if reviewer:
        parts.append(f"Reviewer：{reviewer}")
    if qa_summary:
        parts.append(f"QA 摘要：{qa_summary}")
    if qa_next:
        parts.append(f"下一步建议：{qa_next}")
    return "\n".join(parts)


def build_pm_review(result: Dict[str, Any], attempt: int, attempts: int, qa_enabled: bool) -> str:
    acceptance = result.get("acceptance")
    status = str(result.get("status") or "").strip().lower()
    qa_summary = compact_text(str(result.get("qa_summary") or "").strip(), 160)
    if qa_enabled:
        if acceptance is True or status == "success":
            return f"收到，QA 已通过。{qa_summary or '这次任务完成得很好。'}"
        if acceptance is False or status == "fail":
            if attempt < attempts:
                return f"收到，QA 未通过。{qa_summary or '请继续修复未满足的验收项。'}"
            return f"收到，QA 未通过。{qa_summary or '先暂停该任务，后续我会调整要求。'}"
        return "收到，我会先交给 QA 进一步确认后再决定是否继续。"
    if acceptance is True or status == "success":
        return "收到，总体完成得很好。这次任务我确认通过。"
    if attempt < attempts:
        return "收到，当前仍未满足验收。请继续修复，下一轮优先解决未完成项。"
    return "收到，但仍未达成验收。先暂停这条任务，后续我会调整任务和要求。"


def emit_pm_director_conversation(
    dialogue_full: str,
    run_id: str,
    pm_iteration: int,
    result: Dict[str, Any],
    expected_task_id: str,
    expected_task_title: str,
    attempt: int,
    attempts: int,
    qa_enabled: bool,
) -> Tuple[str, str, str]:
    pm_question = "请确认：刚刚分配的任务你完成了哪些部分？还有哪些未完成？"
    director_report = build_director_response(result, expected_task_title)
    pm_review = build_pm_review(result, attempt, attempts, qa_enabled)
    emit_dialogue(
        dialogue_full,
        speaker="PM",
        type="ask",
        text=pm_question,
        summary="PM follow-up",
        run_id=run_id,
        pm_iteration=pm_iteration,
        refs={"task_id": expected_task_id or None, "phase": "followup"},
    )
    emit_dialogue(
        dialogue_full,
        speaker="Director",
        type="report",
        text=director_report,
        summary="Director report",
        run_id=run_id,
        pm_iteration=pm_iteration,
        refs={"task_id": expected_task_id or None, "phase": "report"},
    )
    if qa_enabled:
        emit_dialogue(
            dialogue_full,
            speaker="PM",
            type="note",
            text="如果开启了 QA，将以 QA 结果作为最终确认依据。",
            summary="QA note",
            run_id=run_id,
            pm_iteration=pm_iteration,
            refs={"task_id": expected_task_id or None, "phase": "qa-note"},
        )
    emit_dialogue(
        dialogue_full,
        speaker="PM",
        type="review",
        text=pm_review,
        summary="PM review",
        run_id=run_id,
        pm_iteration=pm_iteration,
        refs={"task_id": expected_task_id or None, "phase": "review"},
    )
    return pm_question, director_report, pm_review


def build_pm_memo(
    run_id: str,
    pm_iteration: int,
    attempt: int,
    attempts: int,
    expected_task_id: str,
    expected_task_title: str,
    result: Dict[str, Any],
    qa_enabled: bool,
    pm_question: str,
    director_report: str,
    pm_review: str,
) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = str(result.get("status") or "").strip().upper()
    acceptance = result.get("acceptance")
    error_code = str(result.get("error_code") or "").strip()
    completion_summary = compact_text(str(result.get("completion_summary") or "").strip(), 400)
    qa_summary = compact_text(str(result.get("qa_summary") or "").strip(), 200)
    qa_next = compact_text(str(result.get("qa_next") or "").strip(), 200)
    reviewer_summary = compact_text(str(result.get("reviewer_summary") or "").strip(), 200)
    changed_files = result.get("changed_files") or []
    changed_count = len(changed_files) if isinstance(changed_files, list) else 0
    changed_list = ""
    if isinstance(changed_files, list) and changed_files:
        changed_list = ", ".join([str(x) for x in changed_files[:20]])
        if len(changed_files) > 20:
            changed_list += f" ... (+{len(changed_files) - 20})"
    acceptance_text = "PASS" if acceptance is True else "FAIL" if acceptance is False else "UNKNOWN"

    lines = [
        "# PM 备忘录",
        f"- 时间: {ts}",
        f"- run_id: {run_id}",
        f"- PM 轮次: {pm_iteration}",
        f"- Director 尝试: {attempt}/{attempts}",
        f"- 任务 ID: {expected_task_id}",
        f"- 任务标题: {expected_task_title}",
        f"- 结果: {acceptance_text}/{status or 'UNKNOWN'}",
        f"- 变更文件数: {changed_count}",
        f"- QA 启用: {'是' if qa_enabled else '否'}",
    ]
    if error_code:
        lines.append(f"- 错误码: {error_code}")
    if completion_summary:
        lines.append(f"- 完成摘要: {completion_summary}")
    if qa_summary:
        lines.append(f"- QA 摘要: {qa_summary}")
    if qa_next:
        lines.append(f"- QA 建议: {qa_next}")
    if reviewer_summary:
        lines.append(f"- Reviewer 摘要: {reviewer_summary}")
    if changed_list:
        lines.append(f"- 变更文件: {changed_list}")

    lines.extend(
        [
            "",
            "## PM 追问",
            pm_question,
            "",
            "## Director 汇报",
            director_report,
            "",
            "## PM 决策",
            pm_review,
        ]
    )
    return "\n".join(lines) + "\n"


def write_pm_memo(
    workspace_full: str,
    cache_root_full: str,
    run_id: str,
    attempt: int,
    content: str,
) -> Tuple[str, str]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rel_path = os.path.join(".harborpilot", "runtime", "memos", f"PM_MEMO-{run_id}-a{attempt}-{stamp}.md")
    memo_path = resolve_artifact_path(workspace_full, cache_root_full, rel_path)
    write_text_atomic(memo_path, content)
    return memo_path, rel_path


def append_text(path: str, text: str) -> None:
    if not path:
        return
    ensure_parent_dir(path)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text or "")


def write_pm_memo_index(
    workspace_full: str,
    cache_root_full: str,
    record: Dict[str, Any],
) -> str:
    rel_path = os.path.join(".harborpilot", "runtime", "memos", "index.jsonl")
    index_path = resolve_artifact_path(workspace_full, cache_root_full, rel_path)
    append_jsonl(index_path, record)
    return index_path


def write_pm_memo_summary(
    workspace_full: str,
    cache_root_full: str,
    block: str,
) -> Tuple[str, str]:
    rel_path = os.path.join(".harborpilot", "runtime", "memos", "PM_MEMO_SUMMARY.md")
    summary_path = resolve_artifact_path(workspace_full, cache_root_full, rel_path)
    append_text(summary_path, block)
    export_path = os.path.join(workspace_full, "docs", "PM_MEMO_SUMMARY.md")
    append_text(export_path, block)
    return summary_path, export_path


def match_director_result_mode(
    result: Any,
    expected_task_ids: List[str],
    expected_run_id: str,
    since_ts: float,
    mode: str,
) -> Optional[Dict[str, Any]]:
    if not isinstance(result, dict):
        return None
    mode = normalize_match_mode(mode)
    ts_epoch = result_timestamp_epoch(result)
    if since_ts and ts_epoch < since_ts - 1.0:
        return None
    task_id = str(result.get("task_id") or "").strip()
    if mode == "latest":
        return result
    if mode == "run_id":
        run_id = str(result.get("run_id") or "").strip()
        if expected_run_id and run_id != expected_run_id:
            return None
        return result
    if mode == "any":
        if expected_task_ids and (not task_id or task_id not in expected_task_ids):
            return None
        return result
    expected_task_id = expected_task_ids[0] if expected_task_ids else ""
    if not expected_task_id or task_id != expected_task_id:
        return None
    return result


def wait_for_director_result_mode(
    path: str,
    expected_task_ids: List[str],
    expected_run_id: str,
    since_ts: float,
    timeout_s: int,
    mode: str,
) -> Dict[str, Any]:
    deadline = time.time() + max(timeout_s, 1)
    while time.time() < deadline:
        data = read_json_file(path)
        if match_director_result_mode(data, expected_task_ids, expected_run_id, since_ts, mode) is not None:
            return data if isinstance(data, dict) else {"status": "unknown"}
        time.sleep(1)
    return {"status": "blocked", "error_code": "DIRECTOR_NO_RESULT"}


def is_director_done(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    acceptance = result.get("acceptance")
    if acceptance is True:
        return True
    status = str(result.get("status") or "").strip().lower()
    return status == "success"


def read_tail_lines(path: str, max_lines: int = 200) -> List[str]:
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            pos = handle.tell()
            block = 4096
            data = b""
            while pos > 0 and data.count(b"\n") <= max_lines:
                read_size = block if pos >= block else pos
                pos -= read_size
                handle.seek(pos)
                data = handle.read(read_size) + data
    except Exception:
        return []
    text = data.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    if max_lines > 0 and len(lines) > max_lines:
        return lines[-max_lines:]
    return lines


def detect_plan_missing(plan_path: str, log_path: str, since_ts: float) -> str:
    plan_created = False
    if plan_path and os.path.exists(plan_path):
        try:
            plan_created = os.path.getmtime(plan_path) >= max(0.0, since_ts - 2)
        except Exception:
            plan_created = False
    if log_path:
        tail = read_tail_lines(log_path, max_lines=120)
        for line in tail:
            if "PLAN.md" in line and "Edit it and rerun" in line:
                return f"PLAN.md was created. Edit {plan_path} and rerun."
    if plan_created:
        return f"PLAN.md was created. Edit {plan_path} and rerun."
    return ""


def auto_plan_enabled() -> bool:
    value = os.environ.get("HARBORPILOT_AUTO_PLAN", "1").strip().lower()
    return value not in ("0", "false", "no", "off")


def preflight_director_plan(plan_path: str) -> Optional[str]:
    if not plan_path:
        return "PLAN.md path missing."
    if os.path.exists(plan_path):
        return None
    if auto_plan_enabled():
        ensure_plan_file(plan_path, auto_continue=True)
        return None
    ensure_plan_file(plan_path, auto_continue=False)
    return f"PLAN.md was created. Edit {plan_path} and rerun."


def ensure_docs_ready(workspace_full: str) -> Optional[int]:
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
    return None


def archive_task_history(workspace_full: str, cache_root_full: str, run_id: str, iteration: int, 
                        normalized: Dict[str, Any], director_result: Optional[Dict[str, Any]], 
                        timestamp: str) -> None:
    """归档任务历史到TASK_HISTORY.json"""
    try:
        # 任务历史文件路径
        task_history_path = resolve_artifact_path(workspace_full, cache_root_full, ".harborpilot/runtime/TASK_HISTORY.json")
        
        # 创建历史记录
        tasks = normalized.get("tasks", []) if isinstance(normalized, dict) else []
        
        # 计算执行摘要
        total_tasks = len(tasks) if isinstance(tasks, list) else 0
        completed_tasks = 0
        failed_tasks = 0
        
        # 从Director结果中获取执行统计
        successes = 0
        total_executed = 0
        if isinstance(director_result, dict):
            successes = int(director_result.get("successes", 0))
            total_executed = int(director_result.get("total", 0))
        
        # 构建历史记录
        history_record = {
            "round_id": run_id,
            "timestamp": timestamp,
            "pm_iteration": iteration,
            "focus": normalized.get("focus", ""),
            "overall_goal": normalized.get("overall_goal", ""),
            "tasks": tasks,
            "execution_summary": {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "success_rate": successes / total_executed if total_executed > 0 else 0.0
            },
            "director_results": {
                "run_id": director_result.get("run_id", "") if isinstance(director_result, dict) else "",
                "status": director_result.get("status", "unknown") if isinstance(director_result, dict) else "unknown",
                "start_time": director_result.get("start_time", "") if isinstance(director_result, dict) else "",
                "end_time": director_result.get("end_time", "") if isinstance(director_result, dict) else "",
                "successes": successes,
                "total": total_executed,
            },
            "artifacts": {
                "pm_tasks_path": ".harborpilot/runtime/PM_TASKS.json",
                "director_result_path": ".harborpilot/runtime/DIRECTOR_RESULT.json",
                "events_path": ".harborpilot/runtime/events.jsonl",
                "dialogue_path": ".harborpilot/runtime/DIALOGUE.jsonl"
            }
        }
        
        # 读取现有历史
        existing_history = {"rounds": []}
        if os.path.isfile(task_history_path):
            try:
                with open(task_history_path, "r", encoding="utf-8") as f:
                    existing_history = json.load(f)
                    if not isinstance(existing_history, dict) or "rounds" not in existing_history:
                        existing_history = {"rounds": []}
            except Exception:
                existing_history = {"rounds": []}
        
        # 添加新记录
        existing_history["rounds"].append(history_record)
        
        # 保持历史记录在合理范围内（最多保留100轮）
        if len(existing_history["rounds"]) > 100:
            existing_history["rounds"] = existing_history["rounds"][-100:]
        
        # 原子写入
        write_json_atomic(task_history_path, existing_history)
        
        print(f"[history] Archived round {run_id} with {total_tasks} tasks")
        
    except Exception as e:
        print(f"[history] Error archiving task history: {e}")


def run_once(args: argparse.Namespace, iteration: int = 1) -> int:
    backend = str(getattr(args, "pm_backend", "ollama") or "ollama").strip().lower()
    workspace_full = resolve_workspace_path(args.workspace, require_docs=False)
    docs_exit = ensure_docs_ready(workspace_full)
    if docs_exit is not None:
        return docs_exit
    if backend == "codex":
        ensure_codex_available()
    else:
        ensure_ollama_available()
    ramdisk_root = resolve_ramdisk_root(getattr(args, "ramdisk_root", None))
    cache_root_full = build_cache_root(ramdisk_root, workspace_full) or ""
    if state_to_ramdisk_enabled() and not cache_root_full:
        raise RuntimeError(
            "HARBORPILOT_STATE_TO_RAMDISK is enabled but no ramdisk cache root is available. "
            "Set HARBORPILOT_RAMDISK_ROOT (e.g. X:\\) or disable HARBORPILOT_STATE_TO_RAMDISK."
        )
    plan_full = resolve_artifact_path(workspace_full, cache_root_full, args.plan_path)
    gap_full = resolve_artifact_path(workspace_full, cache_root_full, args.gap_report_path)
    qa_full = resolve_artifact_path(workspace_full, cache_root_full, args.qa_path)
    req_full = os.path.join(workspace_full, args.requirements_path)
    pm_out_full = resolve_artifact_path(workspace_full, cache_root_full, args.pm_out)
    pm_report_full = resolve_artifact_path(workspace_full, cache_root_full, args.pm_report)
    pm_state_full = resolve_artifact_path(workspace_full, cache_root_full, args.state_path)
    pm_history_full = resolve_artifact_path(workspace_full, cache_root_full, args.task_history_path)
    
    # Establish run identity and directory early
    run_id = f"pm-{iteration:05d}"
    run_dir = resolve_run_dir(workspace_full, cache_root_full, run_id)
    update_latest_pointer(workspace_full, cache_root_full, run_id)
    
    # Run-specific paths for Director
    run_pm_tasks = os.path.join(run_dir, "PM_TASKS.json")
    run_director_result = os.path.join(run_dir, "DIRECTOR_RESULT.json")
    run_director_log = os.path.join(run_dir, "RUNLOG.md")
    run_events = os.path.join(run_dir, "events.jsonl")
    run_planner_resp = os.path.join(run_dir, "PLANNER_RESPONSE.md")
    run_ollama_resp = os.path.join(run_dir, "OLLAMA_RESPONSE.md")
    run_qa_resp = os.path.join(run_dir, "QA_RESPONSE.md")
    run_reviewer_resp = os.path.join(run_dir, "REVIEWER_RESPONSE.md")
    
    # Point args to run-specific paths for director invocation
    args.director_result_path = run_director_result
    args.director_events_path = run_events
    args.pm_task_path = run_pm_tasks
    args.planner_response_path = run_planner_resp
    args.ollama_response_path = run_ollama_resp
    args.qa_response_path = run_qa_resp
    args.reviewer_response_path = run_reviewer_resp

    events_size_start = 0
    events_seq_start = 0
    if run_events and os.path.exists(run_events):
        try:
            events_size_start = os.path.getsize(run_events)
        except Exception:
            events_size_start = 0
        events_seq_start = scan_last_seq(run_events)

    # Legacy/Root paths (kept for backward compatibility and persistent state)
    director_result_full = resolve_artifact_path(workspace_full, cache_root_full, args.director_result_path)
    stop_flag_full = stop_flag_path(workspace_full)
    dialogue_full = resolve_artifact_path(workspace_full, cache_root_full, args.dialogue_path) if args.dialogue_path else ""
    if dialogue_full:
        set_dialogue_seq(scan_last_seq(dialogue_full))

    pm_last_full = resolve_artifact_path(workspace_full, cache_root_full, args.pm_last_message_path)
    director_log_full = resolve_artifact_path(workspace_full, cache_root_full, run_director_log)
    director_subprocess_log_full = resolve_artifact_path(workspace_full, cache_root_full, DEFAULT_DIRECTOR_SUBPROCESS_LOG)
    director_status_full = resolve_artifact_path(workspace_full, cache_root_full, DEFAULT_DIRECTOR_STATUS)

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

    if not wait_for_agents_confirmation(
        workspace_full,
        cache_root_full,
        pm_state_full,
        pm_state,
        pm_report_full,
        dialogue_full,
        run_id,
        iteration,
        start_timestamp,
        args,
    ):
        return 3

    prompt = build_pm_prompt(
        requirements,
        plan_text,
        gap_report,
        last_qa,
        last_tasks,
        director_result,
        pm_state,
        iteration=iteration,
        run_id=run_id,
        events_path=run_events,
    )
    show_output = bool(getattr(args, "pm_show_output", False))
    print(f"[pm] {start_timestamp} iteration={iteration} backend={backend}")
    sys.stdout.flush()
    
    usage_ctx = UsageContext(
        run_id=run_id,
        task_id="",
        phase="planning",
        mode="pm",
        actor="PM"
    )

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
            usage_ctx=usage_ctx,
            events_path=run_events,
        )
    else:
        output = invoke_ollama(
            prompt, 
            args.model, 
            workspace_full, 
            show_output, 
            args.timeout,
            usage_ctx=usage_ctx,
            events_path=run_events
        )
    print(f"[pm] completed iteration={iteration} output_chars={len(output or '')}")
    sys.stdout.flush()
    exit_code = 0

    try:
        payload = json.loads(strip_ansi(output))
    except Exception:
        payload = {"focus": "parse_failed", "tasks": [], "notes": "PM JSON parse failed."}
    normalized = normalize_pm_payload(payload, iteration, start_timestamp)
    director_tasks, docs_only_tasks = split_director_tasks(
        normalized.get("tasks") if isinstance(normalized, dict) else []
    )
    director_payload = dict(normalized)
    director_payload["tasks"] = director_tasks
    write_json_atomic(pm_out_full, normalized)
    # Also write to run bucket
    write_json_atomic(run_pm_tasks, director_payload)

    run_id = f"pm-{iteration:05d}"
    tasks_for_dialogue = normalized.get("tasks") if isinstance(normalized, dict) else []
    if isinstance(tasks_for_dialogue, list) and tasks_for_dialogue:
        for task in tasks_for_dialogue:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("id") or "")
            task_title = str(task.get("title") or "")
            acc = task.get("acceptance") or []
            acc_summary = ", ".join(acc[:3]) if isinstance(acc, list) else ""
            if any(item for item in docs_only_tasks if str(item.get("id") or "") == task_id):
                emit_dialogue(
                    dialogue_full,
                    speaker="PM",
                    type="handoff",
                    text=f"Docs-only task {task_id}: {task_title}. Director will skip (PM-only).",
                    summary=f"Dispatch (PM-only): {task_id}",
                    run_id=run_id,
                    pm_iteration=iteration,
                    refs={"task_id": task_id, "phase": "handoff", "files": ["PM_TASKS.json"]},
                )
            else:
                emit_dialogue(
                    dialogue_full,
                    speaker="PM",
                    type="handoff",
                    text=f"Assigning task {task_id}: {task_title}. Acceptance: {acc_summary}",
                    summary=f"Dispatch: {task_id}",
                    run_id=run_id,
                    pm_iteration=iteration,
                    refs={"task_id": task_id, "phase": "handoff", "files": ["PM_TASKS.json"]},
                )
    else:
        emit_dialogue(
            dialogue_full,
            speaker="PM",
            type="handoff",
            text="No tasks generated in this iteration.",
            summary="Dispatch: none",
            run_id=run_id,
            pm_iteration=iteration,
            refs={"phase": "handoff", "files": ["PM_TASKS.json"]},
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
        director_attempts = max(int(getattr(args, "director_iterations", 1) or 1), 1)
        match_mode = normalize_match_mode(getattr(args, "director_match_mode", "latest"))
        qa_enabled = is_qa_enabled()
        tasks_for_director = director_payload.get("tasks") if isinstance(director_payload, dict) else []
        primary_director_task = None
        if isinstance(tasks_for_director, list) and tasks_for_director:
            primary_director_task = tasks_for_director[0] if isinstance(tasks_for_director[0], dict) else None
        if primary_director_task:
            task_id = str(primary_director_task.get("id") or "")
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
        run_dir = build_run_dir(workspace_full, cache_root_full, iteration)
        if not os.path.isfile(run_pm_tasks):
            archive_if_exists(pm_out_full, os.path.join(run_dir, "PM_TASKS.json"))
        archive_if_exists(pm_report_full, os.path.join(run_dir, "PM_REPORT.md"))
        expected_task_id = ""
        expected_task_title = ""
        expected_task_ids: List[str] = []
        director_start_epoch = time.time()
        director_skipped = False
        if docs_only_tasks and not tasks_for_director:
            emit_dialogue(
                dialogue_full,
                speaker="PM",
                type="warning",
                text="Docs-only tasks detected; Director skipped (PM-only).",
                summary="Director skipped (docs-only)",
                run_id=run_id,
                pm_iteration=iteration,
                refs={"phase": "guard", "files": ["PM_TASKS.json"]},
            )
            write_director_status(
                director_status_full,
                {
                    "running": False,
                    "started_at": director_start_epoch,
                    "ended_at": time.time(),
                    "updated_at": time.time(),
                    "mode": "pm",
                    "pm_iteration": iteration,
                    "exit_code": 0,
                    "log_path": director_subprocess_log_full or DEFAULT_DIRECTOR_SUBPROCESS_LOG,
                },
            )
            director_skipped = True
        elif docs_only_tasks:
            emit_dialogue(
                dialogue_full,
                speaker="PM",
                type="note",
                text="Docs-only tasks will not be sent to Director.",
                summary="Docs-only tasks skipped",
                run_id=run_id,
                pm_iteration=iteration,
                refs={"phase": "guard", "files": ["PM_TASKS.json"]},
            )
        if isinstance(tasks_for_director, list) and tasks_for_director:
            primary = tasks_for_director[0] if isinstance(tasks_for_director[0], dict) else {}
            expected_task_id = str(primary.get("id") or "")
            expected_task_title = str(primary.get("title") or "")
            for item in tasks_for_director:
                if isinstance(item, dict):
                    task_id = str(item.get("id") or "").strip()
                    if task_id:
                        expected_task_ids.append(task_id)
        expected_run_id = str(normalized.get("run_id") or f"pm-{iteration:05d}").strip()
        plan_block = preflight_director_plan(plan_full)
        plan_blocked = False
        agents_blocked = False
        if plan_block:
            plan_blocked = True
            pm_state["last_director_status"] = "blocked"
            pm_state["last_director_error_code"] = "PLAN_MISSING"
            pm_state["last_director_error_detail"] = plan_block
            write_json_atomic(pm_state_full, pm_state)
            emit_dialogue(
                dialogue_full,
                speaker="PM",
                type="warning",
                text=plan_block,
                summary="PLAN.md missing",
                run_id=run_id,
                pm_iteration=iteration,
                refs={"task_id": expected_task_id or None, "files": ["PLAN.md"]},
                meta={"error_code": "PLAN_MISSING"},
            )
            write_director_status(
                director_status_full,
                {
                    "running": False,
                    "started_at": director_start_epoch,
                    "ended_at": time.time(),
                    "updated_at": time.time(),
                    "mode": "pm",
                    "pm_iteration": iteration,
                    "exit_code": 1,
                    "log_path": director_subprocess_log_full or DEFAULT_DIRECTOR_SUBPROCESS_LOG,
                },
            )
        agents_path = os.path.join(workspace_full, "AGENTS.md")
        if not os.path.isfile(agents_path):
            agents_blocked = True
            pm_state["last_director_status"] = "blocked"
            pm_state["last_director_error_code"] = "AGENTS_MISSING"
            pm_state["last_director_error_detail"] = "AGENTS.md missing. Review AGENTS.generated.md first."
            write_json_atomic(pm_state_full, pm_state)
            emit_dialogue(
                dialogue_full,
                speaker="PM",
                type="warning",
                text="AGENTS.md missing. Please review AGENTS.generated.md and adopt it before running Director.",
                summary="AGENTS.md missing",
                run_id=run_id,
                pm_iteration=iteration,
                refs={"task_id": expected_task_id or None, "files": ["AGENTS.generated.md", "AGENTS.md"]},
                meta={"error_code": "AGENTS_MISSING"},
            )
            write_director_status(
                director_status_full,
                {
                    "running": False,
                    "started_at": director_start_epoch,
                    "ended_at": time.time(),
                    "updated_at": time.time(),
                    "mode": "pm",
                    "pm_iteration": iteration,
                    "exit_code": 1,
                    "log_path": director_subprocess_log_full or DEFAULT_DIRECTOR_SUBPROCESS_LOG,
                },
            )
        director_exit: Optional[int] = None
        matched_result: Optional[Dict[str, Any]] = None
        latest_result: Any = None
        last_dialogue_ts = 0.0
        director_stop_seen = False
        if not plan_blocked and not agents_blocked and not director_skipped:
            if director_stop_requested(workspace_full):
                clear_director_stop_flag(workspace_full)
                pm_state["last_director_status"] = "blocked"
                pm_state["last_director_error_code"] = "STOP_REQUESTED"
                pm_state["last_director_error_detail"] = "Director stop requested."
                write_json_atomic(pm_state_full, pm_state)
                emit_dialogue(
                    dialogue_full,
                    speaker="PM",
                    type="warning",
                    text="Director stop requested. Skipping director run.",
                    summary="Director stop requested",
                    run_id=run_id,
                    pm_iteration=iteration,
                    refs={"task_id": expected_task_id or None},
                    meta={"error_code": "STOP_REQUESTED"},
                )
                write_director_status(
                    director_status_full,
                    {
                        "running": False,
                        "started_at": director_start_epoch,
                        "ended_at": time.time(),
                        "updated_at": time.time(),
                        "mode": "pm",
                        "pm_iteration": iteration,
                        "exit_code": 1,
                        "log_path": director_subprocess_log_full or DEFAULT_DIRECTOR_SUBPROCESS_LOG,
                    },
                )
                director_stop_seen = True
            else:
                for attempt in range(1, director_attempts + 1):
                    director_start_epoch = time.time()
                    status_payload = {
                        "running": True,
                        "started_at": director_start_epoch,
                        "updated_at": time.time(),
                        "mode": "pm",
                        "pm_iteration": iteration,
                        "director_attempt": attempt,
                        "director_attempts": director_attempts,
                        "log_path": director_subprocess_log_full or DEFAULT_DIRECTOR_SUBPROCESS_LOG,
                    }
                    write_director_status(director_status_full, status_payload)
                    if director_attempts > 1:
                        emit_dialogue(
                            dialogue_full,
                            speaker="PM",
                            type="say",
                            text=f"Director attempt {attempt}/{director_attempts}.",
                            summary=f"Director attempt {attempt}/{director_attempts}",
                            run_id=run_id,
                            pm_iteration=iteration,
                            refs={"task_id": expected_task_id or None},
                        )
                    director_pid_holder: Dict[str, int] = {}
                    try:
                        director_exit = run_director_once(
                            args,
                            workspace_full,
                            iteration,
                            subprocess_log_path=director_subprocess_log_full,
                            director_log_path=run_director_log,
                            status_path=director_status_full,
                            status_payload=status_payload,
                            pid_holder=director_pid_holder,
                        )
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
                                "director_attempt": attempt,
                                "director_attempts": director_attempts,
                                "exit_code": director_exit,
                                "pid": director_pid_holder.get("pid"),
                                "log_path": director_subprocess_log_full or DEFAULT_DIRECTOR_SUBPROCESS_LOG,
                            },
                        )
                    if director_exit == 124:
                        timeout_result = build_director_fallback_result(
                            task_id=expected_task_id,
                            task_title=expected_task_title,
                            run_id=expected_run_id,
                            error_code="DIRECTOR_TIMEOUT",
                            reason="Director subprocess timed out.",
                        )
                        if not os.path.isfile(director_result_full):
                            write_json_atomic(director_result_full, timeout_result)
                        matched_result = timeout_result
                        pm_state["last_director_status"] = "blocked"
                        pm_state["last_director_error_code"] = "DIRECTOR_TIMEOUT"
                        pm_state["last_director_error_detail"] = "Director subprocess timeout."
                        write_json_atomic(pm_state_full, pm_state)
                    if director_exit == 130:
                        director_stop_seen = True
                        pm_state["last_director_status"] = "blocked"
                        pm_state["last_director_error_code"] = "STOP_REQUESTED"
                        pm_state["last_director_error_detail"] = "Director stop requested."
                        write_json_atomic(pm_state_full, pm_state)
                        emit_dialogue(
                            dialogue_full,
                            speaker="PM",
                            type="warning",
                            text="Director stop requested. Terminating director run.",
                            summary="Director stop requested",
                            run_id=run_id,
                            pm_iteration=iteration,
                            refs={"task_id": expected_task_id or None},
                            meta={"error_code": "STOP_REQUESTED"},
                        )
                        break
                    if director_exit is None or director_exit == 0:
                        director_check = wait_for_director_result_mode(
                            director_result_full,
                            expected_task_ids,
                            expected_run_id,
                            director_start_epoch,
                            args.director_result_timeout,
                            match_mode,
                        )
                        matched_result = match_director_result_mode(
                            director_check,
                            expected_task_ids,
                            expected_run_id,
                            director_start_epoch,
                            match_mode,
                        )
                    latest_result = read_json_file(director_result_full)
                    latest_match = match_director_result_mode(
                        latest_result,
                        expected_task_ids,
                        expected_run_id,
                        director_start_epoch,
                        match_mode,
                    )
                    if latest_match is not None:
                        matched_result = latest_match
                    result_for_dialogue: Optional[Dict[str, Any]] = None
                    if isinstance(matched_result, dict):
                        result_for_dialogue = matched_result
                    elif isinstance(latest_result, dict):
                        result_for_dialogue = latest_result
                    if result_for_dialogue is not None:
                        ts_epoch = result_timestamp_epoch(result_for_dialogue)
                        if ts_epoch + 1.0 >= director_start_epoch and ts_epoch > last_dialogue_ts:
                            pm_question, director_report, pm_review = emit_pm_director_conversation(
                                dialogue_full,
                                run_id,
                                iteration,
                                result_for_dialogue,
                                expected_task_id,
                                expected_task_title,
                                attempt,
                                director_attempts,
                                qa_enabled,
                            )
                            memo_content = build_pm_memo(
                                run_id=run_id,
                                pm_iteration=iteration,
                                attempt=attempt,
                                attempts=director_attempts,
                                expected_task_id=expected_task_id,
                                expected_task_title=expected_task_title,
                                result=result_for_dialogue,
                                qa_enabled=qa_enabled,
                                pm_question=pm_question,
                                director_report=director_report,
                                pm_review=pm_review,
                            )
                            try:
                                memo_path, memo_rel = write_pm_memo(
                                    workspace_full,
                                    cache_root_full,
                                    run_id,
                                    attempt,
                                    memo_content,
                                )
                                completion_summary = compact_text(
                                    str(result_for_dialogue.get("completion_summary") or ""),
                                    200,
                                )
                                if not completion_summary:
                                    completion_summary = compact_text(
                                        str(result_for_dialogue.get("qa_summary") or result_for_dialogue.get("reason") or ""),
                                        200,
                                    )
                                record = {
                                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "run_id": run_id,
                                    "pm_iteration": iteration,
                                    "director_attempt": attempt,
                                    "director_attempts": director_attempts,
                                    "task_id": expected_task_id,
                                    "task_title": expected_task_title,
                                    "status": str(result_for_dialogue.get("status") or "").strip(),
                                    "acceptance": result_for_dialogue.get("acceptance"),
                                    "summary": completion_summary,
                                    "rel_path": memo_rel.replace("\\", "/"),
                                }
                                index_path = write_pm_memo_index(workspace_full, cache_root_full, record)
                                summary_block = (
                                    f"## {record['timestamp']} {run_id}\n"
                                    f"- Task: {expected_task_id} {expected_task_title}\n"
                                    f"- Result: {record['acceptance']}/{record['status']}\n"
                                    f"- Summary: {completion_summary}\n"
                                    f"- Memo: {record['rel_path']}\n\n"
                                )
                                summary_path, export_path = write_pm_memo_summary(
                                    workspace_full,
                                    cache_root_full,
                                    summary_block,
                                )
                                emit_dialogue(
                                    dialogue_full,
                                    speaker="System",
                                    type="note",
                                    text=f"PM memo saved: {memo_path} | {index_path} | {summary_path} | {export_path}",
                                    summary="PM memo saved",
                                    run_id=run_id,
                                    pm_iteration=iteration,
                                    refs={"task_id": expected_task_id or None, "phase": "memo"},
                                )
                            except Exception as exc:
                                emit_dialogue(
                                    dialogue_full,
                                    speaker="System",
                                    type="warning",
                                    text=f"PM memo failed: {exc}",
                                    summary="PM memo failed",
                                    run_id=run_id,
                                    pm_iteration=iteration,
                                    refs={"task_id": expected_task_id or None, "phase": "memo"},
                                )
                            last_dialogue_ts = ts_epoch
                    else:
                        # Emit dialogue even when Director produced no result.
                        now = datetime.now()
                        now_epoch = now.timestamp()
                        if now_epoch > last_dialogue_ts:
                            fallback_result = {
                                "timestamp": now.isoformat(),
                                "status": "blocked",
                                "acceptance": False,
                                "error_code": "DIRECTOR_NO_RESULT",
                                "reason": "Director did not produce a result for this attempt.",
                                "task_id": expected_task_id,
                                "task_title": expected_task_title,
                            }
                            pm_question, director_report, pm_review = emit_pm_director_conversation(
                                dialogue_full,
                                run_id,
                                iteration,
                                fallback_result,
                                expected_task_id,
                                expected_task_title,
                                attempt,
                                director_attempts,
                                qa_enabled,
                            )
                            memo_content = build_pm_memo(
                                run_id=run_id,
                                pm_iteration=iteration,
                                attempt=attempt,
                                attempts=director_attempts,
                                expected_task_id=expected_task_id,
                                expected_task_title=expected_task_title,
                                result=fallback_result,
                                qa_enabled=qa_enabled,
                                pm_question=pm_question,
                                director_report=director_report,
                                pm_review=pm_review,
                            )
                            try:
                                memo_path, memo_rel = write_pm_memo(
                                    workspace_full,
                                    cache_root_full,
                                    run_id,
                                    attempt,
                                    memo_content,
                                )
                                record = {
                                    "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                                    "run_id": run_id,
                                    "pm_iteration": iteration,
                                    "director_attempt": attempt,
                                    "director_attempts": director_attempts,
                                    "task_id": expected_task_id,
                                    "task_title": expected_task_title,
                                    "status": "blocked",
                                    "acceptance": False,
                                    "summary": "Director did not produce a result for this attempt.",
                                    "rel_path": memo_rel.replace("\\", "/"),
                                }
                                index_path = write_pm_memo_index(workspace_full, cache_root_full, record)
                                summary_block = (
                                    f"## {record['timestamp']} {run_id}\n"
                                    f"- Task: {expected_task_id} {expected_task_title}\n"
                                    f"- Result: {record['acceptance']}/{record['status']}\n"
                                    f"- Summary: {record['summary']}\n"
                                    f"- Memo: {record['rel_path']}\n\n"
                                )
                                summary_path, export_path = write_pm_memo_summary(
                                    workspace_full,
                                    cache_root_full,
                                    summary_block,
                                )
                                emit_dialogue(
                                    dialogue_full,
                                    speaker="System",
                                    type="note",
                                    text=f"PM memo saved: {memo_path} | {index_path} | {summary_path} | {export_path}",
                                    summary="PM memo saved",
                                    run_id=run_id,
                                    pm_iteration=iteration,
                                    refs={"task_id": expected_task_id or None, "phase": "memo"},
                                )
                            except Exception as exc:
                                emit_dialogue(
                                    dialogue_full,
                                    speaker="System",
                                    type="warning",
                                    text=f"PM memo failed: {exc}",
                                    summary="PM memo failed",
                                    run_id=run_id,
                                    pm_iteration=iteration,
                                    refs={"task_id": expected_task_id or None, "phase": "memo"},
                                )
                            last_dialogue_ts = now_epoch
                    if matched_result is not None and is_director_done(matched_result):
                        break
            if expected_task_ids and matched_result is None and not director_stop_seen:
                plan_hint = detect_plan_missing(plan_full, director_log_full, director_start_epoch)
                pm_state["last_director_status"] = "blocked"
                if plan_hint:
                    pm_state["last_director_error_code"] = "PLAN_MISSING"
                    pm_state["last_director_error_detail"] = plan_hint
                    write_json_atomic(pm_state_full, pm_state)
                    emit_dialogue(
                        dialogue_full,
                        speaker="PM",
                        type="warning",
                        text=plan_hint,
                        summary="PLAN.md missing",
                        run_id=run_id,
                        pm_iteration=iteration,
                        refs={"task_id": expected_task_id or None, "files": ["PLAN.md"]},
                        meta={"error_code": "PLAN_MISSING"},
                    )
                else:
                    pm_state["last_director_error_code"] = "DIRECTOR_NO_RESULT"
                    pm_state.pop("last_director_error_detail", None)
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

            if isinstance(matched_result, dict):
                result_status = str(matched_result.get("status") or "").strip().lower()
                if result_status in ("success", "pass", "passed"):
                    task_id = str(matched_result.get("task_id") or expected_task_id or "").strip()
                    task_title = str(matched_result.get("task_title") or expected_task_title or "").strip()
                    task_key = task_id or task_title
                    if task_key:
                        record = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "run_id": run_id,
                            "pm_iteration": iteration,
                            "director_attempt": attempt,
                            "task_id": task_id,
                            "task_title": task_title,
                            "status": result_status,
                        }
                        append_jsonl(pm_history_full, record)
                        completed = pm_state.get("completed_task_ids")
                        if not isinstance(completed, list):
                            completed = []
                        if task_key not in completed:
                            completed.append(task_key)
                        pm_state["completed_task_ids"] = completed
                        pm_state["completed_task_count"] = len(completed)
                        write_json_atomic(pm_state_full, pm_state)
            
            # Sync artifacts back to root/state for persistence/compatibility
            archive_if_exists(run_director_result, os.path.join(workspace_full, ".harborpilot", "runtime", "DIRECTOR_RESULT.json"))
            archive_if_exists(run_planner_resp, os.path.join(workspace_full, ".harborpilot", "runtime", "PLANNER_RESPONSE.md"))
            archive_if_exists(run_ollama_resp, os.path.join(workspace_full, ".harborpilot", "runtime", "OLLAMA_RESPONSE.md"))
            archive_if_exists(run_qa_resp, os.path.join(workspace_full, ".harborpilot", "runtime", "QA_RESPONSE.md"))
            archive_if_exists(run_director_log, os.path.join(workspace_full, ".harborpilot", "runtime", "RUNLOG.md"))

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

    # 归档任务历史到TASK_HISTORY.json
    archive_task_history(workspace_full, cache_root_full, run_id, iteration, normalized, director_result, timestamp)

    if args.max_same_task and same_task_count >= args.max_same_task:
        ensure_parent_dir(pm_report_full)
        with open(pm_report_full, "a", encoding="utf-8") as handle:
            handle.write(
                f"\n## {timestamp} (iteration {iteration}) - warning\n"
                f"Status: same task repeated {same_task_count} times. PM should rotate focus.\n"
            )

    try:
        memory_path = os.path.join(workspace_full, ".harborpilot", "brain", "MEMORY.jsonl")
        run_invariant_sentinel(
            events_path=run_events,
            run_id=run_id,
            step=iteration,
            pm_task_path=pm_out_full,
            contract_fingerprint="",
            events_seq_start=events_seq_start,
            events_size_start=events_size_start,
            memory_path=memory_path,
        )
    except Exception as e:
        print(f"[SENTINEL] Error: {e}")

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="PM wrapper for Ollama loop")
    parser.add_argument("--workspace", "-Workspace", default=os.getcwd())
    parser.add_argument("--model", "-Model", default="modelscope.cn/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:latest")
    parser.add_argument("--pm-backend", default="codex", choices=["codex", "ollama"])
    parser.add_argument("--timeout", "-Timeout", type=int, default=0)
    parser.add_argument("--plan-path", "-PlanPath", default=".harborpilot/runtime/PLAN.md")
    parser.add_argument("--gap-report-path", "-GapReportPath", default=".harborpilot/runtime/GAP_REPORT.md")
    parser.add_argument("--qa-path", "-QaPath", default=".harborpilot/runtime/QA_RESPONSE.md")
    parser.add_argument("--requirements-path", "-RequirementsPath", default="docs/product/requirements.md")
    parser.add_argument("--pm-out", "-PmOut", default=".harborpilot/runtime/PM_TASKS.json")
    parser.add_argument("--pm-report", "-PmReport", default=".harborpilot/runtime/PM_REPORT.md")
    parser.add_argument("--state-path", "-StatePath", default=".harborpilot/runtime/PM_STATE.json")
    parser.add_argument("--task-history-path", "-TaskHistoryPath", default=".harborpilot/runtime/PM_TASK_HISTORY.jsonl")
    parser.add_argument("--director-result-path", "-DirectorResultPath", default=".harborpilot/runtime/DIRECTOR_RESULT.json")
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
    parser.add_argument("--director-iterations", type=int, default=1, help="Director attempts per PM iteration.")
    parser.add_argument(
        "--director-match-mode",
        default="latest",
        choices=["strict", "any", "latest", "run_id"],
        help="How to match director results to a PM run.",
    )
    parser.add_argument("--dialogue-path", default=".harborpilot/runtime/DIALOGUE.jsonl")
    parser.add_argument("--prompt-profile", default="demo_ming_armada", help="Prompt profile (e.g. demo_ming_armada, generic).")
    parser.add_argument("--pm-last-message-path", default=".harborpilot/runtime/PM_LAST_RESPONSE.md")
    parser.add_argument("--ramdisk-root", default="", help="Optional RAM-disk root (Windows default: X:). High-frequency artifacts will be written here.")
    parser.add_argument("--codex-profile", default="")
    parser.add_argument("--codex-full-auto", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--codex-dangerous", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--resume", action="store_true", help="Resume from the last iteration instead of incrementing.")
    args = parser.parse_args()

    try:
        if args.prompt_profile:
            os.environ[PROMPT_PROFILE_ENV] = str(args.prompt_profile).strip()
        workspace_full = resolve_workspace_path(args.workspace, require_docs=False)
        docs_exit = ensure_docs_ready(workspace_full)
        if docs_exit is not None:
            return docs_exit
        ramdisk_root = resolve_ramdisk_root(getattr(args, "ramdisk_root", None))
        cache_root_full = build_cache_root(ramdisk_root, workspace_full) or ""
        if state_to_ramdisk_enabled() and not cache_root_full:
            raise RuntimeError(
                "HARBORPILOT_STATE_TO_RAMDISK is enabled but no ramdisk cache root is available. "
                "Set HARBORPILOT_RAMDISK_ROOT (e.g. X:\\) or disable HARBORPILOT_STATE_TO_RAMDISK."
            )
        dialogue_full = resolve_artifact_path(workspace_full, cache_root_full, args.dialogue_path) if args.dialogue_path else ""
        iterations = 0
        if args.loop:
            state_full = os.path.join(workspace_full, args.state_path)
            state_data = read_json_file(state_full)
            if isinstance(state_data, dict):
                last_iter = state_data.get("pm_iteration")
                try:
                    iterations = int(last_iter) if last_iter is not None else 0
                except Exception:
                    iterations = 0
        
        # If resuming, we want to start AT the last iteration, so we decrement by 1
        # because the loop immediately increments.
        # But wait, if iterations=5, loop does +1 -> 6.
        # If resume=True, we want next to be 5. So we set iterations=4.
        if args.resume and iterations > 0:
            iterations -= 1

        if not args.loop and args.max_iterations <= 1:
            return run_once(args, 1)

        while True:
            # Sync sequence from file to avoid collision with Director
            if dialogue_full:
                set_dialogue_seq(scan_last_seq(dialogue_full))

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
