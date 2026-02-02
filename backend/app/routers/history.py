import os
import json
from typing import Dict, Any, List, Optional
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

@router.get("/history/tasks", dependencies=[Depends(require_auth)])
def history_tasks(request: Request, limit: int = 50) -> Dict[str, Any]:
    """获取PM任务历史记录"""
    state = get_state(request)
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    
    # 任务历史文件路径
    task_history_path = os.path.join(workspace, ".harborpilot", "runtime", "TASK_HISTORY.json")
    
    tasks_history: List[Dict[str, Any]] = []
    
    if os.path.isfile(task_history_path):
        try:
            with open(task_history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "rounds" in data:
                    tasks_history = data["rounds"]
        except Exception:
            pass
    
    # 按时间戳降序排序
    tasks_history.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return {"rounds": tasks_history[:limit]}

@router.get("/history/rounds", dependencies=[Depends(require_auth)])
def history_rounds(request: Request, limit: int = 50) -> Dict[str, Any]:
    """获取完整的PM/Director轮次历史"""
    state = get_state(request)
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    
    # 获取任务历史
    task_history_path = os.path.join(workspace, ".harborpilot", "runtime", "TASK_HISTORY.json")
    task_rounds: List[Dict[str, Any]] = []
    
    if os.path.isfile(task_history_path):
        try:
            with open(task_history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "rounds" in data:
                    task_rounds = data["rounds"]
        except Exception:
            pass
    
    # 获取Director运行历史并合并
    cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
    rel_root = os.path.join(ARTIFACT_ROOT, ARTIFACT_NAMESPACE, "runs")
    runs_dir = resolve_artifact_path(workspace, cache_root, rel_root)
    
    director_runs: Dict[str, Dict[str, Any]] = {}
    if os.path.isdir(runs_dir):
        try:
            for entry in os.scandir(runs_dir):
                if not entry.is_dir():
                    continue
                run_id = entry.name
                result_path = os.path.join(entry.path, "DIRECTOR_RESULT.json")
                if os.path.isfile(result_path):
                    try:
                        with open(result_path, "r", encoding="utf-8") as h:
                            result_data = json.load(h)
                            if isinstance(result_data, dict):
                                director_runs[run_id] = {
                                    "status": result_data.get("status", "unknown"),
                                    "start_time": result_data.get("start_time", ""),
                                    "end_time": result_data.get("end_time", ""),
                                    "successes": result_data.get("successes", 0),
                                    "total": result_data.get("total", 0),
                                }
                    except Exception:
                        pass
        except Exception:
            pass
    
    # 合并任务历史和Director执行结果
    merged_rounds = []
    for round_data in task_rounds:
        round_id = round_data.get("round_id", "")
        director_result = director_runs.get(round_id, {})
        
        merged_round = {
            **round_data,
            "director_results": director_result
        }
        merged_rounds.append(merged_round)
    
    # 按时间戳降序排序
    merged_rounds.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return {"rounds": merged_rounds[:limit]}

@router.get("/history/round/{round_id}", dependencies=[Depends(require_auth)])
def history_round_detail(request: Request, round_id: str) -> Dict[str, Any]:
    """获取特定轮次的详细信息"""
    state = get_state(request)
    workspace = state.settings.workspace or DEFAULT_WORKSPACE
    
    # 从任务历史中查找
    task_history_path = os.path.join(workspace, ".harborpilot", "runtime", "TASK_HISTORY.json")
    round_detail: Optional[Dict[str, Any]] = None
    
    if os.path.isfile(task_history_path):
        try:
            with open(task_history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "rounds" in data:
                    for round_data in data["rounds"]:
                        if round_data.get("round_id") == round_id:
                            round_detail = round_data
                            break
        except Exception:
            pass
    
    if not round_detail:
        raise HTTPException(status_code=404, detail=f"Round {round_id} not found")
    
    # 尝试加载相关的工件内容
    artifacts = round_detail.get("artifacts", {})
    artifact_contents = {}
    
    for artifact_type, path in artifacts.items():
        full_path = os.path.join(workspace, path)
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    if artifact_type == "events_path":
                        # 事件文件可能是JSONL格式，只读取最后几行
                        lines = f.readlines()
                        artifact_contents[artifact_type] = "".join(lines[-50:])  # 最后50行
                    else:
                        artifact_contents[artifact_type] = f.read()
            except Exception:
                artifact_contents[artifact_type] = f"Error reading {path}"
    
    return {
        "round": round_detail,
        "artifact_contents": artifact_contents
    }
