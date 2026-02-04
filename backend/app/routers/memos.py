from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from ..state import AppState, Auth
from ..config import DEFAULT_WORKSPACE
from ..services.memos import list_memos

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.get("/memos/list", dependencies=[Depends(require_auth)])
def get_memos(request: Request, limit: int = 200) -> Dict[str, Any]:
    state = get_state(request)
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    ramdisk_root = state.settings.ramdisk_root or ""
    return list_memos(workspace, ramdisk_root, limit)
