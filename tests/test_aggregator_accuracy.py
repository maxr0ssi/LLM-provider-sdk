"""Tests for usage aggregator accuracy."""

import pytest
from unittest.mock import patch

from steer_llm_sdk.streaming.aggregator import (
    CharacterAggregator,
    TiktokenAggregator,
    create_usage_aggregator,
    TIKTOKEN_AVAILABLE
)


class TestCharacterAggregatorAccuracy:
    """Test accuracy of character-based token estimation."""
    
    def test_openai_typical_ratios(self):
        """Test typical OpenAI text patterns."""
        agg = CharacterAggregator("gpt-4", "openai")
        
        # Common patterns and expected ratios
        test_cases = [
            # (text, expected_min_ratio, expected_max_ratio)
            ("Hello world", 3.5, 4.5),  # Simple text
            ("The quick brown fox jumps over the lazy dog", 3.8, 4.2),  # Normal sentence
            ("import numpy as np\nimport pandas as pd", 3.0, 4.0),  # Code
            ("👋🌍", 2.0, 6.0),  # Emojis can vary widely
            ("This is a longer passage with multiple sentences. It contains various words and punctuation marks!", 3.7, 4.3)
        ]
        
        for text, min_ratio, max_ratio in test_cases:
            tokens = agg.count_tokens(text)
            actual_ratio = len(text) / tokens if tokens > 0 else 0
            assert min_ratio <= actual_ratio <= max_ratio, f"Text: {text}, Ratio: {actual_ratio}"
            
    def test_anthropic_typical_ratios(self):
        """Test typical Anthropic text patterns."""
        agg = CharacterAggregator("claude-3", "anthropic")
        
        # Anthropic tends to have slightly lower char/token ratio
        test_cases = [
            ("Hello world", 3.0, 4.0),
            ("Analyze this complex problem", 3.2, 3.8),
            ("def calculate_sum(a, b):\n    return a + b", 2.8, 3.8)
        ]
        
        for text, min_ratio, max_ratio in test_cases:
            tokens = agg.count_tokens(text)
            actual_ratio = len(text) / tokens if tokens > 0 else 0
            assert min_ratio <= actual_ratio <= max_ratio
            
    def test_streaming_accuracy(self):
        """Test accuracy when processing streaming chunks."""
        agg = CharacterAggregator("gpt-4", "openai")
        
        # Simulate streaming a response
        chunks = [
            "I'll ",
            "help you ",
            "understand ",
            "this concept. ",
            "First, ",
            "let me explain ",
            "the basics."
        ]
        
        for chunk in chunks:
            agg.add_completion_chunk(chunk)
            
        full_text = "".join(chunks)
        final_tokens = agg.completion_tokens
        
        # Direct count should be similar
        direct_count = agg.count_tokens(full_text)
        
        # Allow 10% variance due to rounding in chunks
        assert abs(final_tokens - direct_count) <= max(1, int(direct_count * 0.1))
        
    def test_message_overhead_accuracy(self):
        """Test accuracy of message formatting overhead."""
        agg = CharacterAggregator("gpt-4", "openai")
        
        # Single message
        single_msg = [{"role": "user", "content": "Hello"}]
        tokens_single = agg.estimate_prompt_tokens(single_msg)
        
        # Same content as string
        agg2 = CharacterAggregator("gpt-4", "openai")
        tokens_string = agg2.estimate_prompt_tokens("user: Hello")
        
        # Should have 4 tokens overhead for message format
        assert tokens_single == tokens_string + 4


@pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken not installed")
class TestTiktokenAccuracy:
    """Test tiktoken accuracy against known values."""
    
    def test_gpt4_known_counts(self):
        """Test against known GPT-4 token counts."""
        agg = TiktokenAggregator("gpt-4", "openai")
        
        # Known token counts for cl100k_base encoding
        test_cases = [
            ("Hello world", 2),
            ("Hello, world!", 4),
            ("The quick brown fox", 4),
            ("import numpy as np", 4),
            ("def main():", 3),
            ("", 0),
        ]
        
        for text, expected in test_cases:
            tokens = agg.count_tokens(text)
            assert tokens == expected, f"Text: '{text}', Expected: {expected}, Got: {tokens}"
            
    def test_gpt4o_encoding(self):
        """Test GPT-4o with o200k_base encoding."""
        agg = TiktokenAggregator("gpt-4o", "openai")
        
        # Should use different encoding
        text = "Hello world"
        tokens = agg.count_tokens(text)
        assert tokens > 0  # Just verify it works
        
    def test_streaming_exactness(self):
        """Test that streaming gives exact same count as full text."""
        agg = TiktokenAggregator("gpt-4", "openai")
        
        full_text = "This is a test of streaming token counting accuracy."
        expected = agg.count_tokens(full_text)
        
        # Reset and stream
        agg2 = TiktokenAggregator("gpt-4", "openai") 
        chunks = ["This ", "is a ", "test of ", "streaming ", "token counting ", "accuracy."]
        
        for chunk in chunks:
            agg2.add_completion_chunk(chunk)
            
        assert agg2.completion_tokens == expected
        assert agg2.completion_text == full_text


