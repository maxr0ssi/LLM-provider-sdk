"""Main orchestrator for tool-based execution.

The orchestrator coordinates execution through registered tools rather
than directly calling sub-agents. This enables rich domain-specific
logic while keeping the SDK neutral.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

from ..streaming.manager import EventManager
from .base import BaseOrchestrator
from .tool_registry import get_global_registry
from .options import OrchestrationConfig
from .streaming import OrchestratorEventManager
from .models.evidence_bundle import EvidenceBundle
from .errors import BudgetExceeded, ConflictError, OrchestratorError


class OrchestrationOutput(BaseModel):
    """Result from orchestrator execution."""
    
    content: Union[str, Dict[str, Any]] = Field(
        ...,
        description="Merged content from all sub-agents"
    )
    
    usage: Dict[str, Any] = Field(
        default_factory=dict,
        description="Total usage across all sub-agents"
    )
    
    cost_usd: Optional[float] = Field(
        default=None,
        description="Total cost in USD"
    )
    
    cost_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by sub-agent"
    )
    
    elapsed_ms: int = Field(
        ...,
        description="Total elapsed time in milliseconds"
    )
    
    per_agent: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Results and metadata per sub-agent"
    )
    
    status: str = Field(
        default="succeeded",
        description="Overall status: succeeded, partial, failed"
    )
    
    errors: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Errors by sub-agent name"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class Orchestrator(BaseOrchestrator):
    """Orchestrates execution through registered tools.
    
    The orchestrator is responsible for:
    1. Selecting appropriate tools based on the request
    2. Invoking tools with proper options
    3. Handling tool results (e.g., Evidence Bundles)
    4. Managing streaming events from tools
    5. Enforcing budgets and timeouts
    """
    
    def __init__(self):
        """Initialize orchestrator."""
        super().__init__()
        self.registry = get_global_registry()
    
    async def run(
        self,
        request: Union[str, Dict[str, Any]],
        tool_name: str,
        tool_options: Optional[Dict[str, Any]] = None,
        options: Optional[OrchestrationConfig] = None,
        event_manager: Optional[EventManager] = None
    ) -> OrchestrationOutput:
        """Execute a tool and return the result.
        
        Args:
            request: Request data (string or dict)
            tool_name: Name of the registered tool to execute
            tool_options: Tool-specific options
            options: Orchestration options
            event_manager: Optional event manager for streaming
            
        Returns:
            OrchestratorResult with tool output
            
        Raises:
            ValueError: If tool not found
            BudgetExceeded: If resource budget is exceeded
            ConflictError: If idempotency conflict occurs
        """
        start_time = time.time()
        options = options or OrchestrationConfig()
        
        # Get the tool
        tool = self.registry.get_tool(tool_name)
        if not tool:
            raise ValueError(
                f"Tool '{tool_name}' not found. "
                f"Available tools: {list(self.registry.list_tools().keys())}"
            )
        
        # Setup event management
        orch_events = OrchestratorEventManager(event_manager, options.redactor_cb)
        
        # Emit orchestration start
        if options.streaming and event_manager:
            await self._emit_start_event(
                orch_events, tool_name, tool.version, options.request_id
            )
        
        # Prepare request
        if isinstance(request, str):
            request_dict = {"query": request}
        else:
            request_dict = request
        
        # Merge tool options with orchestrator options
        merged_tool_options = {
            **(tool_options or {}),
            "max_parallel": options.max_parallel,
            "trace_id": options.trace_id,
            "request_id": options.request_id,
        }
        
        # Add budget if specified
        if options.budget:
            merged_tool_options["global_budget"] = options.budget
        
        # Add timeout if specified
        if options.timeout_ms:
            merged_tool_options["timeout_ms"] = options.timeout_ms
        
        # Execute the tool
        try:
            # Apply global timeout if configured
            if options.timeout_ms:
                tool_result = await asyncio.wait_for(
                    tool.execute(
                        request_dict,
                        merged_tool_options,
                        orch_events.create_tool_manager(tool_name) if options.streaming else None
                    ),
                    timeout=options.timeout_ms / 1000.0
                )
            else:
                tool_result = await tool.execute(
                    request_dict,
                    merged_tool_options,
                    orch_events.create_tool_manager(tool_name) if options.streaming else None
                )
                
        except asyncio.TimeoutError:
            raise BudgetExceeded(
                'time',
                options.timeout_ms,
                int((time.time() - start_time) * 1000),
                affected_agents=[tool_name]
            )
        except Exception as e:
            # Wrap tool errors
            error_info = {
                'type': type(e).__name__,
                'message': str(e),
                'code': getattr(e, 'code', 'TOOL_ERROR'),
                'is_retryable': getattr(e, 'is_retryable', False)
            }
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # Emit error event
            if options.streaming and event_manager:
                await self._emit_error_event(
                    orch_events, tool_name, e, elapsed_ms, options.request_id
                )
            
            # Return error result
            return OrchestrationOutput(
                content={"error": error_info},
                usage={},
                cost_usd=None,
                cost_breakdown={},
                elapsed_ms=elapsed_ms,
                per_agent={},
                status="failed",
                errors={tool_name: error_info},
                metadata=self._build_metadata(tool_name, tool.version, options)
            )
        
        # Process tool result
        content, usage, cost, metadata = self._process_tool_result(tool_result)
        
        # Check budget
        if options.budget:
            self._check_budget(options.budget, usage, cost, start_time)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Emit orchestration complete
        if options.streaming and event_manager:
            await self._emit_complete_event(
                orch_events, tool_name, tool.version, elapsed_ms, usage, options.request_id
            )
        
        # Build final metadata
        final_metadata = self._build_metadata(
            tool_name, tool.version, options, metadata
        )
        
        return OrchestrationOutput(
            content=content,
            usage=usage,
            cost_usd=cost,
            cost_breakdown={},  # Tools handle their own breakdown
            elapsed_ms=elapsed_ms,
            per_agent={},  # Tools handle per-replicate data
            status="succeeded",
            errors=None,
            metadata=final_metadata
        )
    
