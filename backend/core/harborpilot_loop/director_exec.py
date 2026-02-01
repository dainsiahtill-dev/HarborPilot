import difflib
import os
import re
import shlex
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from io_utils import emit_event, ensure_parent_dir, write_text_atomic
from prompts import (
    apply_file_blocks,
    build_file_context,
    build_ollama_prompt,
    build_qa_prompt,
    build_reviewer_prompt,
    parse_file_blocks,
)
from shared import FILE_BLOCK_RE, normalize_path, strip_ansi
from ollama_utils import invoke_ollama


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _enforce_utf8() -> None:
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


def _build_utf8_env() -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    return env


_enforce_utf8()


def _build_refs(
    state: Any,
    phase: str,
    files: Optional[List[str]] = None,
    evidence_path: Optional[str] = None,
    trajectory_path: Optional[str] = None,
) -> Dict[str, Any]:
    refs = {
        "task_id": getattr(state, "current_task_id", "") or None,
        "task_fingerprint": getattr(state, "current_task_fingerprint", "") or None,
        "run_id": getattr(state, "current_run_id", "") or None,
        "pm_iteration": getattr(state, "current_pm_iteration", None),
        "director_iteration": getattr(state, "current_director_iteration", None),
        "phase": phase,
    }
    if files:
        refs["files"] = files
    if evidence_path:
        refs["evidence_path"] = evidence_path
    if trajectory_path:
        refs["trajectory_path"] = trajectory_path
    return refs


def _truncate_text(text: str, limit: int = 800) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _is_docs_path(path: str) -> bool:
    if not path:
        return False
    normalized = normalize_path(path).lstrip("/")
    lowered = normalized.lower()
    return lowered == "docs" or lowered.startswith("docs/")


def _append_log(log_path: str, text: str) -> None:
    if not log_path:
        return
    ensure_parent_dir(log_path)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(text)


def _write_text(path: str, text: str) -> None:
    write_text_atomic(path, text or "")


def parse_file_blocks_fallback(text: str) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    if not text:
        return blocks
    for match in FILE_BLOCK_RE.finditer(text):
        path = normalize_path(match.group(1))
        content = match.group(2) or ""
        if not path:
            continue
        blocks.append({"path": path, "content": content.rstrip("\n") + "\n"})
    return blocks


def snapshot_files(paths: List[str], workspace: str) -> Dict[str, Optional[str]]:
    snapshot: Dict[str, Optional[str]] = {}
    for path in paths:
        if not path:
            continue
        full_path = os.path.join(workspace, path)
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as handle:
                    snapshot[path] = handle.read()
            except Exception:
                snapshot[path] = None
        else:
            snapshot[path] = None
    return snapshot


def restore_snapshot(
    snapshot: Dict[str, Optional[str]],
    workspace: str,
    log_path: str,
    *,
    events_path: str = "",
    refs: Optional[Dict[str, Any]] = None,
) -> None:
    emit_event(
        events_path,
        kind="action",
        actor="Director",
        name="rollback",
        refs=refs or {},
        summary=f"Rollback {len(snapshot)} file(s)",
        input={"files": list(snapshot.keys())},
    )
    for path, content in snapshot.items():
        if not path:
            continue
        full_path = os.path.join(workspace, path)
        if content is None:
            if os.path.isfile(full_path):
                try:
                    os.remove(full_path)
                    _append_log(log_path, f"[ROLLBACK] Removed {path}\n")
                except Exception as exc:
                    _append_log(log_path, f"[WARN] Failed to remove {path}: {exc}\n")
            continue
        try:
            ensure_parent_dir(full_path)
            with open(full_path, "w", encoding="utf-8") as handle:
                handle.write(content)
            _append_log(log_path, f"[ROLLBACK] Restored {path}\n")
        except Exception as exc:
            _append_log(log_path, f"[WARN] Failed to restore {path}: {exc}\n")
    emit_event(
        events_path,
        kind="observation",
        actor="Director",
        name="rollback",
        refs=refs or {},
        summary="Rollback completed",
        ok=True,
        output={"files": list(snapshot.keys())},
        truncation={"truncated": False},
    )


