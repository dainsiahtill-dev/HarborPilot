import os
import json
import asyncio
from typing import Dict, Any, Optional, Set, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..state import AppState, Auth
from ..config import CHANNEL_FILES, DEFAULT_WORKSPACE
from ..utils import (
    build_cache_root,
    resolve_artifact_path,
    read_file_tail,
    read_incremental,
    get_lancedb_status,
)
from ..services.artifacts import (
    build_snapshot,
    build_memory_payload,
    build_success_stats_payload,
    read_director_status,
)
from ..services.process import terminate_process
from core.harborpilot_loop.anthropomorphic.integration import (
    get_memory_store,
    get_reflection_store,
    init_anthropomorphic_modules,
)

router = APIRouter()


def _build_pm_status(state: AppState) -> Dict[str, Any]:
    running = False
    pid = None
    if state.pm.process:
        if state.pm.process.poll() is None:
            running = True
            pid = state.pm.process.pid
        else:
            terminate_process(state.pm)
    return {
        "running": running,
        "pid": pid,
        "mode": state.pm.mode,
        "started_at": state.pm.started_at,
    }


def _build_director_status(state: AppState, workspace: str, cache_root: str) -> Dict[str, Any]:
    running = False
    pid = None
    if state.director.process:
        if state.director.process.poll() is None:
            running = True
            pid = state.director.process.pid
        else:
            terminate_process(state.director)
    status_data = read_director_status(workspace, cache_root)
    return {
        "running": running,
        "pid": pid,
        "mode": state.director.mode,
        "started_at": state.director.started_at,
        "status": status_data,
    }


def _build_anthro_state(state: AppState) -> Optional[Dict[str, Any]]:
    try:
        base_dir = state.settings.ramdisk_root or state.settings.workspace or DEFAULT_WORKSPACE
        init_anthropomorphic_modules(base_dir)
        mem_store = get_memory_store()
        ref_store = get_reflection_store()
        if not mem_store:
            return None
        last_step = 0
        total_reflections = 0
        if ref_store:
            last_step = ref_store.get_last_reflection_step()
            total_reflections = len(ref_store.reflections)
        recent_errors = mem_store.count_recent_errors(last_step)
        total_memories = len(mem_store.memories)
        return {
            "last_reflection_step": last_step,
            "recent_error_count": recent_errors,
            "total_memories": total_memories,
            "total_reflections": total_reflections,
        }
    except Exception:
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    auth: Auth = websocket.app.state.auth
    state: AppState = websocket.app.state.app_state

    await websocket.accept()
    token = websocket.query_params.get("token")
    if not auth.check(f"Bearer {token}"):
        await websocket.close(code=1008)
        return

    send_lock = asyncio.Lock()
    subscriptions: Set[str] = set()
    channel_states: Dict[str, Dict[str, Any]] = {}
    tail_lines = 200
    active = True

    async def send_json(payload: Dict[str, Any]) -> None:
        async with send_lock:
            await websocket.send_text(json.dumps(payload))

    async def send_status() -> None:
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        payload: Dict[str, Any] = {
            "type": "status",
            "pm_status": _build_pm_status(state),
            "director_status": _build_director_status(state, workspace, cache_root),
            "snapshot": build_snapshot(state),
            "lancedb": get_lancedb_status(),
            "memory": build_memory_payload(workspace, cache_root),
            "success_stats": build_success_stats_payload(workspace, cache_root),
            "anthro_state": _build_anthro_state(state),
        }
        await send_json(payload)

    def resolve_channel_path(channel: str) -> str:
        rel = CHANNEL_FILES.get(channel)
        if not rel:
            return ""
        workspace = state.settings.workspace or DEFAULT_WORKSPACE
        cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
        return resolve_artifact_path(workspace, cache_root, rel)

    async def send_snapshot_for_channel(channel: str, path: str) -> None:
        content = read_file_tail(path, max_lines=tail_lines)
        lines = content.splitlines() if content else []
        await send_json({"type": "snapshot", "channel": channel, "lines": lines})
        try:
            channel_states[channel]["pos"] = os.path.getsize(path)
        except Exception:
            channel_states[channel]["pos"] = 0

    async def send_incremental_for_channel(channel: str, path: str) -> None:
        state_obj = channel_states.setdefault(channel, {"pos": 0})
        lines = read_incremental(path, state_obj, max_chars=20000)
        for line in lines:
            await send_json({"type": "line", "channel": channel, "text": line})

    async def push_loop() -> None:
        interval_sec = max(1, int(getattr(state.settings, "refresh_interval", 3) or 3))
        while active:
            await asyncio.sleep(interval_sec)
            if "status" in subscriptions or not subscriptions:
                await send_status()
            for channel in list(subscriptions):
                if channel == "status":
                    continue
                path = resolve_channel_path(channel)
                if not path or not os.path.isfile(path):
                    continue
                state_obj = channel_states.setdefault(channel, {"pos": 0})
                if state_obj.pop("snapshot", False):
                    await send_snapshot_for_channel(channel, path)
                await send_incremental_for_channel(channel, path)

    async def handle_subscribe(message: Dict[str, Any]) -> None:
        nonlocal tail_lines
        channels = message.get("channels")
        if not channels:
            channel = message.get("channel")
            channels = [channel] if channel else []
        if isinstance(channels, str):
            channels = [channels]
        if not isinstance(channels, list):
            channels = []
        requested_lines = message.get("tail_lines")
        if isinstance(requested_lines, int) and requested_lines > 0:
            tail_lines = requested_lines
        for channel in channels:
            if not isinstance(channel, str):
                continue
            subscriptions.add(channel)
            channel_states.setdefault(channel, {"pos": 0})["snapshot"] = True
        if "status" in subscriptions:
            await send_status()

    async def handle_unsubscribe(message: Dict[str, Any]) -> None:
        channels = message.get("channels")
        if not channels:
            channel = message.get("channel")
            channels = [channel] if channel else []
        if isinstance(channels, str):
            channels = [channels]
        if not isinstance(channels, list):
            channels = []
        for channel in channels:
            if not isinstance(channel, str):
                continue
            subscriptions.discard(channel)
            channel_states.pop(channel, None)

    sender_task = asyncio.create_task(push_loop())

    try:
        await send_status()
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except Exception:
                continue
            msg_type = message.get("type")
            if msg_type == "subscribe":
                await handle_subscribe(message)
            elif msg_type == "unsubscribe":
                await handle_unsubscribe(message)
            elif msg_type == "ping":
                await send_json({"type": "pong"})
            elif msg_type == "status":
                await send_status()
    except WebSocketDisconnect:
        pass
    finally:
        active = False
        sender_task.cancel()
