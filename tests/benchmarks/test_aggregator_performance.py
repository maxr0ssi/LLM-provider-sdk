"""Performance benchmarks for usage aggregators."""

import pytest
import time
from typing import List
import random
import string

from steer_llm_sdk.streaming.aggregator import (
    CharacterAggregator,
    TiktokenAggregator,
    create_usage_aggregator,
    TIKTOKEN_AVAILABLE
)


def generate_random_text(length: int) -> str:
    """Generate random text of specified length."""
    return ''.join(random.choices(string.ascii_letters + string.digits + ' .,!?', k=length))


def generate_messages(num_messages: int, avg_length: int) -> List[dict]:
    """Generate random messages."""
    messages = []
    roles = ["system", "user", "assistant"]
    
    for i in range(num_messages):
        messages.append({
            "role": roles[i % len(roles)],
            "content": generate_random_text(avg_length)
        })
    
    return messages


class TestAggregatorPerformance:
    """Benchmark aggregator performance."""
    
    def test_character_aggregator_speed(self):
        """Test character aggregator performance."""
        agg = CharacterAggregator("model", "provider")
        
        # Test prompt estimation
        messages = generate_messages(10, 100)  # 10 messages, ~100 chars each
        
        start = time.time()
        for _ in range(100):  # 100 iterations
            agg.estimate_prompt_tokens(messages)
        prompt_time = time.time() - start
        
        # Test completion tracking
        chunks = [generate_random_text(50) for _ in range(20)]  # 20 chunks
        
        start = time.time()
        for _ in range(100):  # 100 iterations
            agg.completion_text = ""  # Reset
            agg.completion_tokens = 0
            for chunk in chunks:
                agg.add_completion_chunk(chunk)
        completion_time = time.time() - start
        
        # Performance assertions
        assert prompt_time < 0.5  # Should process 100 prompts in < 500ms
        assert completion_time < 1.0  # Should process 100 streams in < 1s
        
        print(f"\nCharacter Aggregator Performance:")
        print(f"  Prompt estimation: {prompt_time*10:.2f}ms per prompt")
        print(f"  Completion tracking: {completion_time*10:.2f}ms per stream")
        
    @pytest.mark.skipif(not TIKTOKEN_AVAILABLE, reason="tiktoken not installed")
    def test_tiktoken_aggregator_speed(self):
        """Test tiktoken aggregator performance."""
        agg = TiktokenAggregator("gpt-4", "openai")
        
        # Test prompt estimation
        messages = generate_messages(10, 100)
        
        start = time.time()
        for _ in range(100):
            agg.estimate_prompt_tokens(messages)
        prompt_time = time.time() - start
        
        # Test completion tracking
        chunks = [generate_random_text(50) for _ in range(20)]
        
        start = time.time()
        for _ in range(100):
            agg.completion_text = ""
            agg.completion_tokens = 0
            for chunk in chunks:
                agg.add_completion_chunk(chunk)
        completion_time = time.time() - start
        
        # Tiktoken is slower but more accurate
        assert prompt_time < 2.0  # Should process 100 prompts in < 2s
        assert completion_time < 3.0  # Should process 100 streams in < 3s
        
        print(f"\nTiktoken Aggregator Performance:")
        print(f"  Prompt estimation: {prompt_time*10:.2f}ms per prompt")
        print(f"  Completion tracking: {completion_time*10:.2f}ms per stream")
        
    def test_incremental_vs_batch_performance(self):
        """Compare incremental vs batch token counting."""
        agg = CharacterAggregator("model", "provider")
        
        # Generate a long text
        long_text = generate_random_text(10000)
        
        # Batch counting
        start = time.time()
        for _ in range(100):
            batch_tokens = agg.count_tokens(long_text)
        batch_time = time.time() - start
        
        # Incremental counting (character by character)
        start = time.time()
        for _ in range(100):
            agg.completion_text = ""
            agg.completion_tokens = 0
            for char in long_text[:1000]:  # Only first 1000 chars for reasonable time
                agg.add_completion_chunk(char)
        incremental_time = time.time() - start
        
        print(f"\nBatch vs Incremental Performance:")
        print(f"  Batch (10K chars): {batch_time*10:.2f}ms per count")
        print(f"  Incremental (1K chars): {incremental_time*10:.2f}ms per stream")
        
        # Batch should be much faster
        assert batch_time < incremental_time / 10
        
    def test_memory_efficiency(self):
        """Test memory efficiency with large texts."""
        agg = CharacterAggregator("model", "provider")
        
        # Generate increasingly large texts
        sizes = [1000, 10000, 100000]
        times = []
        
        for size in sizes:
            text = generate_random_text(size)
            
            start = time.time()
            tokens = agg.count_tokens(text)
            elapsed = time.time() - start
            times.append(elapsed)
            
            # Clear to free memory
            text = None
            
        # Time should scale linearly with size
        # (not exponentially, which would indicate memory issues)
        ratio1 = times[1] / times[0]
        ratio2 = times[2] / times[1]
        
        print(f"\nMemory Efficiency Test:")
        print(f"  1K chars: {times[0]*1000:.2f}ms")
        print(f"  10K chars: {times[1]*1000:.2f}ms (x{ratio1:.1f})")
        print(f"  100K chars: {times[2]*1000:.2f}ms (x{ratio2:.1f})")
        
        # Ratios should be roughly proportional to size increase (10x)
        assert 5 < ratio1 < 20  # Allow some variance
        assert 5 < ratio2 < 20
        
    def test_factory_function_performance(self):
        """Test aggregator creation performance."""
        # Time aggregator creation
        start = time.time()
        for _ in range(1000):
            agg = create_usage_aggregator("gpt-4", "openai", prefer_tiktoken=False)
        char_creation_time = time.time() - start
        
        if TIKTOKEN_AVAILABLE:
            start = time.time()
            for _ in range(100):  # Fewer iterations as tiktoken init is slower
                agg = create_usage_aggregator("gpt-4", "openai", prefer_tiktoken=True)
            tik_creation_time = (time.time() - start) * 10  # Normalize to 1000
            
            print(f"\nAggregator Creation Performance:")
            print(f"  Character: {char_creation_time:.2f}ms per 1000")
            print(f"  Tiktoken: {tik_creation_time:.2f}ms per 1000")
        else:
            print(f"\nAggregator Creation Performance:")
            print(f"  Character: {char_creation_time:.2f}ms per 1000")
            
        # Creation should be fast
        assert char_creation_time < 0.1  # < 100ms for 1000 creations
        
    def test_streaming_simulation(self):
        """Simulate realistic streaming scenario."""
        # Simulate GPT-4 response streaming
        prompt = "Explain quantum computing in simple terms"
        response_chunks = [
            "Quantum computing ",
            "is a type of ",
            "computing that uses ",
            "quantum mechanical ",
            "phenomena like ",
            "superposition and ",
            "entanglement to ",
            "process information. ",
            "\n\nUnlike classical ",
            "computers that use ",
            "bits (0 or 1), ",
            "quantum computers ",
            "use quantum bits ",
            "or 'qubits' which ",
            "can be in multiple ",
            "states simultaneously."
        ]
        
        # Test with character aggregator
        char_agg = CharacterAggregator("gpt-4", "openai")
        
        start = time.time()
        char_agg.estimate_prompt_tokens(prompt)
        for chunk in response_chunks:
            char_agg.add_completion_chunk(chunk)
            # Simulate 50ms network delay
            time.sleep(0.05)
        usage = char_agg.get_usage()
        char_time = time.time() - start
        
        print(f"\nRealistic Streaming Simulation:")
        print(f"  Total time: {char_time*1000:.0f}ms")
        print(f"  Prompt tokens: {usage['prompt_tokens']}")
        print(f"  Completion tokens: {usage['completion_tokens']}")
        print(f"  Total tokens: {usage['total_tokens']}")
        print(f"  Confidence: {usage['confidence']}")
        
        # Should handle streaming without significant overhead
        expected_time = len(response_chunks) * 0.05  # Just the sleep time
        overhead = char_time - expected_time
        assert overhead < 0.1  # Less than 100ms total overhead