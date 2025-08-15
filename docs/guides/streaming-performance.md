# Streaming Performance Optimization Guide

This guide covers techniques for optimizing streaming performance in the Steer LLM SDK.

## Understanding Streaming Metrics

### Key Performance Indicators

```python
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.models.streaming import StreamingOptions

client = SteerLLMClient()

# Enable detailed metrics
streaming_options = StreamingOptions(
    enable_usage_aggregation=True,
    prefer_tiktoken=True,  # More accurate token counting
    enable_json_stream_handler=False  # Disable if not needed
)

response = await client.stream_with_usage(
    messages="Write a long story",
    model="gpt-4",
    streaming_options=streaming_options
)

# Access performance metrics
print(f"Time to First Token: {response.metrics.get('time_to_first_token_ms')}ms")
print(f"Total chunks: {response.metrics.get('chunks')}")
print(f"Chunks/second: {response.metrics.get('chunks_per_second'):.2f}")
print(f"Characters/second: {response.metrics.get('chars_per_second'):.2f}")
```

### Time to First Token (TTFT)

TTFT is critical for user experience. Here's how to optimize it:

```python
import time

# Track TTFT manually
first_token_time = None
start_time = time.time()

async def on_delta(event):
    global first_token_time
    if first_token_time is None and event.get_text():
        first_token_time = time.time()
        ttft = (first_token_time - start_time) * 1000
        print(f"First token received in {ttft:.0f}ms")

response = await client.stream_with_usage(
    messages="Quick response please",
    model="gpt-3.5-turbo",  # Faster model for lower TTFT
    temperature=0.7,
    max_tokens=100,  # Limit output for faster response
    on_delta=on_delta
)
```

## Optimization Techniques

### 1. Model Selection

Different models have different streaming characteristics:

```python
# Benchmark different models
models = ["gpt-3.5-turbo", "gpt-4", "claude-3-haiku", "claude-3-sonnet"]
results = {}

for model in models:
    start = time.time()
    first_chunk_time = None
    
    async def track_first(event):
        nonlocal first_chunk_time
        if first_chunk_time is None:
            first_chunk_time = time.time()
    
    response = await client.stream_with_usage(
        messages="Tell me a joke",
        model=model,
        max_tokens=50,
        on_delta=track_first
    )
    
    results[model] = {
        "ttft": (first_chunk_time - start) * 1000,
        "total_time": (time.time() - start) * 1000,
        "throughput": len(response.get_text()) / (time.time() - start)
    }

# Choose model based on requirements
for model, metrics in results.items():
    print(f"{model}: TTFT={metrics['ttft']:.0f}ms, "
          f"Throughput={metrics['throughput']:.1f} chars/sec")
```

### 2. Chunk Processing Optimization

Process chunks efficiently without blocking:

```python
import asyncio
from collections import deque

class OptimizedStreamProcessor:
    def __init__(self, buffer_size=10):
        self.buffer = deque(maxlen=buffer_size)
        self.processing_task = None
        
    async def process_stream(self, messages, model):
        """Process stream with buffering."""
        
        async def process_buffer():
            """Background processor for chunks."""
            while True:
                if self.buffer:
                    chunk = self.buffer.popleft()
                    # Process chunk (e.g., update UI, parse, etc.)
                    await self._process_chunk(chunk)
                else:
                    await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
        
        # Start background processor
        self.processing_task = asyncio.create_task(process_buffer())
        
        try:
            # Stream and buffer chunks
            async for chunk in client.stream(messages, model):
                self.buffer.append(chunk)
                
                # Yield immediately for real-time updates
                yield chunk
                
        finally:
            # Clean up
            if self.processing_task:
                self.processing_task.cancel()
    
    async def _process_chunk(self, chunk):
        """Process individual chunk."""
        # Your processing logic here
        pass
```

### 3. Concurrent Streaming

Handle multiple streams efficiently:

```python
async def concurrent_streaming(prompts: List[str], model: str):
    """Stream multiple requests concurrently."""
    
    async def stream_with_id(prompt: str, stream_id: int):
        chunks = []
        start_time = time.time()
        
        async for chunk in client.stream(prompt, model):
            chunks.append(chunk)
        
        return {
            "id": stream_id,
            "prompt": prompt,
            "response": "".join(chunks),
            "duration": time.time() - start_time,
            "chunks": len(chunks)
        }
    
    # Limit concurrency
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent streams
    
    async def limited_stream(prompt: str, stream_id: int):
        async with semaphore:
            return await stream_with_id(prompt, stream_id)
    
    # Execute concurrently
    results = await asyncio.gather(*[
        limited_stream(prompt, i) 
        for i, prompt in enumerate(prompts)
    ])
    
    # Analyze performance
    avg_duration = sum(r["duration"] for r in results) / len(results)
    total_chunks = sum(r["chunks"] for r in results)
    
    print(f"Average duration: {avg_duration:.2f}s")
    print(f"Total chunks processed: {total_chunks}")
    
    return results
```

