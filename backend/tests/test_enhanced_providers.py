"""
Tests for enhanced LLM providers with thinking extraction and CLI behavior
"""

import pytest
import sys
from app.llm.providers.codex_cli_provider import CodexCLIProvider
from app.llm.providers.gemini_cli_provider import GeminiCLIProvider
from app.llm.providers.maxmini_provider import MaxminiProvider
from app.llm.providers.gemini_api_provider import GeminiAPIProvider
from app.llm.providers.provider_registry import provider_manager


class TestCodexCLIProvider:
    """Test Codex CLI Provider"""
    
    def test_provider_info(self):
        """Test provider information"""
        info = CodexCLIProvider.get_provider_info()
        assert info.name == "Codex CLI Provider"
        assert info.type == "codex_cli"
        assert info.provider_category == "AGENT"
        assert info.autonomous_file_access is True
        assert info.model_listing_method == "TUI"
        assert "thinking_extraction" in info.supported_features
        assert info.cost_class == "FIXED"
    
    def test_default_config(self):
        """Test default configuration"""
        config = CodexCLIProvider.get_default_config()
        assert "command" in config
        assert "codex_exec" in config
        assert "manual_models" in config
        assert config["codex_exec"]["json"] is True
        assert config["codex_exec"]["sandbox"] == "read-only"
        assert config["cli_mode"] == "headless"
    
    def test_validate_config(self):
        """Test configuration validation"""
        # Valid config
        valid_config = {
            "command": "codex",
            "codex_exec": {
                "json": True,
                "sandbox": "read-only"
            },
            "timeout": 60
        }
        result = CodexCLIProvider.validate_config(valid_config)
        assert result.valid is True
        assert len(result.errors) == 0
        
        # Invalid config
        invalid_config = {
            "command": "definitely_not_a_real_command_12345",
            "codex_exec": "not_a_dict",  # Wrong type
            "timeout": -1  # Invalid timeout
        }
        result = CodexCLIProvider.validate_config(invalid_config)
        assert result.valid is False
        assert len(result.errors) > 0
    
    def test_tui_instructions(self):
        """Test TUI instructions"""
        provider = CodexCLIProvider()
        instructions = provider.get_tui_instructions()
        assert "model_discovery" in instructions
        assert "status_check" in instructions
        assert "permissions" in instructions
        assert "help" in instructions
        assert "exit" in instructions
        
        hint = provider.get_session_status_hint()
        assert "codex" in hint.lower()
        assert "/status" in hint
    
    def test_thinking_extraction(self):
        """Test thinking extraction"""
        response = {
            "output": "<thinking>This is my reasoning process.</thinking>Here's the answer.",
            "config": {"thinking_extraction": {"enabled": True}}
        }
        
        thinking = CodexCLIProvider.extract_thinking_support(response)
        assert thinking.supports_thinking is True
        assert "reasoning process" in thinking.thinking_text
        assert thinking.confidence > 0.1
    
class TestGeminiCLIProvider:
    """Test Gemini CLI Provider"""
    
    def test_provider_info(self):
        """Test provider information"""
        info = GeminiCLIProvider.get_provider_info()
        assert info.name == "Gemini CLI Provider"
        assert info.type == "gemini_cli"
        assert "thinking_extraction" in info.supported_features
        assert info.cost_class == "METERED"
    
    def test_default_config(self):
        """Test default configuration"""
        config = GeminiCLIProvider.get_default_config()
        assert config["command"] == "gemini"
        assert "GOOGLE_API_KEY" in config["env"]
        assert config["thinking_extraction"]["enabled"] is True
        assert config["cli_mode"] == "headless"
    
    def test_validate_config(self):
        """Test configuration validation"""
        # Valid config
        valid_config = {
            "command": "gemini",
            "env": {"GOOGLE_API_KEY": "test_key"},
            "args": ["chat", "--model", "{model}", "--prompt", "{prompt}"]
        }
        result = GeminiCLIProvider.validate_config(valid_config)
        assert result.valid is True
        
        # Invalid config - missing API key
        invalid_config = {
            "command": "gemini",
            "env": {},
            "args": []
        }
        result = GeminiCLIProvider.validate_config(invalid_config)
        assert result.valid is False
        assert "api key" in str(result.errors).lower()
    
    def test_thinking_extraction(self):
        """Test thinking extraction"""
        response = {
            "output": "Let me think about this problem step by step.First, I need to analyze the requirements.",
            "config": {"thinking_extraction": {"enabled": True}}
        }
        
        thinking = GeminiCLIProvider.extract_thinking_support(response)
        assert thinking.supports_thinking is True
        assert thinking.format == "text"
        assert thinking.confidence >= 0.4


class TestMaxminiProvider:
    """Test MiniMax Provider"""
    
    def test_provider_info(self):
        """Test provider information"""
        info = MaxminiProvider.get_provider_info()
        assert info.name == "MiniMax Provider"
        assert info.type == "maxmini"
        assert "chinese_support" in info.supported_features
        assert info.cost_class == "METERED"
    
    def test_default_config(self):
        """Test default configuration"""
        config = MaxminiProvider.get_default_config()
        assert config["base_url"] == "https://api.minimax.chat/v1"
        assert "abab6.5" in config["model_specific"]
    
    def test_thinking_extraction_chinese(self):
        """Test Chinese thinking extraction"""
        response = {
            "output": "<思考>让我分析一下这个问题的各个方面。</思考>基于以上分析，我的建议是...",
            "config": {"thinking_extraction": {"enabled": True}}
        }
        
        thinking = MaxminiProvider.extract_thinking_support(response)
        assert thinking.supports_thinking is True
        assert thinking.format in ("chinese_text", "chinese_xml")
        assert "分析" in thinking.thinking_text
    
class TestGeminiAPIProvider:
    """Test Gemini API Provider"""
    
    def test_provider_info(self):
        """Test provider information"""
        info = GeminiAPIProvider.get_provider_info()
        assert info.name == "Gemini API Provider"
        assert info.type == "gemini_api"
        assert "large_context" in info.supported_features
        assert info.cost_class == "METERED"
    
    def test_default_config(self):
        """Test default configuration"""
        config = GeminiAPIProvider.get_default_config()
        assert "generativelanguage.googleapis.com" in config["base_url"]
        assert "gemini-1.5-pro" in config["model_specific"]
        assert config["model_specific"]["gemini-1.5-pro"]["context_window"] == 2000000
    
    def test_thinking_extraction(self):
        """Test thinking extraction"""
        response = {
            "output": "Looking at this problem, I need to consider multiple factors.Step by step: first analyze, then implement.",
            "config": {"thinking_extraction": {"enabled": True}}
        }
        
        thinking = GeminiAPIProvider.extract_thinking_support(response)
        assert thinking.supports_thinking is True
        assert thinking.confidence >= 0.4


class TestProviderRegistry:
    """Test provider registry functionality"""
    
    def test_provider_manager_initialization(self):
        """Test provider manager initialization"""
        assert provider_manager is not None
        provider_types = provider_manager.list_provider_types()
        assert "codex_cli" in provider_types
        assert "gemini_cli" in provider_types
        assert "maxmini" in provider_types
        assert "gemini_api" in provider_types
    
    def test_provider_info_listing(self):
        """Test provider info listing"""
        providers_info = provider_manager.list_provider_info()
        assert len(providers_info) > 0
        
        # Check that all providers have required fields
        for info in providers_info:
            assert hasattr(info, 'name')
            assert hasattr(info, 'type')
            assert hasattr(info, 'supported_features')
    
    def test_provider_config_validation(self):
        """Test provider configuration validation"""
        # Test valid CLI config
        valid_cli_config = {
            "command": sys.executable,
            "args": ["hello"],
            "timeout": 60
        }
        assert provider_manager.validate_provider_config("codex_cli", valid_cli_config) is True
        
        # Test invalid CLI config
        invalid_cli_config = {"command": "definitely_not_a_real_command_12345"}
        assert provider_manager.validate_provider_config("codex_cli", invalid_cli_config) is False
    
    def test_feature_support_check(self):
        """Test feature support checking"""
        assert provider_manager.supports_feature("codex_cli", "thinking_extraction") is True
        assert provider_manager.supports_feature("maxmini", "chinese_support") is True
        assert provider_manager.supports_feature("gemini_api", "large_context") is True
        assert provider_manager.supports_feature("codex_cli", "nonexistent_feature") is False
    
    def test_legacy_config_migration(self):
        """Test legacy configuration migration"""
        legacy_config = {
            "providers": {
                "old_codex": {
                    "command": "codex",
                    "args": ["exec", "--model", "{model}"]
                },
                "unknown_provider": {
                    "type": "unknown",
                    "some_setting": "value"
                }
            }
        }
        
        migrated = provider_manager.migrate_legacy_config(legacy_config)
        
        # Check that codex was migrated to enhanced CLI
        assert "old_codex" in migrated["providers"]
        assert migrated["providers"]["old_codex"]["type"] == "codex_cli"
        
        # Unknown provider should remain unchanged
        assert "unknown_provider" in migrated["providers"]


if __name__ == "__main__":
    pytest.main([__file__])
