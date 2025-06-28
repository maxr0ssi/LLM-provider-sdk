from typing import Any, AsyncGenerator, Dict, List, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..models.conversation_types import ConversationMessage
from ..models.generation import GenerationParams, GenerationResponse, ProviderType
from .providers.anthropic import anthropic_provider
from .providers.openai import openai_provider
from .providers.xai import xai_provider
from .registry import (
    calculate_cost,
    check_lightweight_availability,
    get_available_models,
    get_config,
    get_default_hyperparameters,
    normalize_params,
)

router = APIRouter()

class LLMRouter:
    """Router for LLM requests across different providers with conversation support."""
    
    def __init__(self):
        self.providers = {
            ProviderType.OPENAI: openai_provider,
            ProviderType.ANTHROPIC: anthropic_provider,
            ProviderType.XAI: xai_provider,
        }
    
    async def generate(self, 
                      messages: Union[str, List[ConversationMessage]], 
                      llm_model_id: str, 
                      raw_params: Dict[str, Any]) -> GenerationResponse:
        """Generate text using the appropriate provider with conversation support."""
        # Get model configuration
        config = get_config(llm_model_id)
        
        # Check availability
        if not check_lightweight_availability(llm_model_id):
            raise HTTPException(
                status_code=400, 
                detail=f"Model {llm_model_id} is not available"
            )
        
        # Normalize parameters
        params = normalize_params(raw_params, config)
        
        # Get provider
        provider = self.providers.get(config.provider)
        if not provider:
            raise HTTPException(
                status_code=500,
                detail=f"Provider {config.provider} not implemented"
            )
        
        # Generate response
        try:
            response = await provider.generate(messages, params)
            
            # Calculate cost if possible
            if config.cost_per_1k_tokens:
                response.cost_usd = calculate_cost(response.usage, config)
            
            return response
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Generation failed: {str(e)}"
            )
    
    async def generate_stream(self, 
                            messages: Union[str, List[ConversationMessage]], 
                            llm_model_id: str, 
                            raw_params: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Generate text with streaming using the appropriate provider with conversation support."""
        # Get model configuration
        config = get_config(llm_model_id)
        
        # Check availability
        if not check_lightweight_availability(llm_model_id):
            raise HTTPException(
                status_code=400, 
                detail=f"Model {llm_model_id} is not available"
            )
        
        # Normalize parameters
        params = normalize_params(raw_params, config)
        
        # Get provider
        provider = self.providers.get(config.provider)
        if not provider:
            raise HTTPException(
                status_code=500,
                detail=f"Provider {config.provider} not implemented"
            )
        
        # Generate streaming response
        try:
            async for chunk in provider.generate_stream(messages, params):
                yield chunk
                
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Streaming generation failed: {str(e)}"
            )
    
    def get_provider_status(self) -> Dict[str, bool]:
        """Get availability status of all providers."""
        return {
            provider_type.value: provider.is_available()
            for provider_type, provider in self.providers.items()
        }


# Global router instance
llm_router = LLMRouter()

# ===== FastAPI Endpoints =====

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
    llm_model_id: str ="GPT-4o Mini",
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

