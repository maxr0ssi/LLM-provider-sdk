"""FastAPI HTTP endpoints for Steer LLM SDK.

This module provides REST API endpoints for the SDK functionality.
It requires FastAPI to be installed (via the 'http' extra).
"""

from typing import Any, Dict

try:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import StreamingResponse
except ImportError:
    raise ImportError(
        "FastAPI is required for HTTP endpoints. "
        "Please install with: pip install steer-llm-sdk[http]"
    )

from ..core.routing.router import LLMRouter
from ..core.routing import get_config, get_available_models, get_default_hyperparameters
from ..providers.base import ProviderError


# Create router instance
router = APIRouter()

# Global LLM router instance
llm_router = LLMRouter()


@router.post("/generate")
async def llm_generate(
    prompt: str,
    llm_model_id: str = "GPT-4o Mini",
    params: Dict[str, Any] = None
):
    """Direct LLM generation endpoint (for testing) - backward compatible."""
    try:
        if params is None:
            params = {}
        
        response = await llm_router.generate(prompt, llm_model_id, params)
        return response
    except ProviderError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def llm_status():
    """Get status of all LLM providers."""
    try:
        status = llm_router.get_provider_status()
        return {"providers": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def llm_stream(
    prompt: str,
    llm_model_id: str = "GPT-4o Mini",
    params: Dict[str, Any] = None
):
    """Stream LLM generation (for future real-time chat) - backward compatible."""
    try:
        if params is None:
            params = {}
        
        async def generate_stream():
            async for chunk in llm_router.generate_stream(prompt, llm_model_id, params):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache"}
        )
    except ProviderError as e:
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model-catalog")
async def model_catalog():
    """Return all enabled LLM model configurations."""
    return get_available_models()


@router.get("/hyperparameters")
async def get_model_hyperparameters(llm_model_id: str = None):
    """Get default hyperparameters for a specific model or provider."""
    try:
        if llm_model_id:
            # Get hyperparameters for specific model
            config = get_config(llm_model_id)
            hyperparams = get_default_hyperparameters(config.provider)
            return {
                "llm_model_id": llm_model_id,
                "provider": config.provider,
                "hyperparameters": hyperparams
            }
        else:
            # Return hyperparameters for all providers
            from config.models import PROVIDER_HYPERPARAMETERS
            return {
                "default": get_default_hyperparameters(),
                "by_provider": PROVIDER_HYPERPARAMETERS
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reliability/metrics")
async def get_reliability_metrics():
    """Get reliability metrics including retry and circuit breaker stats."""
    try:
        return {
            "retry_metrics": llm_router.get_retry_metrics(),
            "circuit_breakers": llm_router.circuit_manager.get_all_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))