from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..types import HealthResult, InvokeResult, ModelListResult


@dataclass
class ProviderInfo:
    """Basic information about an LLM provider"""
    name: str
    type: str
    description: str
    version: str
    author: str
    documentation_url: str
    supported_features: List[str]
    cost_class: str  # LOCAL, FIXED, METERED
    provider_category: str  # "AGENT" or "LLM"
    autonomous_file_access: bool
    requires_file_interfaces: bool
    model_listing_method: str  # "API", "TUI", "NONE"


@dataclass
class ValidationResult:
    """Result of configuration validation"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    normalized_config: Optional[Dict[str, Any]] = None


@dataclass
class ThinkingInfo:
    """Information about thinking/reasoning capabilities"""
    supports_thinking: bool
    confidence: float
    format: Optional[str]
    thinking_text: Optional[str]
    extraction_method: str


@dataclass
class WorkingDirConfig:
    """Configuration for working directory handling"""
    target_directory: Optional[str]
    auto_create: bool
    cleanup_after: bool
    environment_vars: Dict[str, str]


class BaseProvider(ABC):
    """Base interface for all LLM providers"""
    
    @classmethod
    @abstractmethod
    def get_provider_info(cls) -> ProviderInfo:
        """Get basic information about this provider"""
        pass
    
    @classmethod
    @abstractmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get default configuration for this provider"""
        pass
    
    @classmethod
    @abstractmethod
    def validate_config(cls, config: Dict[str, Any]) -> ValidationResult:
        """Validate provider configuration"""
        pass
    
    @abstractmethod
    def health(self, config: Dict[str, Any]) -> HealthResult:
        """Check if the provider is accessible and working"""
        pass
    
    @abstractmethod
    def list_models(self, config: Dict[str, Any]) -> ModelListResult:
        """List available models for this provider"""
        pass
    
    @abstractmethod
    def invoke(self, prompt: str, model: str, config: Dict[str, Any]) -> InvokeResult:
        """Invoke the LLM with the given prompt and model"""
        pass
    
    @classmethod
    def extract_thinking_support(cls, response: Dict[str, Any]) -> ThinkingInfo:
        """Extract thinking/reasoning information from response"""
        # Default implementation - providers should override
        return ThinkingInfo(
            supports_thinking=False,
            confidence=0.0,
            format=None,
            thinking_text=None,
            extraction_method="default"
        )
    
    @classmethod
    def get_working_directory_config(cls, config: Dict[str, Any]) -> WorkingDirConfig:
        """Get working directory configuration"""
        # Default implementation - providers should override
        return WorkingDirConfig(
            target_directory=config.get("working_dir"),
            auto_create=False,
            cleanup_after=False,
            environment_vars=config.get("env", {})
        )
    
    @classmethod
    def supports_feature(cls, feature: str) -> bool:
        """Check if provider supports a specific feature"""
        provider_info = cls.get_provider_info()
        return feature in provider_info.supported_features
    
    @classmethod
    def is_agent_provider(cls) -> bool:
        """Check if this is an Agent-type provider"""
        provider_info = cls.get_provider_info()
        return provider_info.provider_category == "AGENT"
    
    @classmethod
    def is_llm_provider(cls) -> bool:
        """Check if this is a pure LLM provider"""
        provider_info = cls.get_provider_info()
        return provider_info.provider_category == "LLM"
    
    @classmethod
    def requires_file_interfaces(cls) -> bool:
        """Check if provider requires file management interfaces"""
        provider_info = cls.get_provider_info()
        return provider_info.requires_file_interfaces
    
    @classmethod
    def has_autonomous_file_access(cls) -> bool:
        """Check if provider has autonomous file access"""
        provider_info = cls.get_provider_info()
        return provider_info.autonomous_file_access
    
    @classmethod
    def get_model_listing_method(cls) -> str:
        """Get the method used for model listing"""
        provider_info = cls.get_provider_info()
        return provider_info.model_listing_method
    
class ProviderRegistry:
    """Registry for managing LLM providers"""
    
    def __init__(self):
        self._providers: Dict[str, type[BaseProvider]] = {}
    
    def register(self, provider_type: str, provider_class: type[BaseProvider]) -> None:
        """Register a provider class"""
        self._providers[provider_type] = provider_class
    
    def get_provider(self, provider_type: str) -> Optional[type[BaseProvider]]:
        """Get a provider class by type"""
        return self._providers.get(provider_type)
    
    def list_providers(self) -> List[ProviderInfo]:
        """List all registered providers"""
        return [provider_class.get_provider_info() for provider_class in self._providers.values()]
    
    def get_provider_info(self, provider_type: str) -> Optional[ProviderInfo]:
        """Get provider information by type"""
        provider_class = self.get_provider(provider_type)
        return provider_class.get_provider_info() if provider_class else None


# Global provider registry instance
provider_registry = ProviderRegistry()
