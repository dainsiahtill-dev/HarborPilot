import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


SCRIPT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
LOOP_PM_PATH = os.path.join(PROJECT_ROOT, "loops", "loop-pm.py")
DIRECTOR_SCRIPT = os.path.join(PROJECT_ROOT, "loops", "loop-director.py")

DEFAULT_MODEL = "modelscope.cn/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF:latest"
DEFAULT_PLAN = "state/ollama/PLAN.md"
DEFAULT_GAP = "state/ollama/GAP_REPORT.md"
DEFAULT_QA = "state/ollama/QA_RESPONSE.md"
DEFAULT_REQUIREMENTS = "docs/product/requirements.md"
DEFAULT_PM_OUT = "state/ollama/PM_TASKS.json"
DEFAULT_PM_REPORT = "state/ollama/PM_REPORT.md"
DEFAULT_PM_LOG = "state/ollama/PM_LOG.jsonl"
DEFAULT_PM_SUBPROCESS_LOG = "state/ollama/PM_SUBPROCESS.log"
DEFAULT_DIRECTOR_SUBPROCESS_LOG = "state/ollama/DIRECTOR_SUBPROCESS.log"
DEFAULT_DIRECTOR_STATUS = "state/ollama/DIRECTOR_STATUS.json"
DEFAULT_PLANNER = "state/ollama/PLANNER_RESPONSE.md"
DEFAULT_OLLAMA = "state/ollama/OLLAMA_RESPONSE.md"
DEFAULT_RUNLOG = "state/ollama/RUNLOG.md"
DEFAULT_DIALOGUE = "state/ollama/DIALOGUE.jsonl"
AGENTS_DRAFT_REL = "state/ollama/AGENTS.generated.md"
AGENTS_FEEDBACK_REL = "state/ollama/AGENTS.feedback.md"
STATE_TO_RAMDISK_ENV = "HARBORPILOT_STATE_TO_RAMDISK"

CHANNEL_FILES = {
    "pm_report": DEFAULT_PM_REPORT,
    "pm_log": DEFAULT_PM_LOG,
    "pm_subprocess": DEFAULT_PM_SUBPROCESS_LOG,
    "planner": DEFAULT_PLANNER,
    "ollama": DEFAULT_OLLAMA,
    "qa": DEFAULT_QA,
    "runlog": DEFAULT_RUNLOG,
    "dialogue": DEFAULT_DIALOGUE,
    "director_console": DEFAULT_DIRECTOR_SUBPROCESS_LOG,
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


def build_utf8_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_ALL", "en_US.UTF-8")
    if extra:
        env.update(extra)
    return env


enforce_utf8()


def get_lancedb_status() -> Dict[str, Any]:
    try:
        import lancedb  # type: ignore
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "python": sys.executable,
        }
    version = getattr(lancedb, "__version__", None)
    return {
        "ok": True,
        "error": None,
        "python": sys.executable,
        "version": version,
    }


def require_lancedb() -> None:
    status = get_lancedb_status()
    if not status.get("ok"):
        detail = f"lancedb not available (python={status.get('python')})"
        error = status.get("error")
        if error:
            detail = f"{detail}: {error}"
        raise HTTPException(status_code=503, detail=detail)


def log_backend_error(event: str, detail: str, **extra: Any) -> None:
    payload: Dict[str, Any] = {
        "event": event,
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    for key, value in extra.items():
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        payload[key] = value
    try:
        message = json.dumps(payload, ensure_ascii=False)
        print(message, file=sys.stdout, flush=True)
    except Exception:
        print(f"{event}: {detail}", file=sys.stdout, flush=True)

    if detail and "\n" in detail:
        try:
            print("[backend-error-detail]", file=sys.stdout, flush=True)
            print(detail, file=sys.stdout, flush=True)
        except Exception:
            pass

    tail = extra.get("pm_log_tail")
    if isinstance(tail, str) and tail.strip():
        try:
            print("[pm-subprocess-tail]", file=sys.stdout, flush=True)
            print(tail, file=sys.stdout, flush=True)
        except Exception:
            pass


def _default_ramdisk_root() -> str:
    value = os.environ.get("HARBORPILOT_RAMDISK_ROOT", "").strip()
    if value:
        return value
    if os.name == "nt" and os.path.exists("X:\\"):
        return "X:\\"
    return ""


def find_workspace_root(start: str) -> str:
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, "docs")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start)


DEFAULT_WORKSPACE = find_workspace_root(os.getcwd())
DEFAULT_RAMDISK_ROOT = _default_ramdisk_root()


def get_settings_path() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "HarborPilot", "settings.json")


def load_persisted_settings() -> Dict[str, Any]:
    path = get_settings_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_persisted_settings(settings: "Settings") -> None:
    path = get_settings_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(settings.model_dump(), handle, ensure_ascii=False, indent=2)
    except Exception:
        pass


def check_backend_available(settings: "Settings") -> Optional[str]:
    backend = (settings.pm_backend or "").strip().lower()
    if backend == "codex":
        if not shutil.which("codex"):
            return "codex command not found in PATH. Install codex or switch PM backend to ollama."
    elif backend == "ollama":
        if not shutil.which("ollama"):
            return "ollama command not found in PATH. Install Ollama or switch PM backend to codex."
    return None


def build_runtime_issues(settings: "Settings", workspace: str) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    backend = (settings.pm_backend or "").strip().lower()
    if backend == "codex" and not shutil.which("codex"):
        issues.append(
            {
                "code": "CODEX_MISSING",
                "title": "Codex 未安装",
                "detail": "检测不到 codex 命令。请安装 Codex 或在设置里切换 PM Backend 为 Ollama。",
            }
        )
    if not shutil.which("ollama"):
        if backend == "ollama":
            detail = "检测不到 ollama 命令。请安装 Ollama 或在设置里切换 PM Backend 为 Codex。"
            code = "OLLAMA_MISSING"
            title = "Ollama 未安装"
        else:
            detail = "检测不到 ollama 命令。Director 需要 Ollama 才能运行。请安装 Ollama。"
            code = "DIRECTOR_OLLAMA_MISSING"
            title = "Director 依赖缺失"
        issues.append({"code": code, "title": title, "detail": detail})
    return issues


