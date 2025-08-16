"""Base classes for agent runtime adapters.

This module defines the abstract interface that all agent runtime
adapters must implement, along with normalized models for options
and results.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, ConfigDict

from ...agents.models.agent_definition import AgentDefinition
from ...streaming.manager import EventManager
from ...models.streaming import StreamingOptions


class AgentRunOptions(BaseModel):
    """Runtime options for agent execution across different runtimes."""
    model_config = ConfigDict(extra="allow")
    
    # Core options
    runtime: Optional[str] = Field(None, description="Runtime to use (e.g., 'openai_agents')")
    streaming: bool = Field(False, description="Enable streaming mode")
    deterministic: bool = Field(False, description="Enable deterministic mode")
    seed: Optional[int] = Field(None, description="Random seed for deterministic mode")
    
    # Schema options
    strict: Optional[bool] = Field(None, description="Enable strict schema validation")
    responses_use_instructions: bool = Field(False, description="Use instructions format for Responses API")
    
    # Budget constraints
    budget: Optional[Dict[str, int]] = Field(None, description="Token/time budget constraints")
    
    # Observability
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for deduplication")
    trace_id: Optional[str] = Field(None, description="Trace ID for correlation")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    # Streaming configuration
    streaming_options: Optional[StreamingOptions] = Field(None, description="Advanced streaming options")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific metadata")


@dataclass
class PreparedRun:
    """Prepared agent run state (provider-specific).
    
    This class holds the compiled agent state after preparation,
    which is specific to each runtime implementation.
    """
    runtime: str
    agent: Any  # Provider-specific agent object
    config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentRunResult(BaseModel):
    """Normalized result from agent execution."""
    model_config = ConfigDict(extra="allow")
    
    # Core result data
    content: Union[str, Dict[str, Any]] = Field(..., description="Result content")
    usage: Dict[str, Any] = Field(..., description="Token usage information")
    model: str = Field(..., description="Model used")
    elapsed_ms: int = Field(..., description="Execution time in milliseconds")
    
    # Provider information
    provider: str = Field(..., description="Provider name")
    runtime: str = Field(..., description="Runtime used")
    provider_metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific metadata")
    
    # Observability
    trace_id: Optional[str] = Field(None, description="Trace ID for correlation")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    
    # Optional fields
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")
    final_json: Optional[Dict[str, Any]] = Field(None, description="Final JSON if structured output")
    finish_reason: Optional[str] = Field(None, description="Completion reason")
    
    # Cost information
    cost_usd: Optional[float] = Field(None, description="Total cost in USD")
    cost_breakdown: Optional[Dict[str, float]] = Field(None, description="Cost breakdown")
    
    # Error information (for partial results)
    error: Optional[str] = Field(None, description="Error message if partial result")
    status: str = Field("complete", description="Result status: complete, partial, error")


class AgentRuntimeAdapter(ABC):
    """Abstract base class for agent runtime adapters.
    
    All runtime implementations must inherit from this class and
    implement the required methods.
    """
    
    @abstractmethod
    def supports_schema(self) -> bool:
        """Check if this runtime supports JSON schema enforcement."""
        pass
    
    @abstractmethod
    def supports_tools(self) -> bool:
        """Check if this runtime supports tool/function calling."""
        pass
    
    @abstractmethod
    async def prepare(
        self, 
        definition: AgentDefinition, 
        options: AgentRunOptions
    ) -> PreparedRun:
        """Prepare an agent for execution.
        
        This method compiles the agent definition into a runtime-specific
        format and applies any necessary configuration.
        
        Args:
            definition: Agent definition with prompts, schema, tools, etc.
            options: Runtime options including determinism, budgets, etc.
            
        Returns:
            PreparedRun with compiled agent state
        """
        pass
    
    @abstractmethod
    async def run(
        self, 
        prepared: PreparedRun, 
        variables: Dict[str, Any]
    ) -> AgentRunResult:
        """Execute a non-streaming agent run.
        
        Args:
            prepared: Prepared agent state from prepare()
            variables: Variables to substitute in user template
            
        Returns:
            Normalized AgentRunResult
        """
        pass
    
    @abstractmethod
    async def run_stream(
        self, 
        prepared: PreparedRun, 
        variables: Dict[str, Any],
        events: EventManager
    ) -> AsyncIterator[None]:
        """Execute a streaming agent run.
        
        This method yields nothing but emits events through the EventManager.
        
        Args:
            prepared: Prepared agent state from prepare()
            variables: Variables to substitute in user template
            events: EventManager for emitting streaming events
            
        Yields:
            None (events are emitted through EventManager)
        """
        pass
    
    async def close(self) -> None:
        """Clean up any resources held by this adapter.
        
        Default implementation does nothing. Override if cleanup needed.
        """
        pass