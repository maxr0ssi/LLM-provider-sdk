import os
import inspect
from typing import Dict, Any, AsyncGenerator, Optional, List, Tuple, Union
from dotenv import load_dotenv
import xai_sdk
from xai_sdk import AsyncClient

# Load environment variables
load_dotenv()
from xai_sdk.chat import system, user, assistant

from ..base import ProviderAdapter, ProviderError
from ..errors import ErrorMapper
from ...models.generation import GenerationParams, GenerationResponse
from ...models.conversation_types import ConversationMessage
from ...core.capabilities import get_capabilities_for_model
from ...core.normalization.params import normalize_params
from ...core.normalization.usage import normalize_usage
from ...observability.logging import ProviderLogger
from ...streaming import StreamAdapter
from .streaming import stream_chat, stream_chat_with_usage


logger = ProviderLogger("xai")


class XAIProvider(ProviderAdapter):
    """xAI API provider with conversation support, using xai_sdk.AsyncClient"""
    
    def __init__(self, api_key: Optional[str] = None):
        self._client: Optional[AsyncClient] = None
        # Use provided API key, fall back to environment variable
        self._api_key = api_key or os.getenv("XAI_API_KEY")
    
    @property
    def client(self) -> AsyncClient:
        """Lazy initialization of xAI client."""
        if self._client is None:
            if not self._api_key:
                raise Exception("xAI API key not found in environment variables")
            self._client = AsyncClient(api_key=self._api_key)
        return self._client
    
    async def generate(
        self,
        messages: Union[str, List[ConversationMessage]],
        params: GenerationParams
    ) -> GenerationResponse:
        """Generate text using xAI API with conversation support."""
        # Extract request_id from metadata if available
        request_id = params.metadata.get('request_id') if params.metadata else None
        
        with logger.track_request("generate", params.model, request_id=request_id) as request_info:
            try:
                # Format messages for xAI chat
                if isinstance(messages, str):
                    formatted = [user(messages)]
                else:
                    formatted = []
                    for msg in messages:
                        if msg.role == "system":
                            formatted.append(system(msg.content))
                        elif msg.role == "user":
                            formatted.append(user(msg.content))
                        elif msg.role == "assistant":
                            formatted.append(assistant(msg.content))
                
                # Use normalization function to prepare parameters
                caps = get_capabilities_for_model(params.model)
                xai_params = normalize_params(params, params.model, "xai", caps)
                
                # Add messages to parameters
                xai_params["messages"] = formatted
                
                # Create chat and sample response
                chat = await self.client.chat.create(**xai_params)
                response = await chat.sample()
                
                # Extract usage with normalization (xAI may not provide usage data)
                usage_dict = None
                if hasattr(response, 'usage'):
                    try:
                        usage_dict = response.usage if isinstance(response.usage, dict) else {}
                    except Exception:
                        usage_dict = None
                
                usage = normalize_usage(usage_dict, "xai")
                
                # Log usage if available
                if usage:
                    logger.log_usage(usage, params.model, request_info['request_id'])
                
                return GenerationResponse(
                    text=response.content,
                    model=params.model,
                    usage=usage,
                    provider="xai",
                    finish_reason=getattr(response, "finish_reason", None)
                )
            except Exception as e:
                raise ErrorMapper.map_xai_error(e)
    
    async def generate_stream(
        self,
        messages: Union[str, List[ConversationMessage]],
        params: GenerationParams
    ) -> AsyncGenerator[str, None]:
        """Generate text using xAI API with streaming support."""
        # Extract request_id from metadata if available
        request_id = params.metadata.get('request_id') if params.metadata else None
        
        with logger.track_request("stream", params.model, request_id=request_id) as request_info:
            # Initialize StreamAdapter with model
            adapter = StreamAdapter("xai", params.model)
            
            # Configure event processor from streaming options if provided
            # In Pydantic v2, extra fields are in model_extra
            extra_params = getattr(params, 'model_extra', {}) or getattr(params, 'kwargs', {})
            streaming_options = extra_params.get("streaming_options")
            if streaming_options and hasattr(streaming_options, "event_processor") and streaming_options.event_processor:
                adapter.set_event_processor(streaming_options.event_processor, request_info.get('request_id'))
            
            await adapter.start_stream()
            
            try:
                # Format messages for xAI chat
                if isinstance(messages, str):
                    formatted = [user(messages)]
                else:
                    formatted = []
                    for msg in messages:
                        if msg.role == "system":
                            formatted.append(system(msg.content))
                        elif msg.role == "user":
                            formatted.append(user(msg.content))
                        elif msg.role == "assistant":
                            formatted.append(assistant(msg.content))
                
                # Use normalization function to prepare parameters
                caps = get_capabilities_for_model(params.model)
                xai_params = normalize_params(params, params.model, "xai", caps)
                
                # Add messages to parameters
                xai_params["messages"] = formatted
                
                # Create chat and stream response using helper
                chat = await self.client.chat.create(**xai_params)
                async for text in stream_chat(chat, adapter):
                    yield text
                    
            except Exception as e:
                await adapter.complete_stream(error=e)
                raise ErrorMapper.map_xai_error(e)
            finally:
                # Complete stream if not already done
                if not adapter._stream_completed:
                    await adapter.complete_stream()
                
                # Log streaming metrics
                metrics = adapter.get_metrics()
                logger.debug(
                    "Streaming metrics",
                    model=params.model,
                    request_id=request_info['request_id'],
                    chunks=metrics['chunks'],
                    total_chars=metrics['total_chars'],
                    duration_ms=int(metrics['duration_seconds'] * 1000),
                    chunks_per_second=metrics['chunks_per_second']
                )
    
    async def generate_stream_with_usage(
        self,
        messages: Union[str, List[ConversationMessage]],
        params: GenerationParams
    ) -> AsyncGenerator[tuple, None]:
        """Generate text using xAI API with streaming and usage data.
        
        Note: xAI's streaming API may not provide usage data in the same way as OpenAI/Anthropic.
        This implementation collects chunks and estimates usage based on the response.
        """
        # Extract request_id from metadata if available
        request_id = params.metadata.get('request_id') if params.metadata else None
        
        with logger.track_request("stream_with_usage", params.model, request_id=request_id) as request_info:
            # Initialize StreamAdapter with model for aggregation
            adapter = StreamAdapter("xai", params.model)
            
            # Configure event processor from streaming options if provided
            # In Pydantic v2, extra fields are in model_extra
            extra_params = getattr(params, 'model_extra', {}) or getattr(params, 'kwargs', {})
            streaming_options = extra_params.get("streaming_options")
            if streaming_options and hasattr(streaming_options, "event_processor") and streaming_options.event_processor:
                adapter.set_event_processor(streaming_options.event_processor, request_info.get('request_id'))
            
            await adapter.start_stream()
            
            # Configure usage aggregation for xAI (no native streaming usage)
            # Get streaming options from model_extra (Pydantic v2) or extra_params
            extra_params = getattr(params, 'model_extra', {}) or getattr(params, 'extra_params', {}) or {}
            streaming_options = extra_params.get("streaming_options")
            if streaming_options:
                from ...models.streaming import StreamingOptions
                if isinstance(streaming_options, StreamingOptions):
                    adapter.configure_usage_aggregation(
                        enable=streaming_options.enable_usage_aggregation,
                        messages=messages,
                        aggregator_type=streaming_options.aggregator_type,
                        prefer_tiktoken=streaming_options.prefer_tiktoken
                    )
                else:
                    # Default: enable aggregation for xAI
                    adapter.configure_usage_aggregation(
                        enable=True,
                        messages=messages
                    )
            else:
                # Default: enable aggregation for xAI since it has no native usage
                adapter.configure_usage_aggregation(
                    enable=True,
                    messages=messages
                )
            
            try:
                # Format messages for xAI chat
                if isinstance(messages, str):
                    formatted = [user(messages)]
                    prompt_text = messages
                else:
                    formatted = []
                    prompt_parts = []
                    for msg in messages:
                        # Handle both ConversationMessage objects and plain dicts
                        if hasattr(msg, 'role') and hasattr(msg, 'content'):
                            role = msg.role
                            content = msg.content
                        elif isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                            role = msg["role"]
                            content = msg["content"]
                        else:
                            raise ValueError(f"Invalid message format: {type(msg)} - {msg}")
                        
                        prompt_parts.append(content)
                        
                        if role == "system":
                            formatted.append(system(content))
                        elif role == "user":
                            formatted.append(user(content))
                        elif role == "assistant":
                            formatted.append(assistant(content))
                
                    prompt_text = ' '.join(prompt_parts)
                
                # Use normalization function to prepare parameters
                caps = get_capabilities_for_model(params.model)
                xai_params = normalize_params(params, params.model, "xai", caps)
                
                # Add messages to parameters
                xai_params["messages"] = formatted
                
                # Create chat and stream response using helper
                chat = await self.client.chat.create(**xai_params)
                async for item in stream_chat_with_usage(chat, adapter, prompt_text):
                    if isinstance(item, tuple) and item[0] is None and item[1] is not None:
                        usage = item[1]["usage"]
                        logger.log_usage(usage, params.model, request_info['request_id'])
                        
                        # Get final JSON if JSON handler was used
                        final_json = None
                        if adapter.json_handler:
                            final_json = adapter.get_final_json()
                        
                        yield (None, {
                            "usage": usage,
                            "model": params.model,
                            "provider": "xai",
                            "finish_reason": item[1].get("finish_reason"),
                            "cost_usd": None,
                            "cost_breakdown": None,
                            "final_json": final_json  # Include final JSON if available
                        })
                    else:
                        yield item
                
            except Exception as e:
                await adapter.complete_stream(error=e)
                raise ErrorMapper.map_xai_error(e)
            finally:
                # Complete stream if not already done
                if not adapter._stream_completed:
                    await adapter.complete_stream()
                
                # Log streaming metrics
                metrics = adapter.get_metrics()
                logger.debug(
                    "Streaming metrics (with usage)",
                    model=params.model,
                    request_id=request_info['request_id'],
                    chunks=metrics['chunks'],
                    total_chars=metrics['total_chars'],
                    duration_ms=int(metrics['duration_seconds'] * 1000)
                )
    
    def is_available(self) -> bool:
        """Check if xAI API is available."""
        return bool(self._api_key)


# Global instance removed - providers should be created with API keys