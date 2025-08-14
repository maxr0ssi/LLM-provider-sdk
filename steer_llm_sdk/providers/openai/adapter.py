import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import openai
from dotenv import load_dotenv
from openai import AsyncOpenAI

from ..base import ProviderAdapter, ProviderError
from ...models.conversation_types import ConversationMessage
from ...models.generation import GenerationParams, GenerationResponse
from ...core.capabilities import get_capabilities_for_model
from ...core.normalization.params import normalize_params, transform_messages_for_provider, should_use_responses_api
from ...core.normalization.usage import normalize_usage

logger = logging.getLogger(__name__)

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
        """Build payload for OpenAI Responses API."""
        responses_payload: Dict[str, Any] = {
            "model": params.model,
        }
        
        # Add transformed messages (either as input or instructions+messages)
        if isinstance(transformed_messages, dict):
            responses_payload.update(transformed_messages)
        else:
            responses_payload["input"] = transformed_messages
        
        # Copy only Responses API compatible parameters
        # Responses API accepts: temperature, top_p, max_output_tokens, seed, stop
        responses_api_params = ["temperature", "top_p", "seed", "stop"]
        for key in responses_api_params:
            if key in openai_params and openai_params[key] is not None:
                responses_payload[key] = openai_params[key]
        
        # Handle max tokens mapping
        if "max_completion_tokens" in openai_params:
            responses_payload["max_output_tokens"] = openai_params["max_completion_tokens"]
        elif "max_tokens" in openai_params:
            responses_payload["max_output_tokens"] = openai_params["max_tokens"]
            
        if text_config is not None:
            responses_payload["text"] = text_config
            
        # Optional: reasoning and metadata pass-through if provided
        if hasattr(params, "reasoning") and getattr(params, "reasoning") is not None:
            responses_payload["reasoning"] = getattr(params, "reasoning")
        if hasattr(params, "metadata") and getattr(params, "metadata") is not None:
            responses_payload["metadata"] = getattr(params, "metadata")
            
        return responses_payload
    

    async def generate(self, 
                      messages: Union[str, List[ConversationMessage]], 
                      params: GenerationParams) -> GenerationResponse:
        """Generate text using OpenAI API with conversation support."""
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
            
            # Enable prompt caching for long system messages (if supported by model)
            if (formatted_messages and 
                formatted_messages[0].get("role") == "system" and 
                len(formatted_messages[0].get("content", "")) > 1024 and
                "gpt-4o" in params.model.lower()):  # Only for models that support caching
                
                # Mark system message for caching
                formatted_messages[0]["cache_control"] = {"type": "ephemeral"}
            
            # Use normalization function to prepare parameters
            caps = get_capabilities_for_model(params.model)
            openai_params = normalize_params(params, params.model, "openai", caps)
            
            # Add messages to the parameters
            openai_params["messages"] = formatted_messages
            
            # Prefer Responses API for supported models when schema is requested
            if should_use_responses_api(params, params.model, caps):
                rf = params.response_format or {}
                schema_cfg = rf.get("json_schema") or rf.get("schema")
                text_config = None
                if schema_cfg:
                    # Ensure root additionalProperties=false as required by Responses API
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
                
                # Build Responses API payload
                responses_payload = self._build_responses_api_payload(
                    params, openai_params, transformed_messages, text_config
                )

                response = await self.client.responses.create(**responses_payload, timeout=self._timeout)

                # Extract text or structured output
                text_content = None
                if hasattr(response, "output_text") and response.output_text:
                    text_content = response.output_text
                elif hasattr(response, "output") and response.output:
                    try:
                        first = response.output[0]
                        if hasattr(first, "content") and first.content:
                            part = first.content[0]
                            # part may have .text or .json
                            if hasattr(part, "text") and part.text is not None:
                                text_content = part.text
                            elif hasattr(part, "json") and part.json is not None:
                                text_content = json.dumps(part.json)
                    except Exception:
                        text_content = None

                if text_content is None:
                    text_content = ""

                # Usage extraction with normalization
                usage_dict = None
                if hasattr(response, "usage") and response.usage is not None:
                    try:
                        usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else dict(response.usage.__dict__)
                    except Exception:
                        usage_dict = {}
                
                usage = normalize_usage(usage_dict, "openai")

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
            
            return GenerationResponse(
                text=message.content,
                model=params.model,
                usage=usage,
                provider="openai",
                finish_reason=response.choices[0].finish_reason
            )
            
        except Exception as e:
            raise ProviderError(f"OpenAI API error: {str(e)}", "openai")
    
    async def generate_stream(self, 
                            messages: Union[str, List[ConversationMessage]], 
                            params: GenerationParams) -> AsyncGenerator[str, None]:
        """Generate text using OpenAI API with streaming and conversation support."""
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

                    stream = await self.client.responses.create(**responses_payload, timeout=self._timeout)
                    # Fallback: some SDKs return an async iterator directly
                    async for event in stream:
                        # Best-effort: yield text deltas if present
                        delta = getattr(event, "delta", None) or getattr(event, "output_text", None)
                        if delta:
                            yield str(delta)
                    return
                except Exception as e:
                    logger.debug("Responses API streaming unavailable or failed, falling back: %s", e)

            # Fallback to Chat Completions streaming
            stream = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise ProviderError(f"OpenAI streaming error: {str(e)}", "openai")
    
    async def generate_stream_with_usage(self, 
                                       messages: Union[str, List[ConversationMessage]], 
                                       params: GenerationParams) -> AsyncGenerator[tuple, None]:
        """Generate text using OpenAI API with streaming and usage data.
        
        Yields tuples of (chunk, usage_data) where usage_data is None except
        for the final yield which contains the complete usage information.
        """
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
            
            # Enable prompt caching for long system messages (if supported by model)
            if (formatted_messages and 
                formatted_messages[0].get("role") == "system" and 
                len(formatted_messages[0].get("content", "")) > 1024 and
                "gpt-4o" in params.model.lower()):  # Only for models that support caching
                
                # Mark system message for caching
                formatted_messages[0]["cache_control"] = {"type": "ephemeral"}
            
            # Use normalization function to prepare parameters
            caps = get_capabilities_for_model(params.model)
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

                    stream = await self.client.responses.create(**responses_payload, timeout=self._timeout)
                    collected = []
                    async for event in stream:
                        delta = getattr(event, "delta", None) or getattr(event, "output_text", None)
                        if delta:
                            text = str(delta)
                            collected.append(text)
                            yield (text, None)
                    # After stream completes, no usage extracted (API variance); yield final usage as None
                    yield (None, {
                        "usage": {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "cache_info": {}
                        },
                        "model": params.model,
                        "provider": "openai",
                        "finish_reason": None,
                        "cost_usd": None,
                        "cost_breakdown": None
                    })
                    return
                except Exception as e:
                    logger.debug("Responses API streaming (with usage) unavailable or failed, falling back: %s", e)

            # Fallback to Chat Completions streaming with usage
            stream = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
            
            collected_chunks = []
            finish_reason = None
            
            async for chunk in stream:
                # Check if this chunk has content
                if chunk.choices and len(chunk.choices) > 0:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        collected_chunks.append(content)
                        yield (content, None)
                    
                    # Capture finish reason
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
                
                # Check if this is the final chunk with usage data
                if hasattr(chunk, 'usage') and chunk.usage is not None:
                    # Extract usage data
                    try:
                        usage_dict = chunk.usage.model_dump() if hasattr(chunk.usage, 'model_dump') else dict(chunk.usage.__dict__)
                    except Exception:
                        usage_dict = {}
                    
                    # Use normalization function for usage
                    usage = normalize_usage(usage_dict, "openai")
                    
                    # Calculate cost
                    # Import from llm.registry (correct package path)
                    from ...core.routing import calculate_cache_savings, calculate_exact_cost, get_config
                    config = get_config(params.model)
                    exact_cost = calculate_exact_cost(usage, config.llm_model_id)
                    cost_breakdown = None
                    
                    if exact_cost is not None:
                        cache_savings = calculate_cache_savings(usage, config.llm_model_id)
                        cost_usd = exact_cost - cache_savings
                        
                        # Add cost breakdown
                        from ...config.constants import (
                            GPT4O_MINI_INPUT_COST_PER_1K,
                            GPT4O_MINI_OUTPUT_COST_PER_1K,
                            GPT41_NANO_INPUT_COST_PER_1K,
                            GPT41_NANO_OUTPUT_COST_PER_1K,
                        )
                        
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
                        
                        if config.llm_model_id == "gpt-4o-mini":
                            input_cost = (prompt_tokens / 1000) * GPT4O_MINI_INPUT_COST_PER_1K
                            output_cost = (completion_tokens / 1000) * GPT4O_MINI_OUTPUT_COST_PER_1K
                        elif config.llm_model_id == "gpt-4.1-nano":
                            input_cost = (prompt_tokens / 1000) * GPT41_NANO_INPUT_COST_PER_1K
                            output_cost = (completion_tokens / 1000) * GPT41_NANO_OUTPUT_COST_PER_1K
                        else:
                            input_cost = exact_cost / 2  # Fallback approximation
                            output_cost = exact_cost / 2
                        
                        cost_breakdown = {
                            "input_cost": input_cost,
                            "output_cost": output_cost,
                            "cache_savings": cache_savings,
                            "total_cost": cost_usd
                        }
                    
                    # Yield final usage data
                    yield (None, {
                        "usage": usage,
                        "model": params.model,
                        "provider": "openai",
                        "finish_reason": finish_reason,
                        "cost_usd": cost_usd if 'cost_usd' in locals() else None,
                        "cost_breakdown": cost_breakdown
                    })
                    
        except Exception as e:
            raise ProviderError(f"OpenAI streaming error: {str(e)}", "openai")
    
    def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        return bool(self._api_key)


# Global instance
openai_provider = OpenAIProvider()
