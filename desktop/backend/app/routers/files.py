from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from ..state import AppState, Auth
from ..config import DEFAULT_WORKSPACE
from ..utils import build_cache_root, resolve_safe_path, read_file_tail, format_mtime

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.get("/files/read", dependencies=[Depends(require_auth)])
def read_file(
    request: Request,
    path: str,
    tail_lines: int = 400,
    max_chars: int = 20000,
) -> Dict[str, Any]:
    state = get_state(request)
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
    full_path = resolve_safe_path(workspace, cache_root, path)
    normalized = full_path.replace("\\", "/").lower()
    allow_fallback = not normalized.endswith("/dialogue.jsonl")
    content = read_file_tail(full_path, max_lines=tail_lines, max_chars=max_chars, allow_fallback=allow_fallback)
    return {
        "path": full_path,
        "rel_path": path,
        "mtime": format_mtime(full_path),
        "content": content,
    }
