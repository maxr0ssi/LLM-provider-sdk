import os
from typing import Dict, Any, AsyncGenerator, Optional, List, Union
import logging
from dotenv import load_dotenv
import xai_sdk
from xai_sdk import AsyncClient

# Load environment variables
load_dotenv()
from xai_sdk.chat import system, user, assistant

from ...models.generation import GenerationParams, GenerationResponse
from ...models.conversation_types import ConversationMessage


logger = logging.getLogger(__name__)


class XAIProvider:
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
        
        # Create chat and sample response
        chat = await self.client.chat.create(
            model=params.model,
            messages=formatted,
            max_tokens=params.max_tokens,
            temperature=params.temperature,
            top_p=params.top_p,
            frequency_penalty=params.frequency_penalty,
            presence_penalty=params.presence_penalty,
            stop=params.stop
        )
        response = await chat.sample()
        
        # Note: xai_sdk.AsyncClient's sample() does not expose token usage by default
        usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cache_info": {},
        }
        
        return GenerationResponse(
            text=response.content,
            model=params.model,
            usage=usage,
            provider="xai",
            finish_reason=getattr(response, "finish_reason", None)
        )
    
    async def generate_stream(
        self,
        messages: Union[str, List[ConversationMessage]],
        params: GenerationParams
    ) -> AsyncGenerator[str, None]:
        """Generate text using xAI API with streaming support."""
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
        
        # Create chat and stream response
        chat = await self.client.chat.create(
            model=params.model,
            messages=formatted,
            max_tokens=params.max_tokens,
            temperature=params.temperature,
            top_p=params.top_p,
            frequency_penalty=params.frequency_penalty,
            presence_penalty=params.presence_penalty,
            stop=params.stop
        )
        async for response, chunk in chat.stream():
            yield chunk.content
    
    async def generate_stream_with_usage(
        self,
        messages: Union[str, List[ConversationMessage]],
        params: GenerationParams
    ) -> AsyncGenerator[tuple, None]:
        """Generate text using xAI API with streaming and usage data.
        
        Note: xAI's streaming API may not provide usage data in the same way as OpenAI/Anthropic.
        This implementation collects chunks and estimates usage based on the response.
        """
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
            
            # Create chat and stream response
            chat = await self.client.chat.create(
                model=params.model,
                messages=formatted,
                max_tokens=params.max_tokens,
                temperature=params.temperature,
                top_p=params.top_p,
                frequency_penalty=params.frequency_penalty,
                presence_penalty=params.presence_penalty,
                stop=params.stop
            )
            
            collected_chunks = []
            finish_reason = None
            
            async for response, chunk in chat.stream():
                if chunk.content:
                    collected_chunks.append(chunk.content)
                    yield (chunk.content, None)
                
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
            
            # Calculate cost if available
            from ..registry import calculate_exact_cost, get_config
            config = get_config(params.model)
            cost_usd = None
            cost_breakdown = None
            
            if config.cost_per_1k_tokens:
                # Simple cost calculation for xAI
                cost_usd = (usage["total_tokens"] / 1000) * config.cost_per_1k_tokens
                cost_breakdown = {
                    "input_cost": (prompt_tokens / 1000) * config.cost_per_1k_tokens / 2,
                    "output_cost": (completion_tokens / 1000) * config.cost_per_1k_tokens / 2,
                    "cache_savings": 0,
                    "total_cost": cost_usd
                }
            
            # Yield final usage data
            yield (None, {
                "usage": usage,
                "model": params.model,
                "provider": "xai",
                "finish_reason": finish_reason or "stop",
                "cost_usd": cost_usd,
                "cost_breakdown": cost_breakdown
            })
            
        except Exception as e:
            raise Exception(f"xAI streaming error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if xAI API is available."""
        return bool(self._api_key)


# Global instance
xai_provider = XAIProvider()