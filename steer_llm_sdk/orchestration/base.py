"""Base orchestrator functionality shared between implementations."""

import time
from typing import Dict, Any, Optional, Tuple, Union
import logging
from pydantic import BaseModel

from .models.evidence_bundle import EvidenceBundle
from .errors import BudgetExceeded
from .streaming import OrchestratorEventManager

logger = logging.getLogger(__name__)


class BaseOrchestrator:
    """Base class with shared orchestrator functionality."""
    
    def __init__(self):
        """Initialize base orchestrator."""
        # Subclasses should set self.registry
    
    def _process_tool_result(
        self,
        tool_result: Any
    ) -> Tuple[Any, Dict[str, Any], Optional[float], Dict[str, Any]]:
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
            
            # Use total usage from bundle
            usage = tool_result.usage_total or {}
            
            # Use total cost from bundle
            cost = tool_result.cost_total_usd
            
            # Extract metadata
            metadata = {
                "bundle_meta": tool_result.meta.model_dump()
            }
            
            return content, usage, cost, metadata
            
        # Handle dictionary result (backward compatibility)
        elif isinstance(tool_result, dict):
            content = tool_result.get("content", tool_result)
            usage = tool_result.get("usage", {})
            cost = tool_result.get("cost_usd")
            metadata = tool_result.get("metadata", {})
            
            return content, usage, cost, metadata
            
        # Handle BaseModel result
        elif isinstance(tool_result, BaseModel):
            result_dict = tool_result.model_dump()
            content = result_dict.get("content", result_dict)
            usage = result_dict.get("usage", {})
            cost = result_dict.get("cost_usd")
            metadata = result_dict.get("metadata", {})
            
            return content, usage, cost, metadata
            
        # Handle other types
        else:
            return tool_result, {}, None, {}
    
    def _check_budget(
        self,
        budget: Dict[str, Any],
        usage: Dict[str, Any],
        cost: Optional[float],
        start_time: float
    ) -> None:
        """Check if execution exceeded budget.
        
        Args:
            budget: Budget constraints
            usage: Actual usage
            cost: Actual cost
            start_time: Start time for elapsed calculation
            
        Raises:
            BudgetExceeded: If any budget constraint is exceeded
        """
        violations = []
        
        # Check token budget
        if "tokens" in budget:
            total_tokens = usage.get("total_tokens", 0)
            if total_tokens > budget["tokens"]:
                violations.append(
                    f"Token budget exceeded: {total_tokens} > {budget['tokens']}"
                )
        
        # Check cost budget
        if "cost_usd" in budget and cost is not None:
            if cost > budget["cost_usd"]:
                violations.append(
                    f"Cost budget exceeded: ${cost:.4f} > ${budget['cost_usd']:.4f}"
                )
        
        # Check time budget
        if "ms" in budget:
            elapsed_ms = int((time.time() - start_time) * 1000)
            if elapsed_ms > budget["ms"]:
                violations.append(
                    f"Time budget exceeded: {elapsed_ms}ms > {budget['ms']}ms"
                )
        
        if violations:
            raise BudgetExceeded(
                f"Budget exceeded: {'; '.join(violations)}",
                budget=budget,
                actual={
                    "tokens": usage.get("total_tokens", 0),
                    "cost_usd": cost,
                    "ms": int((time.time() - start_time) * 1000)
                }
            )
    
    async def _emit_start_event(
        self,
        orch_events: OrchestratorEventManager,
        tool_name: str,
        tool_version: str,
        request_id: Optional[str] = None
    ) -> None:
        """Emit orchestrator start event."""
        await orch_events.emit_orchestrator_start(
            tool_name=tool_name,
            tool_version=tool_version,
            request_id=request_id
        )
    
    async def _emit_complete_event(
        self,
        orch_events: OrchestratorEventManager,
        tool_name: str,
        tool_version: str,
        elapsed_ms: int,
        usage: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> None:
        """Emit orchestrator complete event."""
        await orch_events.emit_orchestrator_complete(
            tool_name=tool_name,
            tool_version=tool_version,
            elapsed_ms=elapsed_ms,
            usage=usage,
            request_id=request_id
        )
    
    async def _emit_error_event(
        self,
        orch_events: OrchestratorEventManager,
        tool_name: str,
        error: Exception,
        elapsed_ms: int,
        request_id: Optional[str] = None
    ) -> None:
        """Emit orchestrator error event."""
        await orch_events.emit_orchestrator_error(
            tool_name=tool_name,
            error=error,
            elapsed_ms=elapsed_ms,
            request_id=request_id
        )
    
    def _build_metadata(
        self,
        tool_name: str,
        tool_version: str,
        options: Any,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build standard metadata for results."""
        metadata = {
            'tool_name': tool_name,
            'tool_version': tool_version
        }
        
        # Add tracing IDs if available
        if hasattr(options, 'trace_id') and options.trace_id:
            metadata['trace_id'] = options.trace_id
        if hasattr(options, 'request_id') and options.request_id:
            metadata['request_id'] = options.request_id
            
        # Add budget if available
        if hasattr(options, 'budget') and options.budget:
            metadata['budget'] = options.budget
            
        # Add extra metadata
        if extra_metadata:
            metadata.update(extra_metadata)
            
        return metadata