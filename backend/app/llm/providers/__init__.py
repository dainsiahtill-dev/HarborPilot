from .ollama_provider import health as ollama_health, list_models as ollama_list_models, invoke as ollama_invoke
from .openai_compat_provider import (
    health as openai_health,
    list_models as openai_list_models,
    invoke as openai_invoke,
)
from .anthropic_compat_provider import (
    health as anthropic_health,
    list_models as anthropic_list_models,
    invoke as anthropic_invoke,
)

# New enhanced providers
from .codex_cli_provider import CodexCLIProvider
from .gemini_cli_provider import GeminiCLIProvider
from .maxmini_provider import MaxminiProvider
from .gemini_api_provider import GeminiAPIProvider

# Base classes and utilities
from .base_provider import BaseProvider, ProviderInfo, ValidationResult, ThinkingInfo, WorkingDirConfig
from .provider_registry import ProviderManager, provider_manager

__all__ = [
    # Legacy provider functions (for backward compatibility)
    "ollama_health",
    "ollama_list_models",
    "ollama_invoke",
    "openai_health",
    "openai_list_models",
    "openai_invoke",
    "anthropic_health",
    "anthropic_list_models",
    "anthropic_invoke",
    
    # Enhanced provider classes
    "CodexCLIProvider",
    "GeminiCLIProvider", 
    "MaxminiProvider",
    "GeminiAPIProvider",
    
    # Base classes and utilities
    "BaseProvider",
    "ProviderInfo",
    "ValidationResult",
    "ThinkingInfo",
    "WorkingDirConfig",
    "ProviderManager",
    "provider_manager",
]
