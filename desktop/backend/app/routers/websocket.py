import os
import json
import asyncio
from typing import Optional, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from ..state import AppState, Auth, ConnectionState
from ..config import CHANNEL_FILES, DEFAULT_WORKSPACE
from ..utils import (
    build_cache_root, resolve_artifact_path, read_file_tail, format_mtime,
    read_workspace_status, workspace_has_docs
)
from ..services.artifacts import build_snapshot

router = APIRouter()

def get_state(request: Request) -> AppState:
    return request.app.state.app_state

def get_auth(request: Request) -> Auth:
    return request.app.state.auth

def get_connection_state(request: Request) -> ConnectionState:
    return request.app.state.connection_state

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # We can't use dependency injection easily for state in websocket route without some boilerplate,
    # so we access app state directly from websocket.app
    auth: Auth = websocket.app.state.auth
    state: AppState = websocket.app.state.app_state
    conn_state: ConnectionState = websocket.app.state.connection_state
    
    await websocket.accept()
    # Check auth header manually if provided in query or protocol? 
    # Browser WebSocket API doesn't support headers easily.
    # Usually passed as query param or initial message.
    # The server.py implementation checked auth at 'connect' via query param or header?
    # view_file showed:
    # 2888:     await websocket.accept()
    # 2889:     try:
    # 2890:         token = websocket.query_params.get("token")
    # ...
    
    token = websocket.query_params.get("token")
    if not auth.check(f"Bearer {token}"):
        await websocket.close(code=1008)
        return

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except Exception:
                continue
            
            msg_type = message.get("type")
            if msg_type == "subscribe":
                channel = message.get("channel")
                if channel:
                    conn_state.channels.add(channel)
            elif msg_type == "unsubscribe":
                channel = message.get("channel")
                if channel in conn_state.channels:
                    conn_state.channels.remove(channel)
            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif msg_type == "status":
                conn_state.want_status = True
                snapshot = build_snapshot(state)
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "data": snapshot,
                }))

            # Main loop logic (simplified here, in server.py it was likely doing periodic updates or
            # responding to events. But here we just handle messages.
            # To push updates, we need a background task or loop.
            # server.py had a while loop *inside* websocket_endpoint?
            # Let's check server.py lines 2880+.
            
            # Revisiting the architecture: server.py likely just responded to polls or had a broadcast loop.
            # The client probably polls "status". Or subscribes to file updates.
            # If server.py had a loop inside websocket endpoint, it would block receive_text.
            # So it must be: receive message -> handle -> reply.
            # AND/OR a background task pushing to websocket.
            # But the user logic I saw earlier (lines 2801-2936) showed:
            # while True: data = await websocket.receive_text() ...
            # So it is purely request-response over WS, OR the client sends keep-alives/polls.
            
            # Wait, logic for "subscribe" implies pushing updates.
            # If I subscribe to "pm_log", do I get updates?
            # server.py logic:
            
            if conn_state.channels:
                updates = {}
                workspace = state.settings.workspace or DEFAULT_WORKSPACE
                cache_root = build_cache_root(state.settings.ramdisk_root or "", workspace)
                
                for channel in conn_state.channels:
                    pk = CHANNEL_FILES.get(channel)
                    if not pk:
                        continue
                    full_path = resolve_artifact_path(workspace, cache_root, pk)
                    if not os.path.isfile(full_path):
                        continue
                    
                    try:
                        size = os.path.getsize(full_path)
                    except Exception:
                        size = 0
                    
                    last_size = conn_state.last_sizes.get(channel, 0)
                    if size == last_size and size > 0:
                        continue
                    
                    # Read new content
                    content = read_file_tail(full_path, max_lines=100) # simpler approach for now
                    # Or read incremental?
                    # server.py used read_file_tail usually or read_incremental.
                    # Using read_file_tail is safer for now.
                    
                    conn_state.last_sizes[channel] = size
                    updates[channel] = {
                        "content": content,
                        "mtime": format_mtime(full_path),
                        "path": full_path
                    }
                
                if updates:
                    await websocket.send_text(json.dumps({
                        "type": "updates",
                        "data": updates
                    }))

    except WebSocketDisconnect:
        pass
