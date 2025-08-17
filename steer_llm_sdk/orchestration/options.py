"""Configuration options for orchestrator behavior."""

from typing import Optional, Dict, Any, Callable, Awaitable
from pydantic import BaseModel, Field, field_validator


class OrchestratorOptions(BaseModel):
    """Options for orchestrator execution."""
    
    # Concurrency control
    max_parallel: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of sub-agents to run in parallel"
    )
    
    # Resource budgets
    budget: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Resource budgets (ms, tokens, cost_usd)"
    )
    
    # Execution behavior
    deterministic: bool = Field(
        default=False,
        description="Enable deterministic execution (pass seed to agents)"
    )
    
    streaming: bool = Field(
        default=False,
        description="Enable streaming mode for sub-agents"
    )
    
    # Retry configuration
    retry_on_failure: bool = Field(
        default=True,
        description="Retry failed sub-agents if error is retryable"
    )
    
    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum retry attempts per sub-agent"
    )
    
    # Timeouts
    timeout_ms: Optional[int] = Field(
        default=None,
        ge=100,
        description="Global timeout in milliseconds"
    )
    
    per_agent_timeout_ms: Optional[int] = Field(
        default=None,
        ge=100,
        description="Timeout per sub-agent in milliseconds"
    )
    
    # Tracing and metadata
    trace_id: Optional[str] = Field(
        default=None,
        description="Trace ID for distributed tracing"
    )
    
    request_id: Optional[str] = Field(
        default=None,
        description="Unique request identifier"
    )
    
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Idempotency key for deduplication"
    )
    
    # Security
    redactor_cb: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = Field(
        default=None,
        description="Callback to redact sensitive data from events/logs"
    )
    
    # Metadata
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata to pass to sub-agents"
    )
    
    # M1 additions - Planning
    quality_requirements: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Quality requirements for planning (e.g., min_confidence)"
    )
    
    # M1 additions - Reliability
    enable_circuit_breaker: bool = Field(
        default=True,
        description="Enable circuit breaker protection"
    )
    
    enable_fallback: bool = Field(
        default=True,
        description="Enable fallback to alternative tools"
    )
    
    @field_validator('budget')
    def validate_budget(cls, v):
        """Validate budget structure."""
        if v is None:
            return v
            
        allowed_keys = {'ms', 'tokens', 'cost_usd'}
        invalid_keys = set(v.keys()) - allowed_keys
        if invalid_keys:
            raise ValueError(f"Invalid budget keys: {invalid_keys}. Allowed: {allowed_keys}")
            
        # Validate numeric values
        for key, value in v.items():
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"Budget '{key}' must be a positive number, got {value}")
                
        return v
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True  # For Callable type