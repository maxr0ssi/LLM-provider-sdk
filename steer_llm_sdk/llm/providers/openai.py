import os
import logging
from typing import Dict, Any, AsyncGenerator, Optional, List, Union
from dotenv import load_dotenv
import openai
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

from ...models.generation import GenerationParams, GenerationResponse
from ...models.conversation_types import ConversationMessage

logger = logging.getLogger(__name__)


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
            
            # Force temperature=1 for o4-mini models (they don't support other values)
            if (params.model.lower().startswith("o4-mini") or params.model.lower() == "o4-mini") and params.temperature != 1.0:
                logger.warning(f"o4-mini models only support temperature=1.0, overriding from {params.temperature}")
                openai_params["temperature"] = 1.0
            
            # Cap temperature at 0.1 for gpt-4.1-mini for better consistency
            if params.model.lower().startswith("gpt-4.1-mini") and params.temperature > 0.1:
                logger.info(f"gpt-4.1-mini temperature capped at 0.1, overriding from {params.temperature}")
                openai_params["temperature"] = 0.1
            
            # Use max_completion_tokens for new models (o4-mini, gpt-4.1-mini, o1-*)
            # Check model name to determine which parameter to use
            model_lower = params.model.lower()
            logger.debug(f"Model: {params.model}, checking if it needs max_completion_tokens")
            
            if any(model_lower.startswith(prefix.lower()) for prefix in ["o4-mini", "gpt-4.1-mini", "o1-"]):
                logger.info(f"Using max_completion_tokens for model {params.model}")
                openai_params["max_completion_tokens"] = params.max_tokens
            else:
                logger.debug(f"Using max_tokens for model {params.model}")
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
            
            # Make API call
            response = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
            
            # Extract response data
            message = response.choices[0].message
            
            # Check for cache indicators (OpenAI automatic caching)
            cache_info = {}
            # print(f"🔍 DEBUG: OpenAI response has usage: {hasattr(response, 'usage')}")  # DISABLED FOR DEMO
            if hasattr(response, 'usage'):
                # Extract detailed token usage including cached tokens
                usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else response.usage.__dict__
                
                # Check for prompt_tokens_details with cached_tokens
                if 'prompt_tokens_details' in usage_dict:
                    prompt_details = usage_dict['prompt_tokens_details']
                    cache_info["prompt_tokens_details"] = prompt_details
                    
                    if isinstance(prompt_details, dict) and 'cached_tokens' in prompt_details:
                        cached_tokens = prompt_details['cached_tokens']
                        cache_info["cached_tokens"] = cached_tokens
                        if cached_tokens > 0:
                            print(f"🎯 OpenAI Cache HIT: {cached_tokens} tokens cached from previous requests")  # DISABLED FOR DEMO
                            print(f"   💰 Cost savings: ~{(cached_tokens / 1000) * 0.000150:.6f} USD saved")  # DISABLED FOR DEMO
                
                # Also check direct cached_tokens field (alternative location)
                if 'cached_tokens' in usage_dict:
                    cached_tokens = usage_dict['cached_tokens']
                    cache_info["cached_tokens"] = cached_tokens
                    if cached_tokens > 0:
                        print(f"🎯 OpenAI Cache HIT: {cached_tokens} tokens cached")  # DISABLED FOR DEMO
                
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
            raise Exception(f"OpenAI API error: {str(e)}")
    
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
                "temperature": params.temperature,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
                "stream": True
            }
            
            # Force temperature=1 for o4-mini models (they don't support other values)
            if (params.model.lower().startswith("o4-mini") or params.model.lower() == "o4-mini") and params.temperature != 1.0:
                logger.warning(f"o4-mini models only support temperature=1.0, overriding from {params.temperature}")
                openai_params["temperature"] = 1.0
            
            # Cap temperature at 0.1 for gpt-4.1-mini for better consistency
            if params.model.lower().startswith("gpt-4.1-mini") and params.temperature > 0.1:
                logger.info(f"gpt-4.1-mini temperature capped at 0.1, overriding from {params.temperature}")
                openai_params["temperature"] = 0.1
            
            # Use max_completion_tokens for new models (o4-mini, gpt-4.1-mini, o1-*)
            # Check model name to determine which parameter to use
            model_lower = params.model.lower()
            logger.debug(f"Model: {params.model}, checking if it needs max_completion_tokens")
            
            if any(model_lower.startswith(prefix.lower()) for prefix in ["o4-mini", "gpt-4.1-mini", "o1-"]):
                logger.info(f"Using max_completion_tokens for model {params.model}")
                openai_params["max_completion_tokens"] = params.max_tokens
            else:
                logger.debug(f"Using max_tokens for model {params.model}")
                openai_params["max_tokens"] = params.max_tokens
            
            if params.stop:
                openai_params["stop"] = params.stop
            
            # Make streaming API call
            stream = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise Exception(f"OpenAI streaming error: {str(e)}")
    
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
                "temperature": params.temperature,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
                "stream": True,
                "stream_options": {"include_usage": True}  # Request usage data in stream
            }
            
            # Force temperature=1 for o4-mini models (they don't support other values)
            if (params.model.lower().startswith("o4-mini") or params.model.lower() == "o4-mini") and params.temperature != 1.0:
                logger.warning(f"o4-mini models only support temperature=1.0, overriding from {params.temperature}")
                openai_params["temperature"] = 1.0
            
            # Cap temperature at 0.1 for gpt-4.1-mini for better consistency
            if params.model.lower().startswith("gpt-4.1-mini") and params.temperature > 0.1:
                logger.info(f"gpt-4.1-mini temperature capped at 0.1, overriding from {params.temperature}")
                openai_params["temperature"] = 0.1
            
            # Use max_completion_tokens for new models (o4-mini, gpt-4.1-mini, o1-*)
            # Check model name to determine which parameter to use
            model_lower = params.model.lower()
            logger.debug(f"Model: {params.model}, checking if it needs max_completion_tokens")
            
            if any(model_lower.startswith(prefix.lower()) for prefix in ["o4-mini", "gpt-4.1-mini", "o1-"]):
                logger.info(f"Using max_completion_tokens for model {params.model}")
                openai_params["max_completion_tokens"] = params.max_tokens
            else:
                logger.debug(f"Using max_tokens for model {params.model}")
                openai_params["max_tokens"] = params.max_tokens
            
            if params.stop:
                openai_params["stop"] = params.stop
                
            if params.response_format:
                openai_params["response_format"] = params.response_format
                
            if params.seed is not None:
                openai_params["seed"] = params.seed
            
            # Make streaming API call
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
                    usage_dict = chunk.usage.model_dump() if hasattr(chunk.usage, 'model_dump') else chunk.usage.__dict__
                    
                    # Check for cache information
                    cache_info = {}
                    if 'prompt_tokens_details' in usage_dict:
                        prompt_details = usage_dict['prompt_tokens_details']
                        cache_info["prompt_tokens_details"] = prompt_details
                        
                        if isinstance(prompt_details, dict) and 'cached_tokens' in prompt_details:
                            cached_tokens = prompt_details['cached_tokens']
                            cache_info["cached_tokens"] = cached_tokens
                            if cached_tokens > 0:
                                print(f"🎯 OpenAI Cache HIT: {cached_tokens} tokens cached from previous requests")
                                print(f"   💰 Cost savings: ~{(cached_tokens / 1000) * 0.000150:.6f} USD saved")
                    
                    usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                        "cache_info": cache_info
                    }
                    
                    # Calculate cost
                    from ..registry import calculate_exact_cost, calculate_cache_savings, get_config
                    config = get_config(params.model)
                    exact_cost = calculate_exact_cost(usage, config.llm_model_id)
                    cost_breakdown = None
                    
                    if exact_cost is not None:
                        cache_savings = calculate_cache_savings(usage, config.llm_model_id)
                        cost_usd = exact_cost - cache_savings
                        
                        # Add cost breakdown
                        from ...LLMConstants import (
                            GPT4O_MINI_INPUT_COST_PER_1K, GPT4O_MINI_OUTPUT_COST_PER_1K,
                            GPT41_NANO_INPUT_COST_PER_1K, GPT41_NANO_OUTPUT_COST_PER_1K
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
            raise Exception(f"OpenAI streaming error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        return bool(self._api_key)


# Global instance
openai_provider = OpenAIProvider()