def assess_patch_risk(
    changed_files: List[str],
    snapshot: Dict[str, Optional[str]],
    workspace: str = "",
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    risk = 0
    reasons: List[str] = []
    
    # Factors
    files_changed_count = len(changed_files)
    lines_added = 0
    lines_removed = 0
    touches_build_system = False
    touches_security_sensitive = False
    touches_runtime_entry = False
    new_files: List[str] = []

    # Check for relaxed policy
    is_relaxed = False
    if policy and isinstance(policy.get("risk"), dict):
        relaxed_repos = policy["risk"].get("relaxed_repos")
        if isinstance(relaxed_repos, list) and workspace:
            norm_workspace = workspace.replace("\\", "/").lower()
            for repo in relaxed_repos:
                if str(repo).lower() in norm_workspace:
                    is_relaxed = True
                    break

    # Analyze files
    for path in changed_files:
        if not path:
            continue
        
        # New files
        old_content = snapshot.get(path)
        if old_content is None:
            new_files.append(path)
        
        # Read new content for diff
        new_content = ""
        full_path = os.path.join(workspace, path) if workspace else path
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    new_content = f.read()
            except Exception:
                pass
        
        # Calculate diff lines
        old_lines = (old_content or "").splitlines()
        new_lines = new_content.splitlines()
        diff = difflib.unified_diff(old_lines, new_lines, n=0)
        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1
        
        # Check specific types
        lower = path.lower()
        if lower.endswith(("package.json", "package-lock.json", "pyproject.toml", "requirements.txt", "tsconfig.json", "vite.config.ts", "vite.config.js", "webpack.config.js")):
            touches_build_system = True
        
        if any(part in lower for part in ("/protocol/", "/auth/", "/core/", "/security/", "/permissions/", "secret", "credential", "login", "token")):
            touches_security_sensitive = True
            
        if lower.endswith(("main.py", "app.py", "index.js", "server.js", "entrypoint.sh", "main.ts", "index.ts")):
            touches_runtime_entry = True

    # Calculate Score
    if files_changed_count >= 6:
        risk += 3
        reasons.append("Too many files changed")
    elif files_changed_count >= 3:
        risk += 2
        reasons.append("Multiple files changed")
    
    if new_files:
        risk += 1
        reasons.append("New files added")

    if lines_added > 200:
        risk += 2
        reasons.append("Large addition (>200 lines)")
    elif lines_added > 50:
        risk += 1
        reasons.append("Medium addition (>50 lines)")

    if touches_build_system:
        risk += 2
        reasons.append("Build system touched")
    
    if touches_security_sensitive:
        risk += 3
        reasons.append("Security sensitive files touched")
        
    if touches_runtime_entry:
        risk += 1
        reasons.append("Runtime entry touched")

    # Apply relaxation
    if is_relaxed:
        risk = max(0, risk - 2)
        reasons.append("Policy relaxed (trusted repo)")

    return {
        "score": risk,
        "reasons": reasons,
        "new_files": new_files,
        "factors": {
            "files_changed_count": files_changed_count,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "touches_build_system": touches_build_system,
            "touches_security_sensitive": touches_security_sensitive,
            "touches_runtime_entry": touches_runtime_entry,
            "test_coverage_delta": None,
        }
    }


def format_risk_summary(risk: Dict[str, Any]) -> str:
    if not risk:
        return "none"
    parts = [f"score={risk.get('score', 0)}"]
    reasons = risk.get("reasons") or []
    if reasons:
        parts.append("reasons=" + "; ".join(reasons))
    gate = risk.get("gate")
    threshold = risk.get("threshold")
    if gate:
        parts.append(f"gate={gate}")
    if threshold is not None:
        parts.append(f"threshold={threshold}")
    return "; ".join(parts)


def format_review_summary(review_payload: Dict[str, Any]) -> str:
    if not isinstance(review_payload, dict):
        return ""
    issues = review_payload.get("issues") or review_payload.get("findings")
    if not isinstance(issues, list) or not issues:
        return ""
    lines = []
    for item in issues[:6]:
        if isinstance(item, str) and item.strip():
            lines.append(f"- {item.strip()}")
    return "\n".join(lines)


def run_ollama_apply(state: Any, brief: str, files: List[str]) -> Dict[str, Any]:
    file_context = build_file_context(files, state.workspace_full)
    prompt = build_ollama_prompt(brief, file_context)
    emit_event(
        getattr(state, "events_full", ""),
        kind="action",
        actor="Director",
        name="ollama_apply",
        refs=_build_refs(state, "apply", files=files),
        summary="Ollama apply",
        input={"files": files, "brief_preview": _truncate_text(brief, 800)},
    )
    start_ts = time.time()
    output = invoke_ollama(prompt, state.model, state.workspace_full, state.show_output, state.timeout)
    _write_text(state.ollama_full, output)
    _append_log(state.log_full, "[OLLAMA]\n" + strip_ansi(output) + "\n")

    blocks = parse_file_blocks(output)
    if not blocks:
        blocks = parse_file_blocks_fallback(output)
    blocked_docs = [block for block in blocks if _is_docs_path(str(block.get("path") or ""))]
    if blocked_docs:
        _append_log(
            state.log_full,
            "[WARN] Director cannot modify docs/. Skipping blocks:\n"
            + "\n".join(f"- {block.get('path')}" for block in blocked_docs)
            + "\n",
        )
    blocks = [block for block in blocks if not _is_docs_path(str(block.get("path") or ""))]
    block_paths = [block.get("path") for block in blocks if block.get("path")]
    snapshot = snapshot_files(block_paths, state.workspace_full) if block_paths else {}
    changed_files = apply_file_blocks(blocks, state.workspace_full) if blocks else []

    if changed_files:
        _append_log(state.log_full, "[OLLAMA] Files changed:\n" + "\n".join(f"- {p}" for p in changed_files) + "\n")
    else:
        _append_log(state.log_full, "[OLLAMA] No files changed.\n")

    emit_event(
        getattr(state, "events_full", ""),
        kind="observation",
        actor="Director",
        name="ollama_apply",
        refs=_build_refs(state, "apply", files=changed_files or files),
        summary=f"Changed {len(changed_files)} file(s)",
        ok=True,
        output={
            "changed_files": changed_files,
            "block_count": len(blocks),
            "ollama_output_path": getattr(state, "ollama_full", ""),
        },
        truncation={"truncated": True, "reason": "output_path_only"},
        duration_ms=int((time.time() - start_ts) * 1000),
    )

    return {"output": output, "changed_files": changed_files, "snapshot": snapshot}


def run_qa(
    state: Any,
    plan_text: str,
    memory_summary: str,
    target_note: str,
    changed_files: List[str],
    planner_output: str,
    ollama_output: str,
    tool_results: str,
    reviewer_summary: str,
    patch_risk: str,
) -> str:
    prompt = build_qa_prompt(
        plan_text,
        memory_summary,
        target_note,
        changed_files,
        planner_output,
        ollama_output,
        tool_results,
        reviewer_summary,
        patch_risk,
        step=getattr(state, "current_director_iteration", 0),
        run_id=getattr(state, "current_run_id", ""),
        events_path=getattr(state, "events_full", ""),
    )
    emit_event(
        getattr(state, "events_full", ""),
        kind="action",
        actor="QA",
        name="qa_review",
        refs=_build_refs(state, "qa", files=changed_files),
        summary="QA review",
        input={"changed_files": changed_files},
    )
    start_ts = time.time()
    output = invoke_ollama(prompt, state.model, state.workspace_full, state.show_output, state.timeout)
    _write_text(state.qa_full, output)
    _append_log(state.log_full, "[QA]\n" + strip_ansi(output) + "\n")
    emit_event(
        getattr(state, "events_full", ""),
        kind="observation",
        actor="QA",
        name="qa_review",
        refs=_build_refs(state, "qa", files=changed_files),
        summary="QA output",
        ok=True,
        output={"qa_output_path": getattr(state, "qa_full", ""), "preview": _truncate_text(output, 800)},
        truncation={"truncated": True, "reason": "preview_only"},
        duration_ms=int((time.time() - start_ts) * 1000),
    )
    return output


def run_reviewer(
    state: Any,
    plan_text: str,
    memory_summary: str,
    target_note: str,
    changed_files: List[str],
    planner_output: str,
    ollama_output: str,
    tool_results: str,
    patch_risk: str,
) -> str:
    prompt = build_reviewer_prompt(
        plan_text,
        memory_summary,
        target_note,
        changed_files,
        planner_output,
        ollama_output,
        tool_results,
        patch_risk,
    )
    emit_event(
        getattr(state, "events_full", ""),
        kind="action",
        actor="Reviewer",
        name="reviewer_review",
        refs=_build_refs(state, "review", files=changed_files),
        summary="Reviewer pass",
        input={"changed_files": changed_files},
    )
    start_ts = time.time()
    output = invoke_ollama(prompt, state.model, state.workspace_full, state.show_output, state.timeout)
    _write_text(state.reviewer_full, output)
    _append_log(state.log_full, "[REVIEWER]\n" + strip_ansi(output) + "\n")
    emit_event(
        getattr(state, "events_full", ""),
        kind="observation",
        actor="Reviewer",
        name="reviewer_review",
        refs=_build_refs(state, "review", files=changed_files),
        summary="Reviewer output",
        ok=True,
        output={"reviewer_output_path": getattr(state, "reviewer_full", ""), "preview": _truncate_text(output, 800)},
        truncation={"truncated": True, "reason": "preview_only"},
        duration_ms=int((time.time() - start_ts) * 1000),
    )
    return output


def filter_npm_commands(commands: List[str]) -> List[str]:
    allowed: List[str] = []
    for cmd in commands:
        normalized = cmd.strip()
        if not normalized:
            continue
        tokens = normalize_npm_command(normalized)
        if tokens:
            allowed.append(normalized)
    return allowed


def normalize_npm_command(cmd: str) -> List[str]:
    if not cmd:
        return []
    normalized = cmd.strip()
    if not normalized:
        return []
    if "\n" in normalized or "\r" in normalized:
        return []
    for ch in ("&", "|", ";", ">", "<"):
        if ch in normalized:
            return []
    try:
        tokens = shlex.split(normalized, posix=os.name != "nt")
    except ValueError:
        return []
    if not tokens:
        return []
    exe_name = os.path.basename(tokens[0]).lower()
    if exe_name not in ("npm", "npm.cmd", "npm.exe"):
        return []
    if len(tokens) < 2:
        return []
    return tokens


def normalize_tool_command(cmd: str) -> List[str]:
    if not cmd:
        return []
    try:
        tokens = shlex.split(cmd, posix=os.name != "nt")
    except ValueError:
        return []
    if not tokens:
        return []
    exe_name = os.path.basename(tokens[0]).lower()
    allowed_exes = {"python", "py", os.path.basename(sys.executable).lower()}
    if exe_name not in allowed_exes:
        return []
    script_index = -1
    for idx in range(1, len(tokens)):
        if tokens[idx].lower().endswith("tools.py") or tokens[idx].lower().endswith("tools\\main.py") or tokens[idx].lower().endswith("tools/main.py"):
            script_index = idx
            break
    if script_index == -1:
        return []
    tools_path = os.path.join(PROJECT_ROOT, "tools", "main.py")
    return [sys.executable] + tokens[1:script_index] + [tools_path] + tokens[script_index + 1 :]


def filter_tool_commands(commands: List[str]) -> List[Dict[str, Any]]:
    allowed: List[Dict[str, Any]] = []
    for cmd in commands:
        normalized = cmd.strip()
        if not normalized:
            continue
        tokens = normalize_tool_command(normalized)
        if tokens:
            allowed.append({"command": normalized, "tokens": tokens})
    return allowed


def run_tool_commands(state: Any, commands: List[str], log_path: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if not commands:
        return results
    safe_commands = filter_tool_commands(commands)
    if not safe_commands:
        _append_log(log_path, "[WARN] No tool commands to run (filtered).\n")
        return results
    for item in safe_commands:
        cmd = item["command"]
        tokens = item["tokens"]
        emit_event(
            getattr(state, "events_full", ""),
            kind="action",
            actor="Tooling",
            name="run_tool_command",
            refs=_build_refs(state, "tool_exec"),
            summary=f"Run tool: {cmd}",
            input={"command": cmd},
        )
        _append_log(log_path, f"[CMD] Running tool: {cmd}\n")
        try:
            start_ts = time.time()
            result = subprocess.run(
                tokens,
                cwd=state.workspace_full,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=state.npm_timeout if state.npm_timeout > 0 else None,
                env=_build_utf8_env(),
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            _append_log(log_path, f"[CMD] Exit code: {result.returncode}\n")
            if stdout:
                _append_log(log_path, "[CMD] STDOUT:\n" + stdout + "\n")
            if stderr:
                _append_log(log_path, "[CMD] STDERR:\n" + stderr + "\n")
            
            # Parse standardized JSON output if available (tools.py wrapper usually outputs JSON if --json is passed, 
            # but here we are calling it without --json to capture stdout/stderr directly for logs.
            # However, since we are invoking tools.py via wrapper, the output is raw text unless we parse it.
            # Wait, tools.py prints raw text by default unless --json.
            # But the user wants 'duration_ms', 'artifacts' etc.
            # The subprocess above CALLS the wrapper script (which is python tools.py ...).
            # If we want structured data back, we should probably pass --json?
            # BUT: current implementation expects readable stdout for the LLM.
            # We can't change the output format to JSON without breaking the LLM's view of the output.
            # SO: We will stick to estimating duration here and leave artifacts empty unless we parse them.
            # Actually, `tools.py` prints normal stdout. 
            # So `result.stdout` is what the tool printed.
            # The `tools.py` modification I made affects what `tools.py` *returns* internally or prints if `--json`.
            # If I run `python tools.py ...`, it prints text.
            # If I want the metadata, I might need to run with --json OR rely on the wrapper to print metadata.
            # But `run_tool_commands` is calling `subprocess.run(tokens...)`.
            # `tokens` is `[python, tools.py, tool_name, args...]`.
            # The changes I made to `tools.py` only affect the internal `Result` dict and JSON output.
            # They do NOT affect the text output (except `_error_result` logic).
            # So `stdout` here is just the tool output.
            # I can't easily get `duration_ms` from the inner tool unless I parse it or measure it here.
            # Measuring `time.time() - start_ts` here is "good enough" for the event log.
            # `artifacts`: I can't get this unless the tool prints it.
            # `truncated`: I can't get this unless I parse "TRUNCATED: true" from stdout.
            
            truncated = "TRUNCATED: true" in stdout
            duration_ms = int((time.time() - start_ts) * 1000)
            
            emit_event(
                getattr(state, "events_full", ""),
                kind="observation",
                actor="Tooling",
                name="run_tool_command",
                refs=_build_refs(state, "tool_exec"),
                summary=f"tool exit={result.returncode}",
                ok=result.returncode == 0,
                output={
                    "command": cmd,
                    "returncode": result.returncode,
                    "stdout_preview": _truncate_text(stdout, 800),
                    "stderr_preview": _truncate_text(stderr, 800),
                    "artifacts": [], # Cannot extract easily without structured output
                },
                truncation={"truncated": truncated, "reason": "tool_output"},
                duration_ms=duration_ms,
            )
            results.append(
                {
                    "command": cmd,
                    "returncode": result.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "duration_ms": duration_ms,
                    "truncated": truncated,
                    "artifacts": [],
                }
            )
            if result.returncode != 0 and not state.continue_on_error:
                break
        except subprocess.TimeoutExpired:
            _append_log(log_path, f"[CMD] Timeout after {state.npm_timeout}s: {cmd}\n")
            emit_event(
                getattr(state, "events_full", ""),
                kind="observation",
                actor="Tooling",
                name="run_tool_command",
                refs=_build_refs(state, "tool_exec"),
                summary="tool timeout",
                ok=False,
                output={"command": cmd, "returncode": -1},
                truncation={"truncated": False},
                error="timeout",
            )
            results.append(
                {"command": cmd, "returncode": -1, "stdout": "", "stderr": "timeout"}
            )
            if not state.continue_on_error:
                break
        except Exception as exc:
            _append_log(log_path, f"[CMD] Failed to run '{cmd}': {exc}\n")
            emit_event(
                getattr(state, "events_full", ""),
                kind="observation",
                actor="Tooling",
                name="run_tool_command",
                refs=_build_refs(state, "tool_exec"),
                summary="tool error",
                ok=False,
                output={"command": cmd, "returncode": -1},
                truncation={"truncated": False},
                error=str(exc),
            )
            results.append(
                {"command": cmd, "returncode": -1, "stdout": "", "stderr": str(exc)}
            )
            if not state.continue_on_error:
                break
    return results


def format_tool_results(results: List[Dict[str, Any]], max_chars: int = 6000) -> str:
    if not results:
        return ""
    lines: List[str] = []
    total = 0
    for item in results:
        cmd = item.get("command") or ""
        code = item.get("returncode")
        stdout = item.get("stdout") or ""
        stderr = item.get("stderr") or ""
        header = f"COMMAND: {cmd}\nEXIT: {code}"
        body = []
        if stdout:
            body.append("STDOUT:\n" + stdout.strip())
        if stderr:
            body.append("STDERR:\n" + stderr.strip())
        block = header + ("\n" + "\n".join(body) if body else "")
        if total + len(block) > max_chars:
            lines.append("TRUNCATED: true")
            break
        lines.append(block)
        total += len(block)
    return "\n\n".join(lines).strip()


def run_npm_commands(state: Any, commands: List[str], log_path: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if not commands:
        return results
    safe_commands: List[Dict[str, Any]] = []
    for cmd in commands:
        normalized = cmd.strip()
        if not normalized:
            continue
        tokens = normalize_npm_command(normalized)
        if tokens:
            safe_commands.append({"command": normalized, "tokens": tokens})
    if not safe_commands:
        _append_log(log_path, "[WARN] No npm commands to run (filtered by safety rules).\n")
        return results
    for item in safe_commands:
        cmd = item["command"]
        tokens = item["tokens"]
        emit_event(
            getattr(state, "events_full", ""),
            kind="action",
            actor="Tooling",
            name="run_npm",
            refs=_build_refs(state, "tool_exec"),
            summary=f"Run npm: {cmd}",
            input={"command": cmd},
        )
        _append_log(log_path, f"[CMD] Running: {cmd}\n")
        try:
            start_ts = time.time()
            result = subprocess.run(
                tokens,
                cwd=state.workspace_full,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=state.npm_timeout if state.npm_timeout > 0 else None,
                env=_build_utf8_env(),
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            _append_log(log_path, f"[CMD] Exit code: {result.returncode}\n")
            if stdout:
                _append_log(log_path, "[CMD] STDOUT:\n" + stdout + "\n")
            if stderr:
                _append_log(log_path, "[CMD] STDERR:\n" + stderr + "\n")
            emit_event(
                getattr(state, "events_full", ""),
                kind="observation",
                actor="Tooling",
                name="run_npm",
                refs=_build_refs(state, "tool_exec"),
                summary=f"npm exit={result.returncode}",
                ok=result.returncode == 0,
                output={
                    "command": cmd,
                    "returncode": result.returncode,
                    "stdout_preview": _truncate_text(stdout, 800),
                    "stderr_preview": _truncate_text(stderr, 800),
                },
                truncation={"truncated": True, "reason": "preview_only"},
                duration_ms=int((time.time() - start_ts) * 1000),
            )
            results.append(
                {
                    "command": cmd,
                    "returncode": result.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
            if result.returncode != 0 and not state.continue_on_error:
                break
        except subprocess.TimeoutExpired:
            _append_log(log_path, f"[CMD] Timeout after {state.npm_timeout}s: {cmd}\n")
            emit_event(
                getattr(state, "events_full", ""),
                kind="observation",
                actor="Tooling",
                name="run_npm",
                refs=_build_refs(state, "tool_exec"),
                summary="npm timeout",
                ok=False,
                output={"command": cmd, "returncode": -1},
                truncation={"truncated": False},
                error="timeout",
            )
            results.append(
                {"command": cmd, "returncode": -1, "stdout": "", "stderr": "timeout"}
            )
            if not state.continue_on_error:
                break
        except Exception as exc:
            _append_log(log_path, f"[CMD] Failed to run '{cmd}': {exc}\n")
            emit_event(
                getattr(state, "events_full", ""),
                kind="observation",
                actor="Tooling",
                name="run_npm",
                refs=_build_refs(state, "tool_exec"),
                summary="npm error",
                ok=False,
                output={"command": cmd, "returncode": -1},
                truncation={"truncated": False},
                error=str(exc),
            )
            results.append(
                {"command": cmd, "returncode": -1, "stdout": "", "stderr": str(exc)}
            )
            if not state.continue_on_error:
                break
    return results
