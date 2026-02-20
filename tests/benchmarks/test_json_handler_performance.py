"""Performance benchmarks for JSON stream handler."""

import json
import time
from typing import List, Dict, Any
import statistics

from steer_llm_sdk.streaming.json_handler import JsonStreamHandler


def benchmark_simple_objects(iterations: int = 1000) -> Dict[str, float]:
    """Benchmark simple object parsing."""
    handler = JsonStreamHandler()
    obj = {"key": "value", "number": 42}
    json_str = json.dumps(obj)
    
    times = []
    for _ in range(iterations):
        handler.reset()
        start = time.perf_counter()
        handler.process_chunk(json_str)
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)  # Convert to ms
        
    return {
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "min_ms": min(times),
        "max_ms": max(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0
    }


def benchmark_streaming_chunks(chunk_sizes: List[int]) -> Dict[str, Any]:
    """Benchmark different chunk sizes."""
    results = {}
    
    # Create a moderately complex object
    obj = {
        "data": [{"id": i, "value": f"test_{i}"} for i in range(100)],
        "metadata": {"total": 100, "page": 1}
    }
    json_str = json.dumps(obj)
    
    for chunk_size in chunk_sizes:
        handler = JsonStreamHandler()
        chunks = [json_str[i:i+chunk_size] for i in range(0, len(json_str), chunk_size)]
        
        start = time.perf_counter()
        for chunk in chunks:
            handler.process_chunk(chunk)
        elapsed = time.perf_counter() - start
        
        results[f"chunk_size_{chunk_size}"] = {
            "time_ms": elapsed * 1000,
            "num_chunks": len(chunks),
            "ms_per_chunk": (elapsed * 1000) / len(chunks)
        }
        
    return results


def benchmark_complex_nesting(max_depth: int = 50) -> Dict[str, float]:
    """Benchmark deeply nested objects."""
    results = {}
    
    for depth in [10, 20, 30, 40, 50]:
        if depth > max_depth:
            break
            
        # Create nested object
        obj = {"level": 0}
        current = obj
        for i in range(1, depth):
            current["nested"] = {"level": i}
            current = current["nested"]
            
        json_str = json.dumps(obj)
        handler = JsonStreamHandler()
        
        start = time.perf_counter()
        handler.process_chunk(json_str)
        elapsed = time.perf_counter() - start
        
        results[f"depth_{depth}"] = elapsed * 1000
        
    return results


def benchmark_responses_api_pattern() -> Dict[str, Any]:
    """Benchmark Responses API streaming pattern."""
    handler = JsonStreamHandler()
    
    # Simulate incremental responses
    responses = []
    text = "The answer to life, the universe, and everything is 42"
    words = text.split()
    
    current = ""
    for word in words:
        current += word + " "
        responses.append({"text": current.strip()})
        
    # Time processing all responses
    start = time.perf_counter()
    for resp in responses:
        handler.process_chunk(json.dumps(resp))
    elapsed = time.perf_counter() - start
    
    all_objects = handler.get_all_objects()
    
    return {
        "total_time_ms": elapsed * 1000,
        "num_objects": len(all_objects),
        "ms_per_object": (elapsed * 1000) / len(all_objects) if all_objects else 0,
        "final_object": all_objects[-1] if all_objects else None
    }


def benchmark_json_repair() -> Dict[str, float]:
    """Benchmark JSON repair functionality."""
    handler = JsonStreamHandler()
    
    incomplete_jsons = [
        '{"key": "value"',  # Missing closing brace
        '[1, 2, 3',  # Missing closing bracket
        '{"nested": {"inner": "value"}',  # Nested incomplete
        '{"array": [1, 2, {"obj": true}]'  # Complex incomplete
    ]
    
    times = []
    for incomplete in incomplete_jsons:
        handler.reset()
        handler.buffer = incomplete
        
        start = time.perf_counter()
        handler._repair_json(incomplete)
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)
        
    return {
        "mean_repair_ms": statistics.mean(times),
        "max_repair_ms": max(times)
    }


def run_all_benchmarks():
    """Run all benchmarks and print results."""
    print("JSON Stream Handler Performance Benchmarks")
    print("=" * 50)
    
    # Simple objects
    print("\n1. Simple Object Parsing (1000 iterations):")
    simple_results = benchmark_simple_objects()
    for key, value in simple_results.items():
        print(f"   {key}: {value:.4f}")
        
    # Streaming chunks
    print("\n2. Streaming with Different Chunk Sizes:")
    chunk_results = benchmark_streaming_chunks([10, 50, 100, 500, 1000])
    for chunk_size, metrics in chunk_results.items():
        print(f"   {chunk_size}:")
        for key, value in metrics.items():
            print(f"      {key}: {value:.4f}")
            
    # Complex nesting
    print("\n3. Deeply Nested Objects:")
    nesting_results = benchmark_complex_nesting()
    for depth, time_ms in nesting_results.items():
        print(f"   {depth}: {time_ms:.4f} ms")
        
    # Responses API pattern
    print("\n4. Responses API Pattern:")
    responses_results = benchmark_responses_api_pattern()
    for key, value in responses_results.items():
        if key != "final_object":
            print(f"   {key}: {value}")
            
    # JSON repair
    print("\n5. JSON Repair Performance:")
    repair_results = benchmark_json_repair()
    for key, value in repair_results.items():
        print(f"   {key}: {value:.4f}")
        
    # Overall assessment
    print("\n" + "=" * 50)
    print("Performance Assessment:")
    if simple_results["mean_ms"] < 0.1:
        print("✅ Simple object parsing: EXCELLENT (< 0.1ms)")
    elif simple_results["mean_ms"] < 1:
        print("✅ Simple object parsing: GOOD (< 1ms)")
    else:
        print("⚠️ Simple object parsing: NEEDS OPTIMIZATION")
        
    # Check chunk processing
    chunk_100 = chunk_results.get("chunk_size_100", {})
    if chunk_100.get("ms_per_chunk", float('inf')) < 0.5:
        print("✅ Chunk processing: GOOD (< 0.5ms per chunk)")
    else:
        print("⚠️ Chunk processing: May need optimization")


if __name__ == "__main__":
    run_all_benchmarks()