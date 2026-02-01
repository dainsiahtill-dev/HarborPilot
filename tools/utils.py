import os
import sys
from typing import Dict, Any, List, Tuple

Result = Dict[str, Any]
MAX_READ_LINES = 200
MAX_READ_BYTES = 64 * 1024
MAX_LINE_CHARS = 300
MAX_RG_RESULTS_DEFAULT = 50
MAX_RG_RESULTS_LIMIT = 200
MAX_TREE_ENTRIES = 2000
MAX_FILE_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
}

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

def build_utf8_env() -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    return env

def normalize_args(args: List[str]) -> List[str]:
    if args and args[0] == "--":
        return args[1:]
    return args

def find_repo_root(start: str) -> str:
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, ".git")) or os.path.isfile(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start)

def ensure_within_root(root: str, path: str) -> str:
    full = os.path.abspath(os.path.join(root, path)) if not os.path.isabs(path) else os.path.abspath(path)
    root = os.path.abspath(root)
    try:
        common = os.path.commonpath([root, full])
    except ValueError:
        raise ValueError(f"Path escapes repo root: {path}")
    if common != root:
        raise ValueError(f"Path escapes repo root: {path}")
    return full

def relpath(root: str, path: str) -> str:
    try:
        return os.path.relpath(path, root)
    except Exception:
        return path

def truncate_line(text: str) -> str:
    if len(text) <= MAX_LINE_CHARS:
        return text
    return text[:MAX_LINE_CHARS] + "..."

def format_slice(path: str, start: int, end: int, lines: List[Tuple[int, str]], truncated: bool) -> str:
    rel = path
    header = [
        f"FILE: {rel}",
        f"LINES: {start}-{end}",
        f"TRUNCATED: {'true' if truncated else 'false'}",
    ]
    body = [f"{line_no:>6} | {text}" for line_no, text in lines]
    return "\n".join(header + body)

def error_result(tool: str, message: str, exit_code: int = 2) -> Result:
    return {
        "ok": False,
        "tool": tool,
        "error": message,
        "exit_code": exit_code,
        "stdout": "",
        "stderr": message,
        "duration": 0.0,
        "duration_ms": 0,
        "truncated": False,
        "artifacts": [],
        "command": [tool],
    }

def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        return handle.read()
