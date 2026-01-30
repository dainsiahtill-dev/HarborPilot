import os
import re
import subprocess
import sys
from typing import Dict, List, Optional

from io_utils import ensure_codex_available, ensure_parent_dir, read_file_safe


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
        "- Prefer repo tools (python tools.py repo_read_* ) over PowerShell reads when available.\n"
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
) -> str:
    codex_path = ensure_codex_available()
    if not output_file:
        output_file = os.path.join(workspace, "state", "ollama", "CODEX_LAST_MESSAGE.md")
    ensure_parent_dir(output_file)

    args = ["exec", "--cd", workspace, "--output-last-message", output_file, "--color", "never"]
    if dangerous:
        args.append("--dangerously-bypass-approvals-and-sandbox")
    elif full_auto:
        args.append("--full-auto")
    if profile:
        args.extend(["--profile", profile])
    args.append("-")

    cmd = build_codex_command(args, codex_path)
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    env.setdefault("LC_CTYPE", "en_US.UTF-8")
    if extra_env:
        env.update(extra_env)

    capture_stdout = str(os.environ.get("HARBORPILOT_CODEX_CAPTURE_STDOUT", "0")).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
        "",
    )

    def _run_once(run_prompt: str) -> str:
        if os.name == "nt":
            cmd_str = subprocess.list2cmdline(cmd)
            run_cmd = ["cmd.exe", "/c", f"chcp 65001 >NUL & {cmd_str}"]
        else:
            run_cmd = cmd
        if capture_stdout:
            result = subprocess.run(
                run_cmd,
                input=run_prompt,
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
            if output and (show_output or not sys.stdout.isatty()):
                try:
                    sys.stdout.write(output)
                    sys.stdout.flush()
                except Exception:
                    pass
            return output
        subprocess.run(
            run_cmd,
            input=run_prompt,
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
        output = _run_once(run_prompt)
        if capture_stdout and _detect_encoding_violations(output):
            output = _run_once(_retry_prompt_for_encoding(prompt))
    except subprocess.TimeoutExpired:
        return ""

    return _read_codex_output(output_file)