### 4. Memory-Efficient Streaming

For long outputs, process chunks without storing everything:

```python
class MemoryEfficientStreamer:
    def __init__(self, chunk_processor):
        self.chunk_processor = chunk_processor
        self.total_chars = 0
        self.chunk_count = 0
        
    async def stream_and_process(self, messages, model, **kwargs):
        """Stream and process without storing full response."""
        
        async for chunk in client.stream(messages, model, **kwargs):
            # Process chunk immediately
            processed = await self.chunk_processor(chunk)
            
            # Track stats without storing
            self.total_chars += len(chunk)
            self.chunk_count += 1
            
            # Yield processed result
            yield processed
        
        print(f"Processed {self.chunk_count} chunks, {self.total_chars} chars")

# Example: Real-time translation
async def translate_chunk(chunk: str) -> str:
    # Simulate translation processing
    return chunk.upper()  # Simple example

streamer = MemoryEfficientStreamer(translate_chunk)

async for translated in streamer.stream_and_process(
    "Tell me a long story",
    "gpt-4"
):
    print(translated, end="", flush=True)
```

### 5. Adaptive Streaming

Adjust streaming parameters based on network conditions:

```python
class AdaptiveStreamer:
    def __init__(self):
        self.latency_history = deque(maxlen=10)
        self.throughput_history = deque(maxlen=10)
        
    async def stream_adaptive(self, messages, model):
        """Adapt streaming based on performance."""
        
        chunk_times = []
        last_time = time.time()
        
        # Start with default options
        streaming_options = StreamingOptions()
        
        async for chunk in client.stream(
            messages, 
            model,
            streaming_options=streaming_options
        ):
            current_time = time.time()
            chunk_latency = current_time - last_time
            chunk_times.append(chunk_latency)
            
            # Adapt based on performance
            if len(chunk_times) > 5:
                avg_latency = sum(chunk_times[-5:]) / 5
                
                if avg_latency > 0.5:  # High latency
                    # Could switch to more aggressive buffering
                    print("High latency detected, adapting...")
                elif avg_latency < 0.1:  # Low latency
                    # Could reduce buffering for lower latency
                    print("Low latency, optimizing for real-time...")
            
            last_time = current_time
            yield chunk
```

## JSON Streaming Performance

### Optimizing JSON Parsing

```python
from steer_llm_sdk.models.streaming import StreamingOptions

# Only enable JSON handler when needed
def create_streaming_options(response_format):
    if response_format and response_format.get("type") == "json_object":
        return StreamingOptions(
            enable_json_stream_handler=True,
            enable_usage_aggregation=True
        )
    else:
        return StreamingOptions(
            enable_json_stream_handler=False,  # Save processing overhead
            enable_usage_aggregation=True
        )

# Benchmark JSON vs non-JSON
async def benchmark_json_overhead():
    # Without JSON processing
    start = time.time()
    response1 = await client.stream_with_usage(
        messages="List 5 items",
        model="gpt-4",
        streaming_options=StreamingOptions(enable_json_stream_handler=False)
    )
    time_without = time.time() - start
    
    # With JSON processing
    start = time.time()
    response2 = await client.stream_with_usage(
        messages='List 5 items as JSON: {"items": [...]}',
        model="gpt-4",
        response_format={"type": "json_object"},
        streaming_options=StreamingOptions(enable_json_stream_handler=True)
    )
    time_with = time.time() - start
    
    overhead = ((time_with - time_without) / time_without) * 100
    print(f"JSON processing overhead: {overhead:.1f}%")
```

## Token Counting Performance

### Choosing the Right Aggregator

```python
from steer_llm_sdk.models.streaming import StreamingOptions

# Benchmark token counting methods
async def benchmark_token_counting():
    text = "This is a sample text for token counting benchmark" * 100
    
    # Character-based (fast, approximate)
    options1 = StreamingOptions(
        enable_usage_aggregation=True,
        prefer_tiktoken=False
    )
    
    start = time.time()
    response1 = await client.stream_with_usage(
        messages=text,
        model="gpt-4",
        streaming_options=options1
    )
    char_time = time.time() - start
    
    # Tiktoken-based (accurate, slower)
    options2 = StreamingOptions(
        enable_usage_aggregation=True,
        prefer_tiktoken=True
    )
    
    start = time.time()
    response2 = await client.stream_with_usage(
        messages=text,
        model="gpt-4",
        streaming_options=options2
    )
    tiktoken_time = time.time() - start
    
    print(f"Character aggregator: {char_time:.3f}s")
    print(f"Tiktoken aggregator: {tiktoken_time:.3f}s")
    print(f"Tiktoken overhead: {((tiktoken_time - char_time) / char_time * 100):.1f}%")
```

## Network Optimization

### Connection Pooling

