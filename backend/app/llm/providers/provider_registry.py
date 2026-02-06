from __future__ import annotations

from typing import Dict, List, Optional, Type, Any
import importlib
import inspect
from pathlib import Path

from .base_provider import BaseProvider, ProviderInfo
from .codex_cli_provider import CodexCLIProvider
from .codex_sdk_provider import CodexSDKProvider
from .ollama_provider import OllamaProvider
from .openai_compat_provider import OpenAICompatProvider
from .anthropic_compat_provider import AnthropicCompatProvider
from .gemini_cli_provider import GeminiCLIProvider
from .minimax_provider import MiniMaxProvider
from .gemini_api_provider import GeminiAPIProvider
from .kimi_provider import KimiProvider


class ProviderManager:
    """Manages provider registration, discovery, and instantiation"""
    
    def __init__(self):
        self._provider_classes: Dict[str, Type[BaseProvider]] = {}
        self._provider_instances: Dict[str, BaseProvider] = {}
        self._register_default_providers()
    
    def _register_default_providers(self) -> None:
        """Register all default providers"""
        # Register enhanced providers
        self.register_provider("codex_sdk", CodexSDKProvider)
        self.register_provider("codex_cli", CodexCLIProvider)  # Use proper Codex CLI provider
        self.register_provider("gemini_cli", GeminiCLIProvider)
        self.register_provider("minimax", MiniMaxProvider)
        self.register_provider("kimi", KimiProvider)
        self.register_provider("gemini_api", GeminiAPIProvider)
        self.register_provider("ollama", OllamaProvider)
        self.register_provider("openai_compat", OpenAICompatProvider)
        self.register_provider("anthropic_compat", AnthropicCompatProvider)
        
        # Legacy function-based providers remain available for backward compatibility.
    
    def register_provider(self, provider_type: str, provider_class: Type[BaseProvider]) -> None:
        """Register a provider class"""
        if not issubclass(provider_class, BaseProvider):
            raise ValueError(f"Provider class {provider_class} must inherit from BaseProvider")
        
        self._provider_classes[provider_type] = provider_class
        
        # Also register with the global registry for backward compatibility
        from .base_provider import provider_registry
        provider_registry.register(provider_type, provider_class)
    
    def get_provider_class(self, provider_type: str) -> Optional[Type[BaseProvider]]:
        """Get a provider class by type"""
        resolved = "codex_cli" if provider_type == "cli" else provider_type
        return self._provider_classes.get(resolved)
    
    def get_provider_instance(self, provider_type: str) -> Optional[BaseProvider]:
        """Get or create a provider instance"""
        if provider_type in self._provider_instances:
            return self._provider_instances[provider_type]
        
        provider_class = self.get_provider_class(provider_type)
        if provider_class:
            instance = provider_class()
            self._provider_instances[provider_type] = instance
            return instance
        
        return None
    
    def list_provider_types(self) -> List[str]:
        """List all registered provider types"""
        return list(self._provider_classes.keys())
    
    def list_provider_info(self) -> List[ProviderInfo]:
        """List information for all registered providers"""
        info_list = []
        for provider_class in self._provider_classes.values():
            try:
                info = provider_class.get_provider_info()
                info_list.append(info)
            except Exception as e:
                print(f"Error getting provider info for {provider_class}: {e}")
        return info_list
    
    def get_provider_info(self, provider_type: str) -> Optional[ProviderInfo]:
        """Get provider information by type"""
        provider_class = self.get_provider_class(provider_type)
        if provider_class:
            try:
                return provider_class.get_provider_info()
            except Exception as e:
                print(f"Error getting provider info for {provider_type}: {e}")
        return None
    
    def validate_provider_config(self, provider_type: str, config: Dict[str, Any]) -> bool:
        """Validate provider configuration"""
        provider_class = self.get_provider_class(provider_type)
        if provider_class:
            try:
                result = provider_class.validate_config(config)
                return result.valid
            except Exception as e:
                print(f"Error validating config for {provider_type}: {e}")
                return False
        return False
    
    def get_provider_default_config(self, provider_type: str) -> Optional[Dict[str, Any]]:
        """Get default configuration for a provider"""
        provider_class = self.get_provider_class(provider_type)
        if provider_class:
            try:
                return provider_class.get_default_config()
            except Exception as e:
                print(f"Error getting default config for {provider_type}: {e}")
        return None
    
    def supports_feature(self, provider_type: str, feature: str) -> bool:
        """Check if a provider supports a specific feature"""
        provider_class = self.get_provider_class(provider_type)
        if provider_class:
            try:
                return provider_class.supports_feature(feature)
            except Exception as e:
                print(f"Error checking feature support for {provider_type}: {e}")
        return False
    
    def discover_providers(self, providers_dir: Optional[str] = None) -> None:
        """Discover and register providers from a directory"""
        if providers_dir is None:
            providers_dir = Path(__file__).parent
        
        providers_path = Path(providers_dir)
        if not providers_path.exists():
            return
        
        # Look for provider files
        for file_path in providers_path.glob("*_provider.py"):
            if file_path.name.startswith("__"):
                continue
            
            module_name = file_path.stem
            try:
                # Import the module
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Look for provider classes
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, BaseProvider) and 
                        obj != BaseProvider and 
                        not name.startswith("_")):
                        
                        # Register the provider
                        provider_type = obj.get_provider_info().type
                        self.register_provider(provider_type, obj)
                        print(f"Discovered and registered provider: {provider_type}")
                        
            except Exception as e:
                print(f"Error discovering provider from {file_path}: {e}")
    
    def get_provider_for_config(self, config: Dict[str, Any]) -> Optional[str]:
        """Determine provider type from configuration"""
        provider_type = config.get("type")
        if provider_type:
            if provider_type == "cli":
                command = str(config.get("command", "")).lower()
                if "gemini" in command:
                    return "gemini_cli"
                return "codex_cli"
            return provider_type
        
        # Try to infer from other config fields
        command = config.get("command", "").lower()
        base_url = config.get("base_url", "").lower()
        
        if "codex" in command:
            return "codex_cli"
        elif "gemini" in command:
            return "gemini_cli"
        elif "minimax" in base_url:
            return "minimax"
        elif "generativelanguage.googleapis.com" in base_url:
            return "gemini_api"
        elif "api.openai.com" in base_url:
            return "openai_compat"
        elif "127.0.0.1:11434" in base_url or "localhost:11434" in base_url:
            return "ollama"
        elif "anthropic" in base_url:
            return "anthropic_compat"
        
        return None
    
    def migrate_legacy_config(self, legacy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate legacy configuration to new provider format"""
        migrated = legacy_config.copy()
        
        providers = migrated.get("providers", {})
        migrated_providers = {}
        
        for provider_id, provider_config in providers.items():
            if not isinstance(provider_config, dict):
                continue
            
            # Determine provider type
            provider_type = self.get_provider_for_config(provider_config)
            if not provider_type:
                # Keep as-is if we can't determine the type
                migrated_providers[provider_id] = provider_config
                continue
            
            # Get default config for the provider
            default_config = self.get_provider_default_config(provider_type) or {}
            
            # Merge with existing config
            merged_config = {**default_config, **provider_config}
            
            # Ensure type is set
            merged_config["type"] = provider_type
            
            migrated_providers[provider_id] = merged_config
        
        migrated["providers"] = migrated_providers
        return migrated
    
    def health_check_all(self, configs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Perform health checks on all configured providers"""
        results = {}
        
        for provider_id, config in configs.items():
            provider_type = self.get_provider_for_config(config)
            if not provider_type:
                results[provider_id] = {
                    "ok": False,
                    "error": "Unknown provider type"
                }
                continue
            
            provider_instance = self.get_provider_instance(provider_type)
            if not provider_instance:
                results[provider_id] = {
                    "ok": False,
                    "error": f"Could not instantiate provider {provider_type}"
                }
                continue
            
            try:
                health_result = provider_instance.health(config)
                results[provider_id] = health_result.to_dict()
            except Exception as e:
                results[provider_id] = {
                    "ok": False,
                    "error": str(e)
                }
        
        return results


# Global provider manager instance
provider_manager = ProviderManager()
