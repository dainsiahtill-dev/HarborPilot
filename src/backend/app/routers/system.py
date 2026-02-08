from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from ..state import AppState, Auth
from ..config import SettingsUpdate, DEFAULT_WORKSPACE
from ..utils import (
    get_lancedb_status, save_persisted_settings, validate_workspace,
    normalize_ramdisk_root, workspace_has_docs, clear_workspace_status,
    write_workspace_status
)
from ..services.artifacts import build_snapshot
import os

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.get("/health", dependencies=[Depends(require_auth)])
def health() -> Dict[str, Any]:
    lancedb_status = get_lancedb_status()
    return {
        "ok": bool(lancedb_status.get("ok")),
        "version": "0.1",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lancedb_ok": bool(lancedb_status.get("ok")),
        "lancedb_error": lancedb_status.get("error"),
        "python": lancedb_status.get("python"),
    }

@router.get("/settings", dependencies=[Depends(require_auth)])
def get_settings(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    return state.settings.model_dump()

@router.post("/settings", dependencies=[Depends(require_auth)])
def update_settings(request: Request, payload: SettingsUpdate) -> Dict[str, Any]:
    state = get_state(request)
    if payload.workspace:
        payload.workspace = validate_workspace(payload.workspace)
    workspace_root = payload.workspace or state.settings.workspace or DEFAULT_WORKSPACE
    if payload.ramdisk_root is not None:
        normalized = normalize_ramdisk_root(payload.ramdisk_root)
        if normalized:
            try:
                ws_abs = os.path.abspath(workspace_root)
                if os.path.commonpath([ws_abs, normalized]) == ws_abs:
                    payload.ramdisk_root = ""
                else:
                    payload.ramdisk_root = normalized
            except Exception:
                payload.ramdisk_root = normalized
    state.settings.apply_update(payload)
    if payload.workspace:
        if workspace_has_docs(state.settings.workspace):
            clear_workspace_status(state.settings.workspace)
        else:
            write_workspace_status(
                state.settings.workspace,
                status="NEEDS_DOCS_INIT",
                reason="docs/ directory not found",
                actions=["INIT_DOCS_WIZARD"],
            )
    save_persisted_settings(state.settings)
    return state.settings.model_dump()

@router.get("/state/snapshot", dependencies=[Depends(require_auth)])
def state_snapshot(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    return build_snapshot(state)
