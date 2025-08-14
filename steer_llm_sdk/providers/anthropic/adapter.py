import os
from typing import Dict, Any, AsyncGenerator, Optional, List, Tuple, Union
import logging
from dotenv import load_dotenv
import anthropic
from anthropic import AsyncAnthropic

# Load environment variables
load_dotenv()

from ..base import ProviderAdapter, ProviderError
from ...models.generation import GenerationParams, GenerationResponse
from ...models.conversation_types import ConversationMessage
from ...core.capabilities import get_capabilities_for_model
from ...core.normalization.params import normalize_params, transform_messages_for_provider
from ...core.normalization.usage import normalize_usage


logger = logging.getLogger(__name__)


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
            
            # Transform messages for Anthropic format (system message separate)
            all_messages = [{"role": "system", "content": system_message}] if system_message else []
            all_messages.extend(formatted_messages)
            transformed = transform_messages_for_provider(all_messages, "anthropic")

            # Add messages to parameters
            if isinstance(transformed, dict):
                anthropic_params.update(transformed)

                # Drop system if None to avoid SDK type validation error
                if anthropic_params.get("system") is None:
                    anthropic_params.pop("system", None)

                # Enable prompt caching for long system messages
                if "system" in anthropic_params and isinstance(anthropic_params["system"], str):
                    system_text = anthropic_params["system"]
                    if len(system_text) > 1024:
                        anthropic_params["system"] = [
                            {
                                "type": "text",
                                "text": system_text,
                                "cache_control": {"type": "ephemeral"}
                            }
                        ]
                        logger.debug("Anthropic: caching system prompt (%s chars)", len(system_text))
            else:
                anthropic_params["messages"] = transformed
            
            # Make API call
            response = await self.client.messages.create(**anthropic_params)
            
            # Extract response data
            text_content = ""
            for content_block in response.content:
                if content_block.type == "text":
                    text_content += content_block.text
            
            # Extract usage with normalization
            usage_dict = None
            if hasattr(response, 'usage'):
                try:
                    usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else response.usage.__dict__
                except Exception:
                    usage_dict = {}
            
            usage = normalize_usage(usage_dict, "anthropic")
            
            return GenerationResponse(
                text=text_content,
                model=params.model,
                usage=usage,
                provider="anthropic",
                finish_reason=response.stop_reason
            )
            
        except Exception as e:
            raise ProviderError(f"Anthropic API error: {str(e)}", "anthropic")
    
    async def generate_stream(self, 
                            messages: Union[str, List[ConversationMessage]], 
                            params: GenerationParams) -> AsyncGenerator[str, None]:
        """Generate text using Anthropic API with streaming and conversation support."""
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
            
            # Transform messages for Anthropic format
            all_messages = [{"role": "system", "content": system_message}] if system_message else []
            all_messages.extend(formatted_messages)
            transformed = transform_messages_for_provider(all_messages, "anthropic")

            # Add messages to parameters
            if isinstance(transformed, dict):
                anthropic_params.update(transformed)
                # Drop system if None to satisfy SDK
                if anthropic_params.get("system") is None:
                    anthropic_params.pop("system", None)
            else:
                anthropic_params["messages"] = transformed
            
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
            
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        yield event.delta.text
                        
        except Exception as e:
            raise ProviderError(f"Anthropic streaming error: {str(e)}", "anthropic")
    
    async def generate_stream_with_usage(self, 
                                       messages: Union[str, List[ConversationMessage]], 
                                       params: GenerationParams) -> AsyncGenerator[tuple, None]:
        """Generate text using Anthropic API with streaming and usage data.
        
        Yields tuples of (chunk, usage_data) where usage_data is None except
        for the final yield which contains the complete usage information.
        """
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

            # Add system message as top-level parameter if present (and not already structured)
            if system_message:
                # Enable prompt caching for long system messages (like Anthropic's guide)
                if len(system_message) > 1024:  # Only cache long system prompts
                    anthropic_params["system"] = [
                        {
                            "type": "text",
                            "text": system_message,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                    logger.debug("Anthropic: caching system prompt (%s chars)", len(system_message))
                else:
                    anthropic_params["system"] = system_message
            
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
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        chunk = event.delta.text
                        collected_chunks.append(chunk)
                        yield (chunk, None)
                
                elif event.type == "message_delta":
                    # Capture usage data from message_delta event
                    if hasattr(event, 'usage'):
                        usage_data = event.usage
                    if hasattr(event.delta, 'stop_reason'):
                        finish_reason = event.delta.stop_reason
                
                elif event.type == "message_stop":
                    # Final event - process usage data
                    if usage_data:
                        # Extract usage information
                        usage_dict = usage_data.model_dump() if hasattr(usage_data, 'model_dump') else usage_data.__dict__
                        
                        # Check for cache information
                        cache_info = {}
                        if hasattr(usage_data, 'cache_creation_input_tokens'):
                            cache_creation = usage_data.cache_creation_input_tokens
                            cache_info["cache_creation_input_tokens"] = cache_creation
                            if cache_creation and cache_creation > 0:
                                logger.debug("Anthropic cache creation: %s tokens", cache_creation)
                        
                        if hasattr(usage_data, 'cache_read_input_tokens'):
                            cache_read = usage_data.cache_read_input_tokens
                            cache_info["cache_read_input_tokens"] = cache_read
                            if cache_read and cache_read > 0:
                                logger.debug("Anthropic cache hit: %s tokens", cache_read)
                        
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
                        
                        # Calculate cost
                        from ...core.routing import calculate_exact_cost, calculate_cache_savings, get_config
                        config = get_config(params.model)
                        exact_cost = calculate_exact_cost(usage, config.llm_model_id)
                        cost_breakdown = None
                        
                        if exact_cost is not None:
                            cache_savings = calculate_cache_savings(usage, config.llm_model_id)
                            cost_usd = exact_cost - cache_savings
                            
                            # Simple cost breakdown for Anthropic
                            cost_breakdown = {
                                "input_cost": (usage["prompt_tokens"] / 1000) * (config.input_cost_per_1k_tokens or 0),
                                "output_cost": (usage["completion_tokens"] / 1000) * (config.output_cost_per_1k_tokens or 0),
                                "cache_savings": cache_savings,
                                "total_cost": cost_usd
                            }
                        
                        # Yield final usage data
                        yield (None, {
                            "usage": usage,
                            "model": params.model,
                            "provider": "anthropic",
                            "finish_reason": finish_reason,
                            "cost_usd": cost_usd if 'cost_usd' in locals() else None,
                            "cost_breakdown": cost_breakdown
                        })
                    
        except Exception as e:
            raise ProviderError(f"Anthropic streaming error: {str(e)}", "anthropic")
    
    def is_available(self) -> bool:
        """Check if Anthropic API is available."""
        return bool(self._api_key)


# Global instance
anthropic_provider = AnthropicProvider()
