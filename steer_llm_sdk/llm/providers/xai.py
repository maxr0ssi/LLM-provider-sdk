import os
from typing import Dict, Any, AsyncGenerator, Optional, List, Union
from dotenv import load_dotenv
import xai_sdk
from xai_sdk import AsyncClient

# Load environment variables
load_dotenv()
from xai_sdk.chat import system, user, assistant

from ...models.generation import GenerationParams, GenerationResponse
from ...models.conversation_types import ConversationMessage


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
        chat = self.client.chat.create(
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
        usage: Dict[str, int] = {}
        
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
        chat = self.client.chat.create(
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
    
    def is_available(self) -> bool:
        """Check if xAI API is available."""
        return bool(self._api_key)


# Global instance
xai_provider = XAIProvider()