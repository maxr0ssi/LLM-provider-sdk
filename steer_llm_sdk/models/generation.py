from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from enum import Enum


class ProviderType(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    XAI = "xai"


class GenerationParams(BaseModel):
    """
    Normalized generation parameters for all providers.
    
    This model defines the standard parameters that can be used across all providers.
    Provider adapters use the capability registry to map these parameters to
    provider-specific formats.
    """
    # Core parameters
    model: str = Field(..., description="Model identifier")
    max_tokens: int = Field(default=512, ge=1, le=50000, description="Maximum tokens to generate")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Nucleus sampling parameter")
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0, description="Presence penalty")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")
    
    # Structured output and determinism
    response_format: Optional[Dict[str, Any]] = Field(None, description="Response format (e.g., JSON schema)")
    seed: Optional[int] = Field(None, description="Random seed for deterministic generation")
    
    # New fields for Responses API and agent support
    responses_use_instructions: Optional[bool] = Field(
        None, 
        description="Map first system message to instructions field (Responses API)"
    )
    strict: Optional[bool] = Field(
        None,
        description="Enable strict schema adherence (Responses API)"
    )
    reasoning: Optional[Dict[str, Any]] = Field(
        None,
        description="Reasoning configuration (e.g., effort levels)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata (trace_id, idempotency_key, etc.)"
    )
    
    # Provider-specific parameters (kept for backward compatibility)
    top_k: Optional[int] = Field(None, ge=0, description="Top-k sampling (Anthropic)")
    logprobs: Optional[bool] = Field(None, description="Return log probabilities (OpenAI)")
    
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
    # Legacy blended pricing support for tests
    cost_per_1k_tokens: Optional[float] = None


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
