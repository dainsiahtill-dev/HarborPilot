import json
import os
import re
import subprocess
import sys
import time
from typing import Dict, List, Optional, Union, Any
try:
    from .usage import UsageContext, TokenUsage, track_usage
except ImportError:
    from usage import UsageContext, TokenUsage, track_usage

from io_utils import ensure_codex_available, ensure_parent_dir, read_file_safe



def _env_flag(name: str, default: str = "") -> bool:
    value = str(os.environ.get(name, default)).strip().lower()
    return value in ("1", "true", "yes", "on")

def _decode_with_fallback(data: bytes) -> str:
    if not data:
        return ""
    try:
        text = data.decode("utf-8")
        return text
    except UnicodeDecodeError:
        pass
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    if text:
        bad = text.count("\ufffd")
        if bad / max(len(text), 1) < 0.02:
            return text
    for enc in ("utf-8-sig", "gbk", "cp936"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def _read_codex_output(path: str) -> str:
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        text = _decode_with_fallback(data)
        # Normalize output to UTF-8 for downstream consumers.
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        except Exception:
            pass
        return text
    except Exception:
        return read_file_safe(path)



def _extract_codex_json_output(raw_output: str) -> str:
    lines = (raw_output or '').splitlines()
    reasoning_parts: List[str] = []
    message_parts: List[str] = []
    for line in lines:
        trimmed = line.strip()
        if not trimmed or not trimmed.startswith("{"):
            continue
        try:
            payload = json.loads(trimmed)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        item = payload.get("item")
        if payload.get("type") == "item.completed" and isinstance(item, dict):
            item_type = str(item.get("type") or "")
            text = item.get("text")
            if not isinstance(text, str):
                continue
            if item_type in ("reasoning", "thought", "analysis"):
                reasoning_parts.append(text.strip())
            elif item_type in ("agent_message", "assistant_message", "message"):
                message_parts.append(text.strip())
    if not reasoning_parts and not message_parts:
        return raw_output
    output_chunks: List[str] = []
    if reasoning_parts:
        output_chunks.append("<thinking>" + "\n\n".join(reasoning_parts).strip() + "</thinking>")
    if message_parts:
        output_chunks.append("\n".join(message_parts).strip())
    return "\n".join(output_chunks).strip()

def build_codex_command(base_args: List[str], codex_path: str) -> List[str]:
    ext = os.path.splitext(codex_path)[1].lower()
    if ext == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", codex_path] + base_args
    if ext in (".cmd", ".bat"):
        return ["cmd.exe", "/c", codex_path] + base_args
    return [codex_path] + base_args


def _detect_encoding_violations(output: str) -> bool:
    if not output:
        return False
    patterns = [
        r"(?i)Get-Content\\b(?![^\r\n]*-Encoding)",
        r"(?i)Set-Content\\b(?![^\r\n]*-Encoding)",
        r"(?i)Add-Content\\b(?![^\r\n]*-Encoding)",
        r"(?i)Out-File\\b(?![^\r\n]*-Encoding)",
    ]
    return any(re.search(p, output) for p in patterns)


def _encoding_guardrail() -> str:
    return (
        "Encoding guardrail (HARD RULE): You MUST use UTF-8 for any PowerShell read/write.\n"
        "- Reads: Get-Content -Encoding utf8 (or Get-Content -Raw -Encoding utf8).\n"
        "- Writes: Set-Content -Encoding utf8, Add-Content -Encoding utf8, Out-File -Encoding utf8.\n"
        "- Do NOT set global PowerShell defaults; just include -Encoding utf8 in each command.\n"
        "- If you already ran a PowerShell command without UTF-8, re-run it immediately with the UTF-8 flags.\n"
        "- Prefer repo tools (python -m tools.main repo_read_* ) over PowerShell reads when available.\n"
    )


def _retry_prompt_for_encoding(prompt: str) -> str:
    return _encoding_guardrail() + "\n" + prompt


def invoke_codex(
    prompt: str,
    output_file: str,
    workspace: str,
    show_output: bool,
    full_auto: bool,
    dangerous: bool,
    profile: str,
    timeout: int,
    extra_env: Optional[Dict[str, str]] = None,
    usage_ctx: Optional[Union['UsageContext', Any]] = None,
    events_path: str = ""
) -> str:
    codex_path = ensure_codex_available()
    codex_model = str(os.environ.get("HARBORPILOT_CODEX_MODEL") or "gpt-5.2-codex").strip() or "gpt-5.2-codex"
    codex_sandbox = str(os.environ.get("HARBORPILOT_CODEX_SANDBOX") or "danger-full-access").strip() or "danger-full-access"
    codex_color = str(os.environ.get("HARBORPILOT_CODEX_COLOR") or "never").strip() or "never"
    codex_cd = str(os.environ.get("HARBORPILOT_CODEX_CD") or "").strip() or workspace
    codex_approvals = str(os.environ.get("HARBORPILOT_CODEX_APPROVALS") or "").strip()
    codex_output_schema = str(os.environ.get("HARBORPILOT_CODEX_OUTPUT_SCHEMA") or "").strip()
    codex_add_dirs = str(os.environ.get("HARBORPILOT_CODEX_ADD_DIRS") or "").strip()
    codex_config_overrides = str(os.environ.get("HARBORPILOT_CODEX_CONFIG") or "").strip()
    codex_use_oss = _env_flag("HARBORPILOT_CODEX_OSS", "0")
    codex_skip_git_check = _env_flag("HARBORPILOT_CODEX_SKIP_GIT_CHECK", "1")

    args = ["exec", "--cd", codex_cd, "--color", codex_color]
    if codex_skip_git_check:
        args.append("--skip-git-repo-check")
    args += ["--model", codex_model, "--sandbox", codex_sandbox, "--json"]
    if codex_approvals:
        args += ["--ask-for-approval", codex_approvals]
    if codex_use_oss:
        args.append("--oss")
    if codex_output_schema:
        args += ["--output-schema", codex_output_schema]
    if codex_add_dirs:
        for entry in re.split(r"[;,]", codex_add_dirs):
            entry = entry.strip()
            if entry:
                args += ["--add-dir", entry]
    if codex_config_overrides:
        for entry in re.split(r"[;,]", codex_config_overrides):
            entry = entry.strip()
            if entry:
                args += ["--config", entry]
    if dangerous:
        args.append("--dangerously-bypass-approvals-and-sandbox")
    elif full_auto:
        args.append("--full-auto")
    if profile:
        args.extend(["--profile", profile])

    cmd = build_codex_command(args, codex_path)
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    env.setdefault("LC_CTYPE", "en_US.UTF-8")
    if extra_env:
        env.update(extra_env)

    capture_stdout = True if "--json" in args else str(os.environ.get("HARBORPILOT_CODEX_CAPTURE_STDOUT", "0")).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
        "",
    )

    def _run_once(run_prompt: str) -> str:
        run_cmd = cmd + [run_prompt]
        if os.name == "nt":
            cmd_str = subprocess.list2cmdline(run_cmd)
            run_cmd = ["cmd.exe", "/c", f"chcp 65001 >NUL & {cmd_str}"]
        if capture_stdout:
            result = subprocess.run(
                run_cmd,
                input=None,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=workspace,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout if timeout > 0 else None,
                check=False,
            )
            output = result.stdout or ""
            if output and "--json" in args:
                output = _extract_codex_json_output(output)
            if output and (show_output or not sys.stdout.isatty()):
                try:
                    sys.stdout.write(output)
                    sys.stdout.flush()
                except Exception:
                    pass
            return output
        subprocess.run(
            run_cmd,
            input=None,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            env=env,
            stdout=None,
            stderr=None,
            timeout=timeout if timeout > 0 else None,
            check=False,
        )
        return ""

    try:
        use_guard = str(os.environ.get("HARBORPILOT_CODEX_UTF8_GUARD", "1")).strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
            "",
        )
        run_prompt = (_encoding_guardrail() + "\n" + prompt) if use_guard else prompt

        start_time = time.time()
        output = _run_once(run_prompt)
        duration_ms = int((time.time() - start_time) * 1000)

        if capture_stdout and _detect_encoding_violations(output):
            output = _run_once(_retry_prompt_for_encoding(prompt))
            duration_ms = int((time.time() - start_time) * 1000)

        if usage_ctx and events_path:
            p_chars = len(run_prompt)
            c_chars = len(output)
            p_tokens = p_chars // 4
            c_tokens = c_chars // 4
            usage_obj = TokenUsage(
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=p_tokens + c_tokens,
                estimated=True,
                prompt_chars=p_chars,
                completion_chars=c_chars
            )
            track_usage(events_path, usage_ctx, "codex-cli", "codex", usage_obj, duration_ms, ok=bool(output))

    except subprocess.TimeoutExpired:
        if usage_ctx and events_path:
            usage_obj = TokenUsage(
                prompt_tokens=len(prompt)//4, completion_tokens=0, total_tokens=len(prompt)//4, estimated=True,
                prompt_chars=len(prompt), completion_chars=0
            )
            track_usage(events_path, usage_ctx, "codex-cli", "codex", usage_obj, 0, ok=False, error="Timeout")
        return ""

    return output

