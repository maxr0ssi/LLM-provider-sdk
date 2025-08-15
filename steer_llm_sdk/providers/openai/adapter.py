import json
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import openai
from dotenv import load_dotenv
from openai import AsyncOpenAI

from ..base import ProviderAdapter, ProviderError
from ..errors import ErrorMapper
from ...models.conversation_types import ConversationMessage
from ...models.generation import GenerationParams, GenerationResponse
from ...core.capabilities import (
    get_capabilities_for_model,
    format_responses_api_schema,
    get_cache_control_config,
    supports_prompt_caching
)
from ...core.normalization.params import normalize_params, transform_messages_for_provider, should_use_responses_api
from ...core.normalization.usage import normalize_usage
from ...observability.logging import ProviderLogger
from ...streaming import StreamAdapter
from .payloads import build_responses_api_payload, apply_prompt_cache_control
from .parsers import extract_text_from_responses_api
from .streaming import stream_responses_api, stream_responses_api_with_usage

logger = ProviderLogger("openai")

# Load environment variables
load_dotenv()

class OpenAIProvider(ProviderAdapter):
    """OpenAI API provider with conversation support."""
    
    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._api_key = os.getenv("OPENAI_API_KEY")
        # Allow overriding default timeout via env variable (seconds)
        try:
            self._timeout: float = float(os.getenv("OPENAI_TIMEOUT", "60"))
        except ValueError:
            self._timeout = 60.0
    
    @property
    def client(self) -> AsyncOpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            if not self._api_key:
                raise Exception("OpenAI API key not found in environment variables")
            # Apply timeout to all requests through this client
            self._client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout)
        return self._client
    
    def _build_responses_api_payload(self, params: GenerationParams, openai_params: dict, 
                                   transformed_messages: Any, text_config: Optional[dict] = None) -> dict:
        return build_responses_api_payload(params, openai_params, transformed_messages, text_config)
    

    async def generate(self, 
                      messages: Union[str, List[ConversationMessage]], 
                      params: GenerationParams) -> GenerationResponse:
        """Generate text using OpenAI API with conversation support."""
        with logger.track_request("generate", params.model) as request_info:
            try:
                # Handle backward compatibility - convert string prompt to messages
                if isinstance(messages, str):
                    formatted_messages = [{"role": "user", "content": messages}]
                else:
                    formatted_messages = []
                    for msg in messages:
                        # Handle both ConversationMessage objects and plain dicts
                        if hasattr(msg, 'role') and hasattr(msg, 'content'):
                            # ConversationMessage object
                            formatted_messages.append({"role": msg.role, "content": msg.content})
                        elif isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                            # Plain dict with role/content
                            formatted_messages.append({"role": msg["role"], "content": msg["content"]})
                        else:
                            raise ValueError(f"Invalid message format: {type(msg)} - {msg}")
                
                # Use normalization function to prepare parameters
                caps = get_capabilities_for_model(params.model)
                
                # Enable prompt caching for long system messages (moved to payload helper)
                formatted_messages = apply_prompt_cache_control(caps, formatted_messages)
                
                openai_params = normalize_params(params, params.model, "openai", caps)
                
                # Add messages to the parameters
                openai_params["messages"] = formatted_messages
                
                # Prefer Responses API for supported models when schema is requested
                if should_use_responses_api(params, params.model, caps):
                    rf = params.response_format or {}
                    schema_cfg = rf.get("json_schema") or rf.get("schema")
                    text_config = None
                    if schema_cfg:
                        # Use policy helper to format schema properly
                        text_config = format_responses_api_schema(
                            schema_cfg,
                            rf.get("name", "result"),
                            rf.get("strict", None)
                        )
                    # Transform messages for Responses API
                    use_instructions = getattr(params, "responses_use_instructions", False)
                    transformed_messages = transform_messages_for_provider(formatted_messages, "openai", use_instructions)
                    
                    # Build Responses API payload
                    responses_payload = self._build_responses_api_payload(
                        params, openai_params, transformed_messages, text_config
                    )

                    response = await self.client.responses.create(**responses_payload, timeout=self._timeout)
                    text_content = extract_text_from_responses_api(response) or ""

                    # Usage extraction with normalization
                    usage_dict = None
                    if hasattr(response, "usage") and response.usage is not None:
                        try:
                            usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else dict(response.usage.__dict__)
                        except Exception:
                            usage_dict = {}
                    
                    usage = normalize_usage(usage_dict, "openai")
                    
                    # Log usage if available
                    if usage:
                        logger.log_usage(usage, params.model, request_info['request_id'])

                    return GenerationResponse(
                        text=text_content,
                        model=params.model,
                        usage=usage,
                        provider="openai",
                        finish_reason=None
                    )

                # Fallback: Chat Completions API
                response = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
                
                # Extract response data
                message = response.choices[0].message
                
                # Extract usage with normalization
                usage_dict = None
                if hasattr(response, 'usage') and response.usage is not None:
                    try:
                        usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else dict(response.usage.__dict__)
                    except Exception:
                        usage_dict = {}
                
                usage = normalize_usage(usage_dict, "openai")
                
                # Log usage if available
                if usage:
                    logger.log_usage(usage, params.model, request_info['request_id'])
                
                return GenerationResponse(
                    text=message.content,
                    model=params.model,
                    usage=usage,
                    provider="openai",
                    finish_reason=response.choices[0].finish_reason
                )
                
            except Exception as e:
                raise ErrorMapper.map_openai_error(e)
    
    async def generate_stream(self, 
                            messages: Union[str, List[ConversationMessage]], 
                            params: GenerationParams) -> AsyncGenerator[str, None]:
        """Generate text using OpenAI API with streaming and conversation support."""
        with logger.track_request("stream", params.model) as request_info:
            # Initialize StreamAdapter
            adapter = StreamAdapter("openai", params.model)
            
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
                
                # Configure usage aggregation (OpenAI provides usage in stream, so not needed)
            
            await adapter.start_stream()
            
            try:
                # Handle backward compatibility - convert string prompt to messages
                if isinstance(messages, str):
                    formatted_messages = [{"role": "user", "content": messages}]
                else:
                    formatted_messages = []
                    for msg in messages:
                        # Handle both ConversationMessage objects and plain dicts
                        if hasattr(msg, 'role') and hasattr(msg, 'content'):
                            # ConversationMessage object
                            formatted_messages.append({"role": msg.role, "content": msg.content})
                        elif isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                            # Plain dict with role/content
                            formatted_messages.append({"role": msg["role"], "content": msg["content"]})
                        else:
                            raise ValueError(f"Invalid message format: {type(msg)} - {msg}")
                
                # Use normalization function to prepare parameters
                caps = get_capabilities_for_model(params.model)
                openai_params = normalize_params(params, params.model, "openai", caps)
                
                # Add messages and stream flag
                openai_params["messages"] = formatted_messages
                openai_params["stream"] = True
                
                # Responses API streaming for supported models with schema
                if should_use_responses_api(params, params.model, caps):
                    try:
                        rf = params.response_format or {}
                        schema_cfg = rf.get("json_schema") or rf.get("schema")
                        text_config = None
                        if schema_cfg:
                            try:
                                schema_root = dict(schema_cfg)
                            except Exception:
                                schema_root = schema_cfg
                            if isinstance(schema_root, dict) and "additionalProperties" not in schema_root:
                                schema_root["additionalProperties"] = False
                            text_config = {
                                "format": {
                                    "type": "json_schema",
                                    "name": rf.get("name", "result"),
                                    "schema": schema_root,
                                    "strict": rf.get("strict", None),
                                }
                            }
                        # Transform messages for Responses API
                        use_instructions = getattr(params, "responses_use_instructions", False)
                        transformed_messages = transform_messages_for_provider(formatted_messages, "openai", use_instructions)
                        
                        # Build Responses API payload with stream flag
                        responses_payload = self._build_responses_api_payload(
                            params, openai_params, transformed_messages, text_config
                        )
                        responses_payload["stream"] = True
                        async for piece in stream_responses_api(self.client, responses_payload, adapter):
                            yield piece
                        return
                    except Exception as e:
                        logger.debug(
                            "Responses API streaming unavailable or failed; falling back",
                            model=params.model,
                            request_id=request_info['request_id'],
                            error=e
                        )

                    # Fallback to Chat Completions streaming
                    stream = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
                    async for chunk in stream:
                        # Use adapter for normalization
                        delta = adapter.normalize_delta(chunk)
                        text = delta.get_text()
                        if text:
                            await adapter.track_chunk(len(text), text)
                            yield text
                else:
                    # Standard Chat Completions streaming for non-Responses API models
                    stream = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
                    async for chunk in stream:
                        # Use adapter for normalization
                        delta = adapter.normalize_delta(chunk)
                        text = delta.get_text()
                        if text:
                            await adapter.track_chunk(len(text), text)
                            yield text
                
            except Exception as e:
                await adapter.complete_stream(error=e)
                raise ErrorMapper.map_openai_error(e)
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
        """Generate text using OpenAI API with streaming and usage data.
        
        Yields tuples of (chunk, usage_data) where usage_data is None except
        for the final yield which contains the complete usage information.
        """
        with logger.track_request("stream_with_usage", params.model) as request_info:
            # Initialize StreamAdapter
            adapter = StreamAdapter("openai", params.model)
            
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
                
                # Configure usage aggregation (OpenAI provides usage in stream, so not needed)
            
            await adapter.start_stream()
            
            try:
                # Handle backward compatibility - convert string prompt to messages
                if isinstance(messages, str):
                    formatted_messages = [{"role": "user", "content": messages}]
                else:
                    formatted_messages = []
                    for msg in messages:
                        # Handle both ConversationMessage objects and plain dicts
                        if hasattr(msg, 'role') and hasattr(msg, 'content'):
                            # ConversationMessage object
                            formatted_messages.append({"role": msg.role, "content": msg.content})
                        elif isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                            # Plain dict with role/content
                            formatted_messages.append({"role": msg["role"], "content": msg["content"]})
                        else:
                            raise ValueError(f"Invalid message format: {type(msg)} - {msg}")
            
                # Get capabilities for model
                caps = get_capabilities_for_model(params.model)
                
                # Enable prompt caching for long system messages (moved to payload helper)
                formatted_messages = apply_prompt_cache_control(caps, formatted_messages)
                
                # Use normalization function to prepare parameters
                openai_params = normalize_params(params, params.model, "openai", caps)
                
                # Add messages and stream settings
                openai_params["messages"] = formatted_messages
                openai_params["stream"] = True
                openai_params["stream_options"] = {"include_usage": True}  # Request usage data in stream
                
                # Responses API streaming for supported models with schema (include usage if available)
                if should_use_responses_api(params, params.model, caps):
                    try:
                        rf = params.response_format or {}
                        schema_cfg = rf.get("json_schema") or rf.get("schema")
                        text_config = None
                        if schema_cfg:
                            try:
                                schema_root = dict(schema_cfg)
                            except Exception:
                                schema_root = schema_cfg
                            if isinstance(schema_root, dict) and "additionalProperties" not in schema_root:
                                schema_root["additionalProperties"] = False
                            text_config = {
                                "format": {
                                    "type": "json_schema",
                                    "name": rf.get("name", "result"),
                                    "schema": schema_root,
                                    "strict": rf.get("strict", None),
                                }
                            }
                        # Transform messages for Responses API
                        use_instructions = getattr(params, "responses_use_instructions", False)
                        transformed_messages = transform_messages_for_provider(formatted_messages, "openai", use_instructions)
                        
                        # Build Responses API payload with stream flag
                        responses_payload = self._build_responses_api_payload(
                            params, openai_params, transformed_messages, text_config
                        )
                        responses_payload["stream"] = True
                        async for item in stream_responses_api_with_usage(self.client, responses_payload, adapter):
                            yield item
                        return
                    except Exception as e:
                        logger.debug(
                            "Responses API streaming (with usage) unavailable or failed; falling back",
                            model=params.model,
                            request_id=request_info['request_id'],
                            error=e
                        )

                # Fallback to Chat Completions streaming with usage
                stream = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
                
                collected_chunks = []
                finish_reason = None
                
                async for chunk in stream:
                    # Use adapter for normalization
                    delta = adapter.normalize_delta(chunk)
                    text = delta.get_text()
                    
                    if text:
                        await adapter.track_chunk(len(text), text)
                        collected_chunks.append(text)
                        yield (text, None)
                    
                    # Capture finish reason
                    if chunk.choices and len(chunk.choices) > 0:
                        if chunk.choices[0].finish_reason:
                            finish_reason = chunk.choices[0].finish_reason
                    
                    # Check if this is the final chunk with usage data
                    if adapter.should_emit_usage(chunk):
                        usage_dict = adapter.extract_usage(chunk)
                        if usage_dict:
                            # Use normalization function for usage
                            usage = normalize_usage(usage_dict, "openai")
                            
                            # Log usage
                            logger.log_usage(usage, params.model, request_info['request_id'])
                            
                            # Emit usage event
                            await adapter.emit_usage(usage_dict, is_estimated=False)
                            
                            # Yield final usage data
                            yield (None, {
                                "usage": usage,
                                "model": params.model,
                                "provider": "openai",
                                "finish_reason": finish_reason,
                                "cost_usd": None,  # Cost calculation should be done in router/core
                                "cost_breakdown": None
                            })
                else:
                    # Standard Chat Completions streaming for non-Responses API models
                    stream = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
                    
                    collected_chunks = []
                    finish_reason = None
                    
                    async for chunk in stream:
                        # Use adapter for normalization
                        delta = adapter.normalize_delta(chunk)
                        text = delta.get_text()
                        
                        if text:
                            await adapter.track_chunk(len(text), text)
                            collected_chunks.append(text)
                            yield (text, None)
                        
                        # Track finish reason if available
                        if hasattr(chunk, 'choices') and chunk.choices and hasattr(chunk.choices[0], 'finish_reason'):
                            if chunk.choices[0].finish_reason:
                                finish_reason = chunk.choices[0].finish_reason
                        
                        # Check if this is the final chunk with usage data
                        if adapter.should_emit_usage(chunk):
                            usage_dict = adapter.extract_usage(chunk)
                            if usage_dict:
                                # Use normalization function for usage
                                usage = normalize_usage(usage_dict, "openai")
                                
                                # Log usage
                                logger.log_usage(usage, params.model, request_info['request_id'])
                                
                                # Emit usage event
                                await adapter.emit_usage(usage_dict, is_estimated=False)
                                
                                # Get final JSON if JSON handler was used
                                final_json = None
                                if adapter.json_handler:
                                    final_json = adapter.get_final_json()
                                
                                # Yield final usage data
                                yield (None, {
                                    "usage": usage,
                                    "model": params.model,
                                    "provider": "openai",
                                    "finish_reason": finish_reason,
                                    "cost_usd": None,  # Cost calculation should be done in router/core
                                    "cost_breakdown": None,
                                    "final_json": final_json  # Include final JSON if available
                                })
                
            except Exception as e:
                await adapter.complete_stream(error=e)
                raise ErrorMapper.map_openai_error(e)
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
        """Check if OpenAI API is available."""
        return bool(self._api_key)


# Global instance
openai_provider = OpenAIProvider()
