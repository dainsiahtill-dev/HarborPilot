from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from ..config import Settings
from ..utils import resolve_artifact_path, build_cache_root


DEFAULT_POLICIES = {
    "required_ready_roles": ["pm", "director", "qa", "docs"],
    "test_required_suites": ["connectivity", "response", "qualification"],
}


def build_default_config(settings: Optional[Settings] = None) -> Dict[str, Any]:
    pm_backend = (settings.pm_backend if settings else "codex") or "codex"
    pm_provider_id = "codex_cli" if pm_backend.strip().lower() == "codex" else "ollama"
    pm_model = (settings.pm_model if settings else None) or (settings.model if settings else None) or ""
    director_model = (settings.director_model if settings else None) or (settings.model if settings else None) or ""
    docs_provider = (settings.docs_init_provider if settings else "ollama") or "ollama"
    docs_provider_id = "openai_compat"
    if docs_provider.strip().lower() == "ollama":
        docs_provider_id = "ollama"
    elif docs_provider.strip().lower() == "codex":
        docs_provider_id = "codex_cli"
    docs_model = (settings.docs_init_model if settings else None) or pm_model
    openai_base_url = (settings.docs_init_base_url if settings else "") or ""

    providers: Dict[str, Any] = {
        "codex_cli": {
            "type": "cli",
            "command": "codex",
            "args": ["exec", "--color", "never", "--full-auto", "--output-last-message", "{output}", "-"],
            "list_args": ["models", "list"],
            "tui_args": [],
            "output_path": ".harborpilot/runtime/CODEX_LAST_MESSAGE.md",
            "timeout": 60,
        },
        "gemini_cli": {
            "type": "cli",
            "command": "gemini",
            "args": ["chat", "--model", "{model}", "--prompt", "{prompt}"],
            "list_args": ["models", "list"],
            "tui_args": [],
            "timeout": 60,
        },
        "ollama": {
            "type": "ollama",
            "base_url": "http://127.0.0.1:11434",
            "timeout": 60,
        },
        "openai_compat": {
            "type": "openai_compat",
            "base_url": openai_base_url or "https://api.example.com/v1",
            "api_key_ref": "keychain:openai_compat",
            "api_path": "/v1/chat/completions",
            "models_path": "/v1/models",
            "timeout": 60,
            "retries": 0,
        },
        "minimax": {
            "type": "openai_compat",
            "name": "MiniMax",
            "base_url": "https://api.minimax.io/v1",
            "api_key_ref": "keychain:llm:minimax",
            "api_path": "/v1/chat/completions",
            "models_path": "/v1/models",
            "timeout": 60,
            "retries": 0,
        },
        "minimax_anthropic": {
            "type": "anthropic_compat",
            "name": "MiniMax (Anthropic)",
            "base_url": "https://api.minimax.io/anthropic",
            "api_key_ref": "keychain:llm:minimax_anthropic",
            "api_path": "/v1/messages",
            "models_path": "/v1/models",
            "timeout": 60,
            "retries": 0,
        },
    }

    return {
        "schema_version": 1,
        "providers": providers,
        "roles": {
            "pm": {"provider_id": pm_provider_id, "model": pm_model, "profile": "pm-default"},
            "director": {"provider_id": "ollama", "model": director_model, "profile": "director-default"},
            "qa": {"provider_id": "ollama", "model": director_model, "profile": "qa-strict"},
            "docs": {"provider_id": docs_provider_id, "model": docs_model, "profile": "docs-writer"},
        },
        "policies": DEFAULT_POLICIES.copy(),
    }


def llm_config_path(workspace: str, cache_root: str) -> str:
    return resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/config/llm_config.json")


def load_llm_config(workspace: str, cache_root: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    path = llm_config_path(workspace, cache_root)
    if not os.path.isfile(path):
        data = build_default_config(settings)
        _write_json(path, data)
        return data
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    normalized = normalize_llm_config(data, settings=settings)
    if normalized != data:
        _write_json(path, normalized)
    return normalized


def save_llm_config(workspace: str, cache_root: str, payload: Dict[str, Any], settings: Optional[Settings] = None) -> Dict[str, Any]:
    normalized = normalize_llm_config(payload, settings=settings)
    path = llm_config_path(workspace, cache_root)
    _write_json(path, normalized)
    return normalized


def normalize_llm_config(payload: Dict[str, Any], settings: Optional[Settings] = None) -> Dict[str, Any]:
    base = build_default_config(settings)
    data = payload.copy() if isinstance(payload, dict) else {}
    providers = data.get("providers")
    roles = data.get("roles")
    policies = data.get("policies")
    schema_version = data.get("schema_version", 1)
    if not isinstance(providers, dict):
        providers = base.get("providers", {})
    if not isinstance(roles, dict):
        roles = base.get("roles", {})
    if not isinstance(policies, dict):
        policies = base.get("policies", {})
    merged = {
        "schema_version": int(schema_version or 1),
        "providers": {**base.get("providers", {}), **providers},
        "roles": {**base.get("roles", {}), **roles},
        "policies": {**base.get("policies", {}), **policies},
    }
    return merged


def redact_llm_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.loads(json.dumps(payload))
    providers = data.get("providers")
    if isinstance(providers, dict):
        for provider in providers.values():
            if isinstance(provider, dict) and "api_key" in provider:
                provider.pop("api_key", None)
    return data


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def resolve_workspace_cache_root(settings: Settings) -> str:
    return build_cache_root(settings.ramdisk_root or "", settings.workspace)
