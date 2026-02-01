from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from ..state import AppState, Auth, ProcessHandle
from ..config import DEFAULT_PM_SUBPROCESS_LOG
from ..utils import check_backend_available, resolve_artifact_path, build_cache_root
from ..services.process import pm_command, spawn_process, terminate_process, clear_stop_flag
import os
import time

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.post("/pm/run_once", dependencies=[Depends(require_auth)])
def pm_run_once(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    if state.pm.process is not None:
        if state.pm.process.poll() is None:
            return {"ok": False, "error": "running", "pid": state.pm.process.pid}
        # cleanup if finished
        terminate_process(state.pm)
    
    error = check_backend_available(state.settings)
    if error:
        raise HTTPException(status_code=503, detail=error)
    
    workspace = state.settings.workspace
    cmd = pm_command(state.settings, loop_mode=False)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
    # Ensure stop flag is cleared before starting
    clear_stop_flag(workspace, cache_root)
    
    log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_PM_SUBPROCESS_LOG)
    try:
        handle = spawn_process(cmd, workspace, log_path)
        state.pm = handle
        state.pm.mode = "run_once"
        return {"ok": True, "pid": handle.process.pid}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/pm/status", dependencies=[Depends(require_auth)])
def pm_status(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    running = False
    pid = None
    if state.pm.process:
        if state.pm.process.poll() is None:
            running = True
            pid = state.pm.process.pid
        else:
            terminate_process(state.pm)
    return {
        "running": running,
        "pid": pid,
        "mode": state.pm.mode,
        "started_at": state.pm.started_at,
    }

@router.post("/pm/stop", dependencies=[Depends(require_auth)])
def pm_stop(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    if state.pm.process:
        terminate_process(state.pm)
        return {"ok": True}
    return {"ok": False, "error": "not running"}
