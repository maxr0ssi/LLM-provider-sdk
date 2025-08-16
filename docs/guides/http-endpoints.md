# HTTP Endpoints Guide

This guide explains how to use the optional HTTP endpoints provided by the Steer LLM SDK.

## Installation

The HTTP endpoints require FastAPI, which is not included in the base SDK installation. Install with:

```bash
# Install SDK with HTTP support
pip install steer-llm-sdk[http]

# Or add to existing installation
pip install fastapi
```

## Quick Start

### Basic Usage

```python
from fastapi import FastAPI
from steer_llm_sdk.http.api import router as llm_router

# Create FastAPI app
app = FastAPI(title="LLM Service")

# Mount the LLM router
app.include_router(llm_router, prefix="/api/v1")

# Run with uvicorn
# uvicorn main:app --reload
```

### Available Endpoints

1. **POST /api/v1/generate** - Generate text (non-streaming)
2. **POST /api/v1/stream** - Stream text generation
3. **GET /api/v1/status** - Check provider status
4. **GET /api/v1/model-catalog** - List available models
5. **GET /api/v1/hyperparameters** - Get model defaults

## Error Handling

The HTTP layer automatically translates SDK errors to appropriate HTTP status codes:

| SDK Error | HTTP Status | Description |
|-----------|-------------|-------------|
| ProviderError | 500/503 | Provider-specific errors |
| ValidationError | 400 | Invalid request parameters |
| AuthenticationError | 401 | Missing or invalid API key |
| RateLimitError | 429 | Rate limit exceeded |
| NotFoundError | 404 | Model or resource not found |

### Custom Error Handling

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from steer_llm_sdk.providers.base import ProviderError

app = FastAPI()

@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError):
    # Custom error response
    return JSONResponse(
        status_code=exc.status_code or 500,
        content={
            "error": exc.__class__.__name__,
            "message": str(exc),
            "provider": exc.provider,
            "is_retryable": exc.is_retryable,
            "timestamp": time.time()
        }
    )
```

## Usage Examples

### Generate Text

```bash
curl -X POST "http://localhost:8000/api/v1/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a haiku about Python",
    "llm_model_id": "gpt-4",
    "params": {
      "temperature": 0.7,
      "max_tokens": 50
    }
  }'
```

Response:
```json
{
  "text": "Code flows like water\nIndented paths guide the way\nPython simplifies",
  "model": "gpt-4",
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 17,
    "total_tokens": 29
  },
  "cost_usd": 0.00145,
  "provider": "openai",
  "finish_reason": "stop"
}
```

### Stream Text

```python
import httpx
import asyncio

async def stream_example():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/api/v1/stream",
            json={
                "prompt": "Tell me a story",
                "llm_model_id": "gpt-4",
                "params": {"max_tokens": 100}
            }
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]  # Remove "data: " prefix
                    if chunk != "[DONE]":
                        print(chunk, end="", flush=True)

asyncio.run(stream_example())
```

### Check Model Availability

```bash
# Get all available models
curl "http://localhost:8000/api/v1/model-catalog"

# Get model defaults
curl "http://localhost:8000/api/v1/hyperparameters?llm_model_id=gpt-4"
```

## Advanced Configuration

### Authentication Middleware

```python
from fastapi import Depends, HTTPException, Header
from typing import Optional

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if not x_api_key or x_api_key != "your-secret-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# Apply to all LLM endpoints
app.include_router(
    llm_router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)]
)
```

### Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

# Apply rate limits
@app.post("/api/v1/generate")
@limiter.limit("10/minute")
async def generate_with_limit(request: Request, ...):
    # Forward to SDK
    pass
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

## Deployment Options

### Development

```bash
# Install with dev dependencies
pip install steer-llm-sdk[http]
pip install uvicorn

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production with Gunicorn

```bash
# Install production server
pip install gunicorn

# Run with multiple workers
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install SDK with HTTP support
RUN pip install steer-llm-sdk[http] uvicorn

# Copy your app
COPY main.py .

# Set environment variables
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
ENV ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

# Run the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Serverless (AWS Lambda)

```python
from mangum import Mangum
from fastapi import FastAPI
from steer_llm_sdk.http.api import router

app = FastAPI()
app.include_router(router, prefix="/api/v1")

# Lambda handler
handler = Mangum(app)
```

## Using SDK Without HTTP

The SDK can be used directly without any HTTP dependencies:

```python
# Pure Python usage - no FastAPI required
from steer_llm_sdk import SteerLLMClient

async def main():
    client = SteerLLMClient()
    response = await client.generate(
        "Hello, world!",
        model="gpt-4"
    )
    print(response.text)

# Works in notebooks, CLIs, batch jobs, etc.
```

## Performance Considerations

1. **Connection Pooling**: The SDK maintains connection pools for each provider
2. **Streaming**: Use streaming endpoints for real-time responses
3. **Timeouts**: Configure appropriate timeouts for your use case
4. **Workers**: Use multiple workers in production for better concurrency

## Monitoring and Observability

### Request Logging

```python
import logging
from fastapi import Request
import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    logging.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} "
        f"duration={duration:.3f}s"
    )
    return response
```

### Metrics Integration

```python
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

# Metrics
request_count = Counter(
    'llm_requests_total',
    'Total LLM requests',
    ['method', 'model', 'status']
)

request_duration = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration',
    ['method', 'model']
)

@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

## Troubleshooting

### Import Errors

If you see:
```
ImportError: FastAPI is required for HTTP endpoints.
```

Install with: `pip install steer-llm-sdk[http]`

### Provider Errors

Check:
1. API keys are set correctly
2. Model names are valid
3. Network connectivity
4. Rate limits

### Performance Issues

1. Enable connection pooling
2. Use streaming for long responses
3. Implement caching for repeated requests
4. Monitor memory usage with multiple workers

## Best Practices

1. **Security**: Always use authentication in production
2. **Error Handling**: Implement comprehensive error handling
3. **Monitoring**: Log all requests and track metrics
4. **Rate Limiting**: Protect your endpoints from abuse
5. **Documentation**: Keep your API documentation up to date
6. **Testing**: Test both SDK and HTTP layers separately