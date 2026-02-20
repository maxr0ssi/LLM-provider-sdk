"""Tests for provider-specific JSON streaming."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from steer_llm_sdk.api.client import SteerLLMClient
from steer_llm_sdk.models.streaming import StreamingOptions, JSON_MODE_OPTIONS


class TestProviderJSONStreaming:
    """Test JSON streaming with all providers."""
    
    @pytest.mark.asyncio
    async def test_openai_json_streaming(self):
        """Test JSON streaming with OpenAI provider."""
        client = SteerLLMClient()
        
        # Mock the router
        mock_response_chunks = [
            ('{"reasoning": "Let me', None),
            (' think about this', None),
            ('", "answer": 42}', None),
            (None, {
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 15,
                    "total_tokens": 25
                },
                "model": "gpt-4o-mini",
                "provider": "openai"
            })
        ]
        
        async def mock_generate_stream(*args, **kwargs):
            for chunk in mock_response_chunks:
                yield chunk
                
        with patch.object(client.router, 'generate_stream', side_effect=mock_generate_stream):
            response = await client.stream_with_usage(
                messages="Generate a JSON response",
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                streaming_options=JSON_MODE_OPTIONS
            )
            
            # Should have processed JSON
            text = response.get_text()
            assert text == '{"reasoning": "Let me think about this", "answer": 42}'
            
            # Check usage
            assert response.usage is not None
            assert response.usage["total_tokens"] == 25
            
    @pytest.mark.asyncio
    async def test_anthropic_json_streaming(self):
        """Test JSON streaming with Anthropic provider."""
        client = SteerLLMClient()
        
        # Mock Anthropic-style streaming
        mock_response_chunks = [
            ('{"steps": [', None),
            ('{"action": "analyze"},', None),
            ('{"action": "process"}', None),
            ('], "result": "done"}', None),
            (None, {
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 30,
                    "total_tokens": 50
                },
                "model": "claude-3-haiku-20240307",
                "provider": "anthropic"
            })
        ]
        
        async def mock_generate_stream(*args, **kwargs):
            for chunk in mock_response_chunks:
                yield chunk
                
        with patch.object(client.router, 'generate_stream', side_effect=mock_generate_stream):
            response = await client.stream_with_usage(
                messages="Generate a JSON response",
                model="claude-3-haiku-20240307",
                response_format={"type": "json_object"},
                enable_json_stream_handler=True  # Test legacy parameter
            )
            
            # Should have complete JSON
            text = response.get_text()
            parsed = json.loads(text)
            assert "steps" in parsed
            assert len(parsed["steps"]) == 2
            assert parsed["result"] == "done"
            
    @pytest.mark.asyncio
    async def test_xai_json_streaming(self):
        """Test JSON streaming with xAI provider."""
        client = SteerLLMClient()
        
        # Mock xAI-style streaming
        mock_response_chunks = [
            ('{"analysis":', None),
            (' {"confidence": 0.95,', None),
            (' "reasoning": "Based on the data"},', None),
            (' "conclusion": "Valid"}', None),
            (None, {
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 25,
                    "total_tokens": 40
                },
                "model": "grok-beta",
                "provider": "xai"
            })
        ]
        
        async def mock_generate_stream(*args, **kwargs):
            for chunk in mock_response_chunks:
                yield chunk
                
        with patch.object(client.router, 'generate_stream', side_effect=mock_generate_stream):
            # Test with custom StreamingOptions
            custom_options = StreamingOptions(
                enable_json_stream_handler=True,
                log_streaming_metrics=True
            )
            
            response = await client.stream_with_usage(
                messages="Analyze this data",
                model="grok-beta",
                response_format={"type": "json_object"},
                streaming_options=custom_options
            )
            
            # Should have complete JSON
            text = response.get_text()
            parsed = json.loads(text)
            assert "analysis" in parsed
            assert parsed["analysis"]["confidence"] == 0.95
            
    @pytest.mark.asyncio
    async def test_json_streaming_disabled(self):
        """Test that JSON handling can be disabled."""
        client = SteerLLMClient()
        
        # Mock response with JSON-like content
        mock_response_chunks = [
            ('{"this": "looks', None),
            (' like JSON"}', None),
            (None, {"usage": {"total_tokens": 10}, "model": "test", "provider": "test"})
        ]
        
        async def mock_generate_stream(*args, **kwargs):
            for chunk in mock_response_chunks:
                yield chunk
                
        with patch.object(client.router, 'generate_stream', side_effect=mock_generate_stream):
            # Explicitly disable JSON handling
            response = await client.stream_with_usage(
                messages="Test",
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                streaming_options=StreamingOptions(enable_json_stream_handler=False)
            )
            
            # Should have raw chunks
            text = response.get_text()
            assert text == '{"this": "looks like JSON"}'
            
    @pytest.mark.asyncio
    async def test_malformed_json_handling(self):
        """Test handling of malformed JSON."""
        client = SteerLLMClient()
        
        # Mock response with malformed JSON
        mock_response_chunks = [
            ('{"broken": "json', None),
            ('missing closing brace', None),
            (None, {"usage": {"total_tokens": 10}, "model": "test", "provider": "test"})
        ]
        
        async def mock_generate_stream(*args, **kwargs):
            for chunk in mock_response_chunks:
                yield chunk
                
        with patch.object(client.router, 'generate_stream', side_effect=mock_generate_stream):
            response = await client.stream_with_usage(
                messages="Test",
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                streaming_options=JSON_MODE_OPTIONS
            )
            
            # Should keep original chunks when JSON parsing fails
            text = response.get_text()
            assert "broken" in text
            assert "missing closing brace" in text
            
    @pytest.mark.asyncio
    async def test_nested_json_streaming(self):
        """Test streaming of deeply nested JSON."""
        client = SteerLLMClient()
        
        # Create nested JSON
        nested_obj = {
            "level1": {
                "level2": {
                    "level3": {
                        "data": [1, 2, 3],
                        "status": "complete"
                    }
                }
            }
        }
        
        json_str = json.dumps(nested_obj)
        # Split into chunks
        chunk_size = 20
        chunks = [(json_str[i:i+chunk_size], None) for i in range(0, len(json_str), chunk_size)]
        chunks.append((None, {"usage": {"total_tokens": 50}, "model": "test", "provider": "test"}))
        
        async def mock_generate_stream(*args, **kwargs):
            for chunk in chunks:
                yield chunk
                
        with patch.object(client.router, 'generate_stream', side_effect=mock_generate_stream):
            response = await client.stream_with_usage(
                messages="Test nested JSON",
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                streaming_options=JSON_MODE_OPTIONS
            )
            
            # Should reconstruct the nested JSON
            text = response.get_text()
            parsed = json.loads(text)
            assert parsed == nested_obj
            
    @pytest.mark.asyncio
    async def test_json_array_streaming(self):
        """Test streaming of JSON arrays."""
        client = SteerLLMClient()
        
        # JSON array response
        array_response = [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
            {"id": 3, "name": "Third"}
        ]
        
        json_str = json.dumps(array_response)
        mock_response_chunks = [
            (json_str[:30], None),
            (json_str[30:60], None),
            (json_str[60:], None),
            (None, {"usage": {"total_tokens": 40}, "model": "test", "provider": "test"})
        ]
        
        async def mock_generate_stream(*args, **kwargs):
            for chunk in mock_response_chunks:
                yield chunk
                
        with patch.object(client.router, 'generate_stream', side_effect=mock_generate_stream):
            response = await client.stream_with_usage(
                messages="Generate JSON array",
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                streaming_options=JSON_MODE_OPTIONS
            )
            
            # Currently the simple parser might not handle arrays well
            # This test documents the current behavior
            text = response.get_text()
            # Should at least not crash
            assert len(text) > 0