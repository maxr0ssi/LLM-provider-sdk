"""
Agent definition models for the Nexus agent framework.

Provides core models for defining agents, their options, and results.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Budget(BaseModel):
    """Budget constraints for agent execution."""
    model_config = ConfigDict(extra="forbid")
    
    tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens to use")
    ms: Optional[int] = Field(None, ge=1, description="Maximum milliseconds to run")


class Tool(BaseModel):
    """Tool definition for local deterministic functions."""
    model_config = ConfigDict(extra="forbid")
    
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description for LLM")
    parameters: Dict[str, Any] = Field(..., description="JSON schema for parameters")
    handler: Callable = Field(..., description="Python function to execute")
    deterministic: bool = Field(True, description="Whether tool is deterministic")


class AgentDefinition(BaseModel):
    """Definition of an agent with its configuration."""
    model_config = ConfigDict(extra="forbid")
    
    system: str = Field(..., description="System prompt")
    user_template: str = Field(..., description="User prompt template with {variables}")
    json_schema: Optional[Dict[str, Any]] = Field(None, description="Expected output JSON schema")
    model: str = Field(..., description="Model ID to use")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Model parameters")
    tools: Optional[List[Tool]] = Field(None, description="Available tools")
    version: str = Field("1.0", description="Agent version")


class AgentOptions(BaseModel):
    """Runtime options for agent execution."""
    model_config = ConfigDict(extra="forbid")
    
    streaming: bool = Field(False, description="Enable streaming")
    deterministic: bool = Field(False, description="Enable deterministic mode")
    budget: Optional[Budget] = Field(None, description="Execution budget")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for deduplication")
    trace_id: Optional[str] = Field(None, description="Trace ID for observability")
    
    # Streaming callbacks (will be set programmatically, not via JSON)
    on_start: Optional[Callable] = Field(None, exclude=True)
    on_delta: Optional[Callable] = Field(None, exclude=True)
    on_usage: Optional[Callable] = Field(None, exclude=True)
    on_complete: Optional[Callable] = Field(None, exclude=True)
    on_error: Optional[Callable] = Field(None, exclude=True)


class AgentResult(BaseModel):
    """Result from agent execution."""
    model_config = ConfigDict(extra="allow")  # Allow extra fields for provider metadata
    
    content: Any = Field(..., description="Result content (validated against json_schema if provided)")
    usage: Dict[str, Any] = Field(..., description="Token usage information")
    model: str = Field(..., description="Model used")
    elapsed_ms: int = Field(..., description="Execution time in milliseconds")
    provider_metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific metadata")
    trace_id: Optional[str] = Field(None, description="Trace ID for correlation")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")
    
    # Cost information
    cost_usd: Optional[float] = Field(None, description="Total cost in USD")
    cost_breakdown: Optional[Dict[str, float]] = Field(None, description="Cost breakdown by component")
    
    # Error information (for partial results)
    error: Optional[str] = Field(None, description="Error message if partial result")
    status: str = Field("complete", description="Result status: complete, partial, error")