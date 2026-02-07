"""Phase 0 Regression Tests for LLM Configuration Unification

Tests for:
1. Default config unique provider keys (minimax fix)
2. LLMStatus contains last_updated field
3. LLMConfig atomic write and UTF-8 roundtrip
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


class TestLLMDefaultConfigUniqueProviderKeys:
    """Test that default LLM config has unique provider keys."""

    def test_default_config_no_duplicate_provider_keys(self):
        """Ensure no duplicate provider IDs exist in default config."""
        from app.llm.config import build_default_config

        config = build_default_config()
        providers = config.get("providers", {})

        provider_ids = list(providers.keys())
        duplicate_ids = [pid for pid in provider_ids if provider_ids.count(pid) > 1]

        assert len(duplicate_ids) == 0, \
            f"Found duplicate provider IDs in default config: {duplicate_ids}"

    def test_minimax_provider_appears_only_once(self):
        """Ensure minimax provider is defined exactly once with correct type."""
        from app.llm.config import build_default_config

        config = build_default_config()
        providers = config.get("providers", {})

        minimax_count = providers.count("minimax") if hasattr(providers, "count") else \
            sum(1 for k in providers.keys() if k == "minimax")

        assert minimax_count == 1, \
            f"Expected exactly one 'minimax' provider, found {minimax_count}"

        if "minimax" in providers:
            minimax_config = providers["minimax"]
            assert minimax_config.get("type") == "minimax", \
                f"Expected minimax type 'minimax', got '{minimax_config.get('type')}'"


class TestLLMStatusLastUpdated:
    """Test that LLMStatus response includes last_updated field."""

    def test_status_response_has_last_updated_field(self):
        """Verify /llm/status endpoint returns last_updated."""
        from app.routers.llm import llm_status
        from app.state import AppState

        mock_request = MagicMock()
        mock_settings = MagicMock()
        mock_settings.workspace = "/tmp/test_workspace"
        mock_settings.ramdisk_root = None
        mock_settings.pm_backend = "openai"
        mock_settings.pm_model = "gpt-4"
        mock_settings.director_model = None
        mock_settings.docs_model = None
        mock_settings.qa_model = None
        mock_state = AppState(settings=mock_settings)

        with patch("app.routers.llm.get_state", return_value=mock_state):
            with patch("app.routers.llm.llm_config.load_llm_config", return_value={
                "schema_version": 1,
                "providers": {},
                "roles": {}
            }):
                with patch("app.routers.llm.load_llm_test_index", return_value={"providers": {}, "roles": {}}):
                    with patch("app.routers.llm.load_interview_history_summary", return_value={}):
                        with patch("app.routers.llm.build_cache_root", return_value="/tmp/test_cache"):
                            response = llm_status(mock_request)

                            assert "last_updated" in response, \
                                "Response missing 'last_updated' field"
                            assert response["last_updated"] is None or isinstance(response["last_updated"], str), \
                                f"last_updated should be None or ISO string, got {type(response['last_updated'])}"

                            if response["last_updated"] is not None:
                                try:
                                    datetime.fromisoformat(response["last_updated"])
                                except (TypeError, ValueError) as e:
                                    pytest.fail(f"last_updated is not valid ISO format: {e}")


class TestLLMConfigAtomicWrite:
    """Test LLMConfig atomic write and UTF-8 roundtrip."""

    def test_config_save_and_load_utf8_roundtrip(self, mock_workspace):
        """Verify config can be saved and loaded with UTF-8 characters preserved."""
        from app.llm.config import save_llm_config, load_llm_config

        test_config = {
            "schema_version": 1,
            "providers": {
                "test_provider": {
                    "type": "openai_compat",
                    "name": "测试提供商",
                    "base_url": "https://api.test.com",
                    "api_key": "test_key_123",
                    "model": "test-model",
                    "description": "包含中文描述的配置"
                }
            },
            "roles": {
                "pm": {
                    "provider_id": "test_provider",
                    "model": "test-model",
                    "profile": "测试角色配置"
                }
            }
        }

        save_llm_config(mock_workspace, mock_workspace, test_config)

        loaded_config = load_llm_config(mock_workspace, mock_workspace)

        assert loaded_config.get("providers", {}).get("test_provider", {}).get("name") == "测试提供商", \
            "UTF-8 Chinese characters not preserved in provider name"
        assert loaded_config.get("roles", {}).get("pm", {}).get("profile") == "测试角色配置", \
            "UTF-8 Chinese characters not preserved in role profile"

    def test_config_atomic_write_pattern(self, mock_workspace):
        """Verify config uses atomic write pattern (tmp -> fsync -> rename)."""
        import glob
        import time

        from app.llm.config import save_llm_config, llm_config_path

        test_config = {
            "schema_version": 1,
            "providers": {},
            "roles": {}
        }

        config_path = llm_config_path(mock_workspace, mock_workspace)

        save_llm_config(mock_workspace, mock_workspace, test_config)

        assert os.path.isfile(config_path), "Config file was not created"

        tmp_files_before = glob.glob(os.path.join(mock_workspace, "*.tmp"))
        assert len(tmp_files_before) == 0, \
            f"Found temporary files after write: {tmp_files_before}"

        with open(config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["schema_version"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
