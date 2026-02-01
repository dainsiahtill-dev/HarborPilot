import os
import shutil
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from ..state import AppState, Auth
from ..config import DEFAULT_WORKSPACE, ARTIFACT_ROOT, AGENTS_DRAFT_REL, AGENTS_FEEDBACK_REL, AgentsApplyPayload, AgentsFeedbackPayload
from ..utils import build_cache_root, resolve_artifact_path, resolve_safe_path, format_mtime

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.post("/agents/apply", dependencies=[Depends(require_auth)])
def apply_agents(request: Request, payload: AgentsApplyPayload) -> Dict[str, Any]:
    state = get_state(request)
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

@router.post("/agents/feedback", dependencies=[Depends(require_auth)])
def save_agents_feedback(request: Request, payload: AgentsFeedbackPayload) -> Dict[str, Any]:
    state = get_state(request)
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
