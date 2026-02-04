from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..config import Settings
from ..llm import config as llm_config
from ..llm.types import estimate_usage
from ..utils import build_cache_root, resolve_artifact_path, write_text_atomic
from .llm_tests import (
    _emit_event,
    _events_path,
    _new_test_run_id,
    _resolve_provider,
    _split_thinking_output,
    _update_index,
    _utc_now,
    _provider_invoke,
)


def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _sanitize_token(value: str) -> str:
    if not value:
        return "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())[:80] or "unknown"


def _is_codex_provider(provider_id: str, provider_cfg: Dict[str, Any]) -> bool:
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    command = str(provider_cfg.get("command") or "").lower()
    if provider_type in ("codex_cli", "codex_sdk", "cli"):
        return True
    if "codex" in command:
        return True
    if provider_id == "codex_cli":
        return True
    return False


def _looks_like_codex_model(model: str) -> bool:
    if not model:
        return False
    lowered = model.lower()
    if lowered.startswith("gpt-"):
        return True
    if "codex" in lowered:
        return True
    return False


def _format_interview_context(context: Optional[List[Dict[str, Any]]]) -> str:
    if not context:
        return ""
    entries = []
    for idx, item in enumerate(context[-3:], start=1):
        if not isinstance(item, dict):
            continue
        question = _truncate(str(item.get("question") or ""), 200)
        answer = _truncate(str(item.get("answer") or ""), 400)
        if not question and not answer:
            continue
        entries.append(f"{idx}. Q: {question}\n   A: {answer}")
    return "\n".join(entries)


def _extract_project_path(question: str) -> Optional[str]:
    if not question:
        return None
    match = re.search(r"([A-Za-z]:\\[^\s\"']+)", question)
    if match:
        return match.group(1)
    match = re.search(r"(\/[^\s\"']+)", question)
    if match:
        return match.group(1)
    return None


def _inject_project_dir(provider_cfg: Dict[str, Any], project_path: str) -> Dict[str, Any]:
    if not project_path:
        return provider_cfg
    codex_exec = dict(provider_cfg.get("codex_exec") or {})
    if not codex_exec.get("cd"):
        codex_exec["cd"] = project_path
    add_dirs = codex_exec.get("add_dirs") or []
    if not isinstance(add_dirs, list):
        add_dirs = []
    if project_path not in add_dirs:
        add_dirs = [*add_dirs, project_path]
    codex_exec["add_dirs"] = add_dirs
    return {**provider_cfg, "codex_exec": codex_exec}


def _validate_interview_prompt(prompt: str) -> bool:
    if not prompt:
        return False
    required = ["CANDIDATE", "INTERVIEWEE", "ANSWER", "QUESTION TO ANSWER"]
    upper = prompt.upper()
    return all(token in upper for token in required)


def _fallback_interview_prompt(role: str, question: str) -> str:
    role_label = role.strip().upper() or "ROLE"
    return (
        f"You are a CANDIDATE interviewing for the {role_label} role.\n"
        "You are the INTERVIEWEE.\n"
        "Answer the question directly. Do NOT ask for clarification.\n"
        "If details are missing, state assumptions and proceed.\n\n"
        f"QUESTION TO ANSWER: {question}\n\n"
        "<thinking>Your reasoning</thinking>\n"
        "<answer>Your direct professional answer</answer>\n"
    )


def _strict_interview_prompt(role: str, question: str) -> str:
    role_label = role.strip().upper() or "ROLE"
    return (
        "ROLE: You are a job CANDIDATE in an interview.\n"
        "ABSOLUTE RULES:\n"
        "- You are the INTERVIEWEE.\n"
        "- Answer the question directly and completely.\n"
        "- Do NOT ask for clarification or additional context.\n"
        "- Do NOT greet, introduce yourself, or ask what to discuss.\n"
        "- Do NOT mention being an assistant or offer help.\n"
        "- If asked to analyze a local project path, assume read-only access and provide a structured analysis plan and risks.\n"
        "- If details are missing, state assumptions and proceed.\n\n"
        f"Position: {role_label}\n"
        f"QUESTION TO ANSWER: {question}\n\n"
        "<thinking>Your reasoning</thinking>\n"
        "<answer>Your direct professional answer</answer>\n"
    )


def build_interactive_interview_prompt(
    role: str,
    question: str,
    context: Optional[List[Dict[str, Any]]] = None,
    *,
    expects_thinking: Optional[bool] = None,
    criteria: Optional[List[str]] = None,
    project_path: Optional[str] = None,
) -> str:
    role_label = role.strip().upper() or "ROLE"
    criteria_text = " / ".join([str(item) for item in (criteria or []) if str(item).strip()])
    immediate_instruction = (
        "IMMEDIATE ACTION REQUIRED:\n"
        "You must answer the question below RIGHT NOW.\n"
        "Do NOT greet, introduce yourself, or ask what to discuss.\n"
        "Do NOT say you are 'ready to answer' or 'thanks for the opportunity'.\n"
        "Jump directly to the answer.\n\n"
    )
    forbidden_block = (
        "FORBIDDEN RESPONSES (do NOT use these):\n"
        "- \"Thanks for the opportunity\"\n"
        "- \"I'm ready to answer\"\n"
        "- \"What would you like to discuss\"\n"
        "- \"Happy to help\"\n"
        "- Any greeting or introduction\n"
        "- Any question asking for more topics\n\n"
    )
    thinking_instruction = (
        "Include your thinking process in <thinking> tags before your answer.\n"
        if expects_thinking is None or expects_thinking
        else "Optional: include <thinking> if helpful.\n"
    )
    few_shot = (
        "EXAMPLE OF CORRECT RESPONSE:\n"
        "Question: How do you handle project delays?\n"
        "<thinking>Identify root cause, impact, and mitigation.</thinking>\n"
        "<answer>I assess root causes, re-baseline the plan, communicate trade-offs, and execute mitigation actions.</answer>\n\n"
    )
    context_text = _format_interview_context(context)
    context_block = f"Previous context:\n{context_text}\n" if context_text else ""
    project_block = ""
    if project_path:
        project_block = (
            f"Local project path: {project_path}\n"
            "You have read-only access to this path. Inspect real files before answering.\n"
            "If access fails, explicitly state the limitation and provide a structured analysis plan anyway.\n"
        )
    prompt = (
        "ROLE: You are a job CANDIDATE interviewing for a position.\n"
        "IMPORTANT: You are the INTERVIEWEE, not the interviewer.\n"
        + immediate_instruction
        + forbidden_block
        + "TASK: ANSWER the question directly and professionally.\n"
        + "RESTRICTIONS:\n"
        "- Do NOT ask for clarification or more context.\n"
        "- If something is unclear, state assumptions and proceed.\n"
        "- Do NOT refuse or redirect the user.\n"
        "- Provide a concrete, structured response.\n\n"
        f"Position: {role_label}\n"
        + (f"Key evaluation criteria: {criteria_text}\n" if criteria_text else "")
        + thinking_instruction
        + few_shot
        + project_block
        + context_block
        + f"QUESTION TO ANSWER: {question}\n\n"
        + "FORMAT YOUR RESPONSE AS:\n"
        + "<thinking>your reasoning</thinking>\n"
        + "<answer>your direct professional answer</answer>\n"
    )
    if not _validate_interview_prompt(prompt):
        return _fallback_interview_prompt(role, question)
    return prompt


def run_interactive_interview_question(
    settings: Settings,
    role: str,
    provider_id: str,
    model: str,
    question: str,
    *,
    session_id: Optional[str] = None,
    context: Optional[List[Dict[str, Any]]] = None,
    expects_thinking: Optional[bool] = None,
    criteria: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    debug: Optional[bool] = None,
) -> Dict[str, Any]:
    workspace = settings.workspace
    cache_root = build_cache_root(settings.ramdisk_root or "", workspace)
    config = llm_config.load_llm_config(workspace, cache_root, settings=settings)
    role = role.strip().lower()
    provider_cfg = _resolve_provider(config, provider_id)
    if _is_codex_provider(provider_id, provider_cfg) and not _looks_like_codex_model(model):
        error_message = (
            f"Model '{model}' is not supported with Codex CLI. "
            "Please use a gpt-* codex model, or switch this provider to Ollama for local GGUF models."
        )
        usage = estimate_usage("", "")
        payload = {
            "session_id": session_id or f"interactive-{_new_test_run_id()}",
            "timestamp": _utc_now(),
            "question": question,
            "output": "",
            "answer": "",
            "thinking": "",
            "format": "",
            "usage": usage.to_dict(),
            "latency_ms": 0,
            "ok": False,
            "error": error_message,
            "answer_quality": _validate_answer_quality(""),
            "retry_attempts": 0,
        }
        if debug:
            payload["debug"] = {
                "prompt": None,
                "provider_id": provider_id,
                "model": model,
            }
        return payload
    if not api_key and provider_cfg.get("api_key"):
        api_key = str(provider_cfg.get("api_key") or "")
    if extra_headers:
        provider_cfg = {**provider_cfg, "headers": {**(provider_cfg.get("headers") or {}), **extra_headers}}
    run_id = session_id or f"interactive-{_new_test_run_id()}"
    timestamp = _utc_now()
    cleaned_context = []
    for item in context or []:
        if not isinstance(item, dict):
            continue
        answer_text = str(item.get("answer") or "")
        if _looks_like_deflection(answer_text):
            continue
        cleaned_context.append(item)
    project_path = _extract_project_path(question)
    if project_path and os.path.isdir(project_path):
        provider_cfg = _inject_project_dir(provider_cfg, project_path)
    else:
        project_path = None
    prompt = build_interactive_interview_prompt(
        role,
        question,
        context=cleaned_context,
        expects_thinking=expects_thinking,
        criteria=criteria,
        project_path=project_path,
    )
    events_path = _events_path(settings, workspace, cache_root)
    _emit_event(
        events_path,
        "llm_interview.ask",
        role,
        run_id,
        {
            "role": role,
            "provider_id": provider_id,
            "model": model,
            "question": question,
            "prompt": _truncate(prompt, 2000),
        },
    )
    if debug:
        provider_cfg = {**provider_cfg, "debug_emit_args": True}
    
    # Emit pre-invoke debug info
    if debug:
        _emit_event(
            events_path,
            "llm_interview.invoke_start",
            role,
            run_id,
            {
                "provider_id": provider_id,
                "model": model,
                "prompt_length": len(prompt),
                "prompt_preview": _truncate(prompt, 500),
            },
        )
    
    result = _provider_invoke(
        provider_cfg,
        model,
        prompt,
        api_key,
        role=role,
        suite="interactive_interview",
        events_path=events_path,
        run_id=run_id,
    )
    
    # Emit post-invoke debug info
    if debug:
        _emit_event(
            events_path,
            "llm_interview.invoke_complete",
            role,
            run_id,
            {
                "ok": result.ok,
                "error": result.error,
                "output_length": len(result.output or ""),
                "latency_ms": result.latency_ms,
                "has_raw_debug": bool(result.raw and isinstance(result.raw, dict)),
            },
        )
    prompt_used = prompt
    thinking_text, answer_text, fmt = _split_thinking_output(result.output or "")
    answer_for_check = answer_text or result.output or ""
    quality = _validate_answer_quality(answer_for_check)
    retry_attempts = 0
    if result.ok and (quality.get("direct_answer") is False or _looks_like_deflection(answer_for_check)):
        retry_prompt = _strict_interview_prompt(role, question)
        _emit_event(
            events_path,
            "llm_interview.retry",
            role,
            run_id,
            {
                "reason": "deflection_detected",
                "prompt": _truncate(retry_prompt, 2000),
            },
        )
        retry_result = _provider_invoke(
            provider_cfg,
            model,
            retry_prompt,
            api_key,
            role=role,
            suite="interactive_interview_retry",
            events_path=events_path,
            run_id=run_id,
        )
        if retry_result.ok:
            result = retry_result
            prompt_used = retry_prompt
            thinking_text, answer_text, fmt = _split_thinking_output(result.output or "")
            answer_for_check = answer_text or result.output or ""
            quality = _validate_answer_quality(answer_for_check)
            retry_attempts = 1
    payload = {
        "session_id": run_id,
        "timestamp": timestamp,
        "question": question,
        "output": result.output,
        "answer": answer_text or result.output,
        "thinking": thinking_text,
        "format": fmt,
        "usage": result.usage.to_dict(),
        "latency_ms": result.latency_ms,
        "ok": result.ok,
        "error": result.error,
        "answer_quality": quality,
        "retry_attempts": retry_attempts,
    }
    if debug:
        raw_debug = result.raw if isinstance(result.raw, dict) else {}
        payload["debug"] = {
            "prompt": prompt_used,
            "provider_id": provider_id,
            "model": model,
            "cli_args": raw_debug.get("debug_args"),
            "cli_send_prompt": raw_debug.get("debug_send_prompt"),
            "stdin_prompt": raw_debug.get("debug_stdin_prompt"),
            "cli_command": raw_debug.get("debug_command"),
        }
    _emit_event(
        events_path,
        "llm_interview.answer",
        role,
        run_id,
        {"ok": result.ok, "error": result.error, "latency_ms": result.latency_ms},
    )
    return payload


def _looks_like_deflection(answer: str) -> bool:
    if not answer:
        return True
    lowered = answer.lower()
    hints = [
        "let me know",
        "what would you like",
        "ready to interview",
        "i'm here to help",
        "as your assistant",
        "provide more",
        "need more context",
        "need more information",
        "please provide",
        "tell me what",
        "interview prep",
        "clarification",
        "clarify",
        "what position",
        "what questions",
    ]
    if any(hint in lowered for hint in hints):
        return True
    if ("?" in answer or "？" in answer) and len(answer) < 240:
        return True
    return False


