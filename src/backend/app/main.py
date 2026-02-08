from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
    
    # 全局请求验证错误处理器 - 提供详细的验证错误信息
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        # 简化错误信息以便前端理解
        simplified_errors = []
        for error in errors:
            simplified_errors.append({
                "field": " -> ".join(str(loc) for loc in error.get("loc", [])),
                "type": error.get("type", "unknown"),
                "msg": error.get("msg", "Unknown error"),
                "input": str(error.get("input", "N/A"))[:100]  # 限制长度
            })
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Request validation failed",
                "errors": simplified_errors
            }
        )
    
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
    app.include_router(websocket.router)
    app.include_router(anthropomorphic.router)
    app.include_router(llm.router)
    app.include_router(turbo.router)
    app.include_router(arsenal.router)
    return app
