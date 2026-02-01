import os
import sys
import time
import subprocess
import signal
from typing import List, Dict, Optional
from fastapi import HTTPException
from ..config import (
    Settings, DEFAULT_WORKSPACE, DEFAULT_MODEL, DEFAULT_PM_LOG,
    PROJECT_ROOT, LOOP_PM_PATH, DIRECTOR_SCRIPT, ARTIFACT_ROOT, ARTIFACT_NAMESPACE,
    LEGACY_ARTIFACT_ROOT, LEGACY_ARTIFACT_NAMESPACE
)
from ..state import ProcessHandle
from ..utils import build_utf8_env, resolve_artifact_path, get_abs_path

def pm_command(settings: Settings, loop_mode: bool, resume: bool = False) -> List[str]:
    cmd = [
        sys.executable,
        get_abs_path(PROJECT_ROOT, LOOP_PM_PATH),
        "--workspace",
        settings.workspace or DEFAULT_WORKSPACE,
        "--pm-backend",
        settings.pm_backend or "codex",
        "--model",
        settings.pm_model or settings.model or DEFAULT_MODEL,
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
        cmd.extend(["--director-result-timeout", str(settings.pm_director_timeout or 600)])
        cmd.extend(["--director-iterations", str(settings.pm_director_iterations or 1)])
        if settings.pm_director_match_mode:
            cmd.extend(["--director-match-mode", settings.pm_director_match_mode])
        if settings.director_model:
            cmd.extend(["--director-model", settings.director_model])
    return cmd

def director_command(settings: Settings) -> List[str]:
    iterations = settings.director_iterations or 1
    cmd = [sys.executable, DIRECTOR_SCRIPT, "--workspace", settings.workspace or DEFAULT_WORKSPACE]
    if settings.director_model or settings.model:
        cmd.extend(["--model", settings.director_model or settings.model])
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

def spawn_process(cmd: List[str], cwd: str, log_path: str, extra_env: Optional[Dict[str, str]] = None) -> ProcessHandle:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_handle = open(log_path, "a", encoding="utf-8", errors="ignore")
    env = build_utf8_env(extra_env)
    try:
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
    except Exception:
        try:
            log_handle.close()
        except Exception:
            pass
        raise
    return ProcessHandle(process=process, log_handle=log_handle, log_path=log_path, started_at=time.time())

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

def terminate_pid(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        os.kill(pid, signal.SIGTERM)
        try:
            time.sleep(0.5)
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
        return True
    except Exception:
        return False

def clear_stop_flag(workspace: str, cache_root: str) -> None:
    paths = set()
    try:
        paths.add(resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/PM_STOP.flag"))
    except HTTPException:
        paths.add(os.path.join(workspace, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "PM_STOP.flag"))
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

def director_stop_flag_path(workspace: str, cache_root: str) -> str:
    try:
        return resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/DIRECTOR_STOP.flag")
    except HTTPException:
        return os.path.join(workspace, ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "DIRECTOR_STOP.flag")

def clear_director_stop_flag(workspace: str, cache_root: str) -> None:
    paths = set()
    stop_flag = director_stop_flag_path(workspace, cache_root)
    if stop_flag:
        paths.add(stop_flag)
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
