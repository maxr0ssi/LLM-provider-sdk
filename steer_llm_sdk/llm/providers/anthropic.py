import os
from typing import Dict, Any, AsyncGenerator, Optional, List, Union
from dotenv import load_dotenv
import anthropic
from anthropic import AsyncAnthropic

# Load environment variables
load_dotenv()

from ...models.generation import GenerationParams, GenerationResponse
from ...models.conversation_types import ConversationMessage


class AnthropicProvider:
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
            
            # Prepare Anthropic-specific parameters
            anthropic_params = {
                "model": params.model,
                "messages": formatted_messages,
                "max_tokens": params.max_tokens,
                "temperature": params.temperature,
                "top_p": params.top_p,
            }
            
            # Add system message as top-level parameter if present
            if system_message:
                anthropic_params["system"] = system_message
            
            if params.stop:
                anthropic_params["stop_sequences"] = params.stop
            
            # Make API call
            response = await self.client.messages.create(**anthropic_params)
            
            # Extract response data
            text_content = ""
            for content_block in response.content:
                if content_block.type == "text":
                    text_content += content_block.text
            
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
            
            return GenerationResponse(
                text=text_content,
                model=params.model,
                usage=usage,
                provider="anthropic",
                finish_reason=response.stop_reason
            )
            
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")
    
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
            
            # Prepare Anthropic-specific parameters
            anthropic_params = {
                "model": params.model,
                "messages": formatted_messages,
                "max_tokens": params.max_tokens,
                "temperature": params.temperature,
                "top_p": params.top_p,
                "stream": True
            }
            
            # Add system message as top-level parameter if present
            if system_message:
                anthropic_params["system"] = system_message
            
            if params.stop:
                anthropic_params["stop_sequences"] = params.stop
            
            # Make streaming API call
            stream = await self.client.messages.create(**anthropic_params)
            
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        yield event.delta.text
                        
        except Exception as e:
            raise Exception(f"Anthropic streaming error: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if Anthropic API is available."""
        return bool(self._api_key)


# Global instance
anthropic_provider = AnthropicProvider()
