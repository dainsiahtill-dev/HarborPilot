import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

_JSONL_LOCK_STALE_SEC = float(os.environ.get("HARBORPILOT_JSONL_LOCK_STALE_SEC", "120") or 120)
_RAMDISK_ENV = "HARBORPILOT_RAMDISK_ROOT"
_STATE_TO_RAMDISK_ENV = "HARBORPILOT_STATE_TO_RAMDISK"
_IO_FSYNC_ENV = "HARBORPILOT_IO_FSYNC_MODE"
ARTIFACT_ROOT = ".harborpilot"
LEGACY_ARTIFACT_ROOT = "state"
ARTIFACT_NAMESPACE = "runtime"
LEGACY_ARTIFACT_NAMESPACE = "ollama"


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


def find_workspace_root(start: str) -> str:
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, "docs")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return ""


def resolve_workspace_path(path: str, *, require_docs: bool = True) -> str:
    start = (path or "").strip()
    if not start:
        start = os.getcwd()
    start = os.path.abspath(start)
    if not os.path.isdir(start):
        raise ValueError(f"Workspace path does not exist: {start}")
    root = find_workspace_root(start)
    if not root:
        if require_docs:
            raise ValueError(f"No docs/ directory found at or above workspace: {start}")
        return start
    if os.path.abspath(root) != start:
        print(f"[workspace] Using '{root}' (found docs/ above '{start}').")
    return root


WORKSPACE_STATUS_REL = os.path.join(ARTIFACT_ROOT, "WORKSPACE_STATUS.json")


def normalize_artifact_rel_path(rel_path: str) -> str:
    if not rel_path:
        return rel_path
    p = rel_path.replace("\\", "/").lstrip("./")
    plain_prefix = "harborpilot/"
    if p.startswith(plain_prefix):
        return f"{ARTIFACT_ROOT}/" + p[len(plain_prefix):]
    legacy_prefix = f"{LEGACY_ARTIFACT_ROOT}/{LEGACY_ARTIFACT_NAMESPACE}/"
    if p.startswith(legacy_prefix):
        return f"{ARTIFACT_ROOT}/{ARTIFACT_NAMESPACE}/" + p[len(legacy_prefix):]
    legacy_root_prefix = f"{LEGACY_ARTIFACT_ROOT}/"
    if p.startswith(legacy_root_prefix):
        return f"{ARTIFACT_ROOT}/{ARTIFACT_NAMESPACE}/" + p[len(legacy_root_prefix):]
    legacy_dot_prefix = f"{ARTIFACT_ROOT}/{LEGACY_ARTIFACT_NAMESPACE}/"
    if p.startswith(legacy_dot_prefix):
        return f"{ARTIFACT_ROOT}/{ARTIFACT_NAMESPACE}/" + p[len(legacy_dot_prefix):]
    return p


def _strip_artifact_root_prefix(rel_path: str) -> str:
    if not rel_path:
        return rel_path
    p = rel_path.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    prefix = f"{ARTIFACT_ROOT}/"
    if p.startswith(prefix):
        return p[len(prefix):]
    return p


def _artifact_base_dir(workspace_full: str, cache_root_full: str) -> str:
    if cache_root_full:
        return cache_root_full
    return os.path.join(workspace_full, ARTIFACT_ROOT)


def _legacy_double_artifact_path(path: str) -> str:
    if not path:
        return ""
    marker = f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}"
    if marker in path:
        return ""
    runtime_marker = f"{os.sep}{ARTIFACT_NAMESPACE}{os.sep}"
    if runtime_marker in path:
        return path.replace(
            runtime_marker,
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            1,
        )
    return ""


def legacy_artifact_rel_path(rel_path: str) -> str:
    if not rel_path:
        return ""
    p = rel_path.replace("\\", "/").lstrip("./")
    new_prefix = f"{ARTIFACT_ROOT}/{ARTIFACT_NAMESPACE}/"
    if p.startswith(new_prefix):
        return f"{ARTIFACT_ROOT}/{LEGACY_ARTIFACT_NAMESPACE}/" + p[len(new_prefix):]
    return ""


