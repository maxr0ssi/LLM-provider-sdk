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
from .tool_registry import get_global_registry
from .options import OrchestratorOptions
from .streaming import OrchestratorEventManager
from .models.evidence_bundle import EvidenceBundle
from .errors import BudgetExceeded, ConflictError, OrchestratorError


class OrchestratorResult(BaseModel):
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


class Orchestrator:
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
        self.registry = get_global_registry()
    
    async def run(
        self,
        request: Union[str, Dict[str, Any]],
        tool_name: str,
        tool_options: Optional[Dict[str, Any]] = None,
        options: Optional[OrchestratorOptions] = None,
        event_manager: Optional[EventManager] = None
    ) -> OrchestratorResult:
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
        options = options or OrchestratorOptions()
        
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
            await orch_events.emit_orchestrator_start(
                tool_name=tool_name,
                tool_version=tool.version,
                request_id=options.request_id
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
                await orch_events.emit_orchestrator_error(
                    tool_name=tool_name,
                    error=error_info,
                    elapsed_ms=elapsed_ms,
                    request_id=options.request_id
                )
            
            # Return error result
            return OrchestratorResult(
                content={"error": error_info},
                usage={},
                cost_usd=None,
                cost_breakdown={},
                elapsed_ms=elapsed_ms,
                per_agent={},
                status="failed",
                errors={tool_name: error_info},
                metadata={
                    'tool_name': tool_name,
                    'tool_version': tool.version,
                    'trace_id': options.trace_id,
                    'request_id': options.request_id,
                    'budget': options.budget
                }
            )
        
        # Process tool result
        content, usage, cost, metadata = self._process_tool_result(tool_result)
        
        # Check budget
        if options.budget:
            self._check_budget(options.budget, usage, cost, start_time)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        # Emit orchestration complete
        if options.streaming and event_manager:
            await orch_events.emit_orchestrator_complete(
                tool_name=tool_name,
                tool_version=tool.version,
                elapsed_ms=elapsed_ms,
                usage=usage,
                request_id=options.request_id
            )
        
        # Build final metadata
        final_metadata = {
            'tool_name': tool_name,
            'tool_version': tool.version,
            'trace_id': options.trace_id,
            'request_id': options.request_id,
            **metadata
        }
        
        # Add budget to metadata for auditability
        if options.budget:
            final_metadata['budget'] = options.budget
        
        return OrchestratorResult(
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
    
    def _process_tool_result(
        self,
        tool_result: Any
    ) -> tuple[Any, Dict[str, Any], Optional[float], Dict[str, Any]]:
        """Process result from a tool.
        
        Args:
            tool_result: Result from tool execution
            
        Returns:
            Tuple of (content, usage, cost, metadata)
        """
        # Handle Evidence Bundle
        if isinstance(tool_result, EvidenceBundle):
            # Extract content from Evidence Bundle
            content = {
                "evidence_bundle": {
                    "meta": tool_result.meta.model_dump(),
                    "replicates": [r.model_dump() for r in tool_result.replicates],
                    "summary": tool_result.summary.model_dump()
                }
            }
            
            usage = tool_result.usage_total or {}
            cost = tool_result.cost_total_usd
            
            metadata = {
                "bundle_meta": tool_result.meta.model_dump(),
                "replicate_count": len(tool_result.replicates),
                "confidence": tool_result.summary.confidence,
                "early_stopped": tool_result.meta.early_stopped
            }
            
            if tool_result.metadata:
                metadata.update(tool_result.metadata)
                
        # Handle dict results
        elif isinstance(tool_result, dict):
            content = tool_result
            usage = tool_result.get("usage", {})
            cost = tool_result.get("cost_usd")
            metadata = tool_result.get("metadata", {})
            
        # Handle string results
        elif isinstance(tool_result, str):
            content = tool_result
            usage = {}
            cost = None
            metadata = {}
            
        else:
            # Fallback for other types
            content = str(tool_result)
            usage = {}
            cost = None
            metadata = {"result_type": type(tool_result).__name__}
        
        return content, usage, cost, metadata
    
    
    def _check_budget(
        self,
        budget: Dict[str, Any],
        usage: Dict[str, Any],
        cost: Optional[float],
        start_time: float
    ) -> None:
        """Check if budget limits are exceeded.
        
        Args:
            budget: Budget configuration
            usage: Total usage
            cost: Total cost
            start_time: Start timestamp
            
        Raises:
            BudgetExceeded: If any budget limit is exceeded
        """
        # Check time budget
        if 'ms' in budget:
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > budget['ms']:
                raise BudgetExceeded('time', budget['ms'], elapsed_ms)
        
        # Check token budget
        if 'tokens' in budget:
            total_tokens = usage.get('total_tokens', 0)
            if total_tokens > budget['tokens']:
                raise BudgetExceeded('tokens', budget['tokens'], total_tokens)
        
        # Check cost budget
        if 'cost_usd' in budget and cost is not None:
            if cost > budget['cost_usd']:
                raise BudgetExceeded('cost', budget['cost_usd'], cost)
    