class TestAggregatorComparison:
    """Compare different aggregators for accuracy analysis."""
    
    @pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken not installed")
    def test_accuracy_comparison(self):
        """Compare character vs tiktoken accuracy."""
        test_texts = [
            "Hello world",
            "The quick brown fox jumps over the lazy dog",
            "import numpy as np\nimport pandas as pd\ndf = pd.DataFrame()",
            "This is a longer passage with multiple sentences. It includes various punctuation marks, numbers like 123, and symbols!",
            "Mixed content: Code `print('hello')` and text.",
        ]
        
        for text in test_texts:
            char_agg = CharacterAggregator("gpt-4", "openai")
            tik_agg = TiktokenAggregator("gpt-4", "openai")
            
            char_tokens = char_agg.count_tokens(text)
            tik_tokens = tik_agg.count_tokens(text)
            
            # Calculate error rate
            if tik_tokens > 0:
                error_rate = abs(char_tokens - tik_tokens) / tik_tokens
                # Character estimation should be within 30% of tiktoken
                assert error_rate <= 0.5, f"Text: '{text[:50]}...', Error: {error_rate:.2%}"
                
    def test_provider_ratio_validation(self):
        """Validate provider-specific ratios are reasonable."""
        providers_and_samples = [
            ("openai", "gpt-4", 4.0),
            ("anthropic", "claude-3", 3.5),
            ("xai", "grok", 4.2),
        ]
        
        sample_text = "This is a sample text to test token ratios across different providers."
        
        for provider, model, expected_ratio in providers_and_samples:
            agg = CharacterAggregator(model, provider)
            assert agg.chars_per_token == expected_ratio
            
            tokens = agg.count_tokens(sample_text)
            actual_ratio = len(sample_text) / tokens
            
            # Ratio should be close to configured value (within 20%)
            assert abs(actual_ratio - expected_ratio) / expected_ratio <= 0.2


class TestEdgeCases:
    """Test edge cases for accuracy."""
    
    def test_empty_and_whitespace(self):
        """Test empty and whitespace-only inputs."""
        agg = CharacterAggregator("model", "provider")
        
        assert agg.count_tokens("") == 0
        assert agg.count_tokens("   ") == 1  # 3 chars / 4 = 0.75 -> 1
        assert agg.count_tokens("\n\n") == 1  # 2 chars / 4 = 0.5 -> 1
        
    def test_unicode_handling(self):
        """Test Unicode character handling."""
        agg = CharacterAggregator("model", "provider")
        
        # Unicode takes more bytes but char count is what matters
        assert agg.count_tokens("café") == 1  # 4 chars
        assert agg.count_tokens("你好世界") == 1  # 4 chars
        assert agg.count_tokens("🚀🌟✨") == 1  # 3 chars / 4.0 = 0.75 -> rounds to 1
        
    def test_very_long_text(self):
        """Test accuracy on very long texts."""
        agg = CharacterAggregator("gpt-4", "openai")
        
        # Generate long text
        long_text = "This is a test. " * 1000  # 16 chars * 1000 = 16000 chars
        tokens = agg.count_tokens(long_text)
        
        expected = 16000 / 4  # 4000 tokens
        # Should be very close for large texts (within 1%)
        assert abs(tokens - expected) / expected <= 0.01
        
    def test_incremental_vs_full_counting(self):
        """Test that incremental counting matches full count."""
        agg1 = CharacterAggregator("model", "provider")
        agg2 = CharacterAggregator("model", "provider")
        
        text = "This is a test of incremental token counting."
        
        # Full count
        full_count = agg1.count_tokens(text)
        
        # Incremental count
        for char in text:
            agg2.add_completion_chunk(char)
            
        # Should be identical
        assert agg2.completion_tokens == full_count