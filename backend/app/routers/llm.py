from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from ..config import Settings
from ..state import AppState, Auth
from ..utils import build_cache_root, resolve_artifact_path
from ..services.llm_tests import run_llm_tests, load_llm_test_index, reset_llm_test_index
from ..services.llm_tests import run_llm_tests_streaming
from ..services.interactive_interview import (
    run_interactive_interview_question,
    save_interactive_interview_report,
)
from ..services.interactive_interview_streaming import (
    run_interactive_interview_streaming,
    cancel_interactive_interview_stream,
)
from ..llm import config as llm_config
from ..llm.providers import (
    ollama_health,
    ollama_list_models,
    openai_health,
    openai_list_models,
    anthropic_health,
    anthropic_list_models,
    # New enhanced providers
    provider_manager,
)
from ..utils import save_persisted_settings
from ..services.interactive_interview import (
    load_interview_history_summary,
)


router = APIRouter()


def get_state(request: Request) -> AppState:
    return request.app.state.app_state


def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")


class LlmTestPayload(BaseModel):
    role: Optional[str] = None
    provider_id: Optional[str] = None
    model: Optional[str] = None
    suites: Optional[list[str]] = None
    test_level: str = "quick"
    evaluation_mode: Optional[str] = None
    api_key: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    env_overrides: Optional[Dict[str, str]] = None
    prompt_override: Optional[str] = None


class ProviderActionPayload(BaseModel):
    api_key: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class InterviewAskPayload(BaseModel):
    role: str
    provider_id: str
    model: str
    question: str
    context: Optional[list[Dict[str, Any]]] = None
    expects_thinking: Optional[bool] = None
    criteria: Optional[list[str]] = None
    session_id: Optional[str] = None
    api_key: Optional[str] = None
    # 使用空字典作为默认值，避免 None vs {} 的兼容性问题
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    env_overrides: Optional[Dict[str, str]] = Field(default_factory=dict)
    debug: Optional[bool] = None
    
    @field_validator('session_id', mode='before')
    @classmethod
    def normalize_session_id(cls, v):
        """将空字符串或None统一处理为None"""
        if v == '' or v is None:
            return None
        return v
    
    @field_validator('context', mode='before')
    @classmethod
    def normalize_context(cls, v):
        """确保context是列表或None"""
        if v is None or v == []:
            return None
        return v
    
    @field_validator('criteria', mode='before')
    @classmethod
    def normalize_criteria(cls, v):
        """确保criteria是字符串列表或None"""
        if v is None or v == []:
            return None
        # 过滤掉非字符串项
        if isinstance(v, list):
            return [str(item) for item in v if item is not None]
        return v


class InterviewCancelPayload(BaseModel):
    session_id: str


class InterviewSavePayload(BaseModel):
    role: str
    provider_id: str
    model: str
    report: Dict[str, Any]
    session_id: Optional[str] = None


