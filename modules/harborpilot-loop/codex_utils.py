import os
import subprocess
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

    try:
        if os.name == "nt":
            cmd_str = subprocess.list2cmdline(cmd)
            cmd = ["cmd.exe", "/c", f"chcp 65001 >NUL & {cmd_str}"]
        subprocess.run(
            cmd,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            env=env,
            stdout=None if show_output else subprocess.DEVNULL,
            stderr=None if show_output else subprocess.DEVNULL,
            timeout=timeout if timeout > 0 else None,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ""

    return _read_codex_output(output_file)
