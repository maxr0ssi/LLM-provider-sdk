# FastAPI Separation Improvement Plan

## Current State

The FastAPI separation has been implemented successfully with:
- ✅ Core router free of HTTP concerns
- ✅ Optional HTTP module (`steer_llm_sdk/http/api.py`)
- ✅ FastAPI as optional dependency
- ✅ Basic error mapping

## Recommended Improvements

### 1. Enhanced Error Mapping

Create a comprehensive error translation layer:

```python
# steer_llm_sdk/http/errors.py
from typing import Dict, Type
from fastapi import HTTPException
from steer_llm_sdk.providers.base import ProviderError

class HTTPErrorMapper:
    """Maps SDK errors to HTTP responses."""
    
    ERROR_MAPPING: Dict[Type[Exception], int] = {
        # Provider errors
        ProviderError: 500,
        
        # Specific error types (when implemented)
        # ValidationError: 400,
        # AuthenticationError: 401,
        # RateLimitError: 429,
        # NotFoundError: 404,
        # TimeoutError: 504,
    }
    
    @classmethod
    def to_http_exception(cls, error: Exception) -> HTTPException:
        """Convert SDK error to HTTP exception."""
        # Handle ProviderError specially
        if isinstance(error, ProviderError):
            status_code = error.status_code or 500
            if error.is_retryable:
                status_code = 503  # Service Unavailable for retryable errors
            
            return HTTPException(
                status_code=status_code,
                detail={
                    "error": error.__class__.__name__,
                    "message": str(error),
                    "provider": error.provider,
                    "is_retryable": error.is_retryable
                }
            )
        
        # Default mapping
        status_code = cls.ERROR_MAPPING.get(type(error), 500)
        return HTTPException(
            status_code=status_code,
            detail={
                "error": error.__class__.__name__,
                "message": str(error)
            }
        )
```

### 2. Request/Response Models

Add Pydantic models for API contracts:

```python
# steer_llm_sdk/http/models.py
from pydantic import BaseModel
from typing import Optional, Dict, Any

class GenerateRequest(BaseModel):
    prompt: str
    llm_model_id: str = "GPT-4o Mini"
    params: Optional[Dict[str, Any]] = None

class GenerateResponse(BaseModel):
    text: str
    model: str
    usage: Dict[str, Any]
    cost_usd: Optional[float] = None
    provider: str
    finish_reason: Optional[str] = None

class StreamRequest(BaseModel):
    prompt: str
    llm_model_id: str = "GPT-4o Mini"
    params: Optional[Dict[str, Any]] = None
    
class ErrorResponse(BaseModel):
    error: str
    message: str
    provider: Optional[str] = None
    is_retryable: Optional[bool] = None
    timestamp: float
```

### 3. Middleware for Consistency

Add middleware for logging, metrics, and error handling:

```python
# steer_llm_sdk/http/middleware.py
from fastapi import Request
import time
import logging

logger = logging.getLogger(__name__)

async def request_logging_middleware(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    duration = time.time() - start_time
    logger.info(
        f"Response: {request.method} {request.url.path} "
        f"status={response.status_code} duration={duration:.3f}s"
    )
    
    # Add timing header
    response.headers["X-Process-Time"] = str(duration)
    
    return response
```

### 4. OpenAPI Documentation

Enhance API documentation:

```python
# In steer_llm_sdk/http/api.py
from fastapi import APIRouter
from .models import GenerateRequest, GenerateResponse, ErrorResponse

router = APIRouter(
    tags=["LLM"],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    }
)

@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Generate text",
    description="Generate text using specified LLM model"
)
async def llm_generate(request: GenerateRequest):
    """Generate text with full request/response models."""
    # Implementation
```

### 5. Testing Improvements

Add HTTP-specific tests:

```python
# tests/http/test_api.py
import pytest
from fastapi.testclient import TestClient
from steer_llm_sdk.http.api import router

@pytest.fixture
def client():
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

def test_generate_endpoint(client, mock_llm_router):
    response = client.post(
        "/generate",
        json={
            "prompt": "Hello",
            "llm_model_id": "gpt-4"
        }
    )
    assert response.status_code == 200
    assert "text" in response.json()

def test_error_mapping(client, mock_llm_router):
    # Test ProviderError mapping
    mock_llm_router.generate.side_effect = ProviderError(
        "Test error",
        provider="test",
        status_code=429,
        is_retryable=True
    )
    
    response = client.post("/generate", json={"prompt": "test"})
    assert response.status_code == 429
    assert response.json()["is_retryable"] is True
```

### 6. Configuration Module

Add HTTP-specific configuration:

```python
# steer_llm_sdk/http/config.py
from pydantic import BaseSettings

class HTTPSettings(BaseSettings):
    """HTTP API configuration."""
    
    # API settings
    api_prefix: str = "/api/v1"
    enable_cors: bool = True
    cors_origins: list = ["*"]
    
    # Rate limiting
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60
    
    # Timeouts
    request_timeout: int = 300  # 5 minutes
    
    # Documentation
    docs_enabled: bool = True
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    
    class Config:
        env_prefix = "STEER_HTTP_"
```

### 7. Usage Examples

Add example applications:

```python
# examples/http_server.py
"""Example HTTP server using Steer LLM SDK."""

from fastapi import FastAPI
from steer_llm_sdk.http.api import router as llm_router
from steer_llm_sdk.http.middleware import request_logging_middleware

# Create app
app = FastAPI(
    title="LLM API Service",
    description="HTTP API for Steer LLM SDK",
    version="1.0.0"
)

# Add middleware
app.middleware("http")(request_logging_middleware)

# Mount LLM routes
app.include_router(llm_router, prefix="/api/v1")

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Implementation Priority

1. **High Priority**
   - Enhanced error mapping
   - Request/response models
   - Basic tests

2. **Medium Priority**
   - Middleware
   - Configuration module
   - Documentation

3. **Low Priority**
   - Additional examples
   - Performance optimizations
   - Advanced features

## Benefits

1. **Better Error Handling**: Consistent, informative error responses
2. **Type Safety**: Pydantic models for validation
3. **Documentation**: Auto-generated OpenAPI docs
4. **Testability**: Isolated HTTP tests
5. **Configurability**: Environment-based configuration
6. **Observability**: Built-in logging and metrics

## Migration Path

1. These improvements are additive - no breaking changes
2. Existing endpoints continue to work
3. New features can be adopted gradually
4. Documentation guides the transition

## Conclusion

While the FastAPI separation is functionally complete, these improvements would enhance the developer experience and make the HTTP layer more robust and production-ready. The modular approach allows teams to adopt only the features they need.