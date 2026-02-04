import os
import sys
import json
import hashlib
import shutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException
from .config import (
    Settings,
    ARTIFACT_ROOT,
    ARTIFACT_NAMESPACE,
    LEGACY_ARTIFACT_ROOT,
    LEGACY_ARTIFACT_NAMESPACE,
    STATE_TO_RAMDISK_ENV,
    LOOP_MODULE_DIR,
    WORKSPACE_STATUS_REL
)

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

def ensure_loop_modules() -> None:
    if os.path.isdir(LOOP_MODULE_DIR) and LOOP_MODULE_DIR not in sys.path:
        sys.path.insert(0, LOOP_MODULE_DIR)

def normalize_ramdisk_root(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if not os.path.isabs(raw):
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

def state_to_ramdisk_enabled() -> bool:
    value = os.environ.get(STATE_TO_RAMDISK_ENV, "1").strip().lower()
    return value not in ("0", "false", "no", "off")

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

def _cache_join(cache_root_full: str, rel_path: str) -> str:
    if not cache_root_full or not rel_path:
        return ""
    normalized = normalize_artifact_rel_path(rel_path)
    return os.path.join(cache_root_full, _strip_artifact_root_prefix(normalized))

def _cache_join_double(cache_root_full: str, rel_path: str) -> str:
    if not cache_root_full or not rel_path:
        return ""
    normalized = normalize_artifact_rel_path(rel_path)
    if not normalized.startswith(f"{ARTIFACT_ROOT}/"):
        return ""
    stripped = _strip_artifact_root_prefix(normalized)
    return os.path.join(cache_root_full, ARTIFACT_ROOT, stripped)

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

def resolve_artifact_path(workspace_full: str, cache_root_full: str, rel_path: str) -> str:
    if not rel_path:
        return ""
    if os.path.isabs(rel_path):
        return rel_path
    p = normalize_artifact_rel_path(rel_path)
    if p.startswith(f"{ARTIFACT_ROOT}/") and state_to_ramdisk_enabled():
        if not cache_root_full:
            raise HTTPException(
                status_code=500,
                detail=f"{ARTIFACT_ROOT}/ is configured for ramdisk only, but no ramdisk cache root is available",
            )
        return os.path.join(cache_root_full, _strip_artifact_root_prefix(p))
    base = cache_root_full if (cache_root_full and is_hot_artifact_path(p)) else workspace_full
    if base == cache_root_full and p.startswith(f"{ARTIFACT_ROOT}/"):
        return os.path.join(base, _strip_artifact_root_prefix(p))
    return os.path.join(base, p)

def resolve_safe_path(workspace_full: str, cache_root_full: str, rel_path: str) -> str:
    normalized_rel = normalize_artifact_rel_path(rel_path)
    path = resolve_artifact_path(workspace_full, cache_root_full, normalized_rel)
    if not path:
        raise HTTPException(status_code=400, detail="path is required")
    full = os.path.abspath(path)
    roots = [os.path.abspath(workspace_full)]
    if cache_root_full:
        roots.append(os.path.abspath(cache_root_full))
    within_root = False
    for root in roots:
        try:
            if os.path.commonpath([root, full]) == root:
                within_root = True
                break
        except ValueError:
            continue
    if within_root and os.path.exists(full):
        return full
    candidates: List[str] = []
    if within_root:
        double_cache_path = _cache_join_double(cache_root_full, normalized_rel)
        if double_cache_path:
            candidates.append(double_cache_path)
    legacy_rel = legacy_artifact_rel_path(normalized_rel)
    if legacy_rel:
        prefer_cache = bool(cache_root_full and state_to_ramdisk_enabled())
        if prefer_cache and cache_root_full:
            legacy_cache = _cache_join(cache_root_full, legacy_rel)
            if legacy_cache:
                candidates.append(legacy_cache)
        candidates.append(os.path.join(workspace_full, legacy_rel))
        if cache_root_full and not prefer_cache:
            legacy_cache = _cache_join(cache_root_full, legacy_rel)
            if legacy_cache:
                candidates.append(legacy_cache)
    for candidate in candidates:
        if not candidate:
            continue
        if os.path.isfile(candidate) or os.path.isdir(candidate):
            full = os.path.abspath(candidate)
            for root in roots:
                try:
                    if os.path.commonpath([root, full]) == root:
                        return full
                except ValueError:
                    continue
    if within_root:
        return full
    raise HTTPException(status_code=400, detail="path outside workspace")

def read_json(path: str) -> Optional[Dict[str, Any]]:
    if not path or not os.path.isfile(path):
        if not path:
            return None
        legacy_dot = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        legacy_state = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{LEGACY_ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        if legacy_dot != path and os.path.isfile(legacy_dot):
            path = legacy_dot
        elif legacy_state != path and os.path.isfile(legacy_state):
            path = legacy_state
        else:
            return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None

def decode_bytes(data: bytes, *, allow_fallback: bool = True) -> str:
    if not data:
        return ""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
        if not allow_fallback:
            return text
        if text.count("\ufffd") <= max(1, len(text) // 200):
            return text
        try:
            return data.decode("gbk")
        except Exception:
            return text

def read_file_tail(
    path: str,
    max_lines: int = 400,
    max_chars: int = 20000,
    *,
    allow_fallback: bool = True,
) -> str:
    if not path or not os.path.isfile(path):
        if not path:
            return ""
        legacy_dot = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        legacy_state = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{LEGACY_ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        if legacy_dot != path and os.path.isfile(legacy_dot):
            path = legacy_dot
        elif legacy_state != path and os.path.isfile(legacy_state):
            path = legacy_state
        else:
            double_path = _legacy_double_artifact_path(path)
            if double_path and os.path.isfile(double_path):
                path = double_path
            else:
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
                
                if target_lines is not None and lines_found >= target_lines + 1:
                    if max_chars <= 0 or chars_read >= max_chars:
                        break
                
                if max_chars > 0 and chars_read >= max_chars * 2:
                    break

            data = b"".join(reversed(chunks))
            text = decode_bytes(data, allow_fallback=allow_fallback)

            lines = text.splitlines()
            if max_lines > 0 and len(lines) > max_lines:
                lines = lines[-max_lines:]
            content = "\n".join(lines)

            if max_chars > 0 and len(content) > max_chars:
                content = content[-max_chars:]

            return content
    except Exception:
        return ""

def read_file_head(path: str, max_chars: int = 20000, *, allow_fallback: bool = True) -> str:
    if not path or not os.path.isfile(path):
        if not path:
            return ""
        legacy_dot = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        legacy_state = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{LEGACY_ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        if legacy_dot != path and os.path.isfile(legacy_dot):
            path = legacy_dot
        elif legacy_state != path and os.path.isfile(legacy_state):
            path = legacy_state
        else:
            double_path = _legacy_double_artifact_path(path)
            if double_path and os.path.isfile(double_path):
                path = double_path
            else:
                return ""
    try:
        with open(path, "rb") as handle:
            data = handle.read(max_chars if max_chars and max_chars > 0 else 20000)
        return decode_bytes(data, allow_fallback=allow_fallback)
    except Exception:
        return ""

def read_incremental(
    path: str,
    state: Dict[str, Any],
    max_chars: int = 20000,
    *,
    allow_fallback: bool = True,
) -> List[str]:
    if not path or not os.path.isfile(path):
        if not path:
            return []
        legacy_dot = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        legacy_state = path.replace(
            f"{os.sep}{ARTIFACT_ROOT}{os.sep}{ARTIFACT_NAMESPACE}{os.sep}",
            f"{os.sep}{LEGACY_ARTIFACT_ROOT}{os.sep}{LEGACY_ARTIFACT_NAMESPACE}{os.sep}",
        )
        if legacy_dot != path and os.path.isfile(legacy_dot):
            path = legacy_dot
        elif legacy_state != path and os.path.isfile(legacy_state):
            path = legacy_state
        else:
            double_path = _legacy_double_artifact_path(path)
            if double_path and os.path.isfile(double_path):
                path = double_path
            else:
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
    text = decode_bytes(chunk, allow_fallback=allow_fallback)
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

def build_file_status(entries: List[Tuple[str, str]]) -> List[str]:
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

def workspace_status_path(workspace: str) -> str:
    if not workspace:
        return ""
    return os.path.join(workspace, WORKSPACE_STATUS_REL)

def validate_workspace(path: str) -> str:
    if not path:
        raise HTTPException(status_code=400, detail="workspace is required")
    full = os.path.abspath(path)
    if not os.path.isdir(full):
        raise HTTPException(status_code=400, detail="workspace path not found")
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

def write_text_atomic(path: str, text: str) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text or "")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)

def _split_items(value: str) -> List[str]:
    if not value:
        return []
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").replace(",", "\n")
    items: List[str] = []
    for line in normalized.split("\n"):
        line = line.strip()
        if not line:
            continue
        line = line.lstrip("-").strip()
        if line:
            items.append(line)
    return items

def _format_list(items: List[str], placeholder: str = "TBD") -> str:
    if not items:
        return f"- {placeholder}"
    return "\n".join([f"- {item}" for item in items])

def detect_project_profile(workspace: str) -> Dict[str, Any]:
    profile: Dict[str, Any] = {
        "python": False,
        "node": False,
        "go": False,
        "rust": False,
        "package_manager": None,
    }
    if not workspace:
        return profile
    def _exists(name: str) -> bool:
        return os.path.isfile(os.path.join(workspace, name))
    profile["python"] = _exists("pyproject.toml") or _exists("requirements.txt") or _exists("setup.py")
    profile["node"] = _exists("package.json")
    profile["go"] = _exists("go.mod")
    profile["rust"] = _exists("Cargo.toml")
    if profile["node"]:
        if _exists("pnpm-lock.yaml"):
            profile["package_manager"] = "pnpm"
        elif _exists("yarn.lock"):
            profile["package_manager"] = "yarn"
        else:
            profile["package_manager"] = "npm"
    return profile

def default_qa_commands(profile: Dict[str, Any]) -> List[str]:
    commands: List[str] = []
    if profile.get("python"):
        commands.extend(["ruff check .", "mypy", "pytest"])
    if profile.get("node"):
        manager = profile.get("package_manager") or "npm"
        commands.append(f"{manager} test")
    if profile.get("go"):
        commands.append("go test ./...")
    if profile.get("rust"):
        commands.append("cargo test")
    if not commands:
        commands.append("Add project-specific QA commands.")
    return commands

def read_readme_title(workspace: str) -> str:
    if not workspace:
        return ""
    path = os.path.join(workspace, "README.md")
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                if text.startswith("#"):
                    text = text.lstrip("#").strip()
                return text[:120]
    except Exception:
        return ""
    return ""

def normalize_rel_path(rel_path: str) -> str:
    raw = (rel_path or "").replace("\\", "/").lstrip("/")
    norm = os.path.normpath(raw).replace("\\", "/")
    return norm

def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        data = json.loads(candidate)
    except Exception:
        return None
    return data if isinstance(data, dict) else None

def _normalize_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: List[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                items.append(text)
        return items
    if isinstance(value, str):
        return _split_items(value)
    return [str(value).strip()]

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

def save_persisted_settings(settings: Settings) -> None:
    path = get_settings_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(settings.model_dump(), handle, ensure_ascii=False, indent=2)
    except Exception:
        pass

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

def check_backend_available(settings: Settings) -> Optional[str]:
    backend = (settings.pm_backend or "").strip().lower()
    if backend == "codex":
        if not shutil.which("codex"):
            return "codex command not found in PATH. Install codex or switch PM backend to ollama."
    elif backend == "ollama":
        if not shutil.which("ollama"):
            return "ollama command not found in PATH. Install Ollama or switch PM backend to codex."
    return None

def build_runtime_issues(settings: Settings, workspace: str) -> List[Dict[str, str]]:
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

def select_latest_artifact(workspace: str, cache_root: str, rel_path: str) -> str:
    if not rel_path:
        return ""
    paths_to_check = []
    try:
        p1 = resolve_artifact_path(workspace, cache_root, rel_path)
        if p1:
            paths_to_check.append(p1)
    except Exception:
        pass
    
    norm = normalize_artifact_rel_path(rel_path)
    legacy = legacy_artifact_rel_path(norm)
    if legacy:
        try:
            p2 = resolve_artifact_path(workspace, cache_root, legacy)
            if p2:
                paths_to_check.append(p2)
        except Exception:
            pass

    dc = _cache_join_double(cache_root, norm)
    if dc:
        paths_to_check.append(dc)
    
    unique = set()
    for p in paths_to_check:
        if p and os.path.isfile(p):
            unique.add(os.path.abspath(p))
            
    if not unique:
        return ""
        
    best = ""
    best_mtime = -1.0
    for p in unique:
        try:
            mtime = os.path.getmtime(p)
            if mtime > best_mtime:
                best_mtime = mtime
                best = p
        except Exception:
            pass
    return best

def workspace_has_docs(workspace: str) -> bool:
    if not workspace:
        return False
    return os.path.isdir(os.path.join(workspace, "docs"))

def read_workspace_status(workspace: str) -> Optional[Dict[str, Any]]:
    path = workspace_status_path(workspace)
    return read_json(path)

def write_workspace_status(
    workspace: str, status: str, reason: str, actions: List[str]
) -> None:
    path = workspace_status_path(workspace)
    if not path:
        return
    payload = {
        "status": status,
        "reason": reason,
        "actions": actions,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2))

def clear_workspace_status(workspace: str) -> None:
    path = workspace_status_path(workspace)
    if not path:
        return
    if os.path.isfile(path):
        try:
            os.remove(path)
        except Exception:
            pass

def select_docs_target_root(workspace: str) -> str:
    return "docs"

def is_safe_docs_path(rel_path: str, target_root: str) -> bool:
    if ".." in rel_path:
        return False
    normalized = rel_path.replace("\\", "/")
    return normalized.startswith(target_root + "/") or normalized == target_root

def build_docs_templates(
    workspace: str,
    mode: str,
    fields: Dict[str, str],
    qa_commands: List[str]
) -> Dict[str, str]:
    templates = {}
    goal = fields.get("goal", "")
    in_scope = fields.get("in_scope", "")
    out_of_scope = fields.get("out_of_scope", "")
    constraints = fields.get("constraints", "")
    done = fields.get("definition_of_done", "")
    backlog = fields.get("backlog", "")
    
    qa_text = "\n".join([f"- `{cmd}`" for cmd in qa_commands])

    if mode == "minimal":
        templates["docs/product/requirements.md"] = f"""# Product Requirements

## Goal
{goal or "TBD"}

## In Scope
{in_scope or "TBD"}

## Out of Scope
{out_of_scope or "None"}

## Constraints
{constraints or "None"}
"""
        templates["docs/product/plan.md"] = f"""# Implementation Plan

## Definition of Done
{done or "TBD"}

## QA verified with
{qa_text}

## Backlog
{backlog or "TBD"}
"""
    return templates
