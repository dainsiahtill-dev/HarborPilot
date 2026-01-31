import argparse
import fnmatch
import importlib
import json
import os
import re
import subprocess
import sys
import time
from collections import deque
from typing import Any, Dict, List, Callable, Iterable, Tuple, Optional


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

_FILE_CACHE: Dict[str, Dict[str, Any]] = {}


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


def _get_cached_lines(full_path: str) -> Optional[List[str]]:
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
        with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.read().splitlines()
    except Exception:
        return None
    _FILE_CACHE[full_path] = {"mtime": stat.st_mtime, "size": stat.st_size, "lines": lines}
    return lines


def _normalize_args(args: List[str]) -> List[str]:
    if args and args[0] == "--":
        return args[1:]
    return args


def _find_repo_root(start: str) -> str:
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, ".git")) or os.path.isfile(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start)


def _ensure_within_root(root: str, path: str) -> str:
    full = os.path.abspath(os.path.join(root, path)) if not os.path.isabs(path) else os.path.abspath(path)
    root = os.path.abspath(root)
    try:
        common = os.path.commonpath([root, full])
    except ValueError:
        raise ValueError(f"Path escapes repo root: {path}")
    if common != root:
        raise ValueError(f"Path escapes repo root: {path}")
    return full


def _relpath(root: str, path: str) -> str:
    try:
        return os.path.relpath(path, root)
    except Exception:
        return path


def _truncate_line(text: str) -> str:
    if len(text) <= MAX_LINE_CHARS:
        return text
    return text[:MAX_LINE_CHARS] + "..."


def _lines_to_content(lines: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    return [{"n": line_no, "t": text} for line_no, text in lines]


def _format_slice(path: str, start: int, end: int, lines: List[Tuple[int, str]], truncated: bool) -> str:
    rel = path
    header = [
        f"FILE: {rel}",
        f"LINES: {start}-{end}",
        f"TRUNCATED: {'true' if truncated else 'false'}",
    ]
    body = [f"{line_no:>6} | {text}" for line_no, text in lines]
    return "\n".join(header + body)


def _error_result(tool: str, message: str, exit_code: int = 2) -> Result:
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


def _read_lines_range(full_path: str, start: int, end: int) -> Tuple[List[Tuple[int, str]], bool]:
    lines: List[Tuple[int, str]] = []
    truncated = False
    byte_budget = MAX_READ_BYTES
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
            for line_no, line in enumerate(handle, start=1):
                if line_no < start:
                    continue
                if line_no > end:
                    break
                text = _truncate_line(line.rstrip("\n\r"))
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
    return lines, truncated


def _read_lines_range_cached(full_path: str, start: int, end: int) -> Tuple[List[Tuple[int, str]], bool]:
    cached_lines = _get_cached_lines(full_path)
    if cached_lines is None:
        return _read_lines_range(full_path, start, end)
    lines: List[Tuple[int, str]] = []
    truncated = False
    byte_budget = MAX_READ_BYTES
    total_lines = len(cached_lines)
    last = min(end, total_lines)
    for idx in range(start - 1, last):
        text = _truncate_line(cached_lines[idx])
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
    return lines, truncated


def _run_command(cmd: List[str], cwd: str, timeout: int) -> Result:
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout if timeout > 0 else None,
            check=False,
            env=_build_utf8_env(),
        )
        duration = time.time() - start
        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "duration": duration,
            "duration_ms": int(duration * 1000),
            "truncated": False,
            "artifacts": [],
            "command": cmd,
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - start
        return {
            "ok": False,
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": "Timeout expired.",
            "duration": duration,
            "duration_ms": int(duration * 1000),
            "truncated": False,
            "artifacts": [],
            "command": cmd,
        }


def ruff_check(args: List[str], cwd: str, timeout: int) -> Result:
    return _run_command(["ruff", "check"] + args, cwd, timeout)


def ruff_format(args: List[str], cwd: str, timeout: int) -> Result:
    return _run_command(["ruff", "format"] + args, cwd, timeout)


def pytest_run(args: List[str], cwd: str, timeout: int) -> Result:
    return _run_command(["pytest"] + args, cwd, timeout)


def coverage_run(args: List[str], cwd: str, timeout: int) -> Result:
    cmd = ["coverage", "run", "-m", "pytest"]
    if args:
        cmd = ["coverage"] + args
    return _run_command(cmd, cwd, timeout)


def coverage_report(args: List[str], cwd: str, timeout: int) -> Result:
    return _run_command(["coverage", "report", "-m"] + args, cwd, timeout)


def mypy_run(args: List[str], cwd: str, timeout: int) -> Result:
    return _run_command(["mypy"] + args, cwd, timeout)


def jsonschema_validate(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if len(args) < 2:
        return {
            "ok": False,
            "exit_code": 2,
            "stdout": "",
            "stderr": "Usage: jsonschema_validate <schema.json> <data.json>",
            "duration": 0.0,
            "command": ["jsonschema_validate"] + args,
        }
    schema_path = os.path.join(cwd, args[0]) if not os.path.isabs(args[0]) else args[0]
    data_path = os.path.join(cwd, args[1]) if not os.path.isabs(args[1]) else args[1]
    start = time.time()
    try:
        import jsonschema  # type: ignore
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": 3,
            "stdout": "",
            "stderr": f"jsonschema import failed: {exc}",
            "duration": time.time() - start,
            "command": ["jsonschema_validate"] + args,
        }
    try:
        with open(schema_path, "r", encoding="utf-8") as handle:
            schema = json.load(handle)
        with open(data_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        jsonschema.validate(instance=data, schema=schema)
        return {
            "ok": True,
            "exit_code": 0,
            "stdout": "OK",
            "stderr": "",
            "duration": time.time() - start,
            "command": ["jsonschema_validate"] + args,
        }
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "duration": time.time() - start,
            "command": ["jsonschema_validate"] + args,
        }


def pydantic_validate(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if len(args) < 2:
        return {
            "ok": False,
            "exit_code": 2,
            "stdout": "",
            "stderr": "Usage: pydantic_validate <module:ModelClass> <data.json>",
            "duration": 0.0,
            "command": ["pydantic_validate"] + args,
        }
    model_ref = args[0]
    data_path = os.path.join(cwd, args[1]) if not os.path.isabs(args[1]) else args[1]
    start = time.time()
    try:
        module_name, class_name = model_ref.split(":", 1)
        module = importlib.import_module(module_name)
        model = getattr(module, class_name)
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": 3,
            "stdout": "",
            "stderr": f"Model import failed: {exc}",
            "duration": time.time() - start,
            "command": ["pydantic_validate"] + args,
        }
    try:
        with open(data_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if hasattr(model, "model_validate"):
            model.model_validate(data)
        elif hasattr(model, "parse_obj"):
            model.parse_obj(data)
        else:
            raise RuntimeError("Model has no pydantic validation method.")
        return {
            "ok": True,
            "exit_code": 0,
            "stdout": "OK",
            "stderr": "",
            "duration": time.time() - start,
            "command": ["pydantic_validate"] + args,
        }
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "duration": time.time() - start,
            "command": ["pydantic_validate"] + args,
        }


