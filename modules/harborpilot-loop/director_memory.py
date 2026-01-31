import datetime
import os
import re
import subprocess
import sys
from typing import Any, Dict, Optional, Tuple

from io_utils import ensure_memory_dir, extract_field, write_memory_snapshot, write_loop_warning


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


def _append_log(log_path: str, text: str) -> None:
    if log_path:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(text)


def _compact_text(text: str, limit: int = 240) -> str:
    if not text:
        return "no output"
    flat = re.sub(r"\s+", " ", text.replace("\r", " ").replace("\n", " ")).strip()
    if len(flat) > limit:
        flat = flat[:limit] + "..."
    return flat or "no output"


def _extract_summary_next(
    qa_output: str,
    qa_payload: Optional[Dict[str, Any]],
) -> Tuple[str, Optional[str]]:
    summary_patterns = [
        r"(?im)^\s*(?:summary|change summary|brief summary)\s*[:\uFF1A]\s*(.+)$",
        r"(?im)^\s*\*{1,2}(?:summary)\*{1,2}\s*[:\uFF1A]\s*(.+)$",
    ]
    next_patterns = [
        r"(?im)^\s*(?:next step|next steps|next\s*action)\s*[:\uFF1A]\s*(.+)$",
        r"(?im)^\s*\*{1,2}(?:next step)\*{1,2}\s*[:\uFF1A]\s*(.+)$",
    ]

    summary: Optional[str] = None
    if isinstance(qa_payload, dict):
        payload_summary = qa_payload.get("summary")
        if isinstance(payload_summary, str) and payload_summary.strip():
            summary = payload_summary.strip()
    if not summary:
        summary = extract_field(qa_output, summary_patterns)
    if not summary:
        summary = _compact_text(qa_output)

    next_step: Optional[str] = None
    if isinstance(qa_payload, dict):
        payload_next = qa_payload.get("next") or qa_payload.get("next_step")
        if isinstance(payload_next, str) and payload_next.strip():
            next_step = payload_next.strip()
    if not next_step:
        next_step = extract_field(qa_output, next_patterns)

    return summary, next_step


def invoke_lancedb_store(db_dir: str, json_path: str, log_path: str) -> Optional[str]:
    if not db_dir or not json_path:
        return "LANCEDB_STORE_MISSING_PATH"
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lancedb_store.py")
    if not os.path.exists(script_path):
        write_loop_warning(log_path, f"LanceDB store script missing: {script_path}")
        return "LANCEDB_STORE_SCRIPT_MISSING"
    try:
        timeout_sec = 0
        try:
            timeout_sec = int(str(os.environ.get("HARBORPILOT_LANCEDB_STORE_TIMEOUT", "60")).strip())
        except Exception:
            timeout_sec = 60
        timeout_val = timeout_sec if timeout_sec and timeout_sec > 0 else None
        result = subprocess.run(
            [sys.executable, script_path, "--db", db_dir, "--json", json_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_build_utf8_env(),
            timeout=timeout_val,
        )
        if result.stderr:
            write_loop_warning(log_path, f"LanceDB store stderr: {result.stderr}")
            return "LANCEDB_STORE_STDERR"
    except subprocess.TimeoutExpired:
        write_loop_warning(log_path, "LanceDB store timeout")
        return "LANCEDB_STORE_TIMEOUT"
    except Exception as exc:
        write_loop_warning(log_path, f"LanceDB store failed: {exc}")
        return "LANCEDB_STORE_FAILED"
    return None


def update_memory_snapshot(
    state: Any,
    *,
    qa_output: str,
    qa_payload: Optional[Dict[str, Any]],
    iteration_index: int,
    target_index: int,
    target_note: str,
    log_path: str,
    gap_review_ran: bool,
    acceptance: Optional[bool],
) -> Dict[str, Any]:
    warnings: list[str] = []
    backend = str(getattr(state, "memory_backend", "") or "").lower()
    enabled = bool(getattr(state, "memory_enabled", False))
    if backend in ("none", "off", "disabled", "false", "0"):
        enabled = False
    if not enabled:
        return {"memory_data": None, "backend_effective": "none", "warnings": warnings}

    summary, next_step = _extract_summary_next(qa_output, qa_payload)
    memory_data: Dict[str, Any] = {
        "last_run_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_round_index": iteration_index,
        "last_target_index": target_index,
        "last_target": target_note,
        "last_summary": summary,
        "last_next_step": next_step,
        "last_log_path": log_path,
        "last_response_path": getattr(state, "qa_full", ""),
        "last_exit_code": 0 if acceptance is True else 1 if acceptance is False else 0,
    }
    if gap_review_ran:
        memory_data["last_gap_review_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        memory_data["last_gap_report_path"] = getattr(state, "gap_report_full", "")
    if acceptance is False:
        memory_data["last_error"] = "QA acceptance failed"

    ensure_memory_dir(getattr(state, "memory_dir_full", ""))
    try:
        write_memory_snapshot(getattr(state, "memory_snapshot_path", ""), memory_data)
        state.memory_snapshot = memory_data
    except Exception as exc:
        warn = f"MEMORY_SNAPSHOT_WRITE_FAILED: {exc}"
        warnings.append(warn)
        _append_log(log_path, f"[WARN] {warn}\n")

    backend_effective = "file"
    store_enabled = bool(getattr(state, "memory_store_enabled", True))
    store_every = int(getattr(state, "memory_store_every", 1) or 1)
    store_on_accept = bool(getattr(state, "memory_store_on_accept", False))
    store_due = True
    if store_every > 1 and iteration_index % store_every != 0:
        store_due = False
    if store_on_accept and acceptance is not True:
        store_due = False

    if backend in ("lancedb", "both") and store_enabled:
        if store_due:
            warning = invoke_lancedb_store(
                getattr(state, "memory_dir_full", ""),
                getattr(state, "memory_snapshot_path", ""),
                log_path,
            )
            if warning:
                warnings.append(warning)
            else:
                backend_effective = "both" if backend == "both" else "lancedb"
        else:
            warnings.append("LANCEDB_STORE_SKIPPED")
    elif backend in ("lancedb", "both") and not store_enabled:
        warnings.append("LANCEDB_STORE_DISABLED")

    return {
        "memory_data": memory_data,
        "backend_effective": backend_effective,
        "warnings": warnings,
    }