def workspace_has_docs(workspace: str) -> bool:
    if not workspace:
        return False
    return os.path.isdir(os.path.join(workspace, "docs"))


def workspace_status_path(workspace: str) -> str:
    if not workspace:
        return ""
    return os.path.join(workspace, WORKSPACE_STATUS_REL)


def write_workspace_status(
    workspace: str,
    *,
    status: str,
    reason: str,
    actions: Optional[List[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    if not workspace:
        return
    payload: Dict[str, Any] = {
        "status": status,
        "reason": reason,
        "actions": actions or [],
        "workspace_path": os.path.abspath(workspace),
        "timestamp": utc_iso_now(),
    }
    if isinstance(extra, dict):
        payload.update(extra)
    write_json_atomic(workspace_status_path(workspace), payload)


def clear_workspace_status(workspace: str) -> None:
    path = workspace_status_path(workspace)
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def read_workspace_status(workspace: str) -> Optional[Dict[str, Any]]:
    path = workspace_status_path(workspace)
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def normalize_ramdisk_root(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if not os.path.isabs(raw):
        return ""
    if re.match(r"^[a-zA-Z]:$", raw):
        raw = raw + "\\"
    raw = os.path.abspath(raw)
    raw = raw.rstrip("\\/")
    if re.match(r"^[a-zA-Z]:$", raw):
        raw = raw + "\\"
    return raw


def default_ramdisk_root() -> str:
    if os.name != "nt":
        return ""
    if os.path.exists("X:\\"):
        return "X:\\"
    return ""


def resolve_ramdisk_root(cli_value: Optional[str] = None) -> str:
    if cli_value is not None and str(cli_value).strip():
        return normalize_ramdisk_root(str(cli_value))
    env_value = os.environ.get(_RAMDISK_ENV, "").strip()
    if env_value:
        return normalize_ramdisk_root(env_value)
    return normalize_ramdisk_root(default_ramdisk_root())


def state_to_ramdisk_enabled() -> bool:
    value = os.environ.get(_STATE_TO_RAMDISK_ENV, "1").strip().lower()
    return value not in ("0", "false", "no", "off")


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
    ws_abs = os.path.abspath(workspace_full or "")
    if ws_abs:
        try:
            if os.path.commonpath([ws_abs, root]) == ws_abs:
                return ""
        except Exception:
            pass
    ws = os.path.abspath(workspace_full or "").lower()
    digest = hashlib.sha1(ws.encode("utf-8", errors="ignore")).hexdigest()[:12]
    base_name = os.path.basename(root.rstrip("\\/")).lower()
    if base_name in ("harborpilot", ".harborpilot"):
        return os.path.join(root, "cache", digest)
    return os.path.join(root, ".harborpilot", "cache", digest)


def is_hot_artifact_path(rel_path: str) -> bool:
    p = normalize_artifact_rel_path(rel_path)
    if p.startswith(f"{ARTIFACT_ROOT}/") and state_to_ramdisk_enabled():
        return True
    if not p.startswith(f"{ARTIFACT_ROOT}/{ARTIFACT_NAMESPACE}/"):
        return False
    if "/runs/" in p or p.startswith(f"{ARTIFACT_ROOT}/{ARTIFACT_NAMESPACE}/runs/"):
        return True
    if "/memory/" in p or p.startswith(f"{ARTIFACT_ROOT}/{ARTIFACT_NAMESPACE}/memory/"):
        return True
    if "/evidence/" in p or p.startswith(f"{ARTIFACT_ROOT}/{ARTIFACT_NAMESPACE}/evidence/"):
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


def resolve_run_dir(workspace_full: str, cache_root_full: str, run_id: str) -> str:
    if not run_id:
        return ""
    base_root = _artifact_base_dir(workspace_full, cache_root_full)
    return os.path.join(base_root, ARTIFACT_NAMESPACE, "runs", run_id)


def update_latest_pointer(workspace_full: str, cache_root_full: str, run_id: str) -> None:
    if not run_id:
        return
    base_root = _artifact_base_dir(workspace_full, cache_root_full)
    latest_dir = os.path.join(base_root, ARTIFACT_NAMESPACE, "runs", "latest")
    run_dir = resolve_run_dir(workspace_full, cache_root_full, run_id)
    
    # Update latest_run.json for Windows compatibility (and Dashboard reading)
    pointer_path = os.path.join(base_root, ARTIFACT_NAMESPACE, "latest_run.json")
    write_json_atomic(pointer_path, {"run_id": run_id, "path": run_dir})

    # Try to create symlink if possible (best effort)
    if os.path.exists(latest_dir):
        try:
            if os.path.islink(latest_dir):
                os.remove(latest_dir)
            elif os.path.isdir(latest_dir):
                # Don't delete if it's a real directory unless we are sure it's a symlink
                pass 
        except Exception:
            pass
    
    try:
        # On Windows, symlink requires Admin or Developer Mode enabled.
        # Fallback is to rely on latest_run.json
        os.symlink(run_dir, latest_dir, target_is_directory=True)
    except Exception:
        pass


def resolve_artifact_path(workspace_full: str, cache_root_full: str, rel_path: str, run_id: Optional[str] = None) -> str:
    if not rel_path:
        return ""
    if os.path.isabs(rel_path):
        return rel_path
    
    # If run_id is provided and path is a "run-specific" artifact, redirect to run bucket
    if run_id and is_run_artifact(rel_path):
        run_dir = resolve_run_dir(workspace_full, cache_root_full, run_id)
        basename = os.path.basename(rel_path)
        return os.path.join(run_dir, basename)

    p = normalize_artifact_rel_path(rel_path)
    if p.startswith(f"{ARTIFACT_ROOT}/") and state_to_ramdisk_enabled():
        if not cache_root_full:
            raise ValueError(f"{ARTIFACT_ROOT}/ must be stored on ramdisk, but no ramdisk cache root is configured")
        return os.path.join(cache_root_full, _strip_artifact_root_prefix(p))
    base = cache_root_full if (cache_root_full and is_hot_artifact_path(p)) else workspace_full
    if base == cache_root_full and p.startswith(f"{ARTIFACT_ROOT}/"):
        return os.path.join(base, _strip_artifact_root_prefix(p))
    return os.path.join(base, p)


def is_run_artifact(rel_path: str) -> bool:
    """Check if the artifact should be stored in a run-specific bucket."""
    lowered = rel_path.lower().replace("\\", "/")
    if lowered.endswith("director_result.json"):
        return True
    if lowered.endswith("events.jsonl"):
        return True
    if lowered.endswith("trajectory.json"):
        return True
    if lowered.endswith("qa_response.md"):
        return True
    if lowered.endswith("planner_response.md"):
        return True
    if lowered.endswith("ollama_response.md"):
        return True
    if lowered.endswith("reviewer_response.md"):
        return True
    if lowered.endswith("runlog.md"):
        return True
    return False


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def write_text_atomic(path: str, text: str) -> None:
    if not path:
        return
    ensure_parent_dir(path)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text or "")
        handle.flush()
        if _fsync_enabled():
            os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def write_json_atomic(path: str, data: Dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    write_text_atomic(path, payload + "\n")


def ensure_memory_dir(path: str) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


def stop_flag_path(workspace: str) -> str:
    if state_to_ramdisk_enabled():
        cache_root = build_cache_root(resolve_ramdisk_root(None), workspace)
        if not cache_root:
            raise ValueError(f"{ARTIFACT_ROOT}/ must be stored on ramdisk, but no ramdisk cache root is configured")
        return os.path.join(cache_root, ARTIFACT_NAMESPACE, "PM_STOP.flag")
    return os.path.join(workspace, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "PM_STOP.flag")


def stop_requested(workspace: str) -> bool:
    try:
        return os.path.exists(stop_flag_path(workspace))
    except Exception:
        return False


def clear_stop_flag(workspace: str) -> None:
    paths = set()
    try:
        paths.add(stop_flag_path(workspace))
    except Exception:
        pass


def _fsync_enabled() -> bool:
    value = os.environ.get(_IO_FSYNC_ENV, "strict").strip().lower()
    return value not in ("0", "false", "no", "off", "relaxed", "skip", "disabled")
    paths.add(os.path.join(workspace, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "PM_STOP.flag"))
    paths.add(os.path.join(workspace, ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "PM_STOP.flag"))
    paths.add(os.path.join(workspace, LEGACY_ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "PM_STOP.flag"))
    for path in paths:
        if not path:
            continue
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def director_stop_flag_path(workspace: str) -> str:
    if state_to_ramdisk_enabled():
        cache_root = build_cache_root(resolve_ramdisk_root(None), workspace)
        if not cache_root:
            raise ValueError(f"{ARTIFACT_ROOT}/ must be stored on ramdisk, but no ramdisk cache root is configured")
        return os.path.join(cache_root, ARTIFACT_NAMESPACE, "DIRECTOR_STOP.flag")
    return os.path.join(workspace, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "DIRECTOR_STOP.flag")


def director_stop_requested(workspace: str) -> bool:
    try:
        return os.path.exists(director_stop_flag_path(workspace))
    except Exception:
        return False


def clear_director_stop_flag(workspace: str) -> None:
    paths = set()
    try:
        paths.add(director_stop_flag_path(workspace))
    except Exception:
        pass
    paths.add(os.path.join(workspace, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "DIRECTOR_STOP.flag"))
    paths.add(os.path.join(workspace, ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "DIRECTOR_STOP.flag"))
    paths.add(os.path.join(workspace, LEGACY_ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE, "DIRECTOR_STOP.flag"))
    for path in paths:
        if not path:
            continue
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _acquire_lock(lock_path: str, timeout_sec: float = 5.0, poll_sec: float = 0.05) -> Optional[int]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, f"{os.getpid()} {time.time()}".encode("utf-8"))
            return fd
        except FileExistsError:
            stale_sec = _JSONL_LOCK_STALE_SEC
            if stale_sec and stale_sec > 0:
                try:
                    mtime = os.path.getmtime(lock_path)
                    if time.time() - mtime > stale_sec:
                        try:
                            os.remove(lock_path)
                            continue
                        except Exception:
                            pass
                except Exception:
                    pass
            time.sleep(poll_sec)
        except Exception:
            return None
    return None


def _release_lock(fd: int, lock_path: str) -> None:
    try:
        os.close(fd)
    finally:
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass
        except Exception:
            pass


def append_jsonl_atomic(path: str, obj: Dict[str, Any], lock_timeout_sec: float = 5.0) -> None:
    if not path:
        return
    ensure_parent_dir(path)
    lock_path = path + ".lock"
    fd = _acquire_lock(lock_path, timeout_sec=lock_timeout_sec)
    if fd is None:
        try:
            _register_jsonl_flush()
            line = json.dumps(obj, ensure_ascii=False) + "\n"
            with _JSONL_BUFFER_LOCK:
                state = _JSONL_BUFFER.setdefault(path, {"lines": [], "last_flush": time.time()})
                state["lines"].append(line)
                if len(state["lines"]) > _JSONL_MAX_BUFFER:
                    state["lines"] = state["lines"][-_JSONL_MAX_BUFFER:]
            flush_jsonl_buffers(force=False, lock_timeout_sec=lock_timeout_sec)
        except Exception:
            pass
        return
    try:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
            handle.flush()
            if _fsync_enabled():
                os.fsync(handle.fileno())
    finally:
        _release_lock(fd, lock_path)


_JSONL_BUFFER_ENABLED = os.environ.get("HARBORPILOT_JSONL_BUFFERED", "1").strip().lower() not in ("0", "false", "no")
_JSONL_FLUSH_INTERVAL = float(os.environ.get("HARBORPILOT_JSONL_FLUSH_INTERVAL", "1.0") or 1.0)
_JSONL_FLUSH_BATCH = int(os.environ.get("HARBORPILOT_JSONL_FLUSH_BATCH", "50") or 50)
_JSONL_MAX_BUFFER = int(os.environ.get("HARBORPILOT_JSONL_MAX_BUFFER", "2000") or 2000)
_JSONL_BUFFER: Dict[str, Dict[str, Any]] = {}
_JSONL_BUFFER_LOCK = Lock()
_JSONL_ATEXIT_REGISTERED = False


def configure_jsonl_buffer(
    buffered: Optional[bool] = None,
    flush_interval_sec: Optional[float] = None,
    flush_batch: Optional[int] = None,
    max_buffer: Optional[int] = None,
) -> None:
    global _JSONL_BUFFER_ENABLED, _JSONL_FLUSH_INTERVAL, _JSONL_FLUSH_BATCH, _JSONL_MAX_BUFFER
    if buffered is not None:
        _JSONL_BUFFER_ENABLED = bool(buffered)
    if flush_interval_sec is not None:
        _JSONL_FLUSH_INTERVAL = float(flush_interval_sec)
    if flush_batch is not None:
        _JSONL_FLUSH_BATCH = int(flush_batch)
    if max_buffer is not None:
        _JSONL_MAX_BUFFER = int(max_buffer)


def _register_jsonl_flush() -> None:
    global _JSONL_ATEXIT_REGISTERED
    if _JSONL_ATEXIT_REGISTERED:
        return
    try:
        import atexit

        atexit.register(lambda: flush_jsonl_buffers(force=True))
        _JSONL_ATEXIT_REGISTERED = True
    except Exception:
        _JSONL_ATEXIT_REGISTERED = True


def _flush_jsonl_path(path: str, lines: List[str], lock_timeout_sec: float) -> bool:
    if not lines:
        return True
    ensure_parent_dir(path)
    lock_path = path + ".lock"
    fd = _acquire_lock(lock_path, timeout_sec=lock_timeout_sec)
    if fd is None:
        return False
    try:
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write("".join(lines))
            handle.flush()
            if _fsync_enabled():
                os.fsync(handle.fileno())
    finally:
        _release_lock(fd, lock_path)
    return True


def flush_jsonl_buffers(force: bool = False, lock_timeout_sec: float = 5.0) -> None:
    now = time.time()
    with _JSONL_BUFFER_LOCK:
        paths = list(_JSONL_BUFFER.keys())
    for path in paths:
        with _JSONL_BUFFER_LOCK:
            state = _JSONL_BUFFER.get(path)
            if not isinstance(state, dict):
                continue
            lines = state.get("lines") or []
            if not lines:
                continue
            last_flush = float(state.get("last_flush") or 0.0)
            if not force and len(lines) < _JSONL_FLUSH_BATCH and now - last_flush < _JSONL_FLUSH_INTERVAL:
                continue
            lines_to_write = list(lines)
            ok = False
            try:
                ok = bool(_flush_jsonl_path(path, lines_to_write, lock_timeout_sec))
            except Exception:
                ok = False
            state["last_flush"] = time.time()
            if ok:
                state["lines"] = []


def append_jsonl(path: str, obj: Dict[str, Any], lock_timeout_sec: float = 5.0, buffered: Optional[bool] = None) -> None:
    if not path:
        return
    if buffered is None:
        buffered = _JSONL_BUFFER_ENABLED
    if not buffered:
        append_jsonl_atomic(path, obj, lock_timeout_sec=lock_timeout_sec)
        return
    _register_jsonl_flush()
    ensure_parent_dir(path)
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with _JSONL_BUFFER_LOCK:
        state = _JSONL_BUFFER.setdefault(path, {"lines": [], "last_flush": time.time()})
        state["lines"].append(line)
        if len(state["lines"]) > _JSONL_MAX_BUFFER:
            state["lines"] = state["lines"][-_JSONL_MAX_BUFFER:]
    flush_jsonl_buffers(force=False, lock_timeout_sec=lock_timeout_sec)


_dialogue_seq_lock = Lock()
_dialogue_seq = 0
_event_seq_lock = Lock()
_event_seq = 0


def set_dialogue_seq(n: int) -> None:
    global _dialogue_seq
    with _dialogue_seq_lock:
        _dialogue_seq = n


def set_event_seq(n: int) -> None:
    global _event_seq
    with _event_seq_lock:
        _event_seq = n


def scan_last_seq(path: str, key: str = "seq") -> int:
    if not path or not os.path.exists(path):
        return 0
    try:
        with open(path, "rb") as f:
            try:
                f.seek(-8192, os.SEEK_END)
            except OSError:
                f.seek(0)
            lines = f.readlines()
        
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                text = line.decode("utf-8", errors="ignore")
                data = json.loads(text)
                if isinstance(data, dict) and key in data:
                    return int(data[key])
            except Exception:
                continue
    except Exception:
        pass
    return 0


def _next_dialogue_seq() -> int:
    global _dialogue_seq
    with _dialogue_seq_lock:
        _dialogue_seq += 1
        return _dialogue_seq


def _next_event_seq() -> int:
    global _event_seq
    with _event_seq_lock:
        _event_seq += 1
        return _event_seq


def get_event_seq() -> int:
    with _event_seq_lock:
        return _event_seq


def _new_event_id() -> str:
    return str(uuid.uuid4())


def _read_seq_file(path: str) -> int:
    if not path or not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = handle.read().strip()
        if not raw:
            return 0
        return int(raw)
    except Exception:
        return 0


def _write_seq_file(path: str, value: int) -> None:
    try:
        ensure_parent_dir(path)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(int(value)))
    except Exception:
        pass


def _next_seq_for_path(path: str, current: int, key: str = "seq") -> int:
    if not path:
        return current
    seq_path = path + ".seq"
    lock_path = seq_path + ".lock"
    fd = _acquire_lock(lock_path, timeout_sec=2.0)
    if fd is None:
        return current
    try:
        existing = _read_seq_file(seq_path)
        if existing <= 0:
            existing = scan_last_seq(path, key=key)
        next_val = max(existing, current) + 1
        _write_seq_file(seq_path, next_val)
        return next_val
    finally:
        _release_lock(fd, lock_path)


def emit_dialogue(
    dialogue_path: str,
    *,
    speaker: str,
    type: str,
    text: str,
    summary: Optional[str] = None,
    run_id: Optional[str] = None,
    pm_iteration: Optional[int] = None,
    director_iteration: Optional[int] = None,
    refs: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    if not dialogue_path:
        return
    seq = _next_dialogue_seq()
    if dialogue_path:
        seq = _next_seq_for_path(dialogue_path, seq, key="seq")
        set_dialogue_seq(seq)
    payload = {
        "ts": utc_iso_now(),
        "ts_epoch": time.time(),
        "seq": seq,
        "event_id": _new_event_id(),
        "run_id": run_id,
        "pm_iteration": pm_iteration,
        "director_iteration": director_iteration,
        "speaker": speaker,
        "type": type,
        "text": text,
        "summary": summary or (text[:80] if text else ""),
        "refs": refs or {},
        "meta": meta or {},
    }
    append_jsonl_atomic(dialogue_path, payload)


def emit_event(
    event_path: str,
    *,
    kind: str,
    actor: str,
    name: str,
    refs: Optional[Dict[str, Any]] = None,
    summary: str = "",
    meta: Optional[Dict[str, Any]] = None,
    input: Optional[Dict[str, Any]] = None,
    ok: Optional[bool] = None,
    output: Optional[Dict[str, Any]] = None,
    truncation: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    if not event_path:
        return
    seq = _next_event_seq()
    if event_path:
        seq = _next_seq_for_path(event_path, seq, key="seq")
        set_event_seq(seq)
    payload: Dict[str, Any] = {
        "schema_version": 1,
        "ts": utc_iso_now(),
        "ts_epoch": time.time(),
        "seq": seq,
        "event_id": _new_event_id(),
        "kind": kind,
        "actor": actor,
        "name": name,
        "refs": refs or {},
        "summary": summary or "",
        "meta": meta or {},
    }
    if kind == "action":
        payload["input"] = input or {}
    else:
        payload["ok"] = True if ok is None else bool(ok)
        payload["output"] = output or {}
        payload["truncation"] = truncation or {"truncated": False}
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if error:
            payload["error"] = error
    append_jsonl(event_path, payload)


def ensure_plan_file(path: str, auto_continue: bool = False) -> bool:
    if os.path.exists(path):
        return True
    profile = os.environ.get("HARBORPILOT_PROMPT_PROFILE", "demo_ming_armada").strip().lower()
    template_game = """# Ming Armada PLAN
# Write the next batch of tasks for Codex here.
# Keep scope small; prefer incremental changes with tests.
# The loop will synthesize a multi-role collaboration (producer + design + UI + engineering + QA)
# and apply doc updates each iteration.
#
# References:
# - MMO spec index: MMO_CORE_SPEC.md
# - Docs index: docs/agent/README.md
# - Global requirements: docs/product/requirements.md
# - Vision: docs/product/product_spec.md
# - Systems: docs/systems/
# - UX: docs/ux/ui-ux.md
# - Engineering notes: docs/engineering/engineering-notes.md
# - Server entry: apps/server/src/index.ts
# - Client entry: apps/game-client/src/main.ts
# - Physics lab: apps/physics-lab/src/main.ts
## Example tasks:
# - Run npm test and fix any failures.
# - Run npm run build and fix errors.
# - Improve server/client sync performance for sailing rooms.
# - Add/extend MMO documentation in docs/.
"""
    template_generic = """# Project PLAN
# Write the next batch of tasks here.
# Keep scope small; prefer incremental changes with tests.
# The loop will synthesize a multi-role collaboration (producer + design + UI + engineering + QA)
# and apply doc updates each iteration.
#
# Suggested references (adjust to your repo):
# - docs/agent/README.md
# - docs/product/requirements.md
# - docs/product/product_spec.md
# # # #
# Example tasks:
# - Run tests and fix any failures.
# - Run build and fix errors.
# - Improve server/client sync performance.
# - Add/extend documentation.
"""
    template = ""
    try:
        from prompt_loader import get_template

        template = get_template("plan_template")
    except Exception:
        template = template_generic if profile in ("generic", "portable", "default") else template_game
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(template)
    if auto_continue:
        print(f"Created {path}. Continuing with the auto-generated plan.")
        return True
    print(f"Created {path}. Edit it and rerun the script.")
    return False


def resolve_codex_path() -> Optional[str]:
    path = shutil.which("codex")
    if path:
        return path
    timeout_sec = 0
    try:
        timeout_sec = int(str(os.environ.get("HARBORPILOT_PATH_RESOLVE_TIMEOUT", "3")).strip())
    except Exception:
        timeout_sec = 3
    timeout_val = timeout_sec if timeout_sec and timeout_sec > 0 else None
    try:
        output = subprocess.check_output(
            ["where", "codex"],
            text=True,
            encoding="utf-8",
            errors="ignore",
            env=build_utf8_env(),
            timeout=timeout_val,
        )
        for line in output.splitlines():
            line = line.strip()
            if line:
                return line
    except Exception:
        pass
    try:
        output = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Command codex | Select-Object -ExpandProperty Source",
            ],
            text=True,
            encoding="utf-8",
            errors="ignore",
            env=build_utf8_env(),
            timeout=timeout_val,
        )
        for line in output.splitlines():
            line = line.strip()
            if line:
                return line
    except Exception:
        pass
    return None


def ensure_codex_available() -> str:
    path = resolve_codex_path()
    if not path:
        raise RuntimeError("codex command not found in PATH.")
    return path


def resolve_ollama_path() -> Optional[str]:
    path = shutil.which("ollama")
    if path:
        return path
    timeout_sec = 0
    try:
        timeout_sec = int(str(os.environ.get("HARBORPILOT_PATH_RESOLVE_TIMEOUT", "3")).strip())
    except Exception:
        timeout_sec = 3
    timeout_val = timeout_sec if timeout_sec and timeout_sec > 0 else None
    try:
        output = subprocess.check_output(
            ["where", "ollama"],
            text=True,
            encoding="utf-8",
            errors="ignore",
            env=build_utf8_env(),
            timeout=timeout_val,
        )
        for line in output.splitlines():
            line = line.strip()
            if line:
                return line
    except Exception:
        pass
    return None


def ensure_ollama_available() -> str:
    path = resolve_ollama_path()
    if not path:
        raise RuntimeError("ollama command not found in PATH.")
    return path


def ensure_tools_available() -> None:
    missing_execs = []
    missing_modules = []
    for name in ("ruff", "pytest", "coverage", "mypy"):
        if not shutil.which(name):
            missing_execs.append(name)
    for module in ("pydantic", "jsonschema", "tree_sitter", "tree_sitter_languages", "rich"):
        try:
            __import__(module)
        except Exception:
            missing_modules.append(module)
    if missing_execs or missing_modules:
        parts = []
        if missing_execs:
            parts.append("missing executables: " + ", ".join(missing_execs))
        if missing_modules:
            parts.append("missing python modules: " + ", ".join(missing_modules))
        raise RuntimeError("Required tools not available (" + "; ".join(parts) + ").")


def _decode_text_bytes(data: bytes) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
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


def read_file_safe(path: str) -> str:
    if not os.path.exists(path):
        legacy_dot = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        legacy_state = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{LEGACY_ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        if legacy_dot != path and os.path.exists(legacy_dot):
            path = legacy_dot
        elif legacy_state != path and os.path.exists(legacy_state):
            path = legacy_state
        else:
            double_path = _legacy_double_artifact_path(path)
            if double_path and os.path.exists(double_path):
                path = double_path
            else:
                return ""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        return _decode_text_bytes(data)
    except Exception:
        return ""


def read_memory_snapshot(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        legacy_dot = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        legacy_state = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{LEGACY_ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        if legacy_dot != path and os.path.exists(legacy_dot):
            path = legacy_dot
        elif legacy_state != path and os.path.exists(legacy_state):
            path = legacy_state
        else:
            double_path = _legacy_double_artifact_path(path)
            if double_path and os.path.exists(double_path):
                path = double_path
            else:
                return None
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        text = _decode_text_bytes(data)
        return json.loads(text)
    except Exception:
        return None


def write_memory_snapshot(path: str, data: Dict[str, Any]) -> None:
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_memory_summary(snapshot: Optional[Dict[str, Any]], max_chars: int) -> str:
    if not snapshot:
        return "none"
    lines = []
    if snapshot.get("last_run_at"):
        lines.append(f"- last_run_at: {snapshot['last_run_at']}")
    if snapshot.get("last_summary"):
        lines.append(f"- last_summary: {snapshot['last_summary']}")
    if snapshot.get("last_next_step"):
        lines.append(f"- last_next_step: {snapshot['last_next_step']}")
    if snapshot.get("last_log_path"):
        lines.append(f"- last_log_path: {snapshot['last_log_path']}")
    text = "\n".join(lines)
    if max_chars > 0 and len(text) > max_chars:
        return text[:max_chars] + "..."
    return text


def extract_field(text: str, patterns: List[str]) -> str:
    if not text:
        return ""
    for pattern in patterns:
        try:
            match = re.search(pattern, text, flags=re.MULTILINE)
        except re.error:
            match = None
        if match:
            return match.group(1).strip()
    return ""


def write_loop_warning(log_path: str, message: str) -> None:
    if log_path:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(f"[WARN] {message}\n")
    print(f"WARNING: {message}")
