import os
from typing import Dict, Any, List, Optional, Tuple, Deque
from collections import deque
from .utils import (
    MAX_FILE_BYTES, MAX_READ_LINES, MAX_READ_BYTES,
    truncate_line, format_slice, error_result,
    find_repo_root, ensure_within_root, relpath,
    read_text_file_utf8, detect_utf8_warning
)

_FILE_CACHE: Dict[str, Dict[str, Any]] = {}

def get_cached_lines(full_path: str) -> Optional[List[str]]:
    try:
        stat = os.stat(full_path)
    except Exception:
        return None
    if stat.st_size > MAX_FILE_BYTES:
        return None
    cached = _FILE_CACHE.get(full_path)
    if cached:
        if cached.get("mtime") == stat.st_mtime and cached.get("size") == stat.st_size:
            return cached.get("lines")
    try:
        text, warning = read_text_file_utf8(full_path)
        lines = text.splitlines()
    except Exception:
        return None
    _FILE_CACHE[full_path] = {
        "mtime": stat.st_mtime,
        "size": stat.st_size,
        "lines": lines,
        "encoding_warning": warning,
    }
    return lines


def get_cached_warning(full_path: str) -> Optional[str]:
    cached = _FILE_CACHE.get(full_path)
    if cached:
        return cached.get("encoding_warning")
    return None


def lines_to_content(lines: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    return [{"n": line_no, "t": text} for line_no, text in lines]

def read_lines_range(full_path: str, start: int, end: int) -> Tuple[List[Tuple[int, str]], bool, Optional[str]]:
    lines: List[Tuple[int, str]] = []
    truncated = False
    byte_budget = MAX_READ_BYTES
    warning = detect_utf8_warning(full_path)
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, start=1):
                if line_no < start:
                    continue
                if line_no > end:
                    break
                text = truncate_line(line.rstrip("\n\r"))
                if byte_budget <= 0 or len(lines) >= MAX_READ_LINES:
                    truncated = True
                    break
                byte_budget -= len(text.encode("utf-8", errors="ignore"))
                if byte_budget < 0:
                    truncated = True
                    break
                lines.append((line_no, text))
    except Exception:
        raise
    return lines, truncated, warning


def read_lines_range_cached(full_path: str, start: int, end: int) -> Tuple[List[Tuple[int, str]], bool, Optional[str]]:
    cached_lines = get_cached_lines(full_path)
    warning = get_cached_warning(full_path)
    if cached_lines is None:
        return read_lines_range(full_path, start, end)
    warning = get_cached_warning(full_path)
    lines: List[Tuple[int, str]] = []
    truncated = False
    byte_budget = MAX_READ_BYTES
    total_lines = len(cached_lines)
    last = min(end, total_lines)
    for idx in range(start - 1, last):
        text = truncate_line(cached_lines[idx])
        if byte_budget <= 0 or len(lines) >= MAX_READ_LINES:
            truncated = True
            break
        byte_budget -= len(text.encode("utf-8", errors="ignore"))
        if byte_budget < 0:
            truncated = True
            break
        lines.append((idx + 1, text))
    if end > last:
        truncated = truncated
    return lines, truncated, warning


def repo_read_slice(args: List[str], cwd: str, timeout: int) -> Dict[str, Any]:
    _ = timeout
    file_arg = ""
    start = None
    end = None
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--file", "-f") and i + 1 < len(args):
            file_arg = args[i + 1]
            i += 2
            continue
        if token in ("--start", "-s") and i + 1 < len(args):
            try:
                start = int(args[i + 1])
            except Exception:
                start = None
            i += 2
            continue
        if token in ("--end", "-e") and i + 1 < len(args):
            try:
                end = int(args[i + 1])
            except Exception:
                end = None
            i += 2
            continue
        if not file_arg:
            file_arg = token
        elif start is None:
            try:
                start = int(token)
            except Exception:
                start = None
        elif end is None:
            try:
                end = int(token)
            except Exception:
                end = None
        i += 1
    if not file_arg or start is None or end is None:
        return error_result("repo_read_slice", "Usage: repo_read_slice <file> <start> <end> (or --file/--start/--end)")
    if start < 1 or end < start:
        return error_result("repo_read_slice", "invalid line range")

    root = find_repo_root(cwd)
    try:
        full_path = ensure_within_root(root, file_arg)
    except ValueError as exc:
        return error_result("repo_read_slice", str(exc))
    if not os.path.isfile(full_path):
        return error_result("repo_read_slice", f"Not a file: {file_arg}")

    try:
        lines, truncated, warning = read_lines_range_cached(full_path, start, end)
    except Exception as exc:
        return error_result("repo_read_slice", str(exc), exit_code=1)

    rel = relpath(root, full_path)
    actual_end = lines[-1][0] if lines else start - 1
    output = format_slice(rel, start, max(end, actual_end), lines, truncated)
    return {
        "ok": True,
        "tool": "repo_read_slice",
        "file": rel,
        "start_line": start,
        "end_line": actual_end,
        "max_lines": MAX_READ_LINES,
        "truncated": truncated,
        "content": lines_to_content(lines),
        "encoding_warning": warning,
        "warnings": [warning] if warning else [],
        "error": None,
        "exit_code": 0,
        "stdout": output,
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "artifacts": [],
        "command": ["repo_read_slice"],
    }


