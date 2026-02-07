from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from ..config import Settings
from ..utils import resolve_artifact_path, build_cache_root


DEFAULT_ROLE_REQUIREMENTS = {
    "pm": {
        "requires_thinking": True,
        "min_confidence": 0.7,
        "error_message": "PM 岗位需要具备深度思考能力的模型",
    },
    "director": {
        "requires_thinking": True,
        "min_confidence": 0.7,
        "error_message": "Director 岗位需要具备推理能力的模型",
    },
    "qa": {
        "requires_thinking": False,
        "min_confidence": 0.5,
        "error_message": "QA 岗位建议使用具备思考能力的模型",
    },
    "docs": {
        "requires_thinking": False,
        "min_confidence": 0.5,
        "error_message": "Docs 岗位建议使用具备思考能力的模型",
    },
}

DEFAULT_POLICIES = {
    "required_ready_roles": ["pm", "director", "qa", "docs"],
    "test_required_suites": ["connectivity", "response", "qualification"],
    "role_requirements": DEFAULT_ROLE_REQUIREMENTS,
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
            "type": "codex_cli",
            "name": "Codex CLI",
            "command": "codex",
            "args": [],
            "cli_mode": "headless",
            "codex_exec": {
                "cd": "",
                "color": "never",
                "approvals": "",
                "sandbox": "danger-full-access",
                "skip_git_repo_check": True,
                "json": True,
                "experimental_json": False,
                "full_auto": False,
                "yolo": False,
                "oss": False,
                "output_schema": "",
                "output_last_message": "",
                "profile": "",
                "add_dirs": [],
                "config": [],
                "images": [],
                "prompt_from_stdin": False,
            },
            "list_args": [],
            "tui_args": [],
            "timeout": 60,
        },
        "gemini_cli": {
            "type": "gemini_cli",
            "name": "Gemini CLI",
            "command": "gemini",
            "args": ["chat", "--model", "{model}", "--prompt", "{prompt}"],
            "cli_mode": "headless",
            "list_args": ["models", "list"],
            "health_args": ["version"],
            "env": {
                "GOOGLE_API_KEY": "",
                "GOOGLE_GENAI_USE_VERTEXAI": "false",
                "GOOGLE_GENAI_API_KEY": ""
            },
            "timeout": 60,
            "thinking_extraction": {
                "enabled": True,
                "patterns": [
                    r"<thinking>(.*?)</thinking>",
                    r"```thinking(.*?)```",
                    r"Let me think(.*?)(?:\n\n|\n[A-Z])",
                    r"I need to consider(.*?)(?:\n\n|\n[A-Z])"
                ],
                "confidence_threshold": 0.6
            }
        },
        "minimax": {
            "type": "minimax",
            "name": "MiniMax",
            "base_url": "https://api.minimaxi.com/v1",
            "api_key_ref": "keychain:minimax",
            "api_path": "/text/chatcompletion_v2",
            "models_path": "/v1/models",
            "timeout": 60,
            "retries": 3,
            "temperature": 0.7,
            "max_tokens": 196608,
            "thinking_extraction": {
                "enabled": True,
                "patterns": [
                    r"<思考>(.*?)</思考>",
                    r"<thinking>(.*?)</thinking>",
                    r"```思考(.*?)```",
                    r"让我想想(.*?)(?:\n\n|\n[A-Z\u4e00-\u9fff])",
                    r"我需要考虑(.*?)(?:\n\n|\n[A-Z\u4e00-\u9fff])"
                ],
                "confidence_threshold": 0.6
            },
            "model_specific": {
                "abab6.5": {
                    "max_tokens": 245760,
                    "supports_thinking": True
                },
                "abab6.5s": {
                    "max_tokens": 245760,
                    "supports_thinking": True
                },
                "abab6": {
                    "max_tokens": 8192,
                    "supports_thinking": False
                }
            }
        },
        "gemini_api": {
            "type": "gemini_api",
            "name": "Gemini API",
            "base_url": "https://generativelanguage.googleapis.com",
            "api_key_ref": "keychain:gemini",
            "api_path": "/v1beta/models/{model}:generateContent",
            "models_path": "/v1beta/models",
            "timeout": 60,
            "retries": 3,
            "temperature": 0.7,
            "max_tokens": 8192,
            "thinking_extraction": {
                "enabled": True,
                "patterns": [
                    r"<thinking>(.*?)</thinking>",
                    r"```thinking(.*?)```",
                    r"Let me think(.*?)(?:\n\n|\n[A-Z])",
                    r"I need to consider(.*?)(?:\n\n|\n[A-Z])",
                    r"Looking at this(.*?)(?:\n\n|\n[A-Z])",
                    r"Step by step(.*?)(?:\n\n|\n[A-Z])"
                ],
                "confidence_threshold": 0.6
            },
            "model_specific": {
                "gemini-1.5-pro": {
                    "max_tokens": 2097152,
                    "supports_thinking": True,
                    "context_window": 2000000
                },
                "gemini-1.5-flash": {
                    "max_tokens": 1048576,
                    "supports_thinking": True,
                    "context_window": 1000000
                },
                "gemini-1.0-pro": {
                    "max_tokens": 32768,
                    "supports_thinking": False,
                    "context_window": 32768
                }
            }
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
        "anthropic_compat": {
            "type": "anthropic_compat",
            "name": "Anthropic Compatible",
            "base_url": "https://api.anthropic.com/v1",
            "api_key_ref": "keychain:anthropic",
            "api_path": "/v1/messages",
            "models_path": "/v1/models",
            "timeout": 60,
            "retries": 3,
        },
        "kimi": {
            "type": "kimi",
            "name": "Kimi",
            "base_url": "https://api.moonshot.cn/v1",
            "api_key_ref": "keychain:kimi",
            "api_path": "/chat/completions",
            "models_path": "/v1/models",
            "timeout": 60,
            "retries": 3,
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
    try:
        return resolve_artifact_path(workspace, cache_root, ".harborpilot/runtime/config/llm_config.json")
    except Exception:
        # Fallback to local workspace path if cache/ramdisk is invalid
        return os.path.join(workspace, ".harborpilot", "runtime", "config", "llm_config.json")


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
    is_valid, errors, warnings = validate_llm_config(normalized)
    if not is_valid:
        error_msg = "; ".join(errors)
        raise ValueError(f"Invalid LLM configuration: {error_msg}")
    if warnings:
        import logging
        logger = logging.getLogger(__name__)
        for warning in warnings:
            logger.warning(f"LLM config validation warning: {warning}")
    path = llm_config_path(workspace, cache_root)
    _write_json(path, normalized)
    return normalized


def normalize_llm_config(payload: Dict[str, Any], settings: Optional[Settings] = None) -> Dict[str, Any]:
    base = build_default_config(settings)
    
    data = payload.copy() if isinstance(payload, dict) else {}
    schema_version = data.get("schema_version", 1)
    
    # Provider logic: if user supplies providers, use them (allows deletion).
    # Otherwise fall back to defaults.
    user_providers = data.get("providers")
    if isinstance(user_providers, dict):
        providers = user_providers
    else:
        providers = base.get("providers", {})
        
    roles = data.get("roles")
    if not isinstance(roles, dict):
        roles = base.get("roles", {})
        
    policies = data.get("policies")
    if not isinstance(policies, dict):
        policies = base.get("policies", {})
    else:
        base_policies = base.get("policies", {})
        role_requirements = policies.get("role_requirements")
        if isinstance(role_requirements, dict):
            base_role_requirements = base_policies.get("role_requirements", {})
            if isinstance(base_role_requirements, dict):
                policies = {
                    **policies,
                    "role_requirements": {**base_role_requirements, **role_requirements},
                }
    merged = {
        "schema_version": int(schema_version or 1),
        "providers": providers,
        "roles": {**base.get("roles", {}), **roles},
        "policies": {**base.get("policies", {}), **policies},
    }
    return merged


def validate_llm_config(config: Dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    """
    Validate LLM configuration.
    
    Args:
        config: LLM configuration dictionary
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []
    
    if not isinstance(config, dict):
        errors.append("Config must be a dictionary")
        return False, errors, warnings
    
    providers = config.get("providers")
    if isinstance(providers, dict):
        for provider_id, provider_cfg in providers.items():
            if not isinstance(provider_cfg, dict):
                warnings.append(f"Provider '{provider_id}' config is not a dictionary")
                continue
            provider_type = provider_cfg.get("type")
            if not provider_type:
                errors.append(f"Provider '{provider_id}' missing 'type' field")
    
    roles = config.get("roles")
    if isinstance(roles, dict):
        required_roles = config.get("policies", {}).get("required_ready_roles", [])
        for role_id in required_roles:
            if role_id not in roles:
                errors.append(f"Required role '{role_id}' not defined in roles")
        
        for role_id, role_cfg in roles.items():
            if not isinstance(role_cfg, dict):
                warnings.append(f"Role '{role_id}' config is not a dictionary")
                continue
            provider_id = role_cfg.get("provider_id")
            if provider_id:
                if not isinstance(providers, dict):
                    errors.append(f"Role '{role_id}' references provider '{provider_id}' but providers not defined")
                elif provider_id not in providers:
                    errors.append(f"Role '{role_id}' references non-existent provider '{provider_id}'")
    
    schema_version = config.get("schema_version")
    if schema_version is not None and not isinstance(schema_version, int):
        warnings.append(f"Invalid schema_version '{schema_version}', expected integer")
    
    return len(errors) == 0, errors, warnings


def redact_llm_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Keep api_key values so the UI can display plaintext keys without clearing.
    # Deep copy to avoid mutating the original payload.
    return json.loads(json.dumps(payload))


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def resolve_workspace_cache_root(settings: Settings) -> str:
    return build_cache_root(settings.ramdisk_root or "", settings.workspace)