class SettingsUpdate(BaseModel):
    workspace: Optional[str] = None
    pm_backend: Optional[str] = None
    model: Optional[str] = None
    interval: Optional[int] = None
    timeout: Optional[int] = None
    refresh_interval: Optional[int] = None
    auto_refresh: Optional[bool] = None
    show_memory: Optional[bool] = None
    prompt_profile: Optional[str] = None
    ramdisk_root: Optional[str] = None
    json_log_path: Optional[str] = None
    pm_show_output: Optional[bool] = None
    pm_runs_director: Optional[bool] = None
    pm_director_show_output: Optional[bool] = None
    pm_director_timeout: Optional[int] = None
    pm_director_iterations: Optional[int] = None
    pm_director_match_mode: Optional[str] = None
    pm_max_failures: Optional[int] = None
    pm_max_blocked: Optional[int] = None
    pm_max_same: Optional[int] = None
    director_iterations: Optional[int] = None
    director_forever: Optional[bool] = None
    director_show_output: Optional[bool] = None
    qa_enabled: Optional[bool] = None


class Settings(BaseModel):
    workspace: str = Field(default_factory=lambda: DEFAULT_WORKSPACE)
    pm_backend: str = "codex"
    model: str = DEFAULT_MODEL
    interval: int = 20
    timeout: int = 0
    refresh_interval: int = 3
    auto_refresh: bool = True
    show_memory: bool = False
    prompt_profile: str = "demo_ming_armada"
    ramdisk_root: str = DEFAULT_RAMDISK_ROOT
    json_log_path: str = DEFAULT_PM_LOG
    pm_show_output: bool = True
    pm_runs_director: bool = True
    pm_director_show_output: bool = True
    pm_director_timeout: int = 60
    pm_director_iterations: int = 1
    pm_director_match_mode: str = "latest"
    pm_max_failures: int = 5
    pm_max_blocked: int = 5
    pm_max_same: int = 3
    director_iterations: int = 1
    director_forever: bool = False
    director_show_output: bool = True
    qa_enabled: bool = True

    def apply_update(self, update: SettingsUpdate) -> None:
        data = update.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(self, key, value)


class AgentsApplyPayload(BaseModel):
    draft_path: Optional[str] = None


class AgentsFeedbackPayload(BaseModel):
    text: str = ""


@dataclass
class ProcessHandle:
    process: Optional[subprocess.Popen] = None
    log_handle: Optional[Any] = None
    log_path: str = ""
    mode: str = ""
    started_at: Optional[float] = None


@dataclass
class AppState:
    settings: Settings
    pm: ProcessHandle = field(default_factory=ProcessHandle)
    director: ProcessHandle = field(default_factory=ProcessHandle)
    last_pm_payload: Optional[Dict[str, Any]] = None


class Auth:
    def __init__(self, token: str):
        self.token = token or ""

    def check(self, header_value: str) -> bool:
        if not self.token:
            return True
        if not header_value:
            return False
        if not header_value.lower().startswith("bearer "):
            return False
        value = header_value.split(" ", 1)[1].strip()
        return value == self.token


class ConnectionState:
    def __init__(self) -> None:
        self.channels: Set[str] = set()
        self.tail_state: Dict[str, Dict[str, Any]] = {}
        self.last_sizes: Dict[str, int] = {}
        self.want_status: bool = False


def normalize_ramdisk_root(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) == 2 and raw[1] == ":":
        raw = raw + "\\"
    raw = os.path.abspath(raw)
    raw = raw.rstrip("\\/")
    if len(raw) == 2 and raw[1] == ":":
        raw = raw + "\\"
    return raw


def build_cache_root(ramdisk_root: str, workspace_full: str) -> str:
    root = normalize_ramdisk_root(ramdisk_root)
    if not root:
        return ""
    try:
        exists = os.path.exists(root)
    except Exception:
        exists = False
    if not exists:
        return ""
    ws = os.path.abspath(workspace_full or "").lower()
    digest = hashlib.sha1(ws.encode("utf-8", errors="ignore")).hexdigest()[:12]
    base_name = os.path.basename(root.rstrip("\\/")).lower()
    if base_name == "harborpilot":
        return os.path.join(root, "cache", digest)
    return os.path.join(root, "HarborPilot", "cache", digest)


def state_to_ramdisk_enabled() -> bool:
    value = os.environ.get(STATE_TO_RAMDISK_ENV, "1").strip().lower()
    return value not in ("0", "false", "no", "off")


def is_hot_artifact_path(rel_path: str) -> bool:
    p = (rel_path or "").replace("\\", "/").lstrip("./")
    if p.startswith("state/") and state_to_ramdisk_enabled():
        return True
    if not p.startswith("state/ollama/"):
        return False
    if "/runs/" in p or p.startswith("state/ollama/runs/"):
        return True
    if "/memory/" in p or p.startswith("state/ollama/memory/"):
        return True
    if "/evidence/" in p or p.startswith("state/ollama/evidence/"):
        return True
    lowered = p.lower()
    if lowered.endswith("director_result.json"):
        return True
    if lowered.endswith("director_status.json"):
        return True
    if lowered.endswith(".jsonl") or lowered.endswith(".log") or lowered.endswith(".lock"):
        return True
    if lowered.endswith("/runlog.md") or lowered.endswith("runlog.md"):
        return True
    return False


def resolve_artifact_path(workspace_full: str, cache_root_full: str, rel_path: str) -> str:
    if not rel_path:
        return ""
    if os.path.isabs(rel_path):
        return rel_path
    p = (rel_path or "").replace("\\", "/").lstrip("./")
    if p.startswith("state/") and state_to_ramdisk_enabled():
        if not cache_root_full:
            raise HTTPException(status_code=500, detail="state/ is configured for ramdisk only, but no ramdisk cache root is available")
        return os.path.join(cache_root_full, rel_path)
    base = cache_root_full if (cache_root_full and is_hot_artifact_path(rel_path)) else workspace_full
    return os.path.join(base, rel_path)


def resolve_safe_path(workspace_full: str, cache_root_full: str, rel_path: str) -> str:
    path = resolve_artifact_path(workspace_full, cache_root_full, rel_path)
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    full = os.path.abspath(path)
    roots = [os.path.abspath(workspace_full)]
    if cache_root_full:
        roots.append(os.path.abspath(cache_root_full))
    for root in roots:
        try:
            if os.path.commonpath([root, full]) == root:
                return full
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail="path outside workspace")


