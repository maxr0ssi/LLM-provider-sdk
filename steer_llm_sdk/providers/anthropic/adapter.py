import os
from typing import Dict, Any, AsyncGenerator, Optional, List, Tuple, Union
from dotenv import load_dotenv
import anthropic
from anthropic import AsyncAnthropic

# Load environment variables
load_dotenv()

from ..base import ProviderAdapter, ProviderError
from ..errors import ErrorMapper
from ...models.generation import GenerationParams, GenerationResponse
from ...models.conversation_types import ConversationMessage
from ...core.capabilities import (
    get_capabilities_for_model,
    get_cache_control_config,
    supports_prompt_caching
)
from ...core.normalization.params import normalize_params, transform_messages_for_provider
from ...core.normalization.usage import normalize_usage
from ...observability.logging import ProviderLogger
from ...streaming import StreamAdapter
from .parsers import extract_text_from_messages_response
from .payloads import assemble_messages_params, apply_system_cache_control
from .streaming import stream_messages, stream_messages_with_usage


logger = ProviderLogger("anthropic")


class AnthropicProvider(ProviderAdapter):
    """Anthropic Claude API provider with conversation support."""
    
    def __init__(self):
        self._client: Optional[AsyncAnthropic] = None
        self._api_key = os.getenv("ANTHROPIC_API_KEY")
    
    @property
    def client(self) -> AsyncAnthropic:
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            if not self._api_key:
                raise Exception("Anthropic API key not found in environment variables")
            # Initialize without any extra parameters to avoid compatibility issues
            try:
                self._client = AsyncAnthropic(api_key=self._api_key)
            except TypeError:
                # Fallback for older versions
                self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client
    
    async def generate(self, 
                      messages: Union[str, List[ConversationMessage]], 
                      params: GenerationParams) -> GenerationResponse:
        """Generate text using Anthropic API with conversation support."""
        # Extract request_id from raw_params if available
        request_id = params.raw_params.get('request_id') if params.raw_params else None
        
        with logger.track_request("generate", params.model, request_id=request_id) as request_info:
            try:
                # Handle backward compatibility - convert string prompt to messages
                if isinstance(messages, str):
                    formatted_messages = [{"role": "user", "content": messages}]
                    system_message = None
                else:
                    system_message = None
                    formatted_messages = []
                    for msg in messages:
                        if msg.role == "system":
                            system_message = msg.content
                        else:
                            formatted_messages.append({"role": msg.role, "content": msg.content})

                # Normalize params
                caps = get_capabilities_for_model(params.model)
                anthropic_params = normalize_params(params, params.model, "anthropic", caps)

                # Transform messages and assemble
                all_messages = [{"role": "system", "content": system_message}] if system_message else []
                all_messages.extend(formatted_messages)
                transformed = transform_messages_for_provider(all_messages, "anthropic")
                anthropic_params = assemble_messages_params(anthropic_params, transformed)

                # Apply cache_control for long system messages via helper
                anthropic_params = apply_system_cache_control(caps, anthropic_params, system_message)

                # Call API
                response = await self.client.messages.create(**anthropic_params)

                # Parse text
                text_content = extract_text_from_messages_response(response)

                # Usage normalization
                usage_dict = None
                if hasattr(response, 'usage'):
                    try:
                        usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else response.usage.__dict__
                    except Exception:
                        usage_dict = {}
                usage = normalize_usage(usage_dict, "anthropic")
                if usage:
                    logger.log_usage(usage, params.model, request_info['request_id'])

                return GenerationResponse(
                    text=text_content,
                    model=params.model,
                    usage=usage,
                    provider="anthropic",
                    finish_reason=getattr(response, 'stop_reason', None)
                )

            except Exception as e:
                raise ErrorMapper.map_anthropic_error(e)
    
    async def generate_stream(self, 
                            messages: Union[str, List[ConversationMessage]], 
                            params: GenerationParams) -> AsyncGenerator[str, None]:
        """Generate text using Anthropic API with streaming and conversation support."""
        # Extract request_id from raw_params if available
        request_id = params.raw_params.get('request_id') if params.raw_params else None
        
        with logger.track_request("stream", params.model, request_id=request_id) as request_info:
            # Initialize StreamAdapter
            adapter = StreamAdapter("anthropic", params.model)
            
            # Configure streaming options if provided
            # In Pydantic v2, extra fields are in model_extra
            extra_params = getattr(params, 'model_extra', {}) or getattr(params, 'kwargs', {})
            streaming_options = extra_params.get("streaming_options")
            if streaming_options:
                # Configure event processor
                if hasattr(streaming_options, "event_processor") and streaming_options.event_processor:
                    adapter.set_event_processor(streaming_options.event_processor, request_info.get('request_id'))
                
                # Configure JSON handler if response format is JSON
                response_format = params.response_format or {}
                if (hasattr(streaming_options, "enable_json_stream_handler") and 
                    streaming_options.enable_json_stream_handler and 
                    response_format.get("type") == "json_object"):
                    adapter.set_response_format(response_format, enable_json_handler=True)
                
                # Configure usage aggregation if needed
                if (hasattr(streaming_options, "enable_usage_aggregation") and 
                    streaming_options.enable_usage_aggregation):
                    # Anthropic provides usage data, but we can still enable if requested
                    aggregator_type = getattr(streaming_options, "aggregator_type", "auto")
                    adapter.configure_usage_aggregation(aggregator_type, messages)
            
            await adapter.start_stream()
            
            try:
                # Handle backward compatibility - convert string prompt to messages
                if isinstance(messages, str):
                    formatted_messages = [{"role": "user", "content": messages}]
                    system_message = None
                else:
                    # Extract system message and convert to Anthropic format
                    system_message = None
                    formatted_messages = []
                    for msg in messages:
                        if msg.role == "system":
                            system_message = msg.content
                        else:
                            formatted_messages.append({
                                "role": msg.role,
                                "content": msg.content
                            })
                
                # Use normalization function to prepare parameters
                caps = get_capabilities_for_model(params.model)
                anthropic_params = normalize_params(params, params.model, "anthropic", caps)
                anthropic_params["stream"] = True

                # Compose prompt text for fallback usage estimation when provider omits tokens
                try:
                    prompt_text_estimate = []
                    if system_message:
                        prompt_text_estimate.append(system_message)
                    for m in formatted_messages:
                        content = m.get("content")
                        if isinstance(content, str):
                            prompt_text_estimate.append(content)
                    prompt_text_estimate = " ".join(prompt_text_estimate)
                except Exception:
                    prompt_text_estimate = ""
                
                # Transform messages for Anthropic and assemble
                all_messages = [{"role": "system", "content": system_message}] if system_message else []
                all_messages.extend(formatted_messages)
                transformed = transform_messages_for_provider(all_messages, "anthropic")
                anthropic_params = assemble_messages_params(anthropic_params, transformed)
                
                # Compose prompt text estimate for fallback usage calculation
                try:
                    prompt_text_estimate = []
                    if system_message:
                        prompt_text_estimate.append(system_message)
                    for m in formatted_messages:
                        content = m.get("content")
                        if isinstance(content, str):
                            prompt_text_estimate.append(content)
                    prompt_text_estimate = " ".join(prompt_text_estimate)
                except Exception:
                    prompt_text_estimate = ""

                # Apply cache_control for long system messages via helper
                anthropic_params = apply_system_cache_control(caps, anthropic_params, system_message)

                # Make streaming API call via helper
                async for chunk in stream_messages(self.client, anthropic_params, adapter):
                    yield chunk
                
            except Exception as e:
                await adapter.complete_stream(error=e)
                raise ErrorMapper.map_anthropic_error(e)
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
    
    async def generate_stream_with_usage(self, 
                                       messages: Union[str, List[ConversationMessage]], 
                                       params: GenerationParams) -> AsyncGenerator[tuple, None]:
        """Generate text using Anthropic API with streaming and usage data.
        
        Yields tuples of (chunk, usage_data) where usage_data is None except
        for the final yield which contains the complete usage information.
        """
        # Extract request_id from raw_params if available
        request_id = params.raw_params.get('request_id') if params.raw_params else None
        
        with logger.track_request("stream_with_usage", params.model, request_id=request_id) as request_info:
            # Initialize StreamAdapter
            adapter = StreamAdapter("anthropic", params.model)
            
            # Configure streaming options if provided
            # In Pydantic v2, extra fields are in model_extra
            extra_params = getattr(params, 'model_extra', {}) or getattr(params, 'kwargs', {})
            streaming_options = extra_params.get("streaming_options")
            if streaming_options:
                # Configure event processor
                if hasattr(streaming_options, "event_processor") and streaming_options.event_processor:
                    adapter.set_event_processor(streaming_options.event_processor, request_info.get('request_id'))
                
                # Configure JSON handler if response format is JSON
                response_format = params.response_format or {}
                if (hasattr(streaming_options, "enable_json_stream_handler") and 
                    streaming_options.enable_json_stream_handler and 
                    response_format.get("type") == "json_object"):
                    adapter.set_response_format(response_format, enable_json_handler=True)
                
                # Configure usage aggregation if needed
                if (hasattr(streaming_options, "enable_usage_aggregation") and 
                    streaming_options.enable_usage_aggregation):
                    # Anthropic provides usage data, but we can still enable if requested
                    aggregator_type = getattr(streaming_options, "aggregator_type", "auto")
                    adapter.configure_usage_aggregation(aggregator_type, messages)
            
            await adapter.start_stream()
            
            try:
                # Handle backward compatibility - convert string prompt to messages
                if isinstance(messages, str):
                    formatted_messages = [{"role": "user", "content": messages}]
                    system_message = None
                else:
                    # Extract system message and convert to Anthropic format
                    system_message = None
                    formatted_messages = []
                    for msg in messages:
                        # Handle both ConversationMessage objects and plain dicts
                        if hasattr(msg, 'role'):
                            role = msg.role
                            content = msg.content
                        elif isinstance(msg, dict):
                            role = msg.get('role')
                            content = msg.get('content')
                        else:
                            raise ValueError(f"Invalid message format: {type(msg)} - {msg}")
                        
                        if role == "system":
                            system_message = content
                        else:
                            formatted_messages.append({
                                "role": role,
                                "content": content
                            })
                
                # Use normalization function to prepare parameters
                caps = get_capabilities_for_model(params.model)
                anthropic_params = normalize_params(params, params.model, "anthropic", caps)
                anthropic_params["stream"] = True
                
                # Transform messages for Anthropic format (ensure messages field is present)
                all_messages = [{"role": "system", "content": system_message}] if system_message else []
                all_messages.extend(formatted_messages)
                transformed = transform_messages_for_provider(all_messages, "anthropic")

                if isinstance(transformed, dict):
                    anthropic_params.update(transformed)
                    # Drop system if None to satisfy SDK validators
                    if anthropic_params.get("system") is None:
                        anthropic_params.pop("system", None)
                else:
                    anthropic_params["messages"] = transformed

                # Get capabilities for caching check
                caps = get_capabilities_for_model(params.model)
                
                # Add system message with cache_control (helper applies threshold)
                anthropic_params = apply_system_cache_control(caps, anthropic_params, system_message)
                
                if params.stop:
                    anthropic_params["stop_sequences"] = params.stop
                
                # Compose prompt text estimate for fallback usage calculation
                try:
                    prompt_text_estimate = []
                    if system_message:
                        prompt_text_estimate.append(system_message)
                    for m in formatted_messages:
                        content = m.get("content")
                        if isinstance(content, str):
                            prompt_text_estimate.append(content)
                    prompt_text_estimate = " ".join(prompt_text_estimate)
                except Exception:
                    prompt_text_estimate = ""

                # Make streaming API call
                stream = await self.client.messages.create(**anthropic_params)
                
                collected_chunks = []
                finish_reason = None
                usage_data = None
                
                async for event in stream:
                    # Use adapter for normalization
                    delta = adapter.normalize_delta(event)
                    text = delta.get_text()
                    
                    if text:
                        await adapter.track_chunk(len(text), text)
                        collected_chunks.append(text)
                        yield (text, None)
                    
                    # Handle non-content events
                    if event.type == "message_delta":
                        # Capture usage data from message_delta event
                        if hasattr(event, 'usage'):
                            usage_data = event.usage
                        if hasattr(event.delta, 'stop_reason'):
                            finish_reason = event.delta.stop_reason
                    
                    # Check if this event contains final usage data
                    elif adapter.should_emit_usage(event):
                        # Final event - process usage data
                        if usage_data:
                            # Extract usage information
                            usage_dict = usage_data.model_dump() if hasattr(usage_data, 'model_dump') else usage_data.__dict__
                            
                            # Check for cache information
                            cache_info = {}
                            if hasattr(usage_data, 'cache_creation_input_tokens'):
                                cache_creation = usage_data.cache_creation_input_tokens
                                cache_info["cache_creation_input_tokens"] = cache_creation
                                try:
                                    # Convert to int and check if positive
                                    cache_creation_int = int(cache_creation) if cache_creation is not None else 0
                                    if cache_creation_int > 0:
                                        logger.debug("Anthropic cache creation: %s tokens", cache_creation_int)
                                except (TypeError, ValueError):
                                    # Handle MagicMock or other non-numeric values
                                    pass
                            
                            if hasattr(usage_data, 'cache_read_input_tokens'):
                                cache_read = usage_data.cache_read_input_tokens
                                cache_info["cache_read_input_tokens"] = cache_read
                                try:
                                    # Convert to int and check if positive
                                    cache_read_int = int(cache_read) if cache_read is not None else 0
                                    if cache_read_int > 0:
                                        logger.debug("Anthropic cache hit: %s tokens", cache_read_int)
                                except (TypeError, ValueError):
                                    # Handle MagicMock or other non-numeric values
                                    pass
                            
                            # Guard for None values; estimate when provider omits tokens
                            def _estimate_tokens(text: str) -> int:
                                try:
                                    return max(1, int(len(text) / 4)) if text else 0
                                except Exception:
                                    return 0

                            try:
                                prompt_tokens = int(getattr(usage_data, 'input_tokens', 0) or 0)
                            except Exception:
                                prompt_tokens = 0
                            try:
                                completion_tokens = int(getattr(usage_data, 'output_tokens', 0) or 0)
                            except Exception:
                                completion_tokens = 0

                            if prompt_tokens <= 0:
                                prompt_tokens = _estimate_tokens(prompt_text_estimate)
                            if completion_tokens <= 0:
                                completion_text = ''.join(collected_chunks)
                                completion_tokens = _estimate_tokens(completion_text)
                            usage = {
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": prompt_tokens + completion_tokens,
                                "cache_info": cache_info
                            }
                            
                            # Log usage
                            logger.log_usage(usage, params.model, request_info['request_id'])
                            
                            # Get final JSON if JSON handler was used
                            final_json = None
                            if adapter.json_handler:
                                final_json = adapter.get_final_json()
                            
                            # Yield final usage data
                            yield (None, {
                                "usage": usage,
                                "model": params.model,
                                "provider": "anthropic",
                                "finish_reason": finish_reason,
                                "cost_usd": None,  # Cost calculation should be done in router/core
                                "cost_breakdown": None,
                                "final_json": final_json  # Include final JSON if available
                            })
                    
            except Exception as e:
                await adapter.complete_stream(error=e)
                raise ErrorMapper.map_anthropic_error(e)
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
        """Check if Anthropic API is available."""
        return bool(self._api_key)


# Global instance
anthropic_provider = AnthropicProvider()
