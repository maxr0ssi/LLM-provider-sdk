"""Tests for usage aggregator functionality."""

import pytest
from unittest.mock import patch, MagicMock

from steer_llm_sdk.streaming.aggregator import (
    UsageAggregator,
    TiktokenAggregator,
    CharacterAggregator,
    create_usage_aggregator,
    TIKTOKEN_AVAILABLE
)


class TestCharacterAggregator:
    """Test character-based aggregator."""
    
    def test_init(self):
        """Test aggregator initialization."""
        agg = CharacterAggregator("gpt-4", "openai")
        assert agg.model == "gpt-4"
        assert agg.provider == "openai"
        assert agg.chars_per_token == 4.0
        assert agg.prompt_tokens == 0
        assert agg.completion_tokens == 0
        
    def test_provider_specific_ratios(self):
        """Test provider-specific character ratios."""
        openai_agg = CharacterAggregator("gpt-4", "openai")
        assert openai_agg.chars_per_token == 4.0
        
        anthropic_agg = CharacterAggregator("claude-3", "anthropic")
        assert anthropic_agg.chars_per_token == 3.5
        
        xai_agg = CharacterAggregator("grok", "xai")
        assert xai_agg.chars_per_token == 4.2
        
        unknown_agg = CharacterAggregator("unknown", "unknown")
        assert unknown_agg.chars_per_token == 4.0  # default
        
    def test_estimate_prompt_tokens_string(self):
        """Test prompt token estimation with string input."""
        agg = CharacterAggregator("gpt-4", "openai")
        
        # 40 characters / 4 = 10 tokens
        prompt = "This is a test prompt with forty chars.."
        tokens = agg.estimate_prompt_tokens(prompt)
        assert tokens == 10
        assert agg.prompt_tokens == 10
        
    def test_estimate_prompt_tokens_messages(self):
        """Test prompt token estimation with message list."""
        agg = CharacterAggregator("gpt-4", "openai")
        
        messages = [
            {"role": "system", "content": "You are helpful"},  # 22 chars
            {"role": "user", "content": "Hello"}  # 11 chars
        ]
        # Total formatted: "system: You are helpful\nuser: Hello" = 36 chars
        # 36 chars / 4 = 9 tokens
        # Plus 4 tokens per message (2 * 4 = 8)
        tokens = agg.estimate_prompt_tokens(messages)
        assert tokens == 17  # 9 + 8
        
    def test_add_completion_chunk(self):
        """Test adding completion chunks."""
        agg = CharacterAggregator("gpt-4", "openai")
        
        agg.add_completion_chunk("Hello ")  # 6 chars
        assert agg.completion_tokens == 2  # 6/4 = 1.5 -> 2
        
        agg.add_completion_chunk("world!")  # 6 more chars
        assert agg.completion_tokens == 3  # 12/4 = 3
        assert agg.completion_text == "Hello world!"
        
    def test_count_tokens(self):
        """Test token counting."""
        agg = CharacterAggregator("gpt-4", "openai")
        
        assert agg.count_tokens("") == 0
        assert agg.count_tokens("test") == 1  # 4/4 = 1
        assert agg.count_tokens("testing") == 2  # 7/4 = 1.75 -> 2
        assert agg.count_tokens("a" * 100) == 25  # 100/4 = 25
        
    def test_get_usage(self):
        """Test getting aggregated usage."""
        agg = CharacterAggregator("gpt-4", "openai")
        
        agg.estimate_prompt_tokens("Test prompt")
        agg.add_completion_chunk("Test response")
        
        usage = agg.get_usage()
        assert usage["prompt_tokens"] == 3  # 11/4 = 2.75 -> 3
        assert usage["completion_tokens"] == 3  # 13/4 = 3.25 -> 3
        assert usage["total_tokens"] == 6
        assert usage["confidence"] == 0.75  # OpenAI confidence
        assert usage["method"] == "CharacterAggregator"
        
    def test_get_confidence(self):
        """Test confidence scores by provider."""
        openai_agg = CharacterAggregator("gpt-4", "openai")
        assert openai_agg.get_confidence() == 0.75
        
        anthropic_agg = CharacterAggregator("claude", "anthropic")
        assert anthropic_agg.get_confidence() == 0.70
        
        xai_agg = CharacterAggregator("grok", "xai")
        assert xai_agg.get_confidence() == 0.65
        
        unknown_agg = CharacterAggregator("model", "unknown")
        assert unknown_agg.get_confidence() == 0.60


@pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken not installed")
class TestTiktokenAggregator:
    """Test tiktoken-based aggregator."""
    
    def test_init(self):
        """Test tiktoken aggregator initialization."""
        agg = TiktokenAggregator("gpt-4", "openai")
        assert agg.model == "gpt-4"
        assert agg.provider == "openai"
        assert agg.encoding is not None
        
    def test_model_encoding_mapping(self):
        """Test correct encoding selection for models."""
        # GPT-4 uses cl100k_base
        gpt4_agg = TiktokenAggregator("gpt-4", "openai")
        assert gpt4_agg.encoding.name == "cl100k_base"
        
        # GPT-4o uses cl100k_base for now
        gpt4o_agg = TiktokenAggregator("gpt-4o-mini", "openai")
        assert gpt4o_agg.encoding.name == "cl100k_base"
        
        # Unknown model falls back to cl100k_base
        unknown_agg = TiktokenAggregator("unknown-model", "openai")
        assert unknown_agg.encoding.name == "cl100k_base"
        
    def test_estimate_prompt_tokens(self):
        """Test accurate token counting with tiktoken."""
        agg = TiktokenAggregator("gpt-4", "openai")
        
        # Test with known string
        prompt = "Hello, world!"
        tokens = agg.estimate_prompt_tokens(prompt)
        assert tokens > 0  # Exact count depends on encoding
        assert agg.prompt_tokens == tokens
        
    def test_add_completion_chunk(self):
        """Test completion chunk handling."""
        agg = TiktokenAggregator("gpt-4", "openai")
        
        agg.add_completion_chunk("Hello ")
        first_count = agg.completion_tokens
        assert first_count > 0
        
        agg.add_completion_chunk("world!")
        assert agg.completion_tokens > first_count
        assert agg.completion_text == "Hello world!"
        
    def test_get_confidence(self):
        """Test high confidence for tiktoken."""
        agg = TiktokenAggregator("gpt-4", "openai")
        assert agg.get_confidence() == 0.95
        
    def test_messages_handling(self):
        """Test token counting with message format."""
        agg = TiktokenAggregator("gpt-4", "openai")
        
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"}
        ]
        
        tokens = agg.estimate_prompt_tokens(messages)
        # Should include message overhead (4 tokens per message)
        assert tokens > 8  # At least the overhead
        

class TestCreateUsageAggregator:
    """Test aggregator factory function."""
    
    @patch('steer_llm_sdk.streaming.aggregator.TIKTOKEN_AVAILABLE', True)
    def test_create_with_tiktoken_available(self):
        """Test creation when tiktoken is available."""
        # Should use tiktoken for OpenAI
        agg = create_usage_aggregator("gpt-4", "openai", prefer_tiktoken=True)
        if TIKTOKEN_AVAILABLE:
            assert isinstance(agg, TiktokenAggregator)
        else:
            assert isinstance(agg, CharacterAggregator)
            
        # Should use character for non-OpenAI
        agg = create_usage_aggregator("claude", "anthropic", prefer_tiktoken=True)
        assert isinstance(agg, CharacterAggregator)
        
    @patch('steer_llm_sdk.streaming.aggregator.TIKTOKEN_AVAILABLE', False)
    def test_create_without_tiktoken(self):
        """Test creation when tiktoken is not available."""
        agg = create_usage_aggregator("gpt-4", "openai", prefer_tiktoken=True)
        assert isinstance(agg, CharacterAggregator)
        
    def test_create_prefer_character(self):
        """Test creation with character preference."""
        agg = create_usage_aggregator("gpt-4", "openai", prefer_tiktoken=False)
        assert isinstance(agg, CharacterAggregator)
        
    @patch('steer_llm_sdk.streaming.aggregator.TiktokenAggregator')
    def test_tiktoken_fallback_on_error(self, mock_tiktoken_class):
        """Test fallback to character when tiktoken fails."""
        # Make TiktokenAggregator raise an error
        mock_tiktoken_class.side_effect = Exception("Encoding error")
        
        with patch('steer_llm_sdk.streaming.aggregator.TIKTOKEN_AVAILABLE', True):
            agg = create_usage_aggregator("gpt-4", "openai", prefer_tiktoken=True)
            assert isinstance(agg, CharacterAggregator)


class TestUsageAggregatorMessages:
    """Test message handling in aggregators."""
    
    def test_messages_to_text_string(self):
        """Test converting string messages."""
        agg = CharacterAggregator("model", "provider")
        text = agg._messages_to_text("Hello world")
        assert text == "Hello world"
        
    def test_messages_to_text_dict_list(self):
        """Test converting dict message list."""
        agg = CharacterAggregator("model", "provider")
        messages = [
            {"role": "system", "content": "System message"},
            {"role": "user", "content": "User message"}
        ]
        text = agg._messages_to_text(messages)
        assert "system: System message" in text
        assert "user: User message" in text
        
    def test_messages_to_text_object_list(self):
        """Test converting object message list."""
        agg = CharacterAggregator("model", "provider")
        
        # Mock message objects
        msg1 = MagicMock()
        msg1.role = "assistant"
        msg1.content = "Assistant message"
        
        msg2 = MagicMock()
        msg2.role = "user"
        msg2.content = "User followup"
        
        text = agg._messages_to_text([msg1, msg2])
        assert "assistant: Assistant message" in text
        assert "user: User followup" in text
        
    def test_empty_completion_handling(self):
        """Test handling empty completion chunks."""
        agg = CharacterAggregator("model", "provider")
        
        agg.add_completion_chunk("")
        assert agg.completion_tokens == 0
        assert agg.completion_text == ""
        
        agg.add_completion_chunk(None)
        assert agg.completion_tokens == 0
        assert agg.completion_text == ""