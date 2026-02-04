from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from ..state import AppState, Auth
from services.gpu_detector import detect_gpus
from ..utils import save_persisted_settings

router = APIRouter(prefix="/turbo", tags=["turbo"])

class TurboConfig(BaseModel):
    enabled: bool
    auto_detect: Optional[bool] = None
    memory_limit: Optional[int] = None

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.get("/status", dependencies=[Depends(require_auth)])
def get_turbo_status(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    detection = detect_gpus()
    
    # Logic: If auto-detect is on, disable turbo if no gpu found
    # (This is just reporting status, actual logic might differ)
    
    return {
        "enabled": state.settings.gpu_turbo_mode,
        "auto_detect": state.settings.gpu_auto_detect,
        "memory_limit": state.settings.gpu_memory_limit,
        "detection": detection,
        # active determines if the engine is actually using GPU
        "active": state.settings.gpu_turbo_mode and detection["available"]
    }

@router.post("/config", dependencies=[Depends(require_auth)])
def update_turbo_config(request: Request, config: TurboConfig) -> Dict[str, Any]:
    state = get_state(request)
    
    # Update settings
    state.settings.gpu_turbo_mode = config.enabled
    if config.auto_detect is not None:
        state.settings.gpu_auto_detect = config.auto_detect
    if config.memory_limit is not None:
        state.settings.gpu_memory_limit = config.memory_limit
        
    # Save persistence
    save_persisted_settings(state.settings)
    
    # Re-detect if enabled? 
    detection = detect_gpus()
    
    return {
        "enabled": state.settings.gpu_turbo_mode,
        "active": state.settings.gpu_turbo_mode and detection["available"],
        "detection": detection
    }