def _get_ts_parser(language: str):
    try:
        from tree_sitter_languages import get_parser  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"tree_sitter_languages import failed: {exc}")
    return get_parser(language)


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        return handle.read()


def _ts_node_text(content: bytes, node) -> str:
    return content[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")


def _ts_name_node(node):
    name = node.child_by_field_name("name")
    if name is not None:
        return name
    prop = node.child_by_field_name("property")
    if prop is not None:
        return prop
    for child in node.children:
        if child.type == "identifier":
            return child
    return None


def _ts_extract_name(content: bytes, node) -> str:
    name_node = _ts_name_node(node)
    if name_node is None:
        return ""
    return _ts_node_text(content, name_node)


def treesitter_outline(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if len(args) < 2:
        return {
            "ok": False,
            "exit_code": 2,
            "stdout": "",
            "stderr": "Usage: treesitter_outline <language> <file>",
            "duration": 0.0,
            "command": ["treesitter_outline"] + args,
        }
    language = args[0]
    root = _find_repo_root(cwd)
    file_path = os.path.join(cwd, args[1]) if not os.path.isabs(args[1]) else args[1]
    try:
        file_path = _ensure_within_root(root, file_path)
    except ValueError as exc:
        return _error_result("treesitter_outline", str(exc), exit_code=2)
    start = time.time()
    try:
        parser = _get_ts_parser(language)
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": 3,
            "stdout": "",
            "stderr": str(exc),
            "duration": time.time() - start,
            "duration_ms": int((time.time() - start) * 1000),
            "truncated": False,
            "artifacts": [],
            "command": ["treesitter_outline"] + args,
        }
    try:
        with open(file_path, "rb") as handle:
            content = handle.read()
        tree = parser.parse(content)
        root = tree.root_node
        lines = []
        for child in root.children:
            start_row, start_col = child.start_point
            end_row, end_col = child.end_point
            name = _ts_extract_name(content, child)
            label = f"{child.type}"
            if name:
                label += f" {name}"
            lines.append(f"{label} {start_row + 1}:{start_col + 1}-{end_row + 1}:{end_col + 1}")
        output = "\n".join(lines) if lines else "(no top-level nodes)"
        return {
            "ok": True,
            "tool": "treesitter_outline",
            "file": file_path,
            "language": language,
            "entries": lines,
            "exit_code": 0,
            "stdout": output,
            "stderr": "",
            "duration": time.time() - start,
            "duration_ms": int((time.time() - start) * 1000),
            "truncated": False,
            "artifacts": [],
            "command": ["treesitter_outline"] + args,
        }
    except Exception as exc:
        return {
            "ok": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "duration": time.time() - start,
            "duration_ms": int((time.time() - start) * 1000),
            "truncated": False,
            "artifacts": [],
            "command": ["treesitter_outline"] + args,
        }


def _ts_iter_nodes(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        for child in reversed(node.children):
            stack.append(child)


def _ts_find_symbol_nodes(content: bytes, root, symbol: str, kind: str) -> List[Dict[str, Any]]:
    symbol = symbol or ""
    wanted = {kind} if kind else {"function", "class", "method"}
    nodes: List[Dict[str, Any]] = []
    for node in _ts_iter_nodes(root):
        node_type = node.type
        is_class = node_type in {"class_definition", "class_declaration"}
        is_function = node_type in {"function_definition", "function_declaration"}
        is_method = node_type == "method_definition"
        if is_class and "class" not in wanted:
            continue
        if is_function and "function" not in wanted:
            continue
        if is_method and "method" not in wanted:
            continue
        if not (is_class or is_function or is_method):
            continue
        name = _ts_extract_name(content, node)
        if symbol and name != symbol:
            continue
        nodes.append({
            "name": name,
            "node_type": node_type,
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
            "start_byte": node.start_byte,
            "end_byte": node.end_byte,
        })
    return nodes


def treesitter_find_symbol(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if len(args) < 3:
        return _error_result("treesitter_find_symbol", "Usage: treesitter_find_symbol <language> <file> <symbol> [--kind function|class|method] [--max N]")
    language = args[0]
    root = _find_repo_root(cwd)
    file_path = os.path.join(cwd, args[1]) if not os.path.isabs(args[1]) else args[1]
    try:
        file_path = _ensure_within_root(root, file_path)
    except ValueError as exc:
        return _error_result("treesitter_find_symbol", str(exc), exit_code=2)
    symbol = args[2]
    kind = ""
    max_results = 20
    i = 3
    while i < len(args):
        token = args[i]
        if token in ("--kind", "-k") and i + 1 < len(args):
            kind = str(args[i + 1])
            i += 2
            continue
        if token in ("--max", "-m") and i + 1 < len(args):
            try:
                max_results = int(args[i + 1])
            except Exception:
                max_results = 20
            i += 2
            continue
        i += 1
    try:
        parser = _get_ts_parser(language)
    except Exception as exc:
        return _error_result("treesitter_find_symbol", str(exc), exit_code=3)
    try:
        with open(file_path, "rb") as handle:
            content = handle.read()
        tree = parser.parse(content)
        matches = _ts_find_symbol_nodes(content, tree.root_node, symbol, kind)
        truncated = False
        if len(matches) > max_results:
            matches = matches[:max_results]
            truncated = True
        return {
            "ok": True,
            "tool": "treesitter_find_symbol",
            "file": file_path,
            "language": language,
            "symbol": symbol,
            "kind": kind,
            "matches": matches,
            "truncated": truncated,
            "error": None,
            "exit_code": 0,
            "stdout": json.dumps(matches, ensure_ascii=False, indent=2),
            "stderr": "",
            "duration": 0.0,
            "duration_ms": 0,
            "truncated": truncated,
            "artifacts": [],
            "command": ["treesitter_find_symbol"] + args,
        }
    except Exception as exc:
        return _error_result("treesitter_find_symbol", str(exc), exit_code=1)


def _ts_apply_replacement(file_path: str, start_byte: int, end_byte: int, replacement: str) -> None:
    with open(file_path, "rb") as handle:
        content = handle.read()
    if start_byte < 0 or end_byte < start_byte or end_byte > len(content):
        raise ValueError("Invalid byte range for replacement.")
    new_bytes = content[:start_byte] + replacement.encode("utf-8") + content[end_byte:]
    tmp_path = f"{file_path}.tmp"
    try:
        with open(tmp_path, "wb") as handle:
            handle.write(new_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, file_path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def treesitter_replace_node(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if len(args) < 3:
        return _error_result("treesitter_replace_node", "Usage: treesitter_replace_node <language> <file> <symbol> [--kind function|class|method] [--index N] [--text <code>] [--text-file path]")
    language = args[0]
    root = _find_repo_root(cwd)
    file_path = os.path.join(cwd, args[1]) if not os.path.isabs(args[1]) else args[1]
    try:
        file_path = _ensure_within_root(root, file_path)
    except ValueError as exc:
        return _error_result("treesitter_replace_node", str(exc), exit_code=2)
    symbol = args[2]
    kind = ""
    index = 0
    text_value = ""
    text_file = ""
    i = 3
    while i < len(args):
        token = args[i]
        if token in ("--kind", "-k") and i + 1 < len(args):
            kind = str(args[i + 1])
            i += 2
            continue
        if token in ("--index", "-i") and i + 1 < len(args):
            index = int(args[i + 1])
            i += 2
            continue
        if token in ("--text", "-t") and i + 1 < len(args):
            text_value = args[i + 1]
            i += 2
            continue
        if token in ("--text-file", "-f") and i + 1 < len(args):
            text_file = args[i + 1]
            i += 2
            continue
        i += 1
    if not text_value and text_file:
        text_path = os.path.join(cwd, text_file) if not os.path.isabs(text_file) else text_file
        try:
            text_path = _ensure_within_root(root, text_path)
        except ValueError as exc:
            return _error_result("treesitter_replace_node", str(exc), exit_code=2)
        text_value = _read_text_file(text_path)
    if text_value is None:
        text_value = ""
    try:
        parser = _get_ts_parser(language)
    except Exception as exc:
        return _error_result("treesitter_replace_node", str(exc), exit_code=3)
    try:
        with open(file_path, "rb") as handle:
            content = handle.read()
        tree = parser.parse(content)
        matches = _ts_find_symbol_nodes(content, tree.root_node, symbol, kind)
        if not matches or index >= len(matches):
            return _error_result("treesitter_replace_node", "symbol not found", exit_code=4)
        target = matches[index]
        _ts_apply_replacement(file_path, target["start_byte"], target["end_byte"], text_value)
        return {
            "ok": True,
            "tool": "treesitter_replace_node",
            "file": file_path,
            "language": language,
            "symbol": symbol,
            "kind": kind,
            "index": index,
            "start_line": target["start_line"],
            "end_line": target["end_line"],
            "exit_code": 0,
            "stdout": "OK",
            "stderr": "",
            "duration": 0.0,
            "duration_ms": 0,
            "truncated": False,
            "artifacts": [],
            "command": ["treesitter_replace_node"] + args,
        }
    except Exception as exc:
        return _error_result("treesitter_replace_node", str(exc), exit_code=1)


def _indent_lines(text: str, indent: str) -> str:
    lines = text.splitlines()
    if not lines:
        return indent
    indented = [indent + line if line.strip() else line for line in lines]
    return "\\n".join(indented)


def treesitter_insert_method(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if len(args) < 4:
        return _error_result("treesitter_insert_method", "Usage: treesitter_insert_method <language> <file> <class_name> <method_text> [--text-file path]")
    language = args[0]
    root = _find_repo_root(cwd)
    file_path = os.path.join(cwd, args[1]) if not os.path.isabs(args[1]) else args[1]
    try:
        file_path = _ensure_within_root(root, file_path)
    except ValueError as exc:
        return _error_result("treesitter_insert_method", str(exc), exit_code=2)
    class_name = args[2]
    method_text = args[3]
    text_file = ""
    i = 4
    while i < len(args):
        token = args[i]
        if token in ("--text-file", "-f") and i + 1 < len(args):
            text_file = args[i + 1]
            i += 2
            continue
        i += 1
    if text_file:
        text_path = os.path.join(cwd, text_file) if not os.path.isabs(text_file) else text_file
        try:
            text_path = _ensure_within_root(root, text_path)
        except ValueError as exc:
            return _error_result("treesitter_insert_method", str(exc), exit_code=2)
        method_text = _read_text_file(text_path)
    try:
        parser = _get_ts_parser(language)
    except Exception as exc:
        return _error_result("treesitter_insert_method", str(exc), exit_code=3)
    try:
        with open(file_path, "rb") as handle:
            content = handle.read()
        tree = parser.parse(content)
        matches = _ts_find_symbol_nodes(content, tree.root_node, class_name, "class")
        if not matches:
            return _error_result("treesitter_insert_method", "class not found", exit_code=4)
        target = matches[0]
        class_node = None
        for node in _ts_iter_nodes(tree.root_node):
            if node.start_byte == target["start_byte"] and node.end_byte == target["end_byte"]:
                class_node = node
                break
        if class_node is None:
            return _error_result("treesitter_insert_method", "class node not resolved", exit_code=4)
        if language in ("python", "py"):
            body = class_node.child_by_field_name("body")
            if body is None:
                return _error_result("treesitter_insert_method", "class body not found", exit_code=4)
            insert_byte = body.end_byte
            class_line = content[:class_node.start_byte].splitlines()[-1]
            class_indent = re.match(rb"\\s*", class_line).group(0).decode("utf-8", errors="ignore")
            method_indent = class_indent + "    "
            block = "\\n" + _indent_lines(method_text, method_indent).rstrip() + "\\n"
            _ts_apply_replacement(file_path, insert_byte, insert_byte, block)
        else:
            body = class_node.child_by_field_name("body")
            if body is None:
                return _error_result("treesitter_insert_method", "class body not found", exit_code=4)
            insert_byte = body.end_byte - 1
            class_line = content[:class_node.start_byte].splitlines()[-1]
            class_indent = re.match(rb"\\s*", class_line).group(0).decode("utf-8", errors="ignore")
            method_indent = class_indent + "  "
            block = "\\n" + _indent_lines(method_text, method_indent).rstrip() + "\\n" + class_indent
            _ts_apply_replacement(file_path, insert_byte, insert_byte, block)
        return {
            "ok": True,
            "tool": "treesitter_insert_method",
            "file": file_path,
            "language": language,
            "class": class_name,
            "exit_code": 0,
            "stdout": "OK",
            "stderr": "",
            "duration": 0.0,
            "duration_ms": 0,
            "truncated": False,
            "artifacts": [],
            "command": ["treesitter_insert_method"] + args,
        }
    except Exception as exc:
        return _error_result("treesitter_insert_method", str(exc), exit_code=1)


def treesitter_rename_symbol(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if len(args) < 4:
        return _error_result("treesitter_rename_symbol", "Usage: treesitter_rename_symbol <language> <file> <symbol> <new_name> [--kind function|class|method]")
    language = args[0]
    root = _find_repo_root(cwd)
    file_path = os.path.join(cwd, args[1]) if not os.path.isabs(args[1]) else args[1]
    try:
        file_path = _ensure_within_root(root, file_path)
    except ValueError as exc:
        return _error_result("treesitter_rename_symbol", str(exc), exit_code=2)
    symbol = args[2]
    new_name = args[3]
    kind = ""
    i = 4
    while i < len(args):
        token = args[i]
        if token in ("--kind", "-k") and i + 1 < len(args):
            kind = str(args[i + 1])
            i += 2
            continue
        i += 1
    try:
        parser = _get_ts_parser(language)
    except Exception as exc:
        return _error_result("treesitter_rename_symbol", str(exc), exit_code=3)
    try:
        with open(file_path, "rb") as handle:
            content = handle.read()
        tree = parser.parse(content)
        matches = _ts_find_symbol_nodes(content, tree.root_node, symbol, kind)
        if not matches:
            return _error_result("treesitter_rename_symbol", "symbol not found", exit_code=4)
        target = matches[0]
        target_node = None
        for node in _ts_iter_nodes(tree.root_node):
            if node.start_byte == target["start_byte"] and node.end_byte == target["end_byte"]:
                target_node = node
                break
        if target_node is None:
            return _error_result("treesitter_rename_symbol", "symbol node not resolved", exit_code=4)
        name_node = _ts_name_node(target_node)
        if name_node is None:
            return _error_result("treesitter_rename_symbol", "name node not found", exit_code=4)
        _ts_apply_replacement(file_path, name_node.start_byte, name_node.end_byte, new_name)
        return {
            "ok": True,
            "tool": "treesitter_rename_symbol",
            "file": file_path,
            "language": language,
            "symbol": symbol,
            "new_name": new_name,
            "kind": kind,
            "exit_code": 0,
            "stdout": "OK",
            "stderr": "",
            "duration": 0.0,
            "duration_ms": 0,
            "truncated": False,
            "artifacts": [],
            "command": ["treesitter_rename_symbol"] + args,
        }
    except Exception as exc:
        return _error_result("treesitter_rename_symbol", str(exc), exit_code=1)


def repo_tree(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    path = "."
    depth = 3
    max_entries = MAX_TREE_ENTRIES
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--depth", "-d") and i + 1 < len(args):
            try:
                depth = max(0, int(args[i + 1]))
            except Exception:
                depth = 3
            i += 2
            continue
        if token in ("--max", "--max-entries") and i + 1 < len(args):
            try:
                max_entries = max(1, int(args[i + 1]))
            except Exception:
                max_entries = MAX_TREE_ENTRIES
            i += 2
            continue
        if not token.startswith("--") and path == ".":
            path = token
        i += 1

    root = _find_repo_root(cwd)
    try:
        target = _ensure_within_root(root, path)
    except ValueError as exc:
        return {
            "ok": False,
            "tool": "repo_tree",
            "path": path,
            "entries": [],
            "truncated": False,
            "error": str(exc),
            "exit_code": 2,
            "stdout": "",
            "stderr": str(exc),
            "duration": 0.0,
            "duration_ms": 0,
            "truncated": False,
            "artifacts": [],
            "command": ["repo_tree"],
        }
    if not os.path.isdir(target):
        err = f"Not a directory: {path}"
        return {
            "ok": False,
            "tool": "repo_tree",
            "path": path,
            "entries": [],
            "truncated": False,
            "error": err,
            "exit_code": 2,
            "stdout": "",
            "stderr": err,
            "duration": 0.0,
            "duration_ms": 0,
            "truncated": False,
            "artifacts": [],
            "command": ["repo_tree"],
        }

    lines: List[str] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(target):
        rel_dir = os.path.relpath(dirpath, target)
        depth_level = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if depth_level > depth:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        indent = "  " * depth_level
        if rel_dir != ".":
            lines.append(f"{indent}{os.path.basename(dirpath)}/")
        for name in sorted(filenames):
            lines.append(f"{indent}  {name}")
            if len(lines) >= max_entries:
                truncated = True
                break
        if truncated:
            break

    if truncated:
        lines.append("TRUNCATED: true")
    output = "\n".join(lines) if lines else "(empty)"
    return {
        "ok": True,
        "tool": "repo_tree",
        "path": _relpath(root, target),
        "depth": depth,
        "max_entries": max_entries,
        "entries": lines,
        "truncated": truncated,
        "error": None,
        "exit_code": 0,
        "stdout": output,
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "truncated": truncated,
        "artifacts": [],
        "command": ["repo_tree"],
    }


def _iter_files(root: str, paths: List[str], glob_pat: str) -> Iterable[str]:
    for raw in paths:
        try:
            target = _ensure_within_root(root, raw)
        except ValueError:
            continue
        if os.path.isfile(target):
            if glob_pat and not fnmatch.fnmatch(os.path.basename(target), glob_pat):
                continue
            yield target
        elif os.path.isdir(target):
            for dirpath, dirnames, filenames in os.walk(target):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for name in filenames:
                    if glob_pat and not fnmatch.fnmatch(name, glob_pat):
                        continue
                    yield os.path.join(dirpath, name)


def repo_rg(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if not args:
        return _error_result("repo_rg", "Usage: repo_rg <pattern> [paths...] [--max N] [--glob pattern]")
    pattern = args[0]
    max_results = MAX_RG_RESULTS_DEFAULT
    glob_pat = ""
    paths: List[str] = []
    i = 1
    while i < len(args):
        token = args[i]
        if token in ("--max", "-m") and i + 1 < len(args):
            try:
                max_results = int(args[i + 1])
            except Exception:
                max_results = MAX_RG_RESULTS_DEFAULT
            i += 2
            continue
        if token in ("--glob", "-g") and i + 1 < len(args):
            glob_pat = args[i + 1]
            i += 2
            continue
        if not token.startswith("--"):
            paths.append(token)
        i += 1
    max_results = max(1, min(max_results, MAX_RG_RESULTS_LIMIT))
    if not paths:
        paths = ["."]

    root = _find_repo_root(cwd)
    pattern_mode = "regex"
    regex_error = ""
    try:
        regex = re.compile(pattern)
    except Exception as exc:
        pattern_mode = "literal"
        regex_error = f"{exc}"
        try:
            regex = re.compile(re.escape(pattern))
        except Exception:
            return _error_result("repo_rg", f"Invalid pattern: {exc}")

    hits: List[Dict[str, Any]] = []
    lines_out: List[str] = []
    truncated = False
    for file_path in _iter_files(root, paths, glob_pat):
        try:
            if os.path.getsize(file_path) > MAX_FILE_BYTES:
                continue
        except Exception:
            continue
        try:
            cached_lines = _get_cached_lines(file_path)
            if cached_lines is not None:
                for line_no, line in enumerate(cached_lines, start=1):
                    match = regex.search(line)
                    if match:
                        snippet = _truncate_line(line)
                        rel = _relpath(root, file_path)
                        col = match.start() + 1
                        hits.append({"file": rel, "line": line_no, "col": col, "text": snippet})
                        lines_out.append(f"{rel}:{line_no}:{col}: {snippet}")
                        if len(hits) >= max_results:
                            truncated = True
                            break
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                    for line_no, line in enumerate(handle, start=1):
                        match = regex.search(line)
                        if match:
                            snippet = _truncate_line(line.rstrip("\n\r"))
                            rel = _relpath(root, file_path)
                            col = match.start() + 1
                            hits.append({"file": rel, "line": line_no, "col": col, "text": snippet})
                            lines_out.append(f"{rel}:{line_no}:{col}: {snippet}")
                            if len(hits) >= max_results:
                                truncated = True
                                break
            if truncated:
                break
        except Exception:
            continue

    if truncated:
        lines_out.append("TRUNCATED: true")
    output = "\n".join(lines_out) if lines_out else "(no matches)"
    return {
        "ok": True,
        "tool": "repo_rg",
        "pattern": pattern,
        "pattern_mode": pattern_mode,
        "regex_error": regex_error or None,
        "paths": paths,
        "max_results": max_results,
        "hits": hits,
        "truncated": truncated,
        "error": None,
        "exit_code": 0,
        "stdout": output,
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "truncated": truncated,
        "artifacts": [],
        "command": ["repo_rg"],
    }


def repo_read_slice(args: List[str], cwd: str, timeout: int) -> Result:
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
        return _error_result("repo_read_slice", "Usage: repo_read_slice <file> <start> <end> (or --file/--start/--end)")
    if start < 1 or end < start:
        return _error_result("repo_read_slice", "invalid line range")

    root = _find_repo_root(cwd)
    try:
        full_path = _ensure_within_root(root, file_arg)
    except ValueError as exc:
        return _error_result("repo_read_slice", str(exc))
    if not os.path.isfile(full_path):
        return _error_result("repo_read_slice", f"Not a file: {file_arg}")

    try:
        lines, truncated = _read_lines_range_cached(full_path, start, end)
    except Exception as exc:
        return _error_result("repo_read_slice", str(exc), exit_code=1)

    rel = _relpath(root, full_path)
    actual_end = lines[-1][0] if lines else start - 1
    output = _format_slice(rel, start, max(end, actual_end), lines, truncated)
    return {
        "ok": True,
        "tool": "repo_read_slice",
        "file": rel,
        "start_line": start,
        "end_line": actual_end,
        "max_lines": MAX_READ_LINES,
        "truncated": truncated,
        "content": _lines_to_content(lines),
        "error": None,
        "exit_code": 0,
        "stdout": output,
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "truncated": truncated,
        "artifacts": [],
        "command": ["repo_read_slice"],
    }


def repo_read_around(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
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
        return _error_result("repo_read_around", "Usage: repo_read_around <file> <line> [radius] (or --file/--line/--radius)")
    start = max(1, line_no - radius)
    end = line_no + radius
    result = repo_read_slice([file_arg, str(start), str(end)], cwd, timeout)
    result["tool"] = "repo_read_around"
    result["around_line"] = line_no
    result["radius"] = radius
    result["command"] = ["repo_read_around"]
    return result


def repo_read_head(args: List[str], cwd: str, timeout: int) -> Result:
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
        return _error_result("repo_read_head", "Usage: repo_read_head <file> [n] (or --file/--n)")
    requested = max(1, n)
    result = repo_read_slice([file_arg, "1", str(requested)], cwd, timeout)
    result["tool"] = "repo_read_head"
    result["head_lines"] = requested
    result["command"] = ["repo_read_head"]
    return result


def repo_read_tail(args: List[str], cwd: str, timeout: int) -> Result:
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
        return _error_result("repo_read_tail", "Usage: repo_read_tail <file> [n] (or --file/--n)")
    root = _find_repo_root(cwd)
    try:
        full_path = _ensure_within_root(root, file_arg)
    except ValueError as exc:
        return _error_result("repo_read_tail", str(exc))
    if not os.path.isfile(full_path):
        return _error_result("repo_read_tail", f"Not a file: {file_arg}")

    requested = max(1, n)
    truncated = False
    if requested > MAX_READ_LINES:
        requested = MAX_READ_LINES
        truncated = True

    cached_lines = _get_cached_lines(full_path)
    total = 0
    if cached_lines is not None:
        total = len(cached_lines)
        lines_list = [
            (idx + 1, _truncate_line(cached_lines[idx]))
            for idx in range(max(0, total - requested), total)
        ]
    else:
        q: deque[Tuple[int, str]] = deque(maxlen=requested)
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
                for total, line in enumerate(handle, start=1):
                    q.append((total, _truncate_line(line.rstrip("\n\r"))))
        except Exception as exc:
            return _error_result("repo_read_tail", str(exc), exit_code=1)
        lines_list = list(q)

    rel = _relpath(root, full_path)
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
            "error": None,
            "exit_code": 0,
            "stdout": "(empty)",
            "stderr": "",
            "duration": 0.0,
            "duration_ms": 0,
            "truncated": truncated,
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
    output = _format_slice(rel, start, end, kept, truncated)
    return {
        "ok": True,
        "tool": "repo_read_tail",
        "file": rel,
        "start_line": start,
        "end_line": end,
        "max_lines": MAX_READ_LINES,
        "tail_lines": requested,
        "truncated": truncated,
        "content": _lines_to_content(kept),
        "error": None,
        "exit_code": 0,
        "stdout": output,
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "truncated": truncated,
        "artifacts": [],
        "command": ["repo_read_tail"],
    }


def repo_diff(args: List[str], cwd: str, timeout: int) -> Result:
    _ = args
    root = _find_repo_root(cwd)
    cmd = ["git", "diff"]
    if args and args[0] in ("--stat", "-s"):
        cmd = ["git", "diff", "--stat"]
    result = _run_command(cmd, root, timeout)
    result["tool"] = "repo_diff"
    result["error"] = None if result.get("ok") else (result.get("stderr") or "command failed")
    return result


def pytest_target(args: List[str], cwd: str, timeout: int) -> Result:
    return _run_command(["pytest"] + args, cwd, timeout)


def python_run(args: List[str], cwd: str, timeout: int) -> Result:
    if not args:
        return _error_result("python_run", "Usage: python_run (--module mod | --file path) [-- arg ...]")
    module = ""
    file_path = ""
    extra: List[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--module", "-m") and i + 1 < len(args):
            module = args[i + 1]
            i += 2
            continue
        if token in ("--file", "-f") and i + 1 < len(args):
            file_path = args[i + 1]
            i += 2
            continue
        if token == "--":
            extra = args[i + 1 :]
            break
        i += 1
    if module:
        return _run_command([sys.executable, "-m", module] + extra, cwd, timeout)
    if file_path:
        full = os.path.join(cwd, file_path) if not os.path.isabs(file_path) else file_path
        return _run_command([sys.executable, full] + extra, cwd, timeout)
    return _error_result("python_run", "Usage: python_run (--module mod | --file path) [-- arg ...]")


def node_run(args: List[str], cwd: str, timeout: int) -> Result:
    if not args:
        return _error_result("node_run", "Usage: node_run <file> [-- arg ...]")
    file_path = args[0]
    extra: List[str] = []
    if "--" in args:
        sep = args.index("--")
        file_path = args[0]
        extra = args[sep + 1 :]
    full = os.path.join(cwd, file_path) if not os.path.isabs(file_path) else file_path
    return _run_command(["node", full] + extra, cwd, timeout)


def repo_symbols_index(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    max_results = 500
    glob_pat = ""
    paths: List[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--max", "-m") and i + 1 < len(args):
            try:
                max_results = int(args[i + 1])
            except Exception:
                max_results = 500
            i += 2
            continue
        if token in ("--glob", "-g") and i + 1 < len(args):
            glob_pat = args[i + 1]
            i += 2
            continue
        if not token.startswith("--"):
            paths.append(token)
        i += 1
    if not paths:
        paths = ["."]
    root = _find_repo_root(cwd)
    entries: List[Dict[str, Any]] = []
    truncated = False
    py_re = re.compile(r"^\\s*(def|class)\\s+([A-Za-z_][A-Za-z0-9_]*)")
    js_re = re.compile(r"^\\s*export\\s+(function|class|const|let|var|interface|type)\\s+([A-Za-z_][A-Za-z0-9_]*)")
    for file_path in _iter_files(root, paths, glob_pat):
        if not any(file_path.endswith(ext) for ext in (".py", ".js", ".jsx", ".ts", ".tsx")):
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                for line_no, line in enumerate(handle, start=1):
                    match = py_re.match(line)
                    if match:
                        entries.append({
                            "symbol": match.group(2),
                            "kind": match.group(1),
                            "file": _relpath(root, file_path),
                            "line": line_no,
                        })
                    match = js_re.match(line)
                    if match:
                        entries.append({
                            "symbol": match.group(2),
                            "kind": match.group(1),
                            "file": _relpath(root, file_path),
                            "line": line_no,
                        })
                    if len(entries) >= max_results:
                        truncated = True
                        break
            if truncated:
                break
        except Exception:
            continue
    return {
        "ok": True,
        "tool": "repo_symbols_index",
        "paths": paths,
        "max_results": max_results,
        "entries": entries,
        "truncated": truncated,
        "error": None,
        "exit_code": 0,
        "stdout": json.dumps(entries, ensure_ascii=False, indent=2),
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "truncated": truncated,
        "artifacts": [],
        "command": ["repo_symbols_index"],
    }


def repo_import_graph(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    glob_pat = ""
    paths: List[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--glob", "-g") and i + 1 < len(args):
            glob_pat = args[i + 1]
            i += 2
            continue
        if not token.startswith("--"):
            paths.append(token)
        i += 1
    if not paths:
        paths = ["."]
    root = _find_repo_root(cwd)
    edges: List[Dict[str, Any]] = []
    py_re = re.compile(r"^\\s*(?:from|import)\\s+([A-Za-z0-9_\\.]+)")
    js_re = re.compile(r"^\\s*import\\s+.*?from\\s+[\"']([^\"']+)[\"']")
    req_re = re.compile(r"require\\(\\s*[\"']([^\"']+)[\"']\\s*\\)")
    for file_path in _iter_files(root, paths, glob_pat):
        if not any(file_path.endswith(ext) for ext in (".py", ".js", ".jsx", ".ts", ".tsx")):
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    match = py_re.match(line)
                    if match:
                        edges.append({"file": _relpath(root, file_path), "import": match.group(1)})
                    match = js_re.match(line)
                    if match:
                        edges.append({"file": _relpath(root, file_path), "import": match.group(1)})
                    match = req_re.search(line)
                    if match:
                        edges.append({"file": _relpath(root, file_path), "import": match.group(1)})
        except Exception:
            continue
    return {
        "ok": True,
        "tool": "repo_import_graph",
        "paths": paths,
        "edges": edges,
        "exit_code": 0,
        "stdout": json.dumps(edges, ensure_ascii=False, indent=2),
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "truncated": False,
        "artifacts": [],
        "command": ["repo_import_graph"],
    }


def repo_api_surface(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    glob_pat = ""
    paths: List[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--glob", "-g") and i + 1 < len(args):
            glob_pat = args[i + 1]
            i += 2
            continue
        if not token.startswith("--"):
            paths.append(token)
        i += 1
    if not paths:
        paths = ["."]
    root = _find_repo_root(cwd)
    exports: List[Dict[str, Any]] = []
    py_re = re.compile(r"^\\s*(def|class)\\s+([A-Za-z_][A-Za-z0-9_]*)")
    js_re = re.compile(r"^\\s*export\\s+(function|class|const|let|var|interface|type)\\s+([A-Za-z_][A-Za-z0-9_]*)")
    for file_path in _iter_files(root, paths, glob_pat):
        if not any(file_path.endswith(ext) for ext in (".py", ".js", ".jsx", ".ts", ".tsx")):
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                for line_no, line in enumerate(handle, start=1):
                    match = js_re.match(line)
                    if match:
                        exports.append({"symbol": match.group(2), "kind": match.group(1), "file": _relpath(root, file_path), "line": line_no})
                    if file_path.endswith(".py"):
                        match = py_re.match(line)
                        if match:
                            exports.append({"symbol": match.group(2), "kind": match.group(1), "file": _relpath(root, file_path), "line": line_no})
        except Exception:
            continue
    return {
        "ok": True,
        "tool": "repo_api_surface",
        "paths": paths,
        "exports": exports,
        "exit_code": 0,
        "stdout": json.dumps(exports, ensure_ascii=False, indent=2),
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "truncated": False,
        "artifacts": [],
        "command": ["repo_api_surface"],
    }


def _hash_embedding(text: str, dim: int = 256) -> List[float]:
    vec = [0.0] * dim
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", text.lower()):
        idx = (hash(token) % dim + dim) % dim
        vec[idx] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    if norm:
        vec = [v / norm for v in vec]
    return vec


def lancedb_index_code(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    collection = "code_chunks"
    db_path = os.path.join(cwd, ".harborpilot", "ollama", "lancedb")
    glob_pat = ""
    max_files = 200
    chunk_lines = 80
    paths: List[str] = []
    i = 0
    while i < len(args):
        token = args[i]
        if token in ("--collection", "-c") and i + 1 < len(args):
            collection = args[i + 1]
            i += 2
            continue
        if token in ("--db", "--db-path") and i + 1 < len(args):
            db_path = args[i + 1]
            i += 2
            continue
        if token in ("--glob", "-g") and i + 1 < len(args):
            glob_pat = args[i + 1]
            i += 2
            continue
        if token in ("--max-files", "-m") and i + 1 < len(args):
            try:
                max_files = int(args[i + 1])
            except Exception:
                max_files = 200
            i += 2
            continue
        if token in ("--chunk-lines", "-l") and i + 1 < len(args):
            try:
                chunk_lines = int(args[i + 1])
            except Exception:
                chunk_lines = 80
            i += 2
            continue
        if not token.startswith("--"):
            paths.append(token)
        i += 1
    if not paths:
        paths = ["."]
    try:
        import lancedb  # type: ignore
    except Exception as exc:
        return _error_result("lancedb_index_code", f"lancedb import failed: {exc}", exit_code=3)
    root = _find_repo_root(cwd)
    db = lancedb.connect(db_path)
    try:
        table = db.open_table(collection)
    except Exception:
        table = db.create_table(collection, data=[{"vector": [0.0] * 256, "text": "", "file": "", "start_line": 0, "end_line": 0}], mode="overwrite")
        table.delete("start_line = 0")
    records = []
    files_processed = 0
    for file_path in _iter_files(root, paths, glob_pat):
        if files_processed >= max_files:
            break
        if not any(file_path.endswith(ext) for ext in (".py", ".js", ".jsx", ".ts", ".tsx")):
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                lines = handle.read().splitlines()
        except Exception:
            continue
        files_processed += 1
        for start_line in range(1, len(lines) + 1, chunk_lines):
            end_line = min(len(lines), start_line + chunk_lines - 1)
            chunk = "\\n".join(lines[start_line - 1 : end_line])
            vec = _hash_embedding(chunk)
            records.append({
                "vector": vec,
                "text": chunk,
                "file": _relpath(root, file_path),
                "start_line": start_line,
                "end_line": end_line,
            })
    if records:
        table.add(records)
    return {
        "ok": True,
        "tool": "lancedb_index_code",
        "collection": collection,
        "db_path": db_path,
        "records": len(records),
        "exit_code": 0,
        "stdout": f"indexed {len(records)} chunks",
        "stderr": "",
        "duration": 0.0,
        "command": ["lancedb_index_code"],
    }


def lancedb_query_code(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if not args:
        return _error_result("lancedb_query_code", "Usage: lancedb_query_code <query> [--collection name] [--db path] [--k N]")
    query = args[0]
    collection = "code_chunks"
    db_path = os.path.join(cwd, ".harborpilot", "ollama", "lancedb")
    k = 5
    env_k = os.environ.get("HARBORPILOT_RAG_TOPK")
    if env_k:
        try:
            k = int(env_k)
        except Exception:
            k = 5
    i = 1
    while i < len(args):
        token = args[i]
        if token in ("--collection", "-c") and i + 1 < len(args):
            collection = args[i + 1]
            i += 2
            continue
        if token in ("--db", "--db-path") and i + 1 < len(args):
            db_path = args[i + 1]
            i += 2
            continue
        if token in ("--k", "-k") and i + 1 < len(args):
            try:
                k = int(args[i + 1])
            except Exception:
                k = 5
            i += 2
            continue
        i += 1
    try:
        import lancedb  # type: ignore
    except Exception as exc:
        return _error_result("lancedb_query_code", f"lancedb import failed: {exc}", exit_code=3)
    db = lancedb.connect(db_path)
    try:
        table = db.open_table(collection)
    except Exception as exc:
        return _error_result("lancedb_query_code", f"open table failed: {exc}", exit_code=4)
    vec = _hash_embedding(query)
    try:
        results = table.search(vec).limit(k).to_list()
    except Exception as exc:
        return _error_result("lancedb_query_code", f"query failed: {exc}", exit_code=5)
    return {
        "ok": True,
        "tool": "lancedb_query_code",
        "collection": collection,
        "db_path": db_path,
        "query": query,
        "results": results,
        "exit_code": 0,
        "stdout": json.dumps(results, ensure_ascii=False, indent=2),
        "stderr": "",
        "duration": 0.0,
        "command": ["lancedb_query_code"],
    }


def _policy_err(errors: List[str], message: str) -> None:
    errors.append(message)


def policy_validate(args: List[str], cwd: str, timeout: int) -> Result:
    _ = timeout
    if not args:
        return _error_result("policy_validate", "Usage: policy_validate <policy.json>")
    path = args[0]
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    if not os.path.isfile(path):
        return _error_result("policy_validate", f"Not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        return _error_result("policy_validate", f"Invalid JSON: {exc}")
    if not isinstance(payload, dict):
        return _error_result("policy_validate", "Policy root must be an object")

    errors: List[str] = []
    version = payload.get("version")
    if version is not None:
        try:
            version_int = int(version)
            if version_int <= 0:
                _policy_err(errors, "version must be >= 1")
        except Exception:
            _policy_err(errors, "version must be an integer")

    def check_bool(obj: Dict[str, Any], key: str, path: str) -> None:
        if key not in obj:
            return
        value = obj.get(key)
        if isinstance(value, bool):
            return
        if isinstance(value, str) and value.strip().lower() in ("true", "false", "1", "0", "yes", "no", "on", "off"):
            return
        _policy_err(errors, f"{path} must be boolean")

    def check_int(obj: Dict[str, Any], key: str, path: str, min_value: int = 0) -> None:
        if key not in obj:
            return
        value = obj.get(key)
        try:
            value_int = int(value)
        except Exception:
            _policy_err(errors, f"{path} must be integer")
            return
        if value_int < min_value:
            _policy_err(errors, f"{path} must be >= {min_value}")

    def check_float(obj: Dict[str, Any], key: str, path: str, min_value: float = 0.0) -> None:
        if key not in obj:
            return
        value = obj.get(key)
        try:
            value_float = float(value)
        except Exception:
            _policy_err(errors, f"{path} must be number")
            return
        if value_float < min_value:
            _policy_err(errors, f"{path} must be >= {min_value}")

    repair = payload.get("repair")
    if isinstance(repair, dict):
        check_bool(repair, "auto_repair", "repair.auto_repair")
        check_int(repair, "max_attempts", "repair.max_attempts", 0)
        check_bool(repair, "reviewer_enabled", "repair.reviewer_enabled")
        check_int(repair, "reviewer_rounds", "repair.reviewer_rounds", 0)
        check_bool(repair, "rollback_on_fail", "repair.rollback_on_fail")

    risk = payload.get("risk")
    if isinstance(risk, dict):
        check_int(risk, "block_threshold", "risk.block_threshold", 0)
        check_bool(risk, "rollback_on_block", "risk.rollback_on_block")

    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        check_bool(evidence, "write_enabled", "evidence.write_enabled")
        if "verbosity" in evidence:
            if evidence.get("verbosity") not in ("summary", "full"):
                _policy_err(errors, "evidence.verbosity must be 'summary' or 'full'")

    rag = payload.get("rag")
    if isinstance(rag, dict):
        check_bool(rag, "enabled", "rag.enabled")
        check_int(rag, "topk", "rag.topk", 0)

    memory = payload.get("memory")
    if isinstance(memory, dict):
        check_bool(memory, "enabled", "memory.enabled")
        if "backend" in memory:
            if memory.get("backend") not in ("lancedb", "file", "both", "none"):
                _policy_err(errors, "memory.backend must be 'lancedb', 'file', 'both', or 'none'")
        check_bool(memory, "store_enabled", "memory.store_enabled")
        check_int(memory, "store_every", "memory.store_every", 1)
        check_bool(memory, "store_on_accept", "memory.store_on_accept")

    io_cfg = payload.get("io")
    if isinstance(io_cfg, dict):
        check_bool(io_cfg, "jsonl_buffered", "io.jsonl_buffered")
        check_float(io_cfg, "flush_interval_sec", "io.flush_interval_sec", 0.1)
        check_int(io_cfg, "flush_batch", "io.flush_batch", 1)
        check_int(io_cfg, "max_buffer", "io.max_buffer", 10)

    budgets = payload.get("budgets")
    if isinstance(budgets, dict):
        check_int(budgets, "max_tool_rounds", "budgets.max_tool_rounds", 1)
        check_int(budgets, "max_total_lines_read", "budgets.max_total_lines_read", 200)

    qa = payload.get("qa")
    if isinstance(qa, dict):
        check_bool(qa, "default_tools", "qa.default_tools")

    context = payload.get("context")
    if isinstance(context, dict):
        check_int(context, "pm_tasks_max_chars", "context.pm_tasks_max_chars", 0)
        check_int(context, "known_files_max_chars", "context.known_files_max_chars", 0)
        check_int(context, "last_result_max_chars", "context.last_result_max_chars", 0)
        check_int(context, "tool_output_max_chars", "context.tool_output_max_chars", 0)
        check_int(context, "planner_output_max_chars", "context.planner_output_max_chars", 0)
        check_int(context, "ollama_output_max_chars", "context.ollama_output_max_chars", 0)

    ok = not errors
    return {
        "ok": ok,
        "tool": "policy_validate",
        "path": path,
        "errors": errors,
        "exit_code": 0 if ok else 2,
        "stdout": json.dumps({"ok": ok, "errors": errors}, ensure_ascii=False, indent=2),
        "stderr": "",
        "duration": 0.0,
        "duration_ms": 0,
        "truncated": False,
        "artifacts": [],
        "command": ["policy_validate"],
    }


TOOLS: Dict[str, Callable[[List[str], str, int], Result]] = {
    "ruff_check": ruff_check,
    "ruff_format": ruff_format,
    "pytest": pytest_run,
    "coverage_run": coverage_run,
    "coverage_report": coverage_report,
    "mypy": mypy_run,
    "jsonschema_validate": jsonschema_validate,
    "pydantic_validate": pydantic_validate,
    "treesitter_outline": treesitter_outline,
    "treesitter_find_symbol": treesitter_find_symbol,
    "treesitter_replace_node": treesitter_replace_node,
    "treesitter_insert_method": treesitter_insert_method,
    "treesitter_rename_symbol": treesitter_rename_symbol,
    "repo_tree": repo_tree,
    "repo_rg": repo_rg,
    "repo_read_slice": repo_read_slice,
    "repo_read_around": repo_read_around,
    "repo_read_head": repo_read_head,
    "repo_read_tail": repo_read_tail,
    "repo_diff": repo_diff,
    "pytest_target": pytest_target,
    "python_run": python_run,
    "node_run": node_run,
    "repo_symbols_index": repo_symbols_index,
    "repo_import_graph": repo_import_graph,
    "repo_api_surface": repo_api_surface,
    "lancedb_index_code": lancedb_index_code,
    "lancedb_query_code": lancedb_query_code,
    "policy_validate": policy_validate,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="HarborPilot tools CLI")
    parser.add_argument("tool", nargs="?", help="Tool name or 'list'")
    parser.add_argument("tool_args", nargs=argparse.REMAINDER, help="Arguments for the tool")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--timeout", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    tool_name = (args.tool or "").strip()
    if not tool_name or tool_name == "list":
        for name in sorted(TOOLS.keys()):
            print(name)
        return 0

    tool = TOOLS.get(tool_name)
    if not tool:
        print(f"Unknown tool: {tool_name}", file=sys.stderr)
        return 2

    tool_args = _normalize_args(args.tool_args)
    result = tool(tool_args, args.cwd, args.timeout)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result.get("stdout"):
            sys.stdout.write(result["stdout"])
            if not result["stdout"].endswith("\n"):
                sys.stdout.write("\n")
        if result.get("stderr"):
            sys.stderr.write(result["stderr"])
            if not result["stderr"].endswith("\n"):
                sys.stderr.write("\n")
    return int(result.get("exit_code", 1))


if __name__ == "__main__":
    raise SystemExit(main())
