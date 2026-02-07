"""Tests for MiniMax provider streaming functionality"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.llm.providers.minimax_provider import MiniMaxProvider


class TestMiniMaxStreaming:
    """Test suite for MiniMax streaming implementation"""
    
    def test_invoke_stream_is_override(self):
        """Test that MiniMax actually overrides invoke_stream (not using BaseProvider default)"""
        is_override = 'invoke_stream' in MiniMaxProvider.__dict__
        assert is_override, "MiniMax must override invoke_stream for true streaming"
    
    def test_provider_info_declares_streaming(self):
        """Test that provider info declares streaming support"""
        info = MiniMaxProvider.get_provider_info()
        assert "streaming" in info.supported_features
    
    @pytest.mark.asyncio
    async def test_invoke_stream_yields_tokens(self):
        """Test that invoke_stream yields tokens from SSE response"""
        provider = MiniMaxProvider()
        
        # Mock SSE response data
        mock_chunks = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n',
            b'data: {"choices": [{"delta": {"content": " world"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        
        # Create mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'Content-Type': 'text/event-stream'}
        mock_response.content = MagicMock()
        mock_response.content.__aiter__ = MagicMock(return_value=iter(mock_chunks))
        
        # Create mock session
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        config = {
            "api_key": "test-key",
            "base_url": "https://api.test.com",
            "timeout": 30,
        }
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            tokens = []
            async for token in provider.invoke_stream("Hi", "MiniMax-M2.1", config):
                tokens.append(token)
            
            assert len(tokens) == 2
            assert tokens[0] == "Hello"
            assert tokens[1] == " world"
    
    @pytest.mark.asyncio
    async def test_invoke_stream_handles_json_response(self):
        """Test that invoke_stream handles non-streaming JSON response"""
        provider = MiniMaxProvider()
        
        # Mock JSON response
        mock_response_data = {
            "choices": [{"message": {"content": "Hello world this is a test"}}]
        }
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json = AsyncMock(return_value=mock_response_data)
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        config = {
            "api_key": "test-key",
            "base_url": "https://api.test.com",
        }
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            tokens = []
            async for token in provider.invoke_stream("Hi", "MiniMax-M2.1", config):
                tokens.append(token)
            
            # Should yield word by word for JSON response
            assert len(tokens) > 0
            full_response = ''.join(tokens)
            assert "Hello world" in full_response
    
    @pytest.mark.asyncio
    async def test_invoke_stream_handles_error(self):
        """Test that invoke_stream handles HTTP errors"""
        provider = MiniMaxProvider()
        
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        
        mock_session = AsyncMock()
        mock_session.post = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        config = {
            "api_key": "bad-key",
            "base_url": "https://api.test.com",
        }
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            tokens = []
            async for token in provider.invoke_stream("Hi", "MiniMax-M2.1", config):
                tokens.append(token)
            
            assert len(tokens) == 1
            assert tokens[0].startswith("Error:")
    
    @pytest.mark.asyncio
    async def test_invoke_stream_requires_api_key(self):
        """Test that invoke_stream requires API key"""
        provider = MiniMaxProvider()
        config = {}  # No API key
        
        tokens = []
        async for token in provider.invoke_stream("Hi", "MiniMax-M2.1", config):
            tokens.append(token)
        
        assert len(tokens) == 1
        assert "API key is required" in tokens[0]


class TestStreamingDetection:
    """Test suite for streaming detection logic"""
    
    def test_detection_logic(self):
        """Test the new streaming detection logic"""
        provider = MiniMaxProvider()
        
        # The new detection logic
        has_attr = hasattr(provider, 'invoke_stream')
        is_override = 'invoke_stream' in provider.__class__.__dict__
        supports_true = is_override  # New logic
        
        assert has_attr is True  # Always true due to BaseProvider
        assert is_override is True  # MiniMax now overrides
        assert supports_true is True  # Should use true streaming


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
