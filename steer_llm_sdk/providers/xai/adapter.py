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


logger = ProviderLogger("xai")


class XAIProvider(ProviderAdapter):
    """xAI API provider with conversation support, using xai_sdk.AsyncClient"""
    
    def __init__(self):
        self._client: Optional[AsyncClient] = None
        self._api_key = os.getenv("XAI_API_KEY")
    
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
        with logger.track_request("generate", params.model) as request_info:
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
        with logger.track_request("stream", params.model) as request_info:
            # Initialize StreamAdapter
            adapter = StreamAdapter("xai")
            adapter.start_stream()
            
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
                
                # Create chat and stream response
                chat = await self.client.chat.create(**xai_params)
                
                # Handle potential coroutine from chat.stream()
                stream_iter = chat.stream()
                if inspect.iscoroutine(stream_iter):
                    stream_iter = await stream_iter
                    
                async for response, chunk in stream_iter:
                    # Use adapter for normalization - xAI returns tuple of (response, chunk)
                    delta = adapter.normalize_delta((response, chunk))
                    text = delta.get_text()
                    if text:
                        adapter.track_chunk(len(text))
                        yield text
                    
            except Exception as e:
                raise ErrorMapper.map_xai_error(e)
            finally:
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
        with logger.track_request("stream_with_usage", params.model) as request_info:
            # Initialize StreamAdapter
            adapter = StreamAdapter("xai")
            adapter.start_stream()
            
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
                
                # Create chat and stream response
                chat = await self.client.chat.create(**xai_params)
                
                collected_chunks = []
                finish_reason = None
                
                # Handle potential coroutine from chat.stream()
                stream_iter = chat.stream()
                if inspect.iscoroutine(stream_iter):
                    stream_iter = await stream_iter
                
                async for response, chunk in stream_iter:
                    # Use adapter for normalization - xAI returns tuple of (response, chunk)
                    delta = adapter.normalize_delta((response, chunk))
                    text = delta.get_text()
                    
                    if text:
                        adapter.track_chunk(len(text))
                        collected_chunks.append(text)
                        yield (text, None)
                    
                    # Check if response has finish reason
                    if hasattr(response, 'choices') and response.choices:
                        if hasattr(response.choices[0], 'finish_reason'):
                            finish_reason = response.choices[0].finish_reason
                
                # After streaming completes, estimate usage
                # Since xAI may not provide detailed usage, we estimate
                full_text = ''.join(collected_chunks)
                
                # Rough token estimation (4 chars per token on average)
                prompt_tokens = len(prompt_text) // 4
                completion_tokens = len(full_text) // 4
                
                usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "cache_info": {}  # xAI doesn't provide cache info
                }
                
                # Log usage
                logger.log_usage(usage, params.model, request_info['request_id'])
                
                # Yield final usage data
                yield (None, {
                    "usage": usage,
                    "model": params.model,
                    "provider": "xai",
                    "finish_reason": finish_reason or "stop",
                    "cost_usd": None,  # Cost calculation should be done in router/core
                    "cost_breakdown": None
                })
                
            except Exception as e:
                raise ErrorMapper.map_xai_error(e)
            finally:
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


# Global instance
xai_provider = XAIProvider()