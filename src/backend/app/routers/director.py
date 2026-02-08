from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
import os
import re
from ..state import AppState, Auth
from ..config import DEFAULT_DIRECTOR_SUBPROCESS_LOG
from ..utils import require_lancedb, resolve_artifact_path, build_cache_root
from ..llm import config as llm_config
from ..services.llm_tests import load_llm_test_index
from ..services.process import director_command, spawn_process, terminate_process, clear_director_stop_flag, build_invariants_env
from ..services.artifacts import read_director_status

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")


def _ensure_llm_ready(state: AppState, role: str) -> None:
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    config = llm_config.load_llm_config(state.settings.workspace, cache_root, settings=state.settings)
    index = load_llm_test_index(state.settings)
    role_status = (index.get("roles") or {}).get(role) if isinstance(index, dict) else None
    if not isinstance(role_status, dict) or not role_status.get("ready"):
        raise HTTPException(status_code=409, detail=f"{role} LLM not ready; run tests first")
    role_cfg = (config.get("roles") or {}).get(role, {}) if isinstance(config.get("roles"), dict) else {}
    providers = config.get("providers") if isinstance(config.get("providers"), dict) else {}
    provider_cfg = providers.get(role_cfg.get("provider_id"), {}) if isinstance(providers, dict) else {}
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    if role == "director" and provider_type != "ollama":
        raise HTTPException(status_code=409, detail="Director provider not supported for runtime")

@router.post("/director/start", dependencies=[Depends(require_auth)])
def director_start(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    require_lancedb()
    _ensure_llm_ready(state, "director")
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
        extra_env = build_invariants_env(state.settings)
        handle = spawn_process(cmd, workspace, log_path, extra_env=extra_env)
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


@router.get("/director/failure/{run_id}", dependencies=[Depends(require_auth)])
def director_failure_hops(request: Request, run_id: str) -> Dict[str, Any]:
    if not re.match(r"^[a-zA-Z0-9_.:-]+$", run_id or ""):
        raise HTTPException(status_code=400, detail="invalid run_id")

    state = get_state(request)
    workspace = state.settings.workspace
    cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)

    failure_path = resolve_artifact_path(
        workspace,
        cache_root,
        f".harborpilot/runtime/artifacts/runs/{run_id}/failure_hops.json",
    )
    if not os.path.isfile(failure_path):
        raise HTTPException(status_code=404, detail="failure_hops not found")

    try:
        with open(failure_path, "r", encoding="utf-8") as handle:
            payload = handle.read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    import json

    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=500, detail="invalid failure_hops payload")
    if isinstance(data, dict):
        data.setdefault("failure_hops_path", failure_path)
        return data
    raise HTTPException(status_code=500, detail="invalid failure_hops payload")
