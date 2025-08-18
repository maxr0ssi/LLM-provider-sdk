"""Core planner interface and models for tool selection."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class ExecutionStrategy(str, Enum):
    """Strategy for tool execution."""
    SINGLE = "single"  # Execute one tool
    CHAIN = "chain"    # Execute tools in sequence
    PARALLEL = "parallel"  # Execute tools in parallel (future)
    CONDITIONAL = "conditional"  # Execute based on conditions (future)


class ToolMetadata(BaseModel):
    """Metadata about a registered tool."""
    name: str
    version: str
    description: Optional[str] = None
    supported_models: List[str] = Field(default_factory=list)
    default_options: Dict[str, Any] = Field(default_factory=dict)
    capabilities: List[str] = Field(default_factory=list)
    resource_requirements: Dict[str, Any] = Field(default_factory=dict)


class PlanRequest(BaseModel):
    """Context information for planning decisions."""
    budget: Optional[Dict[str, Any]] = None
    quality_requirements: Optional[Dict[str, Any]] = None
    previous_failures: List[str] = Field(default_factory=list)
    circuit_breaker_states: Dict[str, str] = Field(default_factory=dict)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


class PlanDecision(BaseModel):
    """Result of planning process."""
    selected_tool: str
    tool_options: Dict[str, Any] = Field(default_factory=dict)
    fallback_tools: List[str] = Field(default_factory=list)
    execution_strategy: ExecutionStrategy = ExecutionStrategy.SINGLE
    estimated_cost: Optional[float] = None
    estimated_duration_ms: Optional[int] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Planner(ABC):
    """Abstract base class for planners that select and configure tools."""
    
    @abstractmethod
    async def plan(
        self,
        request: Dict[str, Any],
        available_tools: Dict[str, ToolMetadata],
        context: Optional[PlanRequest] = None
    ) -> PlanDecision:
        """
        Plan which tool(s) to execute based on the request.
        
        Args:
            request: The incoming request to process
            available_tools: Dictionary of tool name -> metadata
            context: Optional context for planning decisions
            
        Returns:
            PlanningResult with selected tool and configuration
            
        Raises:
            ValueError: If no suitable tool can be found
        """
        pass
    
    def validate_tool_availability(
        self,
        tool_name: str,
        available_tools: Dict[str, ToolMetadata]
    ) -> bool:
        """Check if a tool is available and ready."""
        if tool_name not in available_tools:
            return False
            
        # Could add additional checks here:
        # - Check circuit breaker state
        # - Check resource availability
        # - Check model compatibility
        
        return True
    
    def estimate_cost(
        self,
        tool_name: str,
        tool_options: Dict[str, Any],
        tool_metadata: ToolMetadata
    ) -> Optional[float]:
        """Estimate the cost of running a tool with given options."""
        # Default implementation - can be overridden
        if "estimated_cost_per_run" in tool_metadata.resource_requirements:
            base_cost = tool_metadata.resource_requirements["estimated_cost_per_run"]
            
            # Adjust for k replicates if specified
            k = tool_options.get("k", 1)
            return base_cost * k
            
        return None
    
    def estimate_duration(
        self,
        tool_name: str,
        tool_options: Dict[str, Any],
        tool_metadata: ToolMetadata
    ) -> Optional[int]:
        """Estimate the duration of running a tool with given options."""
        # Default implementation - can be overridden
        if "estimated_duration_ms" in tool_metadata.resource_requirements:
            base_duration = tool_metadata.resource_requirements["estimated_duration_ms"]
            
            # Adjust for k replicates if specified (assuming some parallelism)
            k = tool_options.get("k", 1)
            parallelism = tool_options.get("max_parallel", 10)
            
            if k <= parallelism:
                return base_duration
            else:
                # Simple estimation: batches of parallel execution
                batches = (k + parallelism - 1) // parallelism
                return base_duration * batches
                
        return None