"""Streaming interactive interview service with real-time output

This module provides a streaming version of the interview functionality
that pushes output to a queue as it becomes available.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import threading
import queue as threading_queue
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..config import Settings
from ..llm import config as llm_config
from ..llm.types import estimate_usage
from ..llm.providers.codex_cli_provider import (
    _build_codex_exec_args,
    _resolve_command,
    _normalize_command,
    _parse_codex_json_output,
    _extract_cli_error_message,
    _pick_reasoning_effort_fallback,
    _set_codex_config_override,
    _truncate,
    _render_args as _provider_render_args,
)
from ..utils import build_cache_root, build_utf8_env
from .interactive_interview import (
    _resolve_provider,
    _is_codex_provider,
    _looks_like_codex_model,
    _format_interview_context,
    _extract_project_path,
    _inject_project_dir,
    _looks_like_deflection,
    _validate_answer_quality,
    _split_thinking_output,
    _strict_interview_prompt,
    build_interactive_interview_prompt,
    _new_test_run_id,
    _utc_now,
)


async def run_interactive_interview_streaming(
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
    output_queue: asyncio.Queue,
) -> Dict[str, Any]:
    """Run interactive interview with real-time streaming output
    
    Args:
        settings: Application settings
        role: Interview role (pm, director, qa, docs)
        provider_id: Provider identifier
        model: Model name
        question: Question to ask
        session_id: Optional session ID
        context: Optional conversation context
        expects_thinking: Whether to expect thinking output
        criteria: Evaluation criteria
        api_key: Optional API key
        extra_headers: Optional extra headers
        output_queue: Async queue for streaming output
        
    Returns:
        Final result dictionary
    """
    workspace = settings.workspace
    cache_root = build_cache_root(settings.ramdisk_root or "", workspace)
    config = llm_config.load_llm_config(workspace, cache_root, settings=settings)
    role = role.strip().lower()
    provider_cfg = _resolve_provider(config, provider_id)
    
    # Check model compatibility
    if _is_codex_provider(provider_id, provider_cfg) and not _looks_like_codex_model(model):
        error_message = (
            f"Model '{model}' is not supported with Codex CLI. "
            "Please use a gpt-* codex model, or switch this provider to Ollama for local GGUF models."
        )
        result = {
            "session_id": session_id or f"interactive-{_new_test_run_id()}",
            "timestamp": _utc_now(),
            "question": question,
            "output": "",
            "answer": "",
            "thinking": "",
            "format": "",
            "usage": estimate_usage("", "").to_dict(),
            "latency_ms": 0,
            "ok": False,
            "error": error_message,
            "answer_quality": {"direct_answer": False, "has_forbidden_phrases": False, "content_length": 0},
            "retry_attempts": 0,
        }
        return result
    
    if not api_key and provider_cfg.get("api_key"):
        api_key = str(provider_cfg.get("api_key") or "")
    if extra_headers:
        provider_cfg = {**provider_cfg, "headers": {**(provider_cfg.get("headers") or {}), **extra_headers}}
    
    run_id = session_id or f"interactive-{_new_test_run_id()}"
    timestamp = _utc_now()
    
    # Clean context
    cleaned_context = []
    for item in context or []:
        if not isinstance(item, dict):
            continue
        answer_text = str(item.get("answer") or "")
        if _looks_like_deflection(answer_text):
            continue
        cleaned_context.append(item)
    
    # Extract project path if any
    project_path = _extract_project_path(question)
    if project_path and os.path.isdir(project_path):
        provider_cfg = _inject_project_dir(provider_cfg, project_path)
    else:
        project_path = None
    
    # Build prompt
    prompt = build_interactive_interview_prompt(
        role,
        question,
        context=cleaned_context,
        expects_thinking=expects_thinking,
        criteria=criteria,
        project_path=project_path,
    )
    
    # Send start event
    await output_queue.put({
        "type": "start",
        "data": {
            "session_id": run_id,
            "timestamp": timestamp,
            "role": role,
            "model": model,
            "question": question,
        }
    })
    
    # Check if Codex provider for streaming
    is_codex = _is_codex_provider(provider_id, provider_cfg)
    
    if is_codex:
        result = await _run_codex_streaming(
            provider_cfg,
            model,
            prompt,
            api_key,
            output_queue,
            run_id,
            question,
        )
    else:
        # For non-Codex providers, run normally but send result
        result = await _run_standard_streaming(
            provider_cfg,
            model,
            prompt,
            api_key,
            output_queue,
            run_id,
            question,
        )
    
    return result


async def _run_codex_streaming(
    provider_cfg: Dict[str, Any],
    model: str,
    prompt: str,
    api_key: Optional[str],
    output_queue: asyncio.Queue,
    run_id: str,
    question: str,
) -> Dict[str, Any]:
    """Run Codex CLI with real-time streaming output"""
    
    command = str(provider_cfg.get("command", "codex")).strip()
    resolved = _resolve_command(command)
    
    if not resolved:
        error_result = {
            "session_id": run_id,
            "timestamp": _utc_now(),
            "question": question,
            "output": "",
            "answer": "",
            "thinking": "",
            "format": "",
            "usage": estimate_usage(prompt, "").to_dict(),
            "latency_ms": 0,
            "ok": False,
            "error": "Codex CLI command not found",
            "answer_quality": {"direct_answer": False, "has_forbidden_phrases": False, "content_length": 0},
            "retry_attempts": 0,
        }
        await output_queue.put({"type": "error", "data": {"error": "Codex CLI command not found"}})
        return error_result
    
    # Build args
    args = _build_codex_exec_args(model, provider_cfg)
    rendered_args, send_prompt = _provider_render_args(args, prompt, model, None)
    
    # Send command info
    await output_queue.put({
        "type": "command",
        "data": {
            "command": resolved,
            "args": rendered_args,
            "send_prompt_via_stdin": send_prompt,
        }
    })
    
    start_time = asyncio.get_event_loop().time()
    stdout_lines = []
    stderr_lines = []
    
    def run_subprocess(loop: asyncio.AbstractEventLoop):
        """Run subprocess in thread and push output to queue"""
        cmd = _normalize_command(resolved) + rendered_args
        
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if send_prompt else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(provider_cfg.get("working_dir") or "") or None,
                env=build_utf8_env(provider_cfg.get("env")),
                bufsize=1,
            )
            
            def read_stream(stream, stream_type: str):
                """Read from stream line by line"""
                for line in iter(stream.readline, ''):
                    if not line:
                        break
                    if stream_type == "stdout":
                        stdout_lines.append(line)
                    else:
                        stderr_lines.append(line)
                    # Push to async queue
                    asyncio.run_coroutine_threadsafe(
                        output_queue.put({
                            "type": stream_type,
                            "data": {"line": line.rstrip('\n')}
                        }),
                        loop
                    )
                stream.close()
            
            # Start reader threads
            stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, "stdout"))
            stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, "stderr"))
            stdout_thread.start()
            stderr_thread.start()
            
            # Send input
            if send_prompt and process.stdin:
                process.stdin.write(prompt)
                process.stdin.close()
            
            # Wait for completion
            process.wait()
            stdout_thread.join()
            stderr_thread.join()
            
            return process.returncode
            
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                output_queue.put({"type": "error", "data": {"error": str(exc)}}),
                loop
            )
            return 1
    
    # Run subprocess in thread
    loop = asyncio.get_event_loop()
    returncode = await loop.run_in_executor(
        None,
        run_subprocess,
        loop
    )
    
    latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
    stdout = ''.join(stdout_lines)
    stderr = ''.join(stderr_lines)
    
    # Parse output
    output = stdout.strip() if stdout else ""
    if output and '--json' in rendered_args:
        output = _parse_codex_json_output(output)
    
    # Extract thinking and answer
    thinking_text, answer_text, fmt = _split_thinking_output(output)
    answer_for_check = answer_text or output or ""
    quality = _validate_answer_quality(answer_for_check)
    
    result = {
        "session_id": run_id,
        "timestamp": _utc_now(),
        "question": question,
        "output": output,
        "answer": answer_text or output,
        "thinking": thinking_text,
        "format": fmt,
        "usage": estimate_usage(prompt, output).to_dict(),
        "latency_ms": latency_ms,
        "ok": returncode == 0,
        "error": stderr if returncode != 0 else None,
        "answer_quality": quality,
        "retry_attempts": 0,
    }
    
    return result


async def _run_standard_streaming(
    provider_cfg: Dict[str, Any],
    model: str,
    prompt: str,
    api_key: Optional[str],
    output_queue: asyncio.Queue,
    run_id: str,
    question: str,
) -> Dict[str, Any]:
    """Run standard (non-Codex) provider with streaming"""
    # Import here to avoid circular imports
    from ..llm.providers.provider_registry import provider_manager
    
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    merged_cfg = {**provider_cfg, "api_key": api_key} if api_key else provider_cfg
    provider_instance = provider_manager.get_provider_instance(provider_type)
    
    start_time = asyncio.get_event_loop().time()
    
    await output_queue.put({
        "type": "stdout",
        "data": {"line": "Running standard provider..."}
    })
    
    try:
        if provider_instance:
            result_obj = provider_instance.invoke(prompt, model, merged_cfg)
            output = result_obj.output
            error = result_obj.error
            ok = result_obj.ok
        else:
            output = ""
            error = f"Unknown provider type: {provider_type}"
            ok = False
        
        latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        thinking_text, answer_text, fmt = _split_thinking_output(output)
        
        result = {
            "session_id": run_id,
            "timestamp": _utc_now(),
            "question": question,
            "output": output,
            "answer": answer_text or output,
            "thinking": thinking_text,
            "format": fmt,
            "usage": estimate_usage(prompt, output).to_dict(),
            "latency_ms": latency_ms,
            "ok": ok,
            "error": error,
            "answer_quality": _validate_answer_quality(answer_text or output),
            "retry_attempts": 0,
        }
        
        return result
        
    except Exception as exc:
        latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        result = {
            "session_id": run_id,
            "timestamp": _utc_now(),
            "question": question,
            "output": "",
            "answer": "",
            "thinking": "",
            "format": "",
            "usage": estimate_usage(prompt, "").to_dict(),
            "latency_ms": latency_ms,
            "ok": False,
            "error": str(exc),
            "answer_quality": {"direct_answer": False, "has_forbidden_phrases": False, "content_length": 0},
            "retry_attempts": 0,
        }
        await output_queue.put({"type": "error", "data": {"error": str(exc)}})
        return result
