from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..state import AppState, Auth
from ..utils import build_cache_root, resolve_artifact_path
from ..services.llm_tests import run_llm_tests, load_llm_test_index, reset_llm_test_index
from ..llm import config as llm_config
from ..llm.providers import (
    cli_health,
    cli_list_models,
    ollama_health,
    ollama_list_models,
    openai_health,
    openai_list_models,
    anthropic_health,
    anthropic_list_models,
)
from ..utils import save_persisted_settings

router = APIRouter()


def get_state(request: Request) -> AppState:
    return request.app.state.app_state


def require_auth(request: Request):
    auth: Auth = request.app.state.auth
    if not auth.check(request.headers.get("authorization", "")):
        raise HTTPException(status_code=401, detail="unauthorized")


class LlmTestPayload(BaseModel):
    role: str
    provider_id: Optional[str] = None
    model: Optional[str] = None
    suites: Optional[list[str]] = None
    test_level: str = "quick"
    api_key: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class ProviderActionPayload(BaseModel):
    api_key: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


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
    if provider_type == "cli":
        return cli_health(provider_cfg).to_dict()
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
    if provider_type == "cli":
        return cli_list_models(provider_cfg).to_dict()
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
    role = payload.role.strip().lower()
    role_cfg = config.get("roles", {}).get(role)
    if not isinstance(role_cfg, dict):
        raise HTTPException(status_code=404, detail="role not configured")
    provider_id = payload.provider_id or role_cfg.get("provider_id")
    model = payload.model or role_cfg.get("model")
    if not provider_id or not model:
        raise HTTPException(status_code=400, detail="provider_id/model required")
    suites = payload.suites or config.get("policies", {}).get("test_required_suites") or []
    report = run_llm_tests(
        state.settings,
        role,
        str(provider_id),
        str(model),
        list(suites),
        payload.test_level or "quick",
        api_key=payload.api_key,
        extra_headers=payload.headers,
    )
    return report


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
    roles_status: Dict[str, Any] = {}
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
    required = config.get("policies", {}).get("required_ready_roles") or []
    blocked = [r for r in required if not roles_status.get(r, {}).get("ready")]
    unsupported = [r for r in required if not roles_status.get(r, {}).get("runtime_supported")]
    global_state = "READY"
    if blocked or unsupported:
        global_state = "BLOCKED"
    return {
        "roles": roles_status,
        "required_ready_roles": required,
        "blocked_roles": blocked,
        "unsupported_roles": unsupported,
        "state": global_state,
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
        elif provider_type == "cli" and ("codex" in command or provider_id == "codex_cli"):
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
        elif provider_type == "cli" and ("codex" in command or provider_id == "codex_cli"):
            settings.docs_init_provider = "codex"
        elif provider_type == "openai_compat":
            settings.docs_init_provider = "custom"
            if provider_cfg.get("base_url"):
                settings.docs_init_base_url = provider_cfg.get("base_url")
            if provider_cfg.get("api_path"):
                settings.docs_init_api_path = provider_cfg.get("api_path")
        if docs_role.get("model"):
            settings.docs_init_model = docs_role.get("model")


def _runtime_supported(role: str, provider_id: Optional[str], provider_cfg: Dict[str, Any]) -> bool:
    provider_type = str(provider_cfg.get("type") or "").strip().lower()
    command = str(provider_cfg.get("command") or "").lower()
    role = role.strip().lower()
    if role == "pm":
        if provider_type == "ollama":
            return True
        if provider_type == "cli" and ("codex" in command or provider_id == "codex_cli"):
            return True
        return False
    if role == "director":
        return provider_type == "ollama"
    return True
