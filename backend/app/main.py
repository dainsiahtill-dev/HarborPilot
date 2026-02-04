from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from .state import AppState, Auth, ConnectionState
from .routers import (
    system, files, docs, agents, pm, director, ollama, lancedb, memos, history, websocket, anthropomorphic, llm, turbo, arsenal
)

def create_app(state: AppState, auth: Auth, cors_origins: List[str]) -> FastAPI:
    app = FastAPI(title="HarborPilot Desktop Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
    
    # Store state in app.state for easy access in routers
    app.state.app_state = state
    app.state.auth = auth
    app.state.connection_state = ConnectionState()
    
    app.include_router(system.router)
    app.include_router(files.router)
    app.include_router(docs.router)
    app.include_router(agents.router)
    app.include_router(pm.router)
    app.include_router(director.router)
    app.include_router(ollama.router)
    app.include_router(lancedb.router)
    app.include_router(memos.router)
    app.include_router(history.router)
    app.include_router(history.router)
    app.include_router(websocket.router)
    app.include_router(anthropomorphic.router)
    app.include_router(llm.router)
    app.include_router(turbo.router)
    app.include_router(arsenal.router)
    
    return app