```python
# The SDK handles connection pooling automatically, but you can tune it:
import httpx

# For high-volume applications
class OptimizedClient(SteerLLMClient):
    def __init__(self):
        super().__init__()
        
        # Increase connection pool size for providers
        # This is handled internally by provider SDKs
        
        # For custom implementations:
        self.http_client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30
            ),
            timeout=httpx.Timeout(30.0, connect=5.0)
        )
```

### Retry Configuration

```python
from steer_llm_sdk.models.streaming import StreamingOptions

# Configure streaming retries
streaming_options = StreamingOptions(
    connection_timeout=5.0,      # Fail fast on connection
    read_timeout=30.0,          # Reasonable read timeout
    retry_on_connection_error=True,
    max_reconnect_attempts=2    # Limited retries
)

# For critical applications
async def stream_with_fallback(messages, primary_model, fallback_model):
    """Stream with fallback to different model."""
    try:
        response = await client.stream_with_usage(
            messages=messages,
            model=primary_model,
            streaming_options=StreamingOptions(
                connection_timeout=3.0,  # Tight timeout for primary
                retry_on_connection_error=False  # Don't retry, fallback instead
            )
        )
        return response
    except Exception as e:
        print(f"Primary model failed: {e}, using fallback")
        return await client.stream_with_usage(
            messages=messages,
            model=fallback_model
        )
```

## Monitoring Streaming Performance

### Real-time Metrics

```python
class StreamingMonitor:
    def __init__(self):
        self.metrics = {
            "chunk_latencies": deque(maxlen=100),
            "chunk_sizes": deque(maxlen=100),
            "timestamps": deque(maxlen=100)
        }
        
    async def monitor_stream(self, messages, model):
        """Stream with detailed monitoring."""
        last_time = time.time()
        chunks_received = 0
        
        async for chunk in client.stream(messages, model):
            current_time = time.time()
            latency = current_time - last_time
            
            self.metrics["chunk_latencies"].append(latency)
            self.metrics["chunk_sizes"].append(len(chunk))
            self.metrics["timestamps"].append(current_time)
            
            chunks_received += 1
            
            # Real-time stats every 10 chunks
            if chunks_received % 10 == 0:
                self.print_stats()
            
            last_time = current_time
            yield chunk
    
    def print_stats(self):
        """Print current performance stats."""
        if self.metrics["chunk_latencies"]:
            avg_latency = sum(self.metrics["chunk_latencies"]) / len(self.metrics["chunk_latencies"])
            avg_size = sum(self.metrics["chunk_sizes"]) / len(self.metrics["chunk_sizes"])
            
            # Calculate throughput
            if len(self.metrics["timestamps"]) >= 2:
                duration = self.metrics["timestamps"][-1] - self.metrics["timestamps"][0]
                total_chars = sum(self.metrics["chunk_sizes"])
                throughput = total_chars / duration if duration > 0 else 0
                
                print(f"Avg latency: {avg_latency*1000:.1f}ms, "
                      f"Avg chunk: {avg_size:.0f} chars, "
                      f"Throughput: {throughput:.0f} chars/sec")
```

### Performance Dashboard

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

# Global monitor
monitor = StreamingMonitor()

@app.get("/stream/{model}")
async def stream_endpoint(model: str, prompt: str):
    """Stream with performance monitoring."""
    
    async def generate():
        async for chunk in monitor.monitor_stream(prompt, model):
            # Send chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        
        # Send final metrics
        stats = {
            "avg_latency_ms": sum(monitor.metrics["chunk_latencies"]) / len(monitor.metrics["chunk_latencies"]) * 1000,
            "total_chunks": len(monitor.metrics["chunk_sizes"]),
            "total_chars": sum(monitor.metrics["chunk_sizes"])
        }
        yield f"data: {json.dumps({'stats': stats})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )

@app.get("/metrics/streaming")
async def get_streaming_metrics():
    """Get current streaming performance metrics."""
    return {
        "recent_chunks": len(monitor.metrics["chunk_latencies"]),
        "avg_latency_ms": sum(monitor.metrics["chunk_latencies"]) / len(monitor.metrics["chunk_latencies"]) * 1000 if monitor.metrics["chunk_latencies"] else 0,
        "avg_chunk_size": sum(monitor.metrics["chunk_sizes"]) / len(monitor.metrics["chunk_sizes"]) if monitor.metrics["chunk_sizes"] else 0
    }
```

## Best Practices

1. **Choose the right model** - Faster models (gpt-3.5-turbo, claude-3-haiku) for lower TTFT
2. **Disable unused features** - Turn off JSON handler and tiktoken if not needed
3. **Process chunks immediately** - Don't buffer unless necessary
4. **Monitor performance** - Track TTFT, throughput, and latency
5. **Use appropriate timeouts** - Balance between reliability and responsiveness
6. **Implement fallbacks** - Have backup models for critical applications
7. **Batch when possible** - But not at the cost of user experience
8. **Profile your application** - Identify bottlenecks specific to your use case
9. **Consider infrastructure** - CDN, edge deployment for global applications
10. **Test under load** - Streaming behavior changes under concurrent load