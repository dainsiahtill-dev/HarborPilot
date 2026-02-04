from services.vision_service import get_vision_service
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from ..state import AppState, Auth
from services.turbo_engine import get_turbo_engine
from services.turbo_scheduler import get_scheduler
from services.arrow_service import get_arrow_service
from fastapi.responses import Response
import os


def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

router = APIRouter(prefix="/arsenal", tags=["arsenal"])

class VisionRequest(BaseModel):
    image: str # Base64
    task: str = "<OD>"

@router.post("/vision/analyze", dependencies=[Depends(require_auth)])
def analyze_ui(request: Request, payload: VisionRequest) -> Dict[str, Any]:
    service = get_vision_service()
    # Auto-load for testing if not loaded
    if not service.is_loaded:
        service.load_model() # This will likely just enable the mock if dependencies missing
    
    return service.analyze_image(payload.image, payload.task)


@router.get("/scheduler/status", dependencies=[Depends(require_auth)])
def get_scheduler_status(request: Request) -> Dict[str, Any]:
    scheduler = get_scheduler()
    return scheduler.get_status()

@router.post("/scheduler/start", dependencies=[Depends(require_auth)])
async def start_scheduler(request: Request) -> Dict[str, Any]:
    scheduler = get_scheduler()
    await scheduler.start(enable_cuda=True)
    return scheduler.get_status()

@router.post("/scheduler/stop", dependencies=[Depends(require_auth)])
async def stop_scheduler(request: Request) -> Dict[str, Any]:
    scheduler = get_scheduler()
    await scheduler.stop()
    return scheduler.get_status()




@router.get("/code_map", dependencies=[Depends(require_auth)])
def get_code_map(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    engine = get_turbo_engine()
    if not engine:
        # Should not happen unless config loading failed completely
        raise HTTPException(status_code=500, detail="Turbo Engine not initialized")
    
    # 1. Gather all "code" files from workspace
    workspace = state.settings.workspace
    if not workspace or not os.path.isdir(workspace):
        return {"points": [], "mode": "error", "message": "Invalid workspace"}
    
    file_contents = {}
    try:
        # Limit to 200 files for V1 speed/safety
        count = 0
        MAX_FILES = 200
        for root, dirs, files in os.walk(workspace):
            # Skip hidden dirs
            if ".git" in dirs: dirs.remove(".git")
            if "node_modules" in dirs: dirs.remove("node_modules")
            if "__pycache__" in dirs: dirs.remove("__pycache__")
            if ".venv" in dirs: dirs.remove(".venv")
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in [".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json"]:
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, workspace)
                
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if content.strip():
                            file_contents[rel_path] = content
                            count += 1
                except Exception:
                    pass
                
                if count >= MAX_FILES:
                    break
            if count >= MAX_FILES:
                break
    except Exception as e:
        print(f"Error scanning files for Code Map: {e}")

    # 2. Generate Map
    points = engine.generate_project_map(file_contents)
    
    # Check for Arrow format request
    output_format = request.query_params.get("format", "json")
    if output_format == "arrow":
        arrow_svc = get_arrow_service()
        if arrow_svc.available:
            # Flatten points for Arrow friendly format if needed, or pass list of dicts
            # points is List[Dict] usually: [{id, x, y, z, ...}]
            ipc_bytes = arrow_svc.to_arrow_ipc(points)
            if ipc_bytes:
                return Response(content=ipc_bytes, media_type="application/vnd.apache.arrow.stream")
    
    return {
        "points": points,
        "mode": "gpu" if (engine.is_active and "cuml" in str(points)) else "cpu",
        "engine_active": engine.is_active
    }
