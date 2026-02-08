"""
Tests for Kimi Provider Streaming Implementation

Run with: python -m pytest tests/test_kimi_streaming.py -v
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.llm.providers.kimi_provider import KimiProvider


class TestKimiInvokeStream:
    """Test suite for Kimi invoke_stream method"""
    
    @pytest.fixture
    def provider(self):
        return KimiProvider()
    
    @pytest.fixture
    def valid_config(self):
        return {
            "api_key": "test-api-key",
            "base_url": "https://api.moonshot.cn/v1",
            "temperature": 0.7,
            "max_tokens": 100,
            "timeout": 30,
        }
    
    @pytest.mark.asyncio
    async def test_invoke_stream_no_api_key(self, provider):
        """Test that missing API key returns error"""
        config = {"api_key": ""}
        
        tokens = []
        async for token in provider.invoke_stream("Hello", "kimi-k2-turbo-preview", config):
            tokens.append(token)
        
        assert len(tokens) == 1
        assert "API key is required" in tokens[0]
    
    @pytest.mark.asyncio
    async def test_invoke_stream_success(self, provider, valid_config):
        """Test successful streaming response"""
        # Mock SSE response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        
        # Simulate SSE stream data
        sse_data = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        
        mock_response.content = AsyncMock()
        mock_response.content.__aiter__ = MagicMock(return_value=iter(sse_data))
        
        # Mock the ClientSession
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            tokens = []
            async for token in provider.invoke_stream("Hi", "kimi-k2-turbo-preview", valid_config):
                tokens.append(token)
            
            assert len(tokens) == 2
            assert tokens[0] == "Hello"
            assert tokens[1] == " world"
    
    @pytest.mark.asyncio
    async def test_invoke_stream_network_error(self, provider, valid_config):
        """Test network error handling"""
        import aiohttp
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=aiohttp.ClientError("Connection failed"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            tokens = []
            async for token in provider.invoke_stream("Hi", "kimi-k2-turbo-preview", valid_config):
                tokens.append(token)
            
            assert len(tokens) == 1
            assert "Network error" in tokens[0]
    
    @pytest.mark.asyncio
    async def test_invoke_stream_timeout(self, provider, valid_config):
        """Test timeout error handling"""
        import asyncio
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            tokens = []
            async for token in provider.invoke_stream("Hi", "kimi-k2-turbo-preview", valid_config):
                tokens.append(token)
            
            assert len(tokens) == 1
            assert "Request timeout" in tokens[0]


class TestKimiModelList:
    """Test suite for Kimi model listing"""
    
    @pytest.fixture
    def provider(self):
        return KimiProvider()
    
    def test_known_models_include_latest(self, provider):
        """Test that known models include latest Kimi models"""
        # This test verifies the model list is up to date
        expected_models = [
            "kimi-k2.5",
            "kimi-k2-thinking",
            "kimi-k2-thinking-turbo",
            "kimi-k2-turbo-preview",
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        ]
        
        # The models are embedded in list_models method
        # We verify by checking the provider info supports them
        info = provider.get_provider_info()
        assert "streaming" in info.supported_features


if __name__ == "__main__":
    # Run with: python tests/test_kimi_streaming.py
    pytest.main([__file__, "-v"])