@router.get("/llm/config", dependencies=[Depends(require_auth)])
def get_llm_config(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    config = llm_config.load_llm_config(state.settings.workspace, cache_root, settings=state.settings)
    return llm_config.redact_llm_config(config)


@router.post("/llm/config", dependencies=[Depends(require_auth)])
def save_llm_config(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    state = get_state(request)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    config_payload = payload.get("config") if isinstance(payload, dict) and "config" in payload else payload
    if not isinstance(config_payload, dict):
        raise HTTPException(status_code=400, detail="invalid config payload")
    config = llm_config.save_llm_config(state.settings.workspace, cache_root, config_payload, settings=state.settings)
    reset_llm_test_index(state.settings)
    _sync_settings_from_llm(state.settings, config)
    save_persisted_settings(state.settings)
    return llm_config.redact_llm_config(config)


@router.post("/llm/providers/{provider_id}/health", dependencies=[Depends(require_auth)])
def provider_health(request: Request, provider_id: str, payload: ProviderActionPayload) -> Dict[str, Any]:
    state = get_state(request)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    config = llm_config.load_llm_config(state.settings.workspace, cache_root, settings=state.settings)
    provider_cfg = _get_provider(config, provider_id)
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    headers = payload.headers or {}
    if headers:
        provider_cfg = {**provider_cfg, "headers": {**(provider_cfg.get("headers") or {}), **headers}}
    api_key = payload.api_key or provider_cfg.get("api_key")
    if api_key:
        provider_cfg = {**provider_cfg, "api_key": api_key}
    
    # Try enhanced providers first
    provider_instance = provider_manager.get_provider_instance(provider_type)
    if provider_instance:
        return provider_instance.health(provider_cfg).to_dict()
    
    # Fallback to function-based providers
    if provider_type == "ollama":
        return ollama_health(provider_cfg).to_dict()
    if provider_type == "openai_compat":
        return openai_health(provider_cfg, api_key).to_dict()
    if provider_type == "anthropic_compat":
        return anthropic_health(provider_cfg, api_key).to_dict()
    
    raise HTTPException(status_code=400, detail="unsupported provider type")


@router.post("/llm/providers/{provider_id}/models", dependencies=[Depends(require_auth)])
def provider_models(request: Request, provider_id: str, payload: ProviderActionPayload) -> Dict[str, Any]:
    state = get_state(request)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    config = llm_config.load_llm_config(state.settings.workspace, cache_root, settings=state.settings)
    provider_cfg = _get_provider(config, provider_id)
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    headers = payload.headers or {}
    if headers:
        provider_cfg = {**provider_cfg, "headers": {**(provider_cfg.get("headers") or {}), **headers}}
    api_key = payload.api_key or provider_cfg.get("api_key")
    if api_key:
        provider_cfg = {**provider_cfg, "api_key": api_key}
    
    # Try enhanced providers first
    provider_instance = provider_manager.get_provider_instance(provider_type)
    if provider_instance:
        return provider_instance.list_models(provider_cfg).to_dict()
    
    # Fallback to function-based providers
    if provider_type == "ollama":
        return ollama_list_models(provider_cfg).to_dict()
    if provider_type == "openai_compat":
        return openai_list_models(provider_cfg, api_key).to_dict()
    if provider_type == "anthropic_compat":
        return anthropic_list_models(provider_cfg, api_key).to_dict()
    
    raise HTTPException(status_code=400, detail="unsupported provider type")


@router.post("/llm/test", dependencies=[Depends(require_auth)])
def llm_test(request: Request, payload: LlmTestPayload) -> Dict[str, Any]:
    state = get_state(request)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    config = llm_config.load_llm_config(state.settings.workspace, cache_root, settings=state.settings)
    
    role = payload.role.strip().lower() if payload.role else ""
    is_connectivity_test = role == "connectivity" or not role
    
    provider_id = payload.provider_id
    model = payload.model
    
    if is_connectivity_test:
        if not provider_id or not model:
            raise HTTPException(status_code=400, detail="连通性测试需要提供 provider_id 和 model")
    else:
        role_cfg = config.get("roles", {}).get(role)
        if not isinstance(role_cfg, dict):
            raise HTTPException(status_code=404, detail=f"角色 '{role}' 未配置")
        if not provider_id:
            provider_id = role_cfg.get("provider_id")
        if not model:
            model = role_cfg.get("model")
        if not provider_id or not model:
            raise HTTPException(status_code=400, detail="provider_id/model required")
    
    suites = payload.suites or ["connectivity", "response"]
    report = run_llm_tests(
        state.settings,
        role or "connectivity",
        str(provider_id),
        str(model),
        list(suites),
        payload.test_level or "quick",
        evaluation_mode=payload.evaluation_mode,
        api_key=payload.api_key,
        extra_headers=payload.headers,
        env_overrides=payload.env_overrides,
        prompt_override=payload.prompt_override,
    )
    return report


@router.post("/llm/test/stream", dependencies=[Depends(require_auth)])
async def llm_test_stream(request: Request, payload: LlmTestPayload):
    """Stream LLM test results using Server-Sent Events (SSE)
    
    This endpoint provides real-time output from LLM tests as they execute,
    allowing the client to see progress for each test suite as it completes.
    Supports connectivity-only tests without role dependency when role='connectivity'.
    """
    state = get_state(request)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    config = llm_config.load_llm_config(state.settings.workspace, cache_root, settings=state.settings)
    
    role = payload.role.strip().lower() if payload.role else ""
    is_connectivity_test = role == "connectivity" or not role
    
    provider_id = payload.provider_id
    model = payload.model
    
    if is_connectivity_test:
        if not provider_id or not model:
            raise HTTPException(status_code=400, detail="连通性测试需要提供 provider_id 和 model")
    else:
        role_cfg = config.get("roles", {}).get(role)
        if not isinstance(role_cfg, dict):
            raise HTTPException(status_code=404, detail=f"角色 '{role}' 未配置")
        if not provider_id:
            provider_id = role_cfg.get("provider_id")
        if not model:
            model = role_cfg.get("model")
        if not provider_id or not model:
            raise HTTPException(status_code=400, detail="provider_id/model required")
    
    suites = payload.suites or ["connectivity", "response"]
    run_id = f"test-{uuid4().hex[:12]}"
    
    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        
        async def run_tests():
            try:
                result = await run_llm_tests_streaming(
                    state.settings,
                    role or "connectivity",
                    str(provider_id),
                    str(model),
                    list(suites),
                    payload.test_level or "quick",
                    evaluation_mode=payload.evaluation_mode,
                    api_key=payload.api_key,
                    extra_headers=payload.headers,
                    env_overrides=payload.env_overrides,
                    prompt_override=payload.prompt_override,
                    output_queue=queue,
                )
            except Exception as exc:
                await queue.put({"type": "error", "data": {"error": str(exc)}})
        
        task = asyncio.create_task(run_tests())
        
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                    
                    event_type = event.get("type", "message")
                    event_data = event.get("data", {})
                    
                    if event_type == "complete":
                        yield f"event: complete\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                        break
                    elif event_type == "error":
                        yield f"event: error\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                        break
                    else:
                        yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                        
                except asyncio.TimeoutError:
                    yield f"event: ping\ndata: {{}}\n\n"
                    
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/llm/interview/ask", dependencies=[Depends(require_auth)])
def llm_interview_ask(request: Request, payload: InterviewAskPayload) -> Dict[str, Any]:
    state = get_state(request)
    return run_interactive_interview_question(
        state.settings,
        payload.role,
        payload.provider_id,
        payload.model,
        payload.question,
        session_id=payload.session_id,
        context=payload.context,
        expects_thinking=payload.expects_thinking,
        criteria=payload.criteria,
        api_key=payload.api_key,
        extra_headers=payload.headers,
        env_overrides=payload.env_overrides,
        debug=payload.debug,
    )


@router.post("/llm/interview/save", dependencies=[Depends(require_auth)])
def llm_interview_save(request: Request, payload: InterviewSavePayload) -> Dict[str, Any]:
    state = get_state(request)
    return save_interactive_interview_report(
        state.settings,
        payload.role,
        payload.provider_id,
        payload.model,
        payload.report,
        session_id=payload.session_id,
    )


@router.post("/llm/interview/cancel", dependencies=[Depends(require_auth)])
def llm_interview_cancel(payload: InterviewCancelPayload) -> Dict[str, Any]:
    # Best-effort cancellation (primarily for Codex CLI streaming subprocess).
    return cancel_interactive_interview_stream(payload.session_id)


@router.post("/llm/interview/stream", dependencies=[Depends(require_auth)])
async def llm_interview_stream(request: Request, payload: InterviewAskPayload):
    """Stream interview responses using Server-Sent Events (SSE)
    
    This endpoint provides real-time output from the LLM as it executes,
    allowing the client to see progress before the final result is ready.
    """
    state = get_state(request)
    run_id = payload.session_id or f"interactive-{uuid4().hex}"
    
    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        
        # Start the interview in a background task
        async def run_interview():
            try:
                result = await run_interactive_interview_streaming(
                    state.settings,
                    payload.role,
                    payload.provider_id,
                    payload.model,
                    payload.question,
                    session_id=run_id,
                    context=payload.context,
                    expects_thinking=payload.expects_thinking,
                    criteria=payload.criteria,
                    api_key=payload.api_key,
                    extra_headers=payload.headers,
                    env_overrides=payload.env_overrides,
                    output_queue=queue,
                )
                await queue.put({"type": "complete", "data": result})
            except Exception as exc:
                await queue.put({"type": "error", "data": {"error": str(exc)}})
        
        # Start the interview task
        task = asyncio.create_task(run_interview())
        
        # Stream events as they arrive
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                    
                    if event.get("type") == "complete":
                        yield f"event: complete\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                        break
                    elif event.get("type") == "error":
                        yield f"event: error\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                        break
                    else:
                        # Regular progress event
                        yield f"event: {event.get('type', 'message')}\ndata: {json.dumps(event.get('data', {}), ensure_ascii=False)}\n\n"
                        
                except asyncio.TimeoutError:
                    yield f"event: ping\ndata: {{}}\n\n"
                    
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            # Ensure any Codex CLI subprocess is terminated when the client disconnects.
            try:
                await asyncio.to_thread(cancel_interactive_interview_stream, run_id)
            except Exception:
                pass
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/llm/test/{test_run_id}", dependencies=[Depends(require_auth)])
def llm_test_report(request: Request, test_run_id: str) -> Dict[str, Any]:
    state = get_state(request)
    report_path = _resolve_test_path(state.settings, test_run_id, "LLM_TEST_REPORT.json")
    if not report_path or not os.path.isfile(report_path):
        raise HTTPException(status_code=404, detail="report not found")
    try:
        with open(report_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        raise HTTPException(status_code=500, detail="failed to read report")
    return data


@router.get("/llm/test/{test_run_id}/transcript", dependencies=[Depends(require_auth)])
def llm_test_transcript(request: Request, test_run_id: str) -> Dict[str, Any]:
    state = get_state(request)
    transcript_path = _resolve_test_path(state.settings, test_run_id, "LLM_TEST_TRANSCRIPT.md")
    if not transcript_path or not os.path.isfile(transcript_path):
        raise HTTPException(status_code=404, detail="transcript not found")
    try:
        with open(transcript_path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except Exception:
        raise HTTPException(status_code=500, detail="failed to read transcript")
    return {"ok": True, "content": content}


@router.get("/llm/status", dependencies=[Depends(require_auth)])
def llm_status(request: Request) -> Dict[str, Any]:
    state = get_state(request)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    config = llm_config.load_llm_config(state.settings.workspace, cache_root, settings=state.settings)
    index = load_llm_test_index(state.settings)
    roles_cfg = config.get("roles", {}) if isinstance(config.get("roles"), dict) else {}
    providers = config.get("providers", {}) if isinstance(config.get("providers"), dict) else {}
    provider_index = index.get("providers", {}) if isinstance(index.get("providers"), dict) else {}
    roles_status: Dict[str, Any] = {}
    providers_status: Dict[str, Any] = {}
    for role, role_cfg in roles_cfg.items():
        if not isinstance(role_cfg, dict):
            continue
        provider_id = role_cfg.get("provider_id")
        provider_cfg = providers.get(provider_id, {}) if isinstance(providers, dict) else {}
        test_info = (index.get("roles") or {}).get(role) if isinstance(index, dict) else None
        runtime_supported = _runtime_supported(role, provider_id, provider_cfg)
        roles_status[role] = {
            "provider_id": provider_id,
            "model": role_cfg.get("model"),
            "profile": role_cfg.get("profile"),
            "ready": bool(test_info.get("ready")) if isinstance(test_info, dict) else False,
            "grade": test_info.get("grade") if isinstance(test_info, dict) else "UNKNOWN",
            "last_run_id": test_info.get("last_run_id") if isinstance(test_info, dict) else None,
            "timestamp": test_info.get("timestamp") if isinstance(test_info, dict) else None,
            "suites": test_info.get("suites") if isinstance(test_info, dict) else None,
            "runtime_supported": runtime_supported,
        }
    for provider_id, provider_cfg in providers.items():
        if not isinstance(provider_cfg, dict):
            continue
        test_info = provider_index.get(provider_id) if isinstance(provider_index, dict) else None
        providers_status[provider_id] = {
            "ready": test_info.get("ready") if isinstance(test_info, dict) else None,
            "grade": test_info.get("grade") if isinstance(test_info, dict) else "UNKNOWN",
            "last_run_id": test_info.get("last_run_id") if isinstance(test_info, dict) else None,
            "timestamp": test_info.get("timestamp") if isinstance(test_info, dict) else None,
            "suites": test_info.get("suites") if isinstance(test_info, dict) else None,
            "model": test_info.get("model") if isinstance(test_info, dict) else None,
            "role": test_info.get("role") if isinstance(test_info, dict) else None,
        }
    required = config.get("policies", {}).get("required_ready_roles") or []
    blocked = [r for r in required if not roles_status.get(r, {}).get("ready")]
    unsupported = [r for r in required if not roles_status.get(r, {}).get("runtime_supported")]
    global_state = "READY"
    if blocked or unsupported:
        global_state = "BLOCKED"

    interview_summary = load_interview_history_summary(state.settings)

    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    config_path = llm_config.llm_config_path(state.settings.workspace, cache_root)
    last_updated: Optional[str] = None
    if os.path.isfile(config_path):
        try:
            mtime = os.path.getmtime(config_path)
            dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            last_updated = dt.isoformat()
        except Exception:
            pass

    return {
        "roles": roles_status,
        "providers": providers_status,
        "required_ready_roles": required,
        "blocked_roles": blocked,
        "unsupported_roles": unsupported,
        "state": global_state,
        "interviews": interview_summary,
        "last_updated": last_updated,
    }


def _get_provider(config: Dict[str, Any], provider_id: str) -> Dict[str, Any]:
    providers = config.get("providers") or {}
    provider_cfg = providers.get(provider_id)
    if not isinstance(provider_cfg, dict):
        raise HTTPException(status_code=404, detail="provider not found")
    return provider_cfg


def _resolve_test_path(settings: Settings, run_id: str, filename: str) -> str:
    if not re.match(r"^[A-Za-z0-9_.-]+$", run_id or ""):
        raise HTTPException(status_code=400, detail="invalid test run id")
    cache_root = build_cache_root(settings.ramdisk_root or "", settings.workspace)
    rel = f".harborpilot/runtime/llm_tests/{run_id}/{filename}"
    return resolve_artifact_path(settings.workspace, cache_root, rel)


def _sync_settings_from_llm(settings: Settings, config: Dict[str, Any]) -> None:
    roles = config.get("roles", {}) if isinstance(config.get("roles"), dict) else {}
    providers = config.get("providers", {}) if isinstance(config.get("providers"), dict) else {}

    pm_role = roles.get("pm") if isinstance(roles.get("pm"), dict) else None
    if pm_role:
        provider_id = pm_role.get("provider_id")
        provider_cfg = providers.get(provider_id, {}) if isinstance(providers, dict) else {}
        provider_type = str(provider_cfg.get("type") or "").strip().lower()
        command = str(provider_cfg.get("command") or "").lower()
        if provider_type == "ollama":
            settings.pm_backend = "ollama"
        elif provider_type in ("cli", "codex_cli", "codex_sdk") and ("codex" in command or provider_id == "codex_cli" or provider_type == "codex_sdk"):
            settings.pm_backend = "codex"
        if pm_role.get("model"):
            settings.pm_model = pm_role.get("model")

    director_role = roles.get("director") if isinstance(roles.get("director"), dict) else None
    if director_role:
        provider_id = director_role.get("provider_id")
        provider_cfg = providers.get(provider_id, {}) if isinstance(providers, dict) else {}
        provider_type = str(provider_cfg.get("type") or "").strip().lower()
        if provider_type == "ollama" and director_role.get("model"):
            settings.director_model = director_role.get("model")

    docs_role = roles.get("docs") if isinstance(roles.get("docs"), dict) else None
    if docs_role:
        provider_id = docs_role.get("provider_id")
        provider_cfg = providers.get(provider_id, {}) if isinstance(providers, dict) else {}
        provider_type = str(provider_cfg.get("type") or "").strip().lower()
        command = str(provider_cfg.get("command") or "").lower()
        if provider_type == "ollama":
            settings.docs_init_provider = "ollama"
        elif provider_type in ("cli", "codex_cli", "codex_sdk") and ("codex" in command or provider_id == "codex_cli" or provider_type == "codex_sdk"):
            settings.docs_init_provider = "codex"
        elif provider_type == "openai_compat":
            settings.docs_init_provider = "custom"
            if provider_cfg.get("base_url"):
                settings.docs_init_base_url = provider_cfg.get("base_url")
            if provider_cfg.get("api_path"):
                settings.docs_init_api_path = provider_cfg.get("api_path")
        if docs_role.get("model"):
            settings.docs_init_model = docs_role.get("model")


@router.get("/llm/providers", dependencies=[Depends(require_auth)])
def list_providers(request: Request) -> Dict[str, Any]:
    """List all available providers with their information"""
    try:
        providers_info = provider_manager.list_provider_info()
        return {
            "providers": [info.__dict__ if hasattr(info, '__dict__') else {
                "name": info.name,
                "type": info.type,
                "description": info.description,
                "version": info.version,
                "author": info.author,
                "documentation_url": info.documentation_url,
                "supported_features": info.supported_features,
                "cost_class": info.cost_class,
                "provider_category": getattr(info, 'provider_category', 'LLM'),
                "autonomous_file_access": getattr(info, 'autonomous_file_access', False),
                "requires_file_interfaces": getattr(info, 'requires_file_interfaces', True),
                "model_listing_method": getattr(info, 'model_listing_method', 'API')
            } for info in providers_info]
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/llm/providers/{provider_type}/info", dependencies=[Depends(require_auth)])
def get_provider_info(request: Request, provider_type: str) -> Dict[str, Any]:
    """Get detailed information about a specific provider"""
    try:
        info = provider_manager.get_provider_info(provider_type)
        if not info:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        return {
            "name": info.name,
            "type": info.type,
            "description": info.description,
            "version": info.version,
            "author": info.author,
            "documentation_url": info.documentation_url,
            "supported_features": info.supported_features,
            "cost_class": info.cost_class
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/llm/providers/{provider_type}/config", dependencies=[Depends(require_auth)])
def get_provider_default_config(request: Request, provider_type: str) -> Dict[str, Any]:
    """Get default configuration for a provider"""
    try:
        config = provider_manager.get_provider_default_config(provider_type)
        if config is None:
            raise HTTPException(status_code=404, detail="Provider not found")
        return config
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/llm/providers/{provider_type}/validate", dependencies=[Depends(require_auth)])
def validate_provider_config(request: Request, provider_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate provider configuration"""
    try:
        result = provider_manager.get_provider_class(provider_type).validate_config(payload)
        return {
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "normalized_config": result.normalized_config
        }
    except Exception as exc:
        return {
            "valid": False,
            "errors": [str(exc)],
            "warnings": [],
            "normalized_config": None
        }


@router.post("/llm/config/migrate", dependencies=[Depends(require_auth)])
def migrate_config(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate legacy configuration to new provider format"""
    try:
        migrated = provider_manager.migrate_legacy_config(payload)
        return migrated
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/llm/providers/health-all", dependencies=[Depends(require_auth)])
def health_check_all(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Perform health checks on all configured providers"""
    try:
        configs = payload.get("providers", {})
        results = provider_manager.health_check_all(configs)
        return results
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _runtime_supported(role: str, provider_id: Optional[str], provider_cfg: Dict[str, Any]) -> bool:
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    command = str(provider_cfg.get("command") or "").lower()
    role = role.strip().lower()
    if role == "pm":
        if provider_type == "ollama":
            return True
        if provider_type == "codex_sdk":
            return True
        if provider_type in ("cli", "codex_cli") and ("codex" in command or provider_id == "codex_cli"):
            return True
        return False
    if role == "director":
        return provider_type == "ollama"
    return True


# ============================================================================
# Runtime Status API
# ============================================================================

@router.get("/llm/runtime-status", dependencies=[Depends(require_auth)])
def get_runtime_status(request: Request) -> Dict[str, Any]:
    """Get runtime execution status for all roles"""
    state = get_state(request)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    runtime_dir = os.path.join(cache_root, ".harborpilot", "runtime")
    
    status = {}
    
    for role_id in ['pm', 'director', 'qa', 'docs']:
        role_status = {
            'running': False,
            'lastRun': None,
            'config': {
                'provider_id': None,
                'model': None,
            }
        }
        
        # Check if role is running (lock file exists)
        lock_file = os.path.join(runtime_dir, f"{role_id}.lock")
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    lock_data = json.load(f)
                    role_status['running'] = True
                    role_status['startedAt'] = lock_data.get('startedAt')
            except:
                role_status['running'] = True
        
        # Get last run time
        status_file = os.path.join(runtime_dir, f"{role_id}_status.json")
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                    role_status['lastRun'] = status_data.get('lastRun')
                    role_status['lastStatus'] = status_data.get('status')
            except:
                pass
        
        # Get role configuration
        try:
            from ..llm.runtime_config import runtime_config
            role_config = runtime_config.get_role_config(role_id)
            if role_config:
                role_status['config'] = {
                    'provider_id': role_config.provider_id,
                    'model': role_config.model,
                    'profile': role_config.profile
                }
        except Exception as e:
            print(f"[RuntimeStatus] Failed to get config for {role_id}: {e}")
        
        status[role_id] = role_status
    
    return {
        'roles': status,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


@router.get("/llm/runtime-status/{role_id}", dependencies=[Depends(require_auth)])
def get_role_runtime_status(request: Request, role_id: str) -> Dict[str, Any]:
    """Get runtime status for a specific role"""
    if role_id not in ['pm', 'director', 'qa', 'docs']:
        raise HTTPException(status_code=400, detail="invalid role_id")
    
    state = get_state(request)
    cache_root = build_cache_root(state.settings.ramdisk_root or "", state.settings.workspace)
    runtime_dir = os.path.join(cache_root, ".harborpilot", "runtime")
    
    role_status = {
        'roleId': role_id,
        'running': False,
        'lastRun': None,
        'config': {
            'provider_id': None,
            'model': None,
        }
    }
    
    # Check if running
    lock_file = os.path.join(runtime_dir, f"{role_id}.lock")
    if os.path.exists(lock_file):
        role_status['running'] = True
        try:
            with open(lock_file, 'r') as f:
                lock_data = json.load(f)
                role_status['startedAt'] = lock_data.get('startedAt')
                role_status['pid'] = lock_data.get('pid')
        except:
            pass
    
    # Get last run
    status_file = os.path.join(runtime_dir, f"{role_id}_status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                status_data = json.load(f)
                role_status['lastRun'] = status_data.get('lastRun')
                role_status['lastStatus'] = status_data.get('status')
                role_status['lastError'] = status_data.get('error')
        except:
            pass
    
    # Get config
    try:
        from ..llm.runtime_config import runtime_config
        role_config = runtime_config.get_role_config(role_id)
        if role_config:
            role_status['config'] = {
                'provider_id': role_config.provider_id,
                'model': role_config.model,
                'profile': role_config.profile
            }
    except Exception as e:
        print(f"[RuntimeStatus] Failed to get config for {role_id}: {e}")
    
    return role_status
