import datetime
import hashlib
import os
from typing import Any, Dict, List, Optional

from io_utils import ensure_parent_dir, write_json_atomic


def _append_log(log_path: str, text: str) -> None:
    if not log_path:
        return
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(text)


def summarize_tool_outputs(outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    rg_queries: List[str] = []
    evidence_refs: List[Dict[str, Any]] = []
    for out in outputs:
        tool = out.get("tool")
        if tool == "repo_rg":
            pattern = out.get("pattern")
            if isinstance(pattern, str) and pattern:
                rg_queries.append(pattern)
        if tool in ("repo_read_around", "repo_read_slice", "repo_read_head", "repo_read_tail"):
            file_path = out.get("file")
            start_line = out.get("start_line")
            end_line = out.get("end_line")
            if file_path and start_line is not None and end_line is not None:
                evidence_refs.append(
                    {
                        "file": file_path,
                        "start_line": start_line,
                        "end_line": end_line,
                        "tool": tool,
                    }
                )
    return {
        "rg_queries": rg_queries,
        "evidence_refs": evidence_refs,
    }


def _hash_content(content: List[Dict[str, Any]]) -> str:
    hasher = hashlib.sha1()
    for item in content:
        if not isinstance(item, dict):
            continue
        text = str(item.get("t") or "")
        hasher.update(text.encode("utf-8", errors="ignore"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def build_evidence_summary(outputs: List[Dict[str, Any]], verbosity: str = "summary") -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for out in outputs:
        if not isinstance(out, dict):
            continue
        tool = out.get("tool")
        item: Dict[str, Any] = {"tool": tool, "cache_hit": out.get("cache_hit", False)}
        if tool in ("repo_read_around", "repo_read_slice", "repo_read_head", "repo_read_tail"):
            content = out.get("content") if isinstance(out.get("content"), list) else []
            item.update(
                {
                    "file": out.get("file"),
                    "start_line": out.get("start_line"),
                    "end_line": out.get("end_line"),
                    "truncated": out.get("truncated"),
                    "line_count": len(content),
                    "hash": _hash_content(content),
                }
            )
            if content:
                if verbosity == "full":
                    item["content"] = content
                else:
                    item["sample"] = content[: min(10, len(content))]
        elif tool == "repo_rg":
            hits = out.get("hits") if isinstance(out.get("hits"), list) else []
            ranked = out.get("ranked_hits") if isinstance(out.get("ranked_hits"), list) else []
            item.update(
                {
                    "pattern": out.get("pattern"),
                    "paths": out.get("paths"),
                    "hit_count": len(hits),
                    "top_hits": ranked[:3],
                    "truncated": out.get("truncated"),
                }
            )
        elif tool == "repo_tree":
            item.update(
                {
                    "path": out.get("path"),
                    "depth": out.get("depth"),
                    "truncated": out.get("truncated"),
                }
            )
        elif tool == "repo_diff":
            item.update({"exit_code": out.get("exit_code"), "ok": out.get("ok")})
        summary.append(item)
    return summary


def write_evidence_package(
    state: Any,
    tool_outputs: List[Dict[str, Any]],
    pm_task_id: str,
    pm_iteration: Optional[int],
    director_iteration: int,
    tool_rounds: int,
    total_lines_read: int,
) -> Optional[str]:
    if not tool_outputs:
        return None
    evidence_dir = os.path.join(state.workspace_full, "state", "ollama", "evidence")
    ensure_parent_dir(os.path.join(evidence_dir, "placeholder"))
    task_part = pm_task_id or "task"
    pm_part = f"{pm_iteration:05d}" if isinstance(pm_iteration, int) else f"{director_iteration:05d}"
    filename = f"EVIDENCE_{task_part}_{pm_part}.json"
    path = os.path.join(evidence_dir, filename)
    payload = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_id": pm_task_id,
        "pm_iteration": pm_iteration,
        "director_iteration": director_iteration,
        "tool_rounds": tool_rounds,
        "total_lines_read": total_lines_read,
        "verbosity": state.evidence_verbosity,
        "items": build_evidence_summary(tool_outputs, state.evidence_verbosity),
    }
    try:
        write_json_atomic(path, payload)
        return path
    except Exception as exc:
        _append_log(state.log_full, f"[WARN] Failed to write evidence package: {exc}\n")
        return None
