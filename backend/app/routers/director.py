from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from ..state import AppState, Auth
from ..config import DEFAULT_DIRECTOR_SUBPROCESS_LOG
from ..utils import require_lancedb, resolve_artifact_path, build_cache_root
from ..services.process import director_command, spawn_process, terminate_process, clear_director_stop_flag
from ..services.artifacts import read_director_status

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.post("/director/start", dependencies=[Depends(require_auth)])
def director_start(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    require_lancedb()
    if state.director.process is not None:
        if state.director.process.poll() is None:
            return {"ok": False, "error": "running", "pid": state.director.process.pid}
        terminate_process(state.director)
    
    workspace = state.settings.workspace
    cmd = director_command(state.settings)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
    clear_director_stop_flag(workspace, cache_root)
    
    log_path = resolve_artifact_path(workspace, cache_root, DEFAULT_DIRECTOR_SUBPROCESS_LOG)
    try:
        handle = spawn_process(cmd, workspace, log_path)
        state.director = handle
        state.director.mode = "director"
        return {"ok": True, "pid": handle.process.pid}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/director/stop", dependencies=[Depends(require_auth)])
def director_stop(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    if state.director.process:
        terminate_process(state.director)
        return {"ok": True}
    return {"ok": False, "error": "not running"}

@router.get("/director/status", dependencies=[Depends(require_auth)])
def director_status_endpoint(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    running = False
    pid = None
    if state.director.process:
        if state.director.process.poll() is None:
            running = True
            pid = state.director.process.pid
        else:
            terminate_process(state.director)
    
    workspace = state.settings.workspace
    cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
    status_data = read_director_status(workspace, cache_root)
    
    return {
        "running": running,
        "pid": pid,
        "mode": state.director.mode,
        "started_at": state.director.started_at,
        "status": status_data,
    }