def read_json(path: str) -> Optional[Dict[str, Any]]:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def read_director_status(workspace: str, cache_root: str) -> Optional[Dict[str, Any]]:
    candidates = []
    cache_path = resolve_artifact_path(workspace, cache_root, DEFAULT_DIRECTOR_STATUS)
    workspace_path = os.path.join(workspace, DEFAULT_DIRECTOR_STATUS)
    for path in (cache_path, workspace_path):
        if not path:
            continue
        if path in candidates:
            continue
        if os.path.isfile(path):
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                mtime = 0.0
            candidates.append((mtime, path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, best_path = candidates[0]
    data = read_json(best_path)
    if isinstance(data, dict):
        data.setdefault("path", best_path)
    return data


def select_latest_artifact(workspace: str, cache_root: str, rel_path: str) -> Optional[str]:
    candidates: List[tuple[float, str]] = []
    cache_path = resolve_artifact_path(workspace, cache_root, rel_path)
    workspace_path = os.path.join(workspace, rel_path)
    for path in (cache_path, workspace_path):
        if not path or not os.path.isfile(path):
            continue
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            mtime = 0.0
        candidates.append((mtime, path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def compute_success_stats(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return {"successes": None, "total": None, "rate": None}
    if isinstance(result.get("results"), list):
        total = len(result["results"])
        successes = len([r for r in result["results"] if str(r.get("status") or "").lower() == "success"])
        rate = successes / total if total > 0 else None
        return {"successes": successes, "total": total, "rate": rate}
    if isinstance(result.get("successes"), (int, float)) and isinstance(result.get("total"), (int, float)):
        total_val = int(result["total"])
        successes_val = int(result["successes"])
        rate_val = result.get("success_rate")
        if not isinstance(rate_val, (int, float)) and total_val > 0:
            rate_val = successes_val / total_val
        return {"successes": successes_val, "total": total_val, "rate": rate_val}
    return {"successes": None, "total": None, "rate": None}


def build_memory_payload(workspace: str, cache_root: str) -> Optional[Dict[str, Any]]:
    path = select_latest_artifact(workspace, cache_root, "state/ollama/memory/last_state.json")
    if not path:
        return None
    content = read_file_tail(path, max_lines=200, max_chars=20000)
    return {"content": content, "mtime": format_mtime(path)}


def build_success_stats_payload(workspace: str, cache_root: str) -> Dict[str, Any]:
    path = select_latest_artifact(workspace, cache_root, "state/ollama/DIRECTOR_RESULT.json")
    result = read_json(path) if path else None
    return compute_success_stats(result)


def decode_bytes(data: bytes) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
        if text.count("\ufffd") <= max(1, len(text) // 200):
            return text
        try:
            return data.decode("gbk")
        except Exception:
            return text


def read_file_tail(path: str, max_lines: int = 400, max_chars: int = 20000) -> str:
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            file_size = handle.tell()
            if file_size == 0:
                return ""

            pos = file_size
            block_size = 4096
            chunks = []
            lines_found = 0
            chars_read = 0

            target_lines = max_lines if max_lines and max_lines > 0 else None

            while pos > 0:
                read_size = block_size if pos >= block_size else pos
                pos -= read_size
                handle.seek(pos)
                chunk = handle.read(read_size)
                if not chunk:
                    break
                
                chunks.append(chunk)
                chars_read += len(chunk)
                lines_found += chunk.count(b"\n")
                
                # Check exit conditions
                # We need enough lines AND enough chars (if specified)
                # But typically we stop if we have enough lines, unless max_chars forces us to read more?
                # Actually, usually we want "at least N lines" but "at most M chars" is for return value.
                # Here we read backwards to find the start point.
                
                if target_lines is not None and lines_found >= target_lines + 1:
                    # We have enough lines. Check if we also have enough chars to cover potential truncation
                    if max_chars <= 0 or chars_read >= max_chars:
                        break
                
                if max_chars > 0 and chars_read >= max_chars * 2:
                    # Safety break if we read way too many chars (even if not enough lines found yet, 
                    # e.g. very long lines)
                    break

            # Join reversed chunks and decode
            data = b"".join(reversed(chunks))
            text = decode_bytes(data)

            # Truncate to exact limits
            lines = text.splitlines()
            if max_lines > 0 and len(lines) > max_lines:
                lines = lines[-max_lines:]
            content = "\n".join(lines)

            if max_chars > 0 and len(content) > max_chars:
                content = content[-max_chars:]

            return content
    except Exception:
        return ""


def read_file_head(path: str, max_chars: int = 20000) -> str:
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as handle:
            data = handle.read(max_chars if max_chars and max_chars > 0 else 20000)
        return decode_bytes(data)
    except Exception:
        return ""


def read_incremental(path: str, state: Dict[str, Any], max_chars: int = 20000) -> List[str]:
    if not path or not os.path.isfile(path):
        return []
    try:
        size = os.path.getsize(path)
    except Exception:
        size = 0
    pos = int(state.get("pos", 0))
    if size < pos:
        pos = 0
    try:
        with open(path, "rb") as handle:
            handle.seek(pos)
            chunk = handle.read()
            state["pos"] = handle.tell()
    except Exception:
        return []
    if not chunk:
        return []
    text = decode_bytes(chunk)
    if max_chars > 0 and len(text) > max_chars:
        text = text[-max_chars:]
    lines = text.splitlines()
    return lines


def format_mtime(path: str) -> str:
    if not path or not os.path.exists(path):
        return "missing"
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "unknown"


def build_file_status(entries: List[tuple[str, str]]) -> List[str]:
    lines: List[str] = []
    for label, path in entries:
        mtime = format_mtime(path)
        lines.append(f"{label}: {mtime}")
    return lines


def get_git_status(workspace: str) -> Dict[str, Any]:
    git_path = os.path.join(workspace, ".git")
    present = os.path.isdir(git_path) or os.path.isfile(git_path)
    return {
        "present": present,
        "root": workspace if present else "",
    }


def validate_workspace(path: str) -> str:
    if not path:
        raise HTTPException(status_code=400, detail="workspace is required")
    full = os.path.abspath(path)
    if not os.path.isdir(full):
        raise HTTPException(status_code=400, detail="workspace path not found")
    if not os.path.isdir(os.path.join(full, "docs")):
        raise HTTPException(status_code=400, detail="workspace must include docs/")
    return full


def get_abs_path(workspace: str, path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(workspace, path)


def parse_int(value: Optional[str], fallback: int) -> int:
    try:
        return int(value) if value is not None else fallback
    except Exception:
        return fallback


def pm_command(settings: Settings, loop_mode: bool, resume: bool = False) -> List[str]:
    cmd = [
        sys.executable,
        get_abs_path(PROJECT_ROOT, LOOP_PM_PATH),
        "--workspace",
        settings.workspace or DEFAULT_WORKSPACE,
        "--pm-backend",
        settings.pm_backend or "codex",
        "--model",
        settings.model or DEFAULT_MODEL,
        "--timeout",
        str(settings.timeout or 0),
        "--json-log",
        settings.json_log_path or DEFAULT_PM_LOG,
    ]
    if settings.pm_show_output:
        cmd.append("--pm-show-output")
    if settings.prompt_profile:
        cmd.extend(["--prompt-profile", settings.prompt_profile])
    if settings.ramdisk_root:
        cmd.extend(["--ramdisk-root", settings.ramdisk_root])
    cmd.extend(
        [
            "--max-failures",
            str(settings.pm_max_failures or 5),
            "--max-blocked",
            str(settings.pm_max_blocked or 5),
            "--max-same-task",
            str(settings.pm_max_same or 3),
        ]
    )
    if loop_mode:
        cmd.extend(["--loop", "--interval", str(settings.interval or 20)])
        if resume:
            cmd.append("--resume")
    if settings.pm_runs_director:
        cmd.append("--run-director")
        if settings.pm_director_show_output:
            cmd.append("--director-show-output")
        cmd.extend(["--director-result-timeout", str(settings.pm_director_timeout or 60)])
        cmd.extend(["--director-iterations", str(settings.pm_director_iterations or 1)])
        if settings.pm_director_match_mode:
            cmd.extend(["--director-match-mode", settings.pm_director_match_mode])
    return cmd


def build_process_env(settings: Settings) -> Dict[str, str]:
    env: Dict[str, str] = {}
    env["HARBORPILOT_QA_ENABLED"] = "1" if settings.qa_enabled else "0"
    return env


def director_command(settings: Settings) -> List[str]:
    iterations = settings.director_iterations or 1
    cmd = [sys.executable, DIRECTOR_SCRIPT, "--workspace", settings.workspace or DEFAULT_WORKSPACE]
    if settings.prompt_profile:
        cmd.extend(["--prompt-profile", settings.prompt_profile])
    if settings.ramdisk_root:
        cmd.extend(["--ramdisk-root", settings.ramdisk_root])
    if settings.director_forever:
        cmd.append("--forever")
    else:
        cmd.extend(["--iterations", str(max(iterations, 1))])
    if settings.director_show_output:
        cmd.append("--show-output")
    return cmd


def terminate_process(handle: ProcessHandle) -> None:
    process = handle.process
    if process is None:
        return
    pid = None
    try:
        pid = process.pid
    except Exception:
        pid = None
    if os.name == "nt" and pid:
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    try:
        process.terminate()
    except Exception:
        pass
    try:
        process.wait(timeout=3)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=3)
        except Exception:
            pass
    handle.process = None
    handle.mode = ""
    handle.started_at = None
    if handle.log_handle is not None:
        try:
            handle.log_handle.close()
        except Exception:
            pass
        handle.log_handle = None


def clear_stop_flag(workspace: str) -> None:
    stop_flag = os.path.join(workspace, "state", "ollama", "PM_STOP.flag")
    try:
        if os.path.exists(stop_flag):
            os.remove(stop_flag)
    except Exception:
        pass


def spawn_process(cmd: List[str], cwd: str, log_path: str, extra_env: Optional[Dict[str, str]] = None) -> ProcessHandle:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_handle = open(log_path, "a", encoding="utf-8", errors="ignore")
    env = build_utf8_env(extra_env)
    process = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return ProcessHandle(process=process, log_handle=log_handle, log_path=log_path, started_at=time.time())


def build_snapshot(state: AppState) -> Dict[str, Any]:
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
    pm_out = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_OUT)
    pm_report = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_REPORT)
    pm_log = resolve_artifact_path(workspace, cache_root, state.settings.json_log_path or DEFAULT_PM_LOG)
    pm_subprocess_log = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
    director_subprocess_log = resolve_artifact_path(workspace, cache_root, DEFAULT_DIRECTOR_SUBPROCESS_LOG)
    dialogue_path = resolve_artifact_path(workspace, cache_root, DEFAULT_DIALOGUE)
    pm_state_path = resolve_artifact_path(workspace, cache_root, "state/ollama/PM_STATE.json")
    director_state_path = resolve_artifact_path(workspace, cache_root, "state/ollama/memory/last_state.json")
    planner_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PLANNER)
    ollama_path = resolve_artifact_path(workspace, cache_root, DEFAULT_OLLAMA)
    qa_path = resolve_artifact_path(workspace, cache_root, DEFAULT_QA)
    runlog_path = resolve_artifact_path(workspace, cache_root, DEFAULT_RUNLOG)
    agents_draft_path = resolve_artifact_path(workspace, cache_root, AGENTS_DRAFT_REL)
    agents_feedback_path = resolve_artifact_path(workspace, cache_root, AGENTS_FEEDBACK_REL)
    agents_target_path = os.path.join(workspace, "AGENTS.md")
    runtime_issues = build_runtime_issues(state.settings, workspace)

    file_entries = [
        ("PM_TASKS.json", pm_out),
        ("PM_REPORT.md", pm_report),
        ("PM_LOG.jsonl", pm_log),
        ("PM_SUBPROCESS.log", pm_subprocess_log),
        ("DIRECTOR_SUBPROCESS.log", director_subprocess_log),
        ("PM_STATE.json", pm_state_path),
        ("last_state.json", director_state_path),
        ("PM_TASK_HISTORY.jsonl", resolve_artifact_path(workspace, cache_root, "state/ollama/PM_TASK_HISTORY.jsonl")),
        ("PLANNER_RESPONSE.md", planner_path),
        ("OLLAMA_RESPONSE.md", ollama_path),
        ("QA_RESPONSE.md", qa_path),
        ("RUNLOG.md", runlog_path),
        ("DIRECTOR_RESULT.json", resolve_artifact_path(workspace, cache_root, "state/ollama/DIRECTOR_RESULT.json")),
        ("DIALOGUE.jsonl", dialogue_path),
    ]

    agents_review: Optional[Dict[str, Any]] = None
    has_agents = os.path.isfile(agents_target_path)
    has_draft = os.path.isfile(agents_draft_path)
    has_feedback = os.path.isfile(agents_feedback_path)
    if (not has_agents) or has_draft or has_feedback:
        draft_failed = False
        if has_draft:
            preview = read_file_head(agents_draft_path, max_chars=2000)
            lowered = preview.lower()
            draft_failed = ("generation failed" in lowered) or ("failed to write last message file" in lowered)
        agents_review = {
            "needs_review": not has_agents,
            "has_agents": has_agents,
            "draft_path": AGENTS_DRAFT_REL if has_draft else None,
            "feedback_path": AGENTS_FEEDBACK_REL if has_feedback else None,
            "draft_mtime": format_mtime(agents_draft_path) if has_draft else None,
            "feedback_mtime": format_mtime(agents_feedback_path) if has_feedback else None,
            "draft_failed": draft_failed,
        }

    payload = read_json(pm_out)
    if payload is None:
        payload = state.last_pm_payload or {}
    else:
        state.last_pm_payload = payload

    tasks = payload.get("tasks") if isinstance(payload, dict) else []
    pm_state_data = read_json(pm_state_path) or {}
    director_state_data = read_json(director_state_path) or {}
    git_status = get_git_status(workspace)

    return {
        "focus": str(payload.get("focus") or "").strip() if isinstance(payload, dict) else "",
        "notes": str(payload.get("notes") or "").strip() if isinstance(payload, dict) else "",
        "tasks": tasks if isinstance(tasks, list) else [],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_status": build_file_status(file_entries),
        "file_paths": [f"{label}: {path}" for label, path in file_entries],
        "pm_state": pm_state_data,
        "director_state": director_state_data,
        "git": git_status,
        "agents_review": agents_review,
        "runtime_issues": runtime_issues,
    }


def create_app(state: AppState, auth: Auth, cors_origins: List[str]) -> FastAPI:
    app = FastAPI(title="HarborPilot Desktop Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code >= 500:
            extra: Dict[str, Any] = {"status_code": exc.status_code, "path": request.url.path, "method": request.method}
            if request.url.path.startswith("/pm/"):
                workspace = state.settings.workspace or DEFAULT_WORKSPACE
                cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
                pm_log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
                tail = read_file_tail(pm_log_path, max_lines=200, max_chars=20000)
                if tail:
                    extra["pm_log_tail"] = tail
                    extra["log_path"] = pm_log_path
            log_backend_error("http_exception", str(exc.detail), **extra)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        extra: Dict[str, Any] = {"path": request.url.path, "method": request.method, "traceback": tb}
        if request.url.path.startswith("/pm/"):
            workspace = state.settings.workspace or DEFAULT_WORKSPACE
            cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
            pm_log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
            tail = read_file_tail(pm_log_path, max_lines=200, max_chars=20000)
            if tail:
                extra["pm_log_tail"] = tail
                extra["log_path"] = pm_log_path
        log_backend_error("unhandled_exception", str(exc), **extra)
        return JSONResponse(status_code=500, content={"detail": f"Internal error: {exc}"})

    def require_auth(request: Request) -> None:
        if not auth.check(request.headers.get("authorization", "")):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.post("/app/shutdown")
    def app_shutdown(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        terminate_process(state.director)
        terminate_process(state.pm)
        return {"ok": True}

    def build_pm_status() -> Dict[str, Any]:
        handle = state.pm
        return {
            "running": handle.process is not None and handle.process.poll() is None,
            "pid": handle.process.pid if handle.process else None,
            "started_at": handle.started_at,
            "mode": handle.mode,
            "log_path": handle.log_path,
        }

    def build_director_status() -> Dict[str, Any]:
        handle = state.director
        backend_running = handle.process is not None and handle.process.poll() is None
        backend_pid = handle.process.pid if handle.process else None
        if backend_running:
            return {
                "running": True,
                "pid": backend_pid,
                "started_at": handle.started_at,
                "mode": handle.mode,
                "log_path": handle.log_path,
            }

        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        pm_status = read_director_status(workspace, cache_root)
        pm_director_running = False
        pm_started_at: Optional[float] = None
        pm_pid: Optional[int] = None
        pm_mode: Optional[str] = None
        pm_log_path: Optional[str] = None
        if isinstance(pm_status, dict):
            pm_director_running = bool(pm_status.get("running"))
            started_at = pm_status.get("started_at")
            if isinstance(started_at, (int, float)):
                pm_started_at = float(started_at)
            else:
                try:
                    pm_started_at = float(started_at)
                except Exception:
                    pm_started_at = None
            pid_value = pm_status.get("pid")
            if isinstance(pid_value, int):
                pm_pid = pid_value
            pm_mode = str(pm_status.get("mode") or "pm").strip() if pm_status.get("mode") else "pm"
            pm_log_path = pm_status.get("log_path") if isinstance(pm_status.get("log_path"), str) else None

        if pm_director_running:
            return {
                "running": True,
                "pid": pm_pid,
                "started_at": pm_started_at,
                "mode": pm_mode,
                "log_path": pm_log_path
                or resolve_artifact_path(workspace, cache_root, DEFAULT_DIRECTOR_SUBPROCESS_LOG),
            }

        return {
            "running": False,
            "pid": None,
            "started_at": None,
            "mode": handle.mode or None,
            "log_path": handle.log_path
            or resolve_artifact_path(workspace, cache_root, DEFAULT_DIRECTOR_SUBPROCESS_LOG),
        }

    def build_status_payload() -> Dict[str, Any]:
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        memory_payload: Optional[Dict[str, Any]] = None
        if state.settings.show_memory:
            memory_payload = build_memory_payload(workspace, cache_root)
        return {
            "pm_status": build_pm_status(),
            "director_status": build_director_status(),
            "snapshot": build_snapshot(state),
            "lancedb": get_lancedb_status(),
            "memory": memory_payload,
            "success_stats": build_success_stats_payload(workspace, cache_root),
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    @app.get("/health")
    def health(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        lancedb_status = get_lancedb_status()
        return {
            "ok": bool(lancedb_status.get("ok")),
            "version": "0.1",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "lancedb_ok": bool(lancedb_status.get("ok")),
            "lancedb_error": lancedb_status.get("error"),
            "python": lancedb_status.get("python"),
        }

    @app.get("/settings")
    def get_settings(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        return state.settings.model_dump()

    @app.post("/settings")
    def update_settings(payload: SettingsUpdate, _: Any = Depends(require_auth)) -> Dict[str, Any]:
        if payload.workspace:
            payload.workspace = validate_workspace(payload.workspace)
        state.settings.apply_update(payload)
        save_persisted_settings(state.settings)
        return state.settings.model_dump()

    @app.get("/state/snapshot")
    def state_snapshot(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        return build_snapshot(state)

    @app.get("/files/read")
    def read_file(
        path: str,
        tail_lines: int = 400,
        max_chars: int = 20000,
        _: Any = Depends(require_auth),
    ) -> Dict[str, Any]:
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        full_path = resolve_safe_path(workspace, cache_root, path)
        content = read_file_tail(full_path, max_lines=tail_lines, max_chars=max_chars)
        return {
            "path": full_path,
            "rel_path": path,
            "mtime": format_mtime(full_path),
            "content": content,
        }

    @app.post("/agents/apply")
    def apply_agents(payload: AgentsApplyPayload, _: Any = Depends(require_auth)) -> Dict[str, Any]:
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        draft_rel = payload.draft_path or AGENTS_DRAFT_REL
        draft_path = resolve_safe_path(workspace, cache_root, draft_rel)
        target_path = os.path.join(workspace, "AGENTS.md")
        if not os.path.isfile(draft_path):
            raise HTTPException(status_code=404, detail="draft not found")
        if os.path.isfile(target_path):
            raise HTTPException(status_code=409, detail="AGENTS.md already exists")
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copyfile(draft_path, target_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"failed to copy AGENTS.md: {exc}")
        return {"ok": True, "target_path": target_path}

    @app.post("/agents/feedback")
    def save_agents_feedback(payload: AgentsFeedbackPayload, _: Any = Depends(require_auth)) -> Dict[str, Any]:
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        feedback_path = resolve_artifact_path(workspace, cache_root, AGENTS_FEEDBACK_REL)
        text = (payload.text or "").strip()
        if not text:
            # allow clearing feedback
            try:
                if os.path.isfile(feedback_path):
                    os.remove(feedback_path)
            except Exception:
                pass
            return {"ok": True, "cleared": True}
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = f"## {timestamp}\n{text}\n"
        try:
            os.makedirs(os.path.dirname(feedback_path), exist_ok=True)
            with open(feedback_path, "w", encoding="utf-8") as handle:
                handle.write(content)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"failed to save feedback: {exc}")
        return {"ok": True, "path": feedback_path, "mtime": format_mtime(feedback_path)}

    @app.get("/memos/list")
    def list_memos(
        limit: int = 200,
        _: Any = Depends(require_auth),
    ) -> Dict[str, Any]:
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        memos_dir = resolve_artifact_path(workspace, cache_root, os.path.join("state", "ollama", "memos"))
        index_path = resolve_artifact_path(workspace, cache_root, os.path.join("state", "ollama", "memos", "index.jsonl"))
        records: List[Dict[str, Any]] = []
        if os.path.isfile(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except Exception:
                            continue
                        if isinstance(record, dict):
                            records.append(record)
            except Exception:
                records = []
        if not records and os.path.isdir(memos_dir):
            try:
                for entry in os.scandir(memos_dir):
                    if not entry.is_file():
                        continue
                    if not entry.name.lower().endswith(".md"):
                        continue
                    if entry.name.lower().startswith("pm_memo_summary"):
                        continue
                    rel_path = os.path.join("state", "ollama", "memos", entry.name).replace("\\", "/")
                    records.append(
                        {
                            "timestamp": format_mtime(entry.path),
                            "rel_path": rel_path,
                            "task_id": "",
                            "task_title": "",
                            "summary": "",
                        }
                    )
            except Exception:
                records = []
        def _record_ts(item: Dict[str, Any]) -> float:
            raw = str(item.get("timestamp") or "")
            try:
                return datetime.fromisoformat(raw).timestamp()
            except Exception:
                return 0.0

        records.sort(key=_record_ts, reverse=True)
        trimmed = records[: max(1, limit)]
        items: List[Dict[str, Any]] = []
        for record in trimmed:
            rel_path = str(record.get("rel_path") or "")
            full_path = resolve_safe_path(workspace, cache_root, rel_path) if rel_path else ""
            items.append(
                {
                    "name": os.path.basename(rel_path) if rel_path else "",
                    "path": rel_path,
                    "mtime": format_mtime(full_path) if full_path else "",
                    "summary": record.get("summary") or "",
                    "task_id": record.get("task_id") or "",
                    "task_title": record.get("task_title") or "",
                    "status": record.get("status") or "",
                    "acceptance": record.get("acceptance"),
                    "run_id": record.get("run_id") or "",
                    "director_attempt": record.get("director_attempt") or None,
                }
            )
        return {"items": items, "count": len(items)}

    @app.get("/pm/status")
    def pm_status(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        return build_pm_status()

    @app.get("/director/status")
    def director_status(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        return build_director_status()

    def list_ollama_models() -> List[str]:
        if not shutil.which("ollama"):
            raise HTTPException(status_code=500, detail="ollama command not found in PATH.")
        try:
            result = subprocess.run(
                ["ollama", "ps"],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=build_utf8_env(),
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"ollama ps failed: {exc}")
        if result.returncode != 0:
            msg = (result.stderr or result.stdout or "ollama ps failed").strip()
            raise HTTPException(status_code=500, detail=msg)
        lines = result.stdout.splitlines()
        models: List[str] = []
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            name = line.split()[0].strip()
            if name and name.lower() != "name":
                models.append(name)
        return models

    @app.get("/ollama/ps")
    def ollama_ps(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        models = list_ollama_models()
        return {"ok": True, "models": models}

    @app.post("/ollama/stop")
    def ollama_stop(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        models = list_ollama_models()
        if not models:
            return {"ok": True, "stopped": [], "failed": [], "models": []}
        stopped: List[str] = []
        failed: List[Dict[str, str]] = []
        for name in models:
            try:
                result = subprocess.run(
                    ["ollama", "stop", name],
                    cwd=PROJECT_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=build_utf8_env(),
                )
            except Exception as exc:
                failed.append({"model": name, "error": str(exc)})
                continue
            if result.returncode == 0:
                stopped.append(name)
            else:
                msg = (result.stderr or result.stdout or "ollama stop failed").strip()
                failed.append({"model": name, "error": msg})
        return {"ok": True, "stopped": stopped, "failed": failed, "models": models}

    @app.get("/lancedb/status")
    def lancedb_status(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        return get_lancedb_status()

    @app.post("/pm/run_once")
    def pm_run_once(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        if state.pm.process is not None and state.pm.process.poll() is None:
            raise HTTPException(status_code=409, detail="pm already running")
        require_lancedb()
        precheck_error = check_backend_available(state.settings)
        if precheck_error:
            workspace = state.settings.workspace or DEFAULT_WORKSPACE
            cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
            pm_log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
            try:
                os.makedirs(os.path.dirname(pm_log_path), exist_ok=True)
                with open(pm_log_path, "a", encoding="utf-8") as handle:
                    handle.write(precheck_error + "\n")
            except Exception:
                pass
            log_backend_error(
                "pm_start_failed",
                precheck_error,
                mode="once",
                log_path=pm_log_path,
            )
            raise HTTPException(status_code=500, detail=precheck_error)
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        clear_stop_flag(workspace)
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        pm_log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
        cmd = pm_command(state.settings, loop_mode=False)
        try:
            state.pm = spawn_process(cmd, PROJECT_ROOT, pm_log_path, build_process_env(state.settings))
        except Exception as exc:
            detail = f"pm failed to spawn: {exc}"
            log_backend_error(
                "pm_start_failed",
                detail,
                mode="once",
                log_path=pm_log_path,
                cmd=cmd,
            )
            raise HTTPException(status_code=500, detail=detail)
        state.pm.mode = "once"
        # quick health check: if process exits immediately, surface an error with log tail
        try:
            time.sleep(0.5)
        except Exception:
            pass
        if state.pm.process is None or state.pm.process.poll() is not None:
            exit_code = state.pm.process.poll() if state.pm.process is not None else None
            stop_flag = os.path.join(workspace, "state", "ollama", "PM_STOP.flag")
            stop_flag_present = os.path.exists(stop_flag)
            tail = read_file_tail(state.pm.log_path, max_lines=200, max_chars=20000)
            terminate_process(state.pm)
            detail = "pm failed to start: exited immediately"
            if stop_flag_present:
                detail = f"pm failed to start: stop requested (found {stop_flag})"
            if exit_code is not None:
                detail = f"{detail} (exit={exit_code})"
            if tail:
                detail = f"{detail}\n{tail}"
            log_backend_error(
                "pm_start_failed",
                detail,
                mode="once",
                log_path=pm_log_path,
                cmd=cmd,
                exit_code=exit_code,
                stop_flag=stop_flag if stop_flag_present else None,
            )
            raise HTTPException(status_code=500, detail=detail)
        return {"ok": True, "pid": state.pm.process.pid}

    @app.post("/pm/start_loop")
    def pm_start_loop(resume: bool = False, _: Any = Depends(require_auth)) -> Dict[str, Any]:
        if state.pm.process is not None and state.pm.process.poll() is None:
            raise HTTPException(status_code=409, detail="pm already running")
        require_lancedb()
        precheck_error = check_backend_available(state.settings)
        if precheck_error:
            workspace = state.settings.workspace or DEFAULT_WORKSPACE
            cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
            pm_log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
            try:
                os.makedirs(os.path.dirname(pm_log_path), exist_ok=True)
                with open(pm_log_path, "a", encoding="utf-8") as handle:
                    handle.write(precheck_error + "\n")
            except Exception:
                pass
            log_backend_error(
                "pm_start_failed",
                precheck_error,
                mode="loop",
                log_path=pm_log_path,
            )
            raise HTTPException(status_code=500, detail=precheck_error)
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        clear_stop_flag(workspace)
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        pm_log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
        cmd = pm_command(state.settings, loop_mode=True, resume=resume)
        try:
            state.pm = spawn_process(cmd, PROJECT_ROOT, pm_log_path, build_process_env(state.settings))
        except Exception as exc:
            detail = f"pm failed to spawn: {exc}"
            log_backend_error(
                "pm_start_failed",
                detail,
                mode="loop",
                log_path=pm_log_path,
                cmd=cmd,
            )
            raise HTTPException(status_code=500, detail=detail)
        state.pm.mode = "loop"
        # quick health check: if process exits immediately, surface an error with log tail
        try:
            time.sleep(0.5)
        except Exception:
            pass
        if state.pm.process is None or state.pm.process.poll() is not None:
            exit_code = state.pm.process.poll() if state.pm.process is not None else None
            stop_flag = os.path.join(workspace, "state", "ollama", "PM_STOP.flag")
            stop_flag_present = os.path.exists(stop_flag)
            tail = read_file_tail(state.pm.log_path, max_lines=200, max_chars=20000)
            terminate_process(state.pm)
            detail = "pm failed to start: exited immediately"
            if stop_flag_present:
                detail = f"pm failed to start: stop requested (found {stop_flag})"
            if exit_code is not None:
                detail = f"{detail} (exit={exit_code})"
            if tail:
                detail = f"{detail}\n{tail}"
            log_backend_error(
                "pm_start_failed",
                detail,
                mode="loop",
                log_path=pm_log_path,
                cmd=cmd,
                exit_code=exit_code,
                stop_flag=stop_flag if stop_flag_present else None,
            )
            raise HTTPException(status_code=500, detail=detail)
        return {"ok": True, "pid": state.pm.process.pid}

    @app.post("/pm/stop")
    def pm_stop(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        stop_flag = os.path.join(workspace, "state", "ollama", "PM_STOP.flag")
        try:
            os.makedirs(os.path.dirname(stop_flag), exist_ok=True)
            with open(stop_flag, "w", encoding="utf-8") as handle:
                handle.write("stop\n")
        except Exception:
            pass
        running = state.pm.process is not None and state.pm.process.poll() is None
        if not running:
            raise HTTPException(status_code=409, detail="pm not running")
        terminate_process(state.pm)
        return {"ok": True}

    @app.post("/director/start")
    def director_start(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        if state.director.process is not None and state.director.process.poll() is None:
            raise HTTPException(status_code=409, detail="director already running")
        require_lancedb()
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        agents_path = os.path.join(workspace, "AGENTS.md")
        if not os.path.isfile(agents_path):
            cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
            draft_path = resolve_artifact_path(workspace, cache_root, AGENTS_DRAFT_REL)
            if os.path.isfile(draft_path):
                preview = read_file_head(draft_path, max_chars=2000).lower()
                if ("generation failed" in preview) or ("failed to write last message file" in preview):
                    raise HTTPException(
                        status_code=409,
                        detail="AGENTS.md required. AGENTS.generated.md generation failed; retry PM to regenerate.",
                    )
            raise HTTPException(status_code=409, detail="AGENTS.md required. Review AGENTS.generated.md first.")
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        director_log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_DIRECTOR_SUBPROCESS_LOG)
        cmd = director_command(state.settings)
        state.director = spawn_process(cmd, PROJECT_ROOT, director_log_path, build_process_env(state.settings))
        state.director.mode = "direct"
        return {"ok": True, "pid": state.director.process.pid}

    @app.post("/director/stop")
    def director_stop(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        terminate_process(state.director)
        return {"ok": True}

    @app.get("/history/runs")
    def history_runs_list(_: Any = Depends(require_auth)) -> Dict[str, Any]:
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        base_root = cache_root or workspace
        runs_root = os.path.join(base_root, "state", "ollama", "runs")
        
        runs = []
        if os.path.isdir(runs_root):
            for name in os.listdir(runs_root):
                path = os.path.join(runs_root, name)
                if not os.path.isdir(path) or name == "latest":
                    continue
                
                run_data = {"id": name}
                
                # Try reading trajectory.json first
                traj_path = os.path.join(path, "trajectory.json")
                if os.path.isfile(traj_path):
                    try:
                        with open(traj_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            run_data["timestamp"] = meta.get("timestamp")
                            if "summary" in meta:
                                run_data.update(meta["summary"])
                            if "task_id" in meta:
                                run_data["task_id"] = meta["task_id"]
                    except Exception:
                        pass
                
                # Fallback to DIRECTOR_RESULT.json
                if "status" not in run_data:
                    result_path = os.path.join(path, "DIRECTOR_RESULT.json")
                    if os.path.isfile(result_path):
                        try:
                            with open(result_path, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                                run_data["status"] = meta.get("status")
                                run_data["task_id"] = meta.get("task_id")
                                run_data["duration"] = meta.get("duration")
                        except Exception:
                            pass
                
                # Get mtime if no timestamp
                if "timestamp" not in run_data:
                    try:
                        mtime = os.path.getmtime(path)
                        run_data["timestamp"] = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass
                
                runs.append(run_data)
        
        # Sort by ID desc
        runs.sort(key=lambda x: x["id"], reverse=True)
        return {"runs": runs}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        token = websocket.query_params.get("token", "")
        if auth.token and token != auth.token:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        connection = ConnectionState()
        poll_interval = 1.0

        async def poll_loop() -> None:
            while True:
                await asyncio.sleep(poll_interval)
                if connection.want_status:
                    payload = {
                        "type": "status",
                        **build_status_payload(),
                    }
                    try:
                        await websocket.send_text(json.dumps(payload))
                    except Exception:
                        return
                if not connection.channels:
                    continue
                workspace = state.settings.workspace or DEFAULT_WORKSPACE
                cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
                for channel in list(connection.channels):
                    rel_path = CHANNEL_FILES.get(channel)
                    if not rel_path:
                        continue
                    path = resolve_artifact_path(workspace, cache_root, rel_path)
                    lines = read_incremental(path, connection.tail_state.setdefault(channel, {}))
                    if not lines:
                        continue
                    for line in lines:
                        payload = {
                            "type": "line",
                            "channel": channel,
                            "text": line,
                            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        }
                        try:
                            await websocket.send_text(json.dumps(payload))
                        except Exception:
                            return

        poll_task = asyncio.create_task(poll_loop())
        try:
            while True:
                message = await websocket.receive_text()
                try:
                    payload = json.loads(message)
                except Exception:
                    continue
                msg_type = payload.get("type")
                if msg_type == "subscribe":
                    channels = payload.get("channels") or []
                    if isinstance(channels, list):
                        connection.channels = {c for c in channels if c in CHANNEL_FILES}
                        connection.want_status = "status" in channels
                    if payload.get("tail_lines"):
                        tail_lines = int(payload.get("tail_lines") or 200)
                        workspace = state.settings.workspace or DEFAULT_WORKSPACE
                        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
                        for channel in connection.channels:
                            rel_path = CHANNEL_FILES.get(channel)
                            if not rel_path:
                                continue
                            path = resolve_artifact_path(workspace, cache_root, rel_path)
                            text = read_file_tail(path, max_lines=tail_lines, max_chars=20000)
                            lines = text.splitlines() if text else []
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "snapshot",
                                        "channel": channel,
                                        "lines": lines,
                                        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                                    }
                                )
                            )
                elif msg_type == "snapshot":
                    channels = payload.get("channels") or []
                    if isinstance(channels, list):
                        workspace = state.settings.workspace or DEFAULT_WORKSPACE
                        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
                        for channel in channels:
                            rel_path = CHANNEL_FILES.get(channel)
                            if not rel_path:
                                continue
                            path = resolve_artifact_path(workspace, cache_root, rel_path)
                            text = read_file_tail(path, max_lines=200, max_chars=20000)
                            lines = text.splitlines() if text else []
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "type": "snapshot",
                                        "channel": channel,
                                        "lines": lines,
                                        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                                    }
                                )
                            )
                else:
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": "unknown message"})
                    )
        except WebSocketDisconnect:
            pass
        finally:
            poll_task.cancel()

    return app


def pick_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token", default=os.environ.get("HARBORPILOT_TOKEN", ""))
    parser.add_argument("--workspace", default=os.environ.get("HARBORPILOT_WORKSPACE", ""))
    parser.add_argument("--log-level", default=os.environ.get("HARBORPILOT_LOG_LEVEL", "info"))
    parser.add_argument("--cors-origins", default=os.environ.get("HARBORPILOT_CORS_ORIGINS", "http://localhost:5173"))
    args = parser.parse_args()

    workspace_arg = args.workspace.strip() if args.workspace else ""
    explicit_workspace = bool(workspace_arg)
    if workspace_arg:
        try:
            workspace = validate_workspace(workspace_arg)
        except HTTPException as exc:
            print(json.dumps({"event": "startup_error", "error": exc.detail}), file=sys.stderr)
            return 2
    else:
        workspace = DEFAULT_WORKSPACE

    settings = Settings(workspace=workspace)
    persisted = load_persisted_settings()
    if persisted:
        if explicit_workspace:
            persisted.pop("workspace", None)
        else:
            saved_ws = persisted.get("workspace")
            if saved_ws:
                try:
                    persisted["workspace"] = validate_workspace(saved_ws)
                except HTTPException:
                    persisted.pop("workspace", None)
        try:
            settings.apply_update(SettingsUpdate(**persisted))
        except Exception:
            pass

    auth = Auth(args.token or "")
    cors_origins = [origin.strip() for origin in (args.cors_origins or "").split(",") if origin.strip()]

    app = create_app(AppState(settings=settings), auth, cors_origins)
    port = args.port if args.port else pick_free_port()
    print(json.dumps({"event": "backend_started", "port": port}), flush=True)

    import uvicorn

    uvicorn.run(app, host=args.host, port=port, log_level=args.log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
