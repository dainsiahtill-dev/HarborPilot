import copy
import json
import os
import re
import shlex
import subprocess
import time
import sys
from typing import Any, Dict, List, Optional, Tuple

from io_utils import emit_event


DEFAULT_READ_RADIUS = 80
MAX_TOOL_READ_LINES = 200
MAX_EVENT_CONTENT_LINES = 40


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


def safe_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _append_log(log_path: str, text: str) -> None:
    if not log_path:
        return
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(text)


def _build_refs(state: Any, phase: str) -> Dict[str, Any]:
    return {
        "task_id": getattr(state, "current_task_id", "") or None,
        "task_fingerprint": getattr(state, "current_task_fingerprint", "") or None,
        "run_id": getattr(state, "current_run_id", "") or None,
        "pm_iteration": getattr(state, "current_pm_iteration", None),
        "director_iteration": getattr(state, "current_director_iteration", None),
        "phase": phase,
    }


def _compact_tool_output(tool: str, output: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    truncation: Dict[str, Any] = {"truncated": False}
    if not isinstance(output, dict):
        return {"raw": str(output)}, truncation
    compact = dict(output)
    if "content" in compact and isinstance(compact["content"], list):
        content = compact["content"]
        if len(content) > MAX_EVENT_CONTENT_LINES:
            compact["content"] = content[:MAX_EVENT_CONTENT_LINES]
            truncation = {
                "truncated": True,
                "reason": "content_lines",
                "original_lines": len(content),
                "kept_lines": MAX_EVENT_CONTENT_LINES,
            }
    if compact.get("truncated") and not truncation.get("truncated"):
        truncation = {"truncated": True, "reason": "tool_truncated"}
    return compact, truncation


def extract_tool_plan(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    plan = payload.get("tool_plan")
    if not isinstance(plan, list):
        return []
    steps: List[Dict[str, Any]] = []
    for item in plan:
        if isinstance(item, dict):
            tool = item.get("tool")
            if isinstance(tool, str) and tool.strip():
                steps.append(item)
            continue
        if isinstance(item, str) and item.strip():
            parsed = parse_tool_plan_item(item)
            if isinstance(parsed, dict) and parsed.get("tool"):
                steps.append(parsed)
    return steps


def extract_tool_budget(payload: Optional[Dict[str, Any]], default_rounds: int, default_lines: int) -> tuple[int, int]:
    max_rounds = default_rounds
    max_lines = default_lines
    if not isinstance(payload, dict):
        return max_rounds, max_lines
    budget = payload.get("budget")
    if isinstance(budget, dict):
        max_rounds = safe_int(budget.get("max_rounds"), max_rounds)
        max_lines = safe_int(budget.get("max_total_lines"), max_lines)
    return max_rounds, max_lines


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [value]
    return []


def _split_tool_step(text: str) -> List[str]:
    if not text:
        return []
    try:
        return shlex.split(text)
    except Exception:
        return text.split()


_KV_ALLOWED_KEYS = {
    "pattern",
    "p",
    "paths",
    "path",
    "file",
    "line",
    "around",
    "around_line",
    "radius",
    "start",
    "start_line",
    "end",
    "end_line",
    "depth",
    "max",
    "max_entries",
    "n",
    "lines",
    "count",
    "glob",
    "g",
    "include",
    "recursive",
}


def _parse_key_value_token(token: str) -> Optional[Tuple[str, str]]:
    if not token or token.startswith("--"):
        return None
    sep = None
    if ":" in token:
        sep = ":"
    elif "=" in token:
        sep = "="
    if sep is None:
        return None
    key, value = token.split(sep, 1)
    key = key.strip().lower()
    if key not in _KV_ALLOWED_KEYS:
        return None
    value = value.strip()
    if not key or value == "":
        return None
    return key, value


def _split_list_value(value: str) -> List[str]:
    if not value:
        return []
    cleaned = value.strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]
    parts = []
    for part in cleaned.split(","):
        part = part.strip().strip("'\"")
        if part:
            parts.append(part)
    return parts


def parse_tool_plan_item(item: str) -> Optional[Dict[str, Any]]:
    tokens = _split_tool_step(item)
    if not tokens:
        return None
    tool = tokens[0].strip()
    if not tool:
        return None
    if tool == "cat" and len(tokens) >= 2:
        return {"tool": "repo_read_head", "args": {"file": tokens[1], "n": MAX_TOOL_READ_LINES}}
    if tool == "repo_ls":
        path: Optional[str] = None
        depth: Optional[int] = None
        i = 1
        while i < len(tokens):
            tok = tokens[i]
            kv = _parse_key_value_token(tok)
            if kv:
                key, value = kv
                if key in ("path", "paths", "include"):
                    items = _split_list_value(value)
                    if items:
                        path = items[0]
                elif key == "recursive":
                    if value.lower() in ("1", "true", "yes", "y", "on"):
                        depth = 6
                i += 1
                continue
            if tok in ("--include", "--path", "--paths"):
                if i + 1 < len(tokens):
                    path = tokens[i + 1].strip("'\"")
                    i += 2
                    continue
            if tok in ("--recursive", "-r", "-R"):
                depth = 6
                i += 1
                continue
            if not tok.startswith("-") and path is None:
                path = tok.strip("'\"")
            i += 1
        args: Dict[str, Any] = {"path": path or "."}
        if depth is not None and depth > 0:
            args["depth"] = depth
        return {"tool": "repo_tree", "args": args}

    if tool == "repo_rg":
        pattern: Optional[str] = None
        paths: List[str] = []
        max_results: Optional[int] = None
        glob_pat: Optional[str] = None
        i = 1
        while i < len(tokens):
            tok = tokens[i]
            kv = _parse_key_value_token(tok)
            if kv:
                key, value = kv
                if key in ("pattern", "p"):
                    pattern = value.strip("'\"")
                elif key in ("paths", "path", "file"):
                    for part in _split_list_value(value):
                        paths.append(part)
                elif key in ("max", "max_results"):
                    try:
                        max_results = int(value)
                    except Exception:
                        pass
                elif key in ("glob", "g"):
                    glob_pat = value.strip("'\"")
                i += 1
                continue
            if tok in ("-p", "--pattern"):
                if i + 1 < len(tokens):
                    pattern = tokens[i + 1]
                    i += 2
                    continue
            if tok in ("--max", "-m"):
                if i + 1 < len(tokens):
                    try:
                        max_results = int(tokens[i + 1])
                    except Exception:
                        pass
                    i += 2
                    continue
            if tok in ("--glob", "-g"):
                if i + 1 < len(tokens):
                    glob_pat = tokens[i + 1]
                    i += 2
                    continue
            if tok in ("--path", "--paths"):
                if i + 1 < len(tokens):
                    paths.extend(_split_list_value(tokens[i + 1]))
                    i += 2
                    continue
            if tok.startswith("--"):
                if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                    i += 2
                else:
                    i += 1
                continue
            if pattern is None:
                pattern = tok.strip("'\"")
            else:
                paths.append(tok.strip("'\""))
            i += 1
        if not pattern:
            return {"tool": tool, "args": {}}
        args: Dict[str, Any] = {"pattern": pattern}
        if paths:
            args["paths"] = paths
        if max_results is not None:
            args["max_results"] = max_results
        if glob_pat:
            args["glob"] = glob_pat
        return {"tool": tool, "args": args}

    if tool in ("repo_read_around", "repo_read_slice", "repo_read_head", "repo_read_tail", "repo_tree", "repo_diff"):
        file_arg: Optional[str] = None
        line_no: Optional[int] = None
        radius: Optional[int] = None
        start: Optional[int] = None
        end: Optional[int] = None
        depth: Optional[int] = None
        max_entries: Optional[int] = None
        count: Optional[int] = None
        stat = False
        positional: List[str] = []
        i = 1
        while i < len(tokens):
            tok = tokens[i]
            kv = _parse_key_value_token(tok)
            if kv:
                key, value = kv
                if key in ("file", "path"):
                    file_arg = value.strip("'\"")
                elif key in ("line", "around", "around_line"):
                    line_no = safe_int(value, -1)
                elif key in ("radius",):
                    radius = safe_int(value, -1)
                elif key in ("start", "start_line"):
                    start = safe_int(value, -1)
                elif key in ("end", "end_line"):
                    end = safe_int(value, -1)
                elif key in ("depth",):
                    depth = safe_int(value, -1)
                elif key in ("max", "max_entries"):
                    max_entries = safe_int(value, -1)
                elif key in ("n", "lines", "count"):
                    count = safe_int(value, -1)
                i += 1
                continue
            if tok in ("--file", "-f", "--path"):
                if i + 1 < len(tokens):
                    file_arg = tokens[i + 1].strip("'\"")
                    i += 2
                    continue
            if tok in ("--line", "--around", "--around_line"):
                if i + 1 < len(tokens):
                    line_no = safe_int(tokens[i + 1], -1)
                    i += 2
                    continue
            if tok == "--radius":
                if i + 1 < len(tokens):
                    radius = safe_int(tokens[i + 1], -1)
                    i += 2
                    continue
            if tok in ("--start", "--start_line"):
                if i + 1 < len(tokens):
                    start = safe_int(tokens[i + 1], -1)
                    i += 2
                    continue
            if tok in ("--end", "--end_line"):
                if i + 1 < len(tokens):
                    end = safe_int(tokens[i + 1], -1)
                    i += 2
                    continue
            if tok == "--depth":
                if i + 1 < len(tokens):
                    depth = safe_int(tokens[i + 1], -1)
                    i += 2
                    continue
            if tok in ("--max", "--max_entries"):
                if i + 1 < len(tokens):
                    max_entries = safe_int(tokens[i + 1], -1)
                    i += 2
                    continue
            if tok in ("--n", "--lines"):
                if i + 1 < len(tokens):
                    count = safe_int(tokens[i + 1], -1)
                    i += 2
                    continue
            if tok == "--stat":
                stat = True
                i += 1
                continue
            if tok.startswith("--"):
                i += 1
                continue
            positional.append(tok)
            i += 1

        if tool == "repo_tree":
            path = positional[0].strip("'\"") if positional else "."
            args: Dict[str, Any] = {"path": path}
            if depth is not None and depth > 0:
                args["depth"] = depth
            if max_entries is not None and max_entries > 0:
                args["max_entries"] = max_entries
            return {"tool": tool, "args": args}

        if tool == "repo_diff":
            args = {"stat": stat}
            return {"tool": tool, "args": args}

        if not file_arg and positional:
            file_arg = positional[0].strip("'\"")
        if tool == "repo_read_around":
            if line_no is None or line_no <= 0:
                if len(positional) >= 2:
                    line_no = safe_int(positional[1], -1)
            if radius is None or radius <= 0:
                if len(positional) >= 3:
                    radius = safe_int(positional[2], DEFAULT_READ_RADIUS)
            args = {"file": file_arg, "line": line_no}
            if radius is not None and radius > 0:
                args["radius"] = radius
            return {"tool": tool, "args": args}
        if tool == "repo_read_slice":
            if start is None or start <= 0:
                if len(positional) >= 2:
                    start = safe_int(positional[1], -1)
            if end is None or end <= 0:
                if len(positional) >= 3:
                    end = safe_int(positional[2], -1)
            return {"tool": tool, "args": {"file": file_arg, "start": start, "end": end}}
        if tool in ("repo_read_head", "repo_read_tail"):
            if count is None or count <= 0:
                if len(positional) >= 2:
                    count = safe_int(positional[1], -1)
            args = {"file": file_arg}
            if count is not None and count > 0:
                args["n"] = count
            return {"tool": tool, "args": args}

    return {"tool": tool, "args": {}}


def score_hit(text: str, file_path: str, patterns: List[str]) -> int:
    score = 0
    lowered = text.lower()
    if re.search(r"\b(def|class|function)\b", lowered):
        score += 5
    if re.search(r"\b(export\s+function|export\s+class)\b", lowered):
        score += 5
    for pat in patterns:
        if not pat:
            continue
        try:
            if re.search(rf"\b{re.escape(pat)}\b", text):
                score += 3
        except Exception:
            continue
    path_lower = file_path.replace("\\", "/").lower()
    if "/loops/" in path_lower or "/modules/" in path_lower:
        score += 2
    if "/test/" in path_lower or "/tests/" in path_lower or "/docs/" in path_lower:
        score -= 3
    if path_lower.endswith(".md"):
        score -= 3
    return score


def annotate_rg_output(output: Dict[str, Any]) -> None:
    hits = output.get("hits")
    if not isinstance(hits, list) or not hits:
        return
    raw_pattern = str(output.get("pattern") or "")
    patterns = [p.strip() for p in raw_pattern.split("|")] if raw_pattern else []
    scored: List[Dict[str, Any]] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        text = str(hit.get("text") or "")
        file_path = str(hit.get("file") or "")
        score = score_hit(text, file_path, patterns)
        hit_copy = dict(hit)
        hit_copy["score"] = score
        scored.append(hit_copy)
    scored.sort(key=lambda item: (item.get("score", 0), item.get("file", ""), item.get("line", 0)), reverse=True)
    output["ranked_hits"] = scored[:3]
    if scored:
        output["best_hit"] = scored[0]


def analyze_slice_content(content: List[Dict[str, Any]]) -> Dict[str, bool]:
    has_def = False
    has_end = False
    for item in content:
        if not isinstance(item, dict):
            continue
        line = str(item.get("t") or "")
        lowered = line.lower()
        if re.search(r"\b(def|class|function)\b", lowered) or "export function" in lowered or "export class" in lowered:
            has_def = True
        if re.search(r"^\s*}\s*$", line) or re.search(r"\breturn\b", lowered):
            has_end = True
    return {"has_def": has_def, "has_end": has_end}


def suggest_radius(truncated: bool, analysis: Dict[str, bool], current_radius: int) -> Optional[int]:
    if not truncated:
        return None
    if not analysis.get("has_def"):
        return max(current_radius, 140)
    if analysis.get("has_def") and not analysis.get("has_end"):
        return max(current_radius, 120)
    return None


def normalize_tool_plan(
    tool_plan: List[Dict[str, Any]],
    around_history: Dict[Tuple[str, int], Dict[str, Any]],
    need_more_context_count: int,
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for step in tool_plan:
        if not isinstance(step, dict):
            continue
        tool = str(step.get("tool") or "").strip()
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        if tool == "repo_read_around":
            file_arg = args.get("file") or args.get("path")
            line_no = args.get("line") or args.get("around_line") or args.get("around")
            radius = safe_int(args.get("radius"), DEFAULT_READ_RADIUS)
            if file_arg and line_no is not None:
                key = (str(file_arg), int(line_no))
                suggestion = around_history.get(key, {}).get("suggest_radius")
                if suggestion and suggestion > radius:
                    args = dict(args)
                    args["radius"] = suggestion
                    step = dict(step)
                    step["args"] = args
                if need_more_context_count >= 2 and key in around_history:
                    start_line = around_history[key].get("start_line")
                    end_line = around_history[key].get("end_line")
                    if isinstance(start_line, int) and isinstance(end_line, int):
                        width = end_line - start_line + 1
                        width = max(width, DEFAULT_READ_RADIUS * 2)
                        width = min(width + 80, MAX_TOOL_READ_LINES)
                        half = width // 2
                        new_start = max(1, int(line_no) - half)
                        new_end = new_start + width - 1
                        step = {
                            "tool": "repo_read_slice",
                            "args": {"file": file_arg, "start": new_start, "end": new_end},
                        }
        normalized.append(step)
    return normalized


def build_tool_cli_args(tool: str, args: Any) -> List[str]:
    if isinstance(args, list):
        return [str(x) for x in args]
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return []
    tool = tool or ""
    if tool == "repo_tree":
        path = args.get("path") or args.get("root") or "."
        depth = args.get("depth")
        max_entries = args.get("max_entries") or args.get("max")
        tokens = [str(path)]
        if depth is not None:
            tokens += ["--depth", str(depth)]
        if max_entries is not None:
            tokens += ["--max", str(max_entries)]
        return tokens
    if tool == "repo_rg":
        pattern = args.get("pattern") or args.get("query")
        if not pattern:
            return []
        paths = _as_list(args.get("paths") or args.get("path"))
        max_results = args.get("max_results") or args.get("max")
        glob_pat = args.get("glob")
        tokens = [str(pattern)]
        tokens += [str(p) for p in paths]
        if max_results is not None:
            tokens += ["--max", str(max_results)]
        if glob_pat:
            tokens += ["--glob", str(glob_pat)]
        return tokens
    if tool == "repo_read_around":
        file_arg = args.get("file") or args.get("path")
        line_no = args.get("line") or args.get("around_line") or args.get("around")
        radius = args.get("radius")
        if not file_arg or line_no is None:
            return []
        tokens = ["--file", str(file_arg), "--line", str(line_no)]
        if radius is not None:
            tokens += ["--radius", str(radius)]
        return tokens
    if tool == "repo_read_slice":
        file_arg = args.get("file") or args.get("path")
        start = args.get("start") or args.get("start_line")
        end = args.get("end") or args.get("end_line")
        if not file_arg or start is None or end is None:
            return []
        return ["--file", str(file_arg), "--start", str(start), "--end", str(end)]
    if tool in ("repo_read_head", "repo_read_tail"):
        file_arg = args.get("file") or args.get("path")
        count = args.get("n") or args.get("lines") or args.get("count")
        if not file_arg:
            return []
        tokens = ["--file", str(file_arg)]
        if count is not None:
            tokens += ["--n", str(count)]
        return tokens
    if tool == "repo_diff":
        tokens: List[str] = []
        if args.get("stat") or args.get("mode") in ("stat", "--stat"):
            tokens.append("--stat")
        return tokens
    return []


def count_tool_output_lines(output: Dict[str, Any]) -> int:
    if not isinstance(output, dict):
        return 0
    if output.get("cache_hit") is True:
        return 0
    tool = output.get("tool")
    if tool in ("repo_read_around", "repo_read_slice", "repo_read_head", "repo_read_tail"):
        content = output.get("content")
        if isinstance(content, list):
            return len(content)
    return 0


def _tools_root() -> str:
    module_dir = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(module_dir, "..", ".."))


def run_tool_plan(
    state: Any,
    tool_plan: List[Dict[str, Any]],
    log_path: str,
    tool_cache: Dict[Tuple[str, Tuple[str, ...]], Dict[str, Any]],
    around_history: Dict[Tuple[str, int], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    outputs: List[Dict[str, Any]] = []
    if not tool_plan:
        return outputs
    allowed_tools = {
        "repo_tree",
        "repo_rg",
        "repo_read_around",
        "repo_read_slice",
        "repo_read_head",
        "repo_read_tail",
        "repo_diff",
    }
    tools_path = os.path.join(_tools_root(), "tools", "main.py")

    def cache_key(tool: str, cli_args: List[str]) -> Tuple[str, Tuple[str, ...]]:
        return (tool, tuple(cli_args))

    def update_around_history(output: Dict[str, Any]) -> None:
        if output.get("tool") != "repo_read_around":
            return
        file_path = output.get("file")
        around_line = output.get("around_line")
        if not file_path or around_line is None:
            return
        content = output.get("content") if isinstance(output.get("content"), list) else []
        analysis = analyze_slice_content(content)
        truncated = bool(output.get("truncated"))
        radius = safe_int(output.get("radius"), DEFAULT_READ_RADIUS)
        suggestion = suggest_radius(truncated, analysis, radius)
        around_history[(str(file_path), int(around_line))] = {
            "start_line": output.get("start_line"),
            "end_line": output.get("end_line"),
            "radius": radius,
            "truncated": truncated,
            "has_def": analysis.get("has_def"),
            "has_end": analysis.get("has_end"),
            "suggest_radius": suggestion,
        }

    def execute_tool(tool: str, cli_args: List[str]) -> Dict[str, Any]:
        events_path = getattr(state, "events_full", "")
        refs = _build_refs(state, "tool_exec")
        emit_event(
            events_path,
            kind="action",
            actor="Tooling",
            name=tool,
            refs=refs,
            summary=f"{tool} {cli_args}",
            input={"args": cli_args},
        )
        key = cache_key(tool, cli_args)
        if key in tool_cache:
            cached = copy.deepcopy(tool_cache[key])
            cached["cache_hit"] = True
            compact, truncation = _compact_tool_output(tool, cached if isinstance(cached, dict) else {})
            emit_event(
                events_path,
                kind="observation",
                actor="Tooling",
                name=tool,
                refs=refs,
                summary=f"{tool} cache_hit",
                ok=bool(cached.get("ok", True)) if isinstance(cached, dict) else True,
                output=compact,
                truncation=truncation,
                meta={"cache_hit": True},
            )
            return cached
        cmd = [sys.executable, tools_path, "--json", tool, "--"] + cli_args
        start_ts = time.time()
        _append_log(log_path, f"[TOOL] Running: {' '.join(cmd)}\n")
        try:
            result = subprocess.run(
                cmd,
                cwd=state.workspace_full,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=state.npm_timeout if getattr(state, "npm_timeout", 0) > 0 else None,
                env=_build_utf8_env(),
            )
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            try:
                parsed = json.loads(stdout) if stdout.strip() else {}
            except Exception as exc:
                parsed = {
                    "ok": False,
                    "tool": tool,
                    "error": f"Invalid JSON output: {exc}",
                    "exit_code": result.returncode,
                    "stdout_raw": stdout,
                    "stderr_raw": stderr,
                }
            if isinstance(parsed, dict):
                parsed.setdefault("tool", tool)
                parsed.setdefault("exit_code", result.returncode)
                parsed.setdefault("cache_hit", False)
            if stderr:
                _append_log(log_path, "[TOOL] STDERR:\n" + stderr + "\n")
            tool_cache[key] = parsed if isinstance(parsed, dict) else {}
            if isinstance(parsed, dict):
                compact, truncation = _compact_tool_output(tool, parsed)
                emit_event(
                    events_path,
                    kind="observation",
                    actor="Tooling",
                    name=tool,
                    refs=refs,
                    summary=f"{tool} exit={parsed.get('exit_code')}",
                    ok=bool(parsed.get("ok", True)),
                    output=compact,
                    truncation=truncation,
                    meta={"cache_hit": parsed.get("cache_hit", False)},
                    duration_ms=int((time.time() - start_ts) * 1000),
                )
            return parsed if isinstance(parsed, dict) else {
                "ok": False,
                "tool": tool,
                "error": "Invalid tool output",
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            timeout_result = {"ok": False, "tool": tool, "error": "timeout", "exit_code": -1, "cache_hit": False}
            emit_event(
                events_path,
                kind="observation",
                actor="Tooling",
                name=tool,
                refs=refs,
                summary=f"{tool} timeout",
                ok=False,
                output=timeout_result,
                truncation={"truncated": False},
                error="timeout",
            )
            return timeout_result
        except Exception as exc:
            error_result = {"ok": False, "tool": tool, "error": str(exc), "exit_code": -1, "cache_hit": False}
            emit_event(
                events_path,
                kind="observation",
                actor="Tooling",
                name=tool,
                refs=refs,
                summary=f"{tool} error",
                ok=False,
                output=error_result,
                truncation={"truncated": False},
                error=str(exc),
            )
            return error_result

    for step in tool_plan:
        tool = str(step.get("tool") or "").strip()
        args = step.get("args")
        if not tool:
            continue
        if tool not in allowed_tools:
            outputs.append({"ok": False, "tool": tool, "error": "tool not allowed", "exit_code": 2})
            _append_log(log_path, f"[TOOL] Skipped unsupported tool: {tool}\n")
            continue
        cli_args = build_tool_cli_args(tool, args)
        if cli_args is None:
            cli_args = []
        if tool.startswith("repo_") and not cli_args and tool != "repo_diff":
            outputs.append({"ok": False, "tool": tool, "error": "invalid args", "exit_code": 2})
            continue
        output = execute_tool(tool, cli_args)
        if isinstance(output, dict) and output.get("tool") == "repo_rg":
            annotate_rg_output(output)
        update_around_history(output if isinstance(output, dict) else {})
        outputs.append(output)

        if tool == "repo_rg" and isinstance(step, dict):
            fallback_lines = safe_int(step.get("fallback_head_lines"), 0)
            if fallback_lines > 0:
                hits = output.get("hits") if isinstance(output, dict) else []
                if not isinstance(hits, list) or not hits:
                    file_arg = None
                    if isinstance(step.get("args"), dict):
                        paths = _as_list(step["args"].get("paths") or step["args"].get("path"))
                        if paths:
                            file_arg = paths[0]
                    if not file_arg and isinstance(output, dict):
                        paths = output.get("paths")
                        if isinstance(paths, list) and paths:
                            file_arg = paths[0]
                    if file_arg and file_arg not in (".", "./"):
                        fallback_args = ["--file", str(file_arg), "--n", str(fallback_lines)]
                        fallback_output = execute_tool("repo_read_head", fallback_args)
                        if isinstance(fallback_output, dict):
                            fallback_output["fallback_from"] = "repo_rg_no_hits"
                        outputs.append(fallback_output)

        if isinstance(step, dict) and step.get("auto_follow") and tool == "repo_rg":
            best = None
            if isinstance(output, dict):
                best = output.get("best_hit")
                if not isinstance(best, dict):
                    ranked = output.get("ranked_hits")
                    if isinstance(ranked, list) and ranked:
                        best = ranked[0]
            if isinstance(best, dict):
                follow_file = best.get("file")
                follow_line = best.get("line")
                follow_radius = None
                if isinstance(step.get("args"), dict):
                    follow_radius = step["args"].get("radius")
                if follow_radius is None:
                    follow_radius = DEFAULT_READ_RADIUS
                if follow_file and follow_line:
                    follow_args = ["--file", str(follow_file), "--line", str(follow_line), "--radius", str(follow_radius)]
                    follow_output = execute_tool("repo_read_around", follow_args)
                    if isinstance(follow_output, dict):
                        follow_output["auto_follow"] = True
                        update_around_history(follow_output)
                    outputs.append(follow_output)
    return outputs
