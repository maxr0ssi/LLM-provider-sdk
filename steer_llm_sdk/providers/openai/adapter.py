import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import openai
from dotenv import load_dotenv
from openai import AsyncOpenAI

from ...reliability.errors import ProviderError
from ...models.conversation_types import ConversationMessage
from ...models.generation import GenerationParams, GenerationResponse
from ...core.capabilities import get_capabilities_for_model

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class OpenAIProvider:
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
    
    def _supports_responses_api(self, model_name: str) -> bool:
        caps = get_capabilities_for_model(model_name)
        return bool(caps.supports_json_schema)

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
            
            # Prepare OpenAI-specific parameters
            openai_params = {
                "model": params.model,
                "messages": formatted_messages,
                "temperature": params.temperature,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
            }
            
            # Apply capability-driven temperature behavior
            caps = get_capabilities_for_model(params.model)
            if caps.fixed_temperature is not None:
                if params.temperature != caps.fixed_temperature:
                    logger.info("Model enforces fixed temperature=%s; overriding from %s", caps.fixed_temperature, params.temperature)
                openai_params["temperature"] = caps.fixed_temperature
            else:
                if not caps.supports_temperature:
                    openai_params.pop("temperature", None)
            
            # Use max_completion_tokens for new models (o4-mini, gpt-4.1-mini, o1-*)
            # Check model name to determine which parameter to use
            logger.debug("Selecting max tokens parameter by capability")
            if caps.uses_max_completion_tokens:
                openai_params["max_completion_tokens"] = params.max_tokens
            else:
                openai_params["max_tokens"] = params.max_tokens
            
            if params.stop:
                openai_params["stop"] = params.stop
            
            # Add response_format if provided
            if params.response_format:
                openai_params["response_format"] = params.response_format
            
            # Add seed if provided
            if params.seed is not None:
                openai_params["seed"] = params.seed
            
            # Add any other extra fields from params (except max_tokens which is already handled)
            excluded_fields = {'model', 'messages', 'temperature', 'top_p', 'frequency_penalty', 
                             'presence_penalty', 'max_tokens', 'stop', 'response_format', 'seed'}
            for field_name in params.model_fields_set:
                if field_name not in excluded_fields and field_name not in openai_params and hasattr(params, field_name):
                    value = getattr(params, field_name)
                    if value is not None:
                        openai_params[field_name] = value
            
            # Prefer Responses API for supported models when schema is requested
            if params.response_format and self._supports_responses_api(params.model):
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
                model_lower = params.model.lower()
                responses_payload: Dict[str, Any] = {
                    "model": params.model,
                    "input": formatted_messages,
                }
                # Optionally map first system message to `instructions` for Responses API
                use_instructions = getattr(params, "responses_use_instructions", False)
                if use_instructions and formatted_messages and formatted_messages[0].get("role") == "system":
                    responses_payload["instructions"] = formatted_messages[0].get("content", "")
                    # Remove system from input if using instructions
                    responses_payload["input"] = formatted_messages[1:]
                if "gpt-5-mini" not in model_lower:
                    responses_payload["temperature"] = openai_params.get("temperature")
                responses_payload["top_p"] = openai_params.get("top_p")
                # Max output tokens naming differs on some models
                caps = get_capabilities_for_model(params.model)
                if caps.uses_max_completion_tokens:
                    responses_payload["max_output_tokens"] = openai_params.get("max_completion_tokens", params.max_tokens)
                else:
                    responses_payload["max_tokens"] = params.max_tokens
                if params.seed is not None:
                    responses_payload["seed"] = params.seed
                if params.stop:
                    responses_payload["stop"] = params.stop
                if text_config is not None:
                    responses_payload["text"] = text_config
                # Optional: reasoning and metadata pass-through if provided
                if hasattr(params, "reasoning") and getattr(params, "reasoning") is not None:
                    responses_payload["reasoning"] = getattr(params, "reasoning")
                if hasattr(params, "metadata") and getattr(params, "metadata") is not None:
                    responses_payload["metadata"] = getattr(params, "metadata")

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

                # Usage extraction
                usage = {}
                if hasattr(response, "usage") and response.usage is not None:
                    usage_obj = response.usage
                    # Try common fields
                    prompt_tokens = getattr(usage_obj, "input_tokens", None) or getattr(usage_obj, "prompt_tokens", 0)
                    completion_tokens = getattr(usage_obj, "output_tokens", None) or getattr(usage_obj, "completion_tokens", 0)
                    total_tokens = getattr(usage_obj, "total_tokens", None)
                    if total_tokens is None:
                        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
                    usage = {
                        "prompt_tokens": prompt_tokens or 0,
                        "completion_tokens": completion_tokens or 0,
                        "total_tokens": total_tokens,
                        "cache_info": {}
                    }

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
            
            # Check for cache indicators (OpenAI automatic caching)
            cache_info = {}
            # print(f"🔍 DEBUG: OpenAI response has usage: {hasattr(response, 'usage')}")  # DISABLED FOR DEMO
            if hasattr(response, 'usage') and response.usage is not None:
                # Extract detailed token usage including cached tokens
                try:
                    usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else dict(response.usage.__dict__)
                except Exception:
                    usage_dict = {}
                
                # Check for prompt_tokens_details with cached_tokens
                if isinstance(usage_dict, dict) and 'prompt_tokens_details' in usage_dict:
                    prompt_details = usage_dict.get('prompt_tokens_details')
                    cache_info["prompt_tokens_details"] = prompt_details
                    
                    if isinstance(prompt_details, dict) and 'cached_tokens' in prompt_details:
                        try:
                            cached_tokens = int(prompt_details.get('cached_tokens') or 0)
                        except Exception:
                            cached_tokens = 0
                        cache_info["cached_tokens"] = cached_tokens
                        if cached_tokens > 0:
                            logger.debug("OpenAI cache hit: %s tokens cached (approx savings included)", cached_tokens)
                
                # Also check direct cached_tokens field (alternative location)
                if isinstance(usage_dict, dict) and 'cached_tokens' in usage_dict:
                    try:
                        cached_tokens = int(usage_dict.get('cached_tokens') or 0)
                    except Exception:
                        cached_tokens = 0
                    cache_info["cached_tokens"] = cached_tokens
                    if cached_tokens > 0:
                        logger.debug("OpenAI cache hit: %s tokens cached", cached_tokens)
                
                # Log full usage for debugging
                # print(f"🔍 OpenAI Usage Details: {usage_dict}")  # DISABLED FOR DEMO
            
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "cache_info": cache_info
            }
            
            return GenerationResponse(
                text=message.content,
                model=params.model,
                usage=usage,
                provider="openai",
                finish_reason=response.choices[0].finish_reason
            )
            
        except Exception as e:
            raise ProviderError(f"OpenAI API error: {str(e)}")
    
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
            
            # Prepare OpenAI-specific parameters
            openai_params = {
                "model": params.model,
                "messages": formatted_messages,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
                "stream": True
            }
            # Capability-driven temperature
            caps = get_capabilities_for_model(params.model)
            if caps.fixed_temperature is not None:
                openai_params["temperature"] = caps.fixed_temperature
            elif caps.supports_temperature:
                openai_params["temperature"] = params.temperature
            
            # Max tokens param by capability
            if caps.uses_max_completion_tokens:
                openai_params["max_completion_tokens"] = params.max_tokens
            else:
                openai_params["max_tokens"] = params.max_tokens
            
            if params.stop:
                openai_params["stop"] = params.stop
            
            # Responses API streaming for supported models with schema
            if params.response_format and self._supports_responses_api(params.model):
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
                    model_lower = params.model.lower()
                    responses_payload: Dict[str, Any] = {
                        "model": params.model,
                        "input": formatted_messages,
                        "stream": True,
                    }
                    use_instructions = getattr(params, "responses_use_instructions", False)
                    if use_instructions and formatted_messages and formatted_messages[0].get("role") == "system":
                        responses_payload["instructions"] = formatted_messages[0].get("content", "")
                        responses_payload["input"] = formatted_messages[1:]
                    if "gpt-5-mini" not in model_lower:
                        responses_payload["temperature"] = openai_params.get("temperature")
                    responses_payload["top_p"] = openai_params.get("top_p")
                    caps = get_capabilities_for_model(params.model)
                    if caps.uses_max_completion_tokens:
                        responses_payload["max_output_tokens"] = openai_params.get("max_completion_tokens", params.max_tokens)
                    else:
                        responses_payload["max_tokens"] = params.max_tokens
                    if params.seed is not None:
                        responses_payload["seed"] = params.seed
                    if params.stop:
                        responses_payload["stop"] = params.stop
                    if text_config is not None:
                        responses_payload["text"] = text_config
                    if hasattr(params, "reasoning") and getattr(params, "reasoning") is not None:
                        responses_payload["reasoning"] = getattr(params, "reasoning")
                    if hasattr(params, "metadata") and getattr(params, "metadata") is not None:
                        responses_payload["metadata"] = getattr(params, "metadata")

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
            raise ProviderError(f"OpenAI streaming error: {str(e)}")
    
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
            
            # Prepare OpenAI-specific parameters
            openai_params = {
                "model": params.model,
                "messages": formatted_messages,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
                "stream": True,
                "stream_options": {"include_usage": True}  # Request usage data in stream
            }
            # Capability-driven temperature
            caps = get_capabilities_for_model(params.model)
            if caps.fixed_temperature is not None:
                openai_params["temperature"] = caps.fixed_temperature
            elif caps.supports_temperature:
                openai_params["temperature"] = params.temperature

            # Max tokens param by capability
            if caps.uses_max_completion_tokens:
                openai_params["max_completion_tokens"] = params.max_tokens
            else:
                openai_params["max_tokens"] = params.max_tokens
            
            if params.stop:
                openai_params["stop"] = params.stop
                
            if params.response_format:
                openai_params["response_format"] = params.response_format
                
            if params.seed is not None:
                openai_params["seed"] = params.seed
            
            # Responses API streaming for supported models with schema (include usage if available)
            if params.response_format and self._supports_responses_api(params.model):
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
                    model_lower = params.model.lower()
                    responses_payload: Dict[str, Any] = {
                        "model": params.model,
                        "input": formatted_messages,
                        "stream": True,
                    }
                    use_instructions = getattr(params, "responses_use_instructions", False)
                    if use_instructions and formatted_messages and formatted_messages[0].get("role") == "system":
                        responses_payload["instructions"] = formatted_messages[0].get("content", "")
                        responses_payload["input"] = formatted_messages[1:]
                    if "gpt-5-mini" not in model_lower:
                        responses_payload["temperature"] = openai_params.get("temperature")
                    responses_payload["top_p"] = openai_params.get("top_p")
                    caps = get_capabilities_for_model(params.model)
                    if caps.uses_max_completion_tokens:
                        responses_payload["max_output_tokens"] = openai_params.get("max_completion_tokens", params.max_tokens)
                    else:
                        responses_payload["max_tokens"] = params.max_tokens
                    if params.seed is not None:
                        responses_payload["seed"] = params.seed
                    if params.stop:
                        responses_payload["stop"] = params.stop
                    if text_config is not None:
                        responses_payload["text"] = text_config
                    if hasattr(params, "reasoning") and getattr(params, "reasoning") is not None:
                        responses_payload["reasoning"] = getattr(params, "reasoning")
                    if hasattr(params, "metadata") and getattr(params, "metadata") is not None:
                        responses_payload["metadata"] = getattr(params, "metadata")

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
                    
                    # Check for cache information
                    cache_info = {}
                    if isinstance(usage_dict, dict) and 'prompt_tokens_details' in usage_dict:
                        prompt_details = usage_dict.get('prompt_tokens_details')
                        cache_info["prompt_tokens_details"] = prompt_details
                        
                        if isinstance(prompt_details, dict) and 'cached_tokens' in prompt_details:
                            try:
                                cached_tokens = int(prompt_details.get('cached_tokens') or 0)
                            except Exception:
                                cached_tokens = 0
                            cache_info["cached_tokens"] = cached_tokens
                            if cached_tokens > 0:
                                logger.debug("OpenAI cache hit: %s tokens cached (approx savings)", cached_tokens)
                    
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                        "cache_info": cache_info
                    }
                    
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
            raise ProviderError(f"OpenAI streaming error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        return bool(self._api_key)


# Global instance
openai_provider = OpenAIProvider()
