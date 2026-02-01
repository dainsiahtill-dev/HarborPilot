import os
import json
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request
from ..state import AppState, Auth
from ..config import DEFAULT_WORKSPACE, ARTIFACT_ROOT, ARTIFACT_NAMESPACE
from ..utils import build_cache_root, resolve_artifact_path, format_mtime

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")

@router.get("/history/runs", dependencies=[Depends(require_auth)])
def history_runs(request: Request, limit: int = 50) -> Dict[str, Any]:
    state = get_state(request)
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
    rel_root = os.path.join(ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "runs")
    runs_dir = resolve_artifact_path(workspace, cache_root, rel_root)
    
    runs: List[Dict[str, Any]] = []
    if os.path.isdir(runs_dir):
        try:
            for entry in os.scandir(runs_dir):
                if not entry.is_dir():
                    continue
                run_id = entry.name
                mtime = format_mtime(entry.path)
                result_path = os.path.join(entry.path, "DIRECTOR_RESULT.json")
                status = "unknown"
                start_time = ""
                end_time = ""
                if os.path.isfile(result_path):
                    try:
                        with open(result_path, "r", encoding="utf-8") as h:
                            data = json.load(h)
                            if isinstance(data, dict):
                                status = str(data.get("status") or "unknown")
                                start_time = str(data.get("start_time") or "")
                                end_time = str(data.get("end_time") or "")
                    except Exception:
                        pass
                runs.append({
                    "id": run_id,
                    "mtime": mtime,
                    "status": status,
                    "start_time": start_time,
                    "end_time": end_time,
                })
        except Exception:
            pass
    
    # Sort by mtime descending
    runs.sort(key=lambda r: r["mtime"], reverse=True)
    return {"runs": runs[:limit]}
