"""Base classes for orchestration tools.

Provides the BundleTool interface that host applications implement
to create specialized tools for parallel agent execution with
statistical analysis.
"""

from typing import Dict, Any, List, Optional
from abc import abstractmethod
from pydantic import BaseModel, Field

from ..tool_registry import Tool
from ..models.evidence_bundle import EvidenceBundle


class BundleOptions(BaseModel):
    """Options for bundle tool execution."""
    
    # Replication settings
    k: int = Field(
        default=3,
        ge=2,
        le=10,
        description="Number of replicates to run"
    )
    
    seeds: Optional[List[int]] = Field(
        default=None,
        description="Random seeds for replicates (auto-generated if None)"
    )
    
    epsilon: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Early stop threshold for pairwise distance"
    )
    
    # Validation
    schema_uri: Optional[str] = Field(
        default=None,
        description="JSON schema URI for output validation"
    )
    
    # Resource limits
    per_replicate_budget: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Budget per replicate (tokens, ms)"
    )
    
    global_budget: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Global budget across all replicates"
    )
    
    # Bundle limits
    bundle_limits: Optional[Dict[str, int]] = Field(
        default=None,
        description="Limits for bundle size (max_fields, max_diffs, max_bytes)"
    )
    
    # Execution
    max_parallel: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum parallel replicates"
    )
    
    timeout_ms: Optional[int] = Field(
        default=None,
        description="Global timeout in milliseconds"
    )
    
    # Metadata
    trace_id: Optional[str] = Field(
        default=None,
        description="Trace ID for distributed tracing"
    )
    
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID for correlation"
    )


class BundleTool(Tool):
    """Base class for bundle tools that run parallel replicates.
    
    Bundle tools execute multiple sub-agents in parallel, validate outputs,
    compute statistical summaries (consensus, disagreements, distances),
    and return an Evidence Bundle for the orchestrator to consume.
    
    Host applications extend this class to implement domain-specific
    bundle tools (e.g., FeasibilityBundleTool, ScoringBundleTool).
    """
    
    @property
    def supports_early_stop(self) -> bool:
        """Whether this tool supports early stopping based on epsilon."""
        return True
    
    @property
    def supports_streaming(self) -> bool:
        """Whether this tool emits streaming events."""
        return True
    
    async def execute(
        self,
        request: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        event_manager: Optional[Any] = None
    ) -> EvidenceBundle:
        """Execute the bundle tool.
        
        This is the main entry point called by the orchestrator.
        
        Args:
            request: Input data for the tool
            options: Tool-specific options (will be parsed as BundleOptions)
            event_manager: Optional event manager for streaming
            
        Returns:
            EvidenceBundle with replicates and summary statistics
        """
        # Parse options
        bundle_options = BundleOptions(**(options or {}))
        
        # Validate request
        self.validate_request(request)
        
        # Generate seeds if not provided
        if bundle_options.seeds is None:
            bundle_options.seeds = self._generate_seeds(bundle_options.k)
        
        # Execute the tool logic
        return await self._execute_bundle(
            request,
            bundle_options,
            event_manager
        )
    
    @abstractmethod
    async def _execute_bundle(
        self,
        request: Dict[str, Any],
        options: BundleOptions,
        event_manager: Optional[Any] = None
    ) -> EvidenceBundle:
        """Execute the bundle tool logic.
        
        Subclasses implement this to:
        1. Run K replicates in parallel
        2. Validate outputs against schema
        3. Compute consensus, disagreements, distances
        4. Optionally early-stop based on epsilon
        5. Return Evidence Bundle
        
        Args:
            request: Validated input data
            options: Parsed bundle options
            event_manager: Optional event manager for streaming
            
        Returns:
            EvidenceBundle with results
        """
        pass
    
    def _generate_seeds(self, k: int) -> List[int]:
        """Generate deterministic seeds for replicates.
        
        Args:
            k: Number of seeds to generate
            
        Returns:
            List of k seeds
        """
        # Simple deterministic seed generation
        # Host apps can override for better strategies
        base_seeds = [11, 23, 47, 59, 71, 83, 97, 113, 127, 139]
        return base_seeds[:k]
    
    async def emit_event(
        self,
        event_manager: Optional[Any],
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """Emit a streaming event if event manager is provided.
        
        Args:
            event_manager: Event manager instance
            event_type: Type of event (e.g., "replicate_done")
            data: Event data
        """
        if event_manager is None:
            return
            
        # Add tool name to event metadata
        if "metadata" not in data:
            data["metadata"] = {}
        data["metadata"]["source"] = self.name
        data["metadata"]["tool_type"] = "bundle"
        
        # Emit based on event type
        # This is simplified - real implementation would use proper event types
        if hasattr(event_manager, "on_delta"):
            from ...models.events import StreamDeltaEvent
            await event_manager.on_delta(StreamDeltaEvent(
                delta={
                    "event_type": event_type,
                    "data": data
                },
                chunk_index=0,
                is_json=True,
                metadata=data["metadata"]
            ))