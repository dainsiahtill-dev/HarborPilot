"""
Tests for enhanced LLM providers with thinking extraction and CLI behavior
"""

import pytest
import sys
from app.llm.providers.codex_cli_provider import CodexCLIProvider
from app.llm.providers.gemini_cli_provider import GeminiCLIProvider
from app.llm.providers.minimax_provider import MiniMaxProvider
from app.llm.providers.gemini_api_provider import GeminiAPIProvider
from app.llm.providers.openai_compat_provider import OpenAICompatProvider
from app.llm.providers.anthropic_compat_provider import AnthropicCompatProvider
from app.llm.providers.ollama_provider import OllamaProvider
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


class TestMiniMaxProvider:
    """Test MiniMax Provider"""
    
    def test_provider_info(self):
        """Test provider information"""
        info = MiniMaxProvider.get_provider_info()
        assert info.name == "MiniMax Provider"
        assert info.type == "minimax"
        assert "chinese_support" in info.supported_features
        assert info.cost_class == "METERED"
    
    def test_default_config(self):
        """Test default configuration"""
        config = MiniMaxProvider.get_default_config()
        assert config["base_url"] == "https://api.minimaxi.com/v1"
        assert config["temperature"] == 0.7
        assert config["max_tokens"] == 2048  # Updated to match actual default
    
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


class TestOpenAICompatProvider:
    """Test OpenAI-compatible provider"""

    def test_provider_info(self):
        info = OpenAICompatProvider.get_provider_info()
        assert info.type == "openai_compat"
        assert info.provider_category == "LLM"
        assert "chat_completions" in info.supported_features

    def test_default_config(self):
        config = OpenAICompatProvider.get_default_config()
        assert "base_url" in config
        assert "api_path" in config
        # models_path is deprecated and removed from default config
        assert "models_path" not in config

    def test_validate_config(self):
        valid_config = {
            "base_url": "https://api.example.com/v1",
            "api_path": "/v1/chat/completions",
            "timeout": 30,
            "retries": 1,
        }
        result = OpenAICompatProvider.validate_config(valid_config)
        assert result.valid is True

        invalid_config = {"base_url": "https://api.example.com/v1"}
        result = OpenAICompatProvider.validate_config(invalid_config)
        assert result.valid is False


class TestAnthropicCompatProvider:
    """Test Anthropic-compatible provider"""

    def test_provider_info(self):
        info = AnthropicCompatProvider.get_provider_info()
        assert info.type == "anthropic_compat"
        assert info.provider_category == "LLM"
        assert "messages_api" in info.supported_features

    def test_default_config(self):
        config = AnthropicCompatProvider.get_default_config()
        assert "api_path" in config
        assert "anthropic_version" in config

    def test_validate_config(self):
        valid_config = {
            "api_path": "/v1/messages",
            "timeout": 30,
            "retries": 1,
        }
        result = AnthropicCompatProvider.validate_config(valid_config)
        assert result.valid is True

        invalid_config = {"timeout": 30}
        result = AnthropicCompatProvider.validate_config(invalid_config)
        assert result.valid is False


class TestOllamaProvider:
    """Test Ollama provider"""

    def test_provider_info(self):
        info = OllamaProvider.get_provider_info()
        assert info.type == "ollama"
        assert info.cost_class == "LOCAL"

    def test_default_config(self):
        config = OllamaProvider.get_default_config()
        assert "base_url" in config
        assert config["use_chat"] is False

    def test_validate_config(self):
        valid_config = {"base_url": "http://127.0.0.1:11434", "timeout": 10}
        result = OllamaProvider.validate_config(valid_config)
        assert result.valid is True


class TestProviderRegistry:
    """Test provider registry functionality"""
    
    def test_provider_manager_initialization(self):
        """Test provider manager initialization"""
        assert provider_manager is not None
        provider_types = provider_manager.list_provider_types()
        assert "codex_cli" in provider_types
        assert "gemini_cli" in provider_types
        assert "minimax" in provider_types
        assert "gemini_api" in provider_types
        assert "ollama" in provider_types
        assert "openai_compat" in provider_types
        assert "anthropic_compat" in provider_types
    
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

        valid_openai_config = {
            "base_url": "https://api.example.com/v1",
            "api_path": "/v1/chat/completions",
        }
        assert provider_manager.validate_provider_config("openai_compat", valid_openai_config) is True

        invalid_openai_config = {"base_url": "https://api.example.com/v1"}
        assert provider_manager.validate_provider_config("openai_compat", invalid_openai_config) is False
    
    def test_feature_support_check(self):
        """Test feature support checking"""
        assert provider_manager.supports_feature("codex_cli", "thinking_extraction") is True
        assert provider_manager.supports_feature("minimax", "chinese_support") is True
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
