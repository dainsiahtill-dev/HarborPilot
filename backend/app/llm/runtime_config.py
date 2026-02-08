"""
Runtime Configuration Manager

Manages role-to-model configuration for runtime scripts.
Reads configuration from the unified LLM config file.
"""

import json
import os
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class RoleModelConfig:
    """Configuration for a specific role"""
    role_id: str
    provider_id: str
    model: str
    profile: Optional[str] = None


class RuntimeConfigManager:
    """
    Runtime configuration manager - reads role model configuration from VisualGraphConfig.
    
    This class provides a singleton interface to access the visual LLM configuration
    that was created through the visual editor. It supports both the new roleAssignments
    format and the legacy roles format for backward compatibility.
    """
    
    _instance = None
    _config_cache = None
    _config_mtime = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _get_config_path(self) -> str:
        """Get the configuration file path"""
        # Priority 1: Environment variable
        env_path = os.environ.get('HARBORPILOT_LLM_CONFIG')
        if env_path:
            return env_path
        
        # Priority 2: Project runtime directory
        project_root = os.environ.get('HARBORPILOT_ROOT', '')
        if project_root:
            runtime_path = os.path.join(project_root, '.harborpilot', 'runtime', 'llm_config.json')
            if os.path.exists(runtime_path):
                return runtime_path
        
        # Priority 3: User home directory
        home = os.path.expanduser('~')
        return os.path.join(home, '.harborpilot', 'llm_config.json')
    
    def _load_config(self) -> Dict:
        """Load configuration file with caching"""
        config_path = self._get_config_path()
        
        if not os.path.exists(config_path):
            print(f"[RuntimeConfig] Config file not found: {config_path}")
            return {}
        
        try:
            mtime = os.path.getmtime(config_path)
            
            # Return cached config if not modified
            if self._config_cache is not None and mtime <= self._config_mtime:
                return self._config_cache
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self._config_cache = config
            self._config_mtime = mtime
            
            print(f"[RuntimeConfig] Loaded config from: {config_path}")
            return config
            
        except Exception as e:
            print(f"[RuntimeConfig] Failed to load config: {e}")
            return {}
    
    def get_role_config(self, role_id: str) -> Optional[RoleModelConfig]:
        """
        Get role model configuration
        
        Priority:
        1. New roleAssignments format (from visual editor)
        2. Legacy roles format (backward compatibility)
        3. None (will use defaults)
        """
        config = self._load_config()
        
        # Priority 1: New roleAssignments format
        assignments = config.get('roleAssignments', [])
        for assignment in assignments:
            if assignment.get('roleId') == role_id:
                return RoleModelConfig(
                    role_id=role_id,
                    provider_id=assignment['providerId'],
                    model=assignment['model'],
                    profile=assignment.get('profile')
                )
        
        # Priority 2: Legacy roles format
        roles = config.get('roles', {})
        role_cfg = roles.get(role_id, {})
        if role_cfg.get('provider_id') and role_cfg.get('model'):
            return RoleModelConfig(
                role_id=role_id,
                provider_id=role_cfg['provider_id'],
                model=role_cfg['model'],
                profile=role_cfg.get('profile')
            )
        
        return None
    
    def get_role_model(self, role_id: str) -> Tuple[str, str]:
        """
        Get role's provider and model with fallback to defaults
        
        Returns:
            Tuple of (provider_id, model)
        """
        config = self.get_role_config(role_id)
        if config:
            print(f"[RuntimeConfig] {role_id}: using {config.provider_id}/{config.model}")
            return config.provider_id, config.model
        
        # Fallback defaults
        defaults = {
            'pm': ('openai', 'gpt-4'),
            'director': ('openai', 'gpt-4'),
            'qa': ('openai', 'gpt-3.5-turbo'),
            'docs': ('openai', 'gpt-3.5-turbo')
        }
        
        default_provider, default_model = defaults.get(role_id, ('openai', 'gpt-3.5-turbo'))
        print(f"[RuntimeConfig] {role_id}: using default {default_provider}/{default_model}")
        return default_provider, default_model
    
    def get_all_role_configs(self) -> Dict[str, RoleModelConfig]:
        """Get configurations for all roles"""
        configs = {}
        for role_id in ['pm', 'director', 'qa', 'docs']:
            config = self.get_role_config(role_id)
            if config:
                configs[role_id] = config
        return configs
    
    def clear_cache(self):
        """Clear configuration cache (useful for testing)"""
        self._config_cache = None
        self._config_mtime = 0


# Global configuration manager instance
runtime_config = RuntimeConfigManager()


# Convenience functions for direct import
def get_role_model(role_id: str) -> Tuple[str, str]:
    """Get role's provider and model"""
    return runtime_config.get_role_model(role_id)


def load_role_config(role_id: str) -> Optional[RoleModelConfig]:
    """Load role configuration"""
    return runtime_config.get_role_config(role_id)