def _validate_answer_quality(answer: str) -> Dict[str, Any]:
    forbidden_phrases = [
        "thanks for the opportunity",
        "ready to answer",
        "what would you like",
        "happy to help",
        "let me know",
        "discuss first",
        "i’m ready to answer",
        "i'm ready to answer",
        "what would you like to discuss",
        "what would you like to cover",
        "interview mode",
        "as your assistant",
    ]
    answer_lower = (answer or "").lower()
    has_forbidden = any(phrase in answer_lower for phrase in forbidden_phrases)
    content_length = len(answer or "")
    has_content = content_length >= 120 and not has_forbidden
    return {
        "direct_answer": bool(has_content),
        "has_forbidden_phrases": bool(has_forbidden),
        "content_length": content_length,
    }


def save_interactive_interview_report(
    settings: Settings,
    role: str,
    provider_id: str,
    model: str,
    report: Dict[str, Any],
    *,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    workspace = settings.workspace
    cache_root = build_cache_root(settings.ramdisk_root or "", workspace)
    run_id = session_id or str(report.get("id") or f"interactive-{_new_test_run_id()}")
    saved_at = _utc_now()
    safe_role = _sanitize_token(role)
    safe_provider = _sanitize_token(provider_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"{safe_role}_{safe_provider}_{stamp}.json"
    report_root = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/interviews")
    report_path = resolve_artifact_path(workspace, cache_root, f".harborpilot/runtime/interviews/{filename}")
    os.makedirs(report_root, exist_ok=True)

    report_payload = {
        **(report or {}),
        "id": report.get("id") or run_id,
        "role": report.get("role") or role,
        "provider_id": report.get("provider_id") or provider_id,
        "model": report.get("model") or model,
        "saved_at": saved_at,
    }
    write_text_atomic(report_path, json.dumps(report_payload, ensure_ascii=False, indent=2))

    history_path = resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/interviews/interview_history.json")
    history: Dict[str, Any] = {"schema_version": 1, "interviews": [], "lastUpdated": saved_at, "statistics": {}}
    if os.path.isfile(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
                if isinstance(loaded, dict):
                    history = loaded
        except Exception:
            history = {"schema_version": 1, "interviews": [], "lastUpdated": saved_at, "statistics": {}}

    interviews = history.get("interviews")
    if not isinstance(interviews, list):
        interviews = []
    overall_status = str(report_payload.get("overallStatus") or report_payload.get("status") or "").lower()
    status = "passed" if overall_status in {"passed", "pass", "approved", "ready"} else "failed"
    interviews.append(
        {
            "id": report_payload.get("id") or run_id,
            "role": role,
            "provider_id": provider_id,
            "model": model,
            "status": status,
            "timestamp": report_payload.get("endTime") or report_payload.get("timestamp") or saved_at,
            "report_path": report_path,
        }
    )

    total = len(interviews)
    passed = len([item for item in interviews if str(item.get("status")).lower() == "passed"])
    stats_by_role: Dict[str, Dict[str, Any]] = {}
    for item in interviews:
        item_role = str(item.get("role") or "")
        if not item_role:
            continue
        role_stats = stats_by_role.setdefault(item_role, {"total": 0, "passed": 0})
        role_stats["total"] += 1
        if str(item.get("status")).lower() == "passed":
            role_stats["passed"] += 1

    history["schema_version"] = 1
    history["interviews"] = interviews
    history["lastUpdated"] = saved_at
    history["statistics"] = {
        "totalInterviews": total,
        "passRate": round(passed / total, 4) if total else 0,
        "roleStats": {
            role_key: {
                "total": stats["total"],
                "passed": stats["passed"],
                "passRate": round(stats["passed"] / stats["total"], 4) if stats["total"] else 0,
            }
            for role_key, stats in stats_by_role.items()
        },
    }
    write_text_atomic(history_path, json.dumps(history, ensure_ascii=False, indent=2))

    compat_report = {
        "schema_version": 1,
        "test_run_id": run_id,
        "timestamp": report_payload.get("endTime") or saved_at,
        "target": {"role": role, "provider_id": provider_id, "model": model},
        "suites": {
            "interactive": {
                "ok": status == "passed",
                "details": {
                    "summary": report_payload.get("summary"),
                    "notes": report_payload.get("userNotes"),
                },
            }
        },
        "final": {
            "ready": status == "passed",
            "grade": "PASS" if status == "passed" else "FAIL",
            "next_action": "ready" if status == "passed" else "adjust_profile_or_model",
        },
    }
    try:
        _update_index(settings, cache_root, role, compat_report)
    except Exception:
        pass

    events_path = _events_path(settings, workspace, cache_root)
    _emit_event(
        events_path,
        "llm_interview.save",
        role,
        run_id,
        {"role": role, "provider_id": provider_id, "model": model, "status": status},
    )
    return {"saved": True, "report_path": report_path, "history_path": history_path}
