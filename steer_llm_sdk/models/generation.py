from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from enum import Enum


class ProviderType(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    XAI = "xai"


class GenerationParams(BaseModel):
    """Normalized generation parameters for all providers."""
    model: str
    max_tokens: int = Field(default=512, ge=1, le=50000)  # Increased limit
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    stop: Optional[List[str]] = None
    # Additional parameters that providers might use
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None
    
    class Config:
        extra = "allow"  # Allow additional fields to pass through
    
    @field_validator('max_tokens')
    def validate_max_tokens(cls, v):
        return min(max(v, 1), 16384)  # Increased limit
    
    @field_validator('temperature')
    def validate_temperature(cls, v):
        return min(max(v, 0.0), 2.0)


class ModelConfig(BaseModel):
    """Model configuration schema."""
    name: str
    display_name: str
    provider: ProviderType
    llm_model_id: str
    description: str
    max_tokens: int = 4096
    temperature: float = 0.7
    enabled: bool = True
    context_length: Optional[int] = None
    requires_local: bool = False
    requires_llama: bool = False
    llm_model_size: Optional[str] = None
    input_cost_per_1k_tokens: Optional[float] = None
    output_cost_per_1k_tokens: Optional[float] = None
    cached_input_cost_per_1k_tokens: Optional[float] = None


class GenerationRequest(BaseModel):
    """Request model for generation."""
    prompt: str
    llm_model_id: str = "GPT-4o Mini"
    params: Dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


class GenerationResponse(BaseModel):
    """Response model for generation."""
    text: str
    model: str
    usage: Dict[str, Any]  # Changed from Dict[str, int] to allow cache_info dict
    cost_usd: Optional[float] = None
    cost_breakdown: Optional[Dict[str, float]] = None  # {"input_cost": 0.001, "output_cost": 0.002, "cache_savings": 0.0005}
    provider: str
    finish_reason: Optional[str] = None


class StreamingResponseWithUsage:
    """Wrapper for streaming responses that can also return usage data."""
    
    def __init__(self):
        self.chunks = []
        self.usage = None
        self.model = None
        self.provider = None
        self.finish_reason = None
        self.cost_usd = None
        self.cost_breakdown = None
    
    def add_chunk(self, chunk: str):
        """Add a chunk to the response."""
        self.chunks.append(chunk)
    
    def set_usage(self, usage: Dict[str, Any], model: str, provider: str, 
                   finish_reason: Optional[str] = None, cost_usd: Optional[float] = None,
                   cost_breakdown: Optional[Dict[str, float]] = None):
        """Set the usage data after streaming completes."""
        self.usage = usage
        self.model = model
        self.provider = provider
        self.finish_reason = finish_reason
        self.cost_usd = cost_usd
        self.cost_breakdown = cost_breakdown
    
    def get_text(self) -> str:
        """Get the complete text from all chunks."""
        return ''.join(self.chunks)
    
    def __iter__(self):
        """Allow iteration over chunks."""
        return iter(self.chunks)
    
    async def __aiter__(self):
        """Allow async iteration over chunks."""
        for chunk in self.chunks:
            yield chunk
