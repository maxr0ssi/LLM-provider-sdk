import os
from typing import Dict, Any, AsyncGenerator, Optional, List, Union
from dotenv import load_dotenv
import openai
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

from ...models.generation import GenerationParams, GenerationResponse
from ...models.conversation_types import ConversationMessage


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
            
            # Prepare OpenAI-specific parameters
            openai_params = {
                "model": params.model,
                "messages": formatted_messages,
                "max_tokens": params.max_tokens,
                "temperature": params.temperature,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
            }
            
            if params.stop:
                openai_params["stop"] = params.stop
            
            # Make API call
            response = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
            
            # Extract response data
            message = response.choices[0].message
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
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
                formatted_messages = [
                    {"role": msg.role, "content": msg.content} 
                    for msg in messages
                ]
            
            # Prepare OpenAI-specific parameters
            openai_params = {
                "model": params.model,
                "messages": formatted_messages,
                "max_tokens": params.max_tokens,
                "temperature": params.temperature,
                "top_p": params.top_p,
                "frequency_penalty": params.frequency_penalty,
                "presence_penalty": params.presence_penalty,
                "stream": True
            }
            
            if params.stop:
                openai_params["stop"] = params.stop
            
            # Make streaming API call
            stream = await self.client.chat.completions.create(**openai_params, timeout=self._timeout)
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            raise Exception(f"OpenAI streaming error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        return bool(self._api_key)


# Global instance
openai_provider = OpenAIProvider()