def repo_read_around(args: List[str], cwd: str, timeout: int) -> Dict[str, Any]:
    file_arg = ""
    line_no = None
    radius = 80
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--file", "-f") and i + 1 < len(args):
            file_arg = args[i + 1]
            i += 2
            continue
        if token in ("--line", "-l") and i + 1 < len(args):
            try:
                line_no = int(args[i + 1])
            except Exception:
                line_no = None
            i += 2
            continue
        if token in ("--radius", "-r") and i + 1 < len(args):
            try:
                radius = int(args[i + 1])
            except Exception:
                radius = 80
            i += 2
            continue
        if not file_arg:
            file_arg = token
        elif line_no is None:
            try:
                line_no = int(token)
            except Exception:
                line_no = None
        elif i + 1 == len(args):
            try:
                radius = int(token)
            except Exception:
                radius = radius
        i += 1
    if not file_arg or line_no is None:
        return error_result("repo_read_around", "Usage: repo_read_around <file> <line> [radius] (or --file/--line/--radius)")
    start = max(1, line_no - radius)
    end = line_no + radius
    # Reuse repo_read_slice logic explicitly or call it? Calling it to avoid dup
    # But need to construct args. A bit messy. Better to refactor repo_read_slice core to be reusable.
    # Since I can't easily refactor the core out without more edits, I will just call repo_read_slice.
    result = repo_read_slice([file_arg, str(start), str(end)], cwd, timeout)
    result["tool"] = "repo_read_around"
    result["around_line"] = line_no
    result["radius"] = radius
    result["command"] = ["repo_read_around"]
    return result


def repo_read_head(args: List[str], cwd: str, timeout: int) -> Dict[str, Any]:
    file_arg = ""
    n = 60
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--file", "-f") and i + 1 < len(args):
            file_arg = args[i + 1]
            i += 2
            continue
        if token in ("--n", "-n") and i + 1 < len(args):
            try:
                n = int(args[i + 1])
            except Exception:
                n = 60
            i += 2
            continue
        if not file_arg:
            file_arg = token
        elif i + 1 == len(args):
            try:
                n = int(token)
            except Exception:
                n = n
        i += 1
    if not file_arg:
        return error_result("repo_read_head", "Usage: repo_read_head <file> [n] (or --file/--n)")
    requested = max(1, n)
    result = repo_read_slice([file_arg, "1", str(requested)], cwd, timeout)
    result["tool"] = "repo_read_head"
    result["head_lines"] = requested
    result["command"] = ["repo_read_head"]
    return result


def repo_read_tail(args: List[str], cwd: str, timeout: int) -> Dict[str, Any]:
    _ = timeout
    file_arg = ""
    n = 60
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--file", "-f") and i + 1 < len(args):
            file_arg = args[i + 1]
            i += 2
            continue
        if token in ("--n", "-n") and i + 1 < len(args):
            try:
                n = int(args[i + 1])
            except Exception:
                n = 60
            i += 2
            continue
        if not file_arg:
            file_arg = token
        elif i + 1 == len(args):
            try:
                n = int(token)
            except Exception:
                n = n
        i += 1
    if not file_arg:
        return error_result("repo_read_tail", "Usage: repo_read_tail <file> [n] (or --file/--n)")
    root = find_repo_root(cwd)
    try:
        full_path = ensure_within_root(root, file_arg)
    except ValueError as exc:
        return error_result("repo_read_tail", str(exc))
    if not os.path.isfile(full_path):
        return error_result("repo_read_tail", f"Not a file: {file_arg}")

    requested = max(1, n)
    truncated = False
    if requested > MAX_READ_LINES:
        requested = MAX_READ_LINES
        truncated = True

    cached_lines = get_cached_lines(full_path)
    warning = get_cached_warning(full_path)
    total = 0
    if cached_lines is not None:
        total = len(cached_lines)
        lines_list = [
            (idx + 1, truncate_line(cached_lines[idx]))
            for idx in range(max(0, total - requested), total)
        ]
    else:
        warning = detect_utf8_warning(full_path)
        q: Deque[Tuple[int, str]] = deque(maxlen=requested)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as handle:
                for total, line in enumerate(handle, start=1):
                    q.append((total, truncate_line(line.rstrip("\n\r"))))
        except Exception as exc:
            return error_result("repo_read_tail", str(exc), exit_code=1)
        lines_list = list(q)

    rel = relpath(root, full_path)
    if total == 0 or not lines_list:
        return {
            "ok": True,
            "tool": "repo_read_tail",
            "file": rel,
            "start_line": 0,
            "end_line": 0,
            "max_lines": MAX_READ_LINES,
            "tail_lines": requested,
            "truncated": truncated,
            "content": [],
            "encoding_warning": warning,
            "warnings": [warning] if warning else [],
            "error": None,
            "exit_code": 0,
            "stdout": "(empty)",
            "stderr": "",
            "duration": 0.0,
            "duration_ms": 0,
            "artifacts": [],
            "command": ["repo_read_tail"],
        }

    byte_budget = MAX_READ_BYTES
    kept_rev: List[Tuple[int, str]] = []
    for line_no, text in reversed(lines_list):
        line_bytes = len(text.encode("utf-8", errors="ignore"))
        if byte_budget - line_bytes < 0:
            truncated = True
            break
        byte_budget -= line_bytes
        kept_rev.append((line_no, text))
    kept = list(reversed(kept_rev))
    start = kept[0][0] if kept else lines_list[0][0]
    end = kept[-1][0] if kept else lines_list[-1][0]
    output = format_slice(rel, start, end, kept, truncated)
    return {
        "ok": True,
        "tool": "repo_read_tail",
        "file": rel,
        "start_line": start,
        "end_line": end,
        "max_lines": MAX_READ_LINES,
        "tail_lines": requested,
        "truncated": truncated,
        "content": lines_to_content(kept),
        "encoding_warning": warning,
        "warnings": [warning] if warning else [],
        "error": None,
        "exit_code": 0,
        "stdout": output,
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "artifacts": [],
        "command": ["repo_read_tail"],
    }
