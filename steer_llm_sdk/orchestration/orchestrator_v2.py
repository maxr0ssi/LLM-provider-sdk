"""Enhanced orchestrator with planning and reliability features (M1).

This module extends the base orchestrator with:
- Automatic tool selection via planner
- Retry and circuit breaker integration
- Idempotency support
- Trace context propagation
"""

import asyncio
import logging
import time
import uuid
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

from ..streaming.manager import EventManager
from ..reliability.idempotency import IdempotencyManager
from .orchestrator import Orchestrator, OrchestratorResult
from .tool_registry import get_global_registry
from .options import OrchestratorOptions
from .streaming import OrchestratorEventManager
from .models.evidence_bundle import EvidenceBundle
from .errors import BudgetExceeded, ConflictError, OrchestratorError
from .planning import (
    Planner,
    PlanningContext,
    PlanningResult,
    RuleBasedPlanner
)
from .reliability import (
    OrchestratorReliabilityConfig,
    ReliableToolExecutor
)


class EnhancedOrchestrator(Orchestrator):
    """Orchestrator with planning and reliability features.
    
    This extends the base orchestrator with M1 features:
    - Automatic tool selection using a planner
    - Retry logic with exponential backoff
    - Circuit breaker protection per provider
    - Idempotency support
    - Request/trace ID propagation
    """
    
    def __init__(
        self,
        planner: Optional[Planner] = None,
        reliability_config: Optional[OrchestratorReliabilityConfig] = None,
        idempotency_manager: Optional[IdempotencyManager] = None
    ):
        """Initialize enhanced orchestrator.
        
        Args:
            planner: Tool selection planner (defaults to RuleBasedPlanner)
            reliability_config: Reliability configuration
            idempotency_manager: Idempotency manager (defaults to in-memory)
        """
        super().__init__()
        
        # Planning
        self.planner = planner or RuleBasedPlanner()
        
        # Reliability
        self.reliability_config = reliability_config or OrchestratorReliabilityConfig()
        self.reliable_executor = ReliableToolExecutor(self.reliability_config)
        
        # Idempotency
        self.idempotency_manager = idempotency_manager or IdempotencyManager()
    
    async def run(
        self,
        request: Union[str, Dict[str, Any]],
        tool_name: Optional[str] = None,
        tool_options: Optional[Dict[str, Any]] = None,
        options: Optional[OrchestratorOptions] = None,
        event_manager: Optional[EventManager] = None
    ) -> OrchestratorResult:
        """Execute with planning and reliability.
        
        Args:
            request: Request data (string or dict)
            tool_name: Optional tool name (if not provided, planner selects)
            tool_options: Tool-specific options
            options: Orchestration options
            event_manager: Optional event manager for streaming
            
        Returns:
            OrchestratorResult with tool output
            
        Raises:
            ValueError: If no suitable tool can be found
            BudgetExceeded: If resource budget is exceeded
            ConflictError: If idempotency conflict occurs
        """
        start_time = time.time()
        options = options or OrchestratorOptions()
        
        # Generate IDs if not provided
        if not options.request_id:
            options.request_id = str(uuid.uuid4())
        if not options.trace_id:
            options.trace_id = options.request_id
        
        # Check idempotency
        if options.idempotency_key:
            try:
                cached_result = await self.idempotency_manager.get(
                    options.idempotency_key
                )
                if cached_result:
                    # Verify payload matches
                    if cached_result.get("request") != request:
                        raise ConflictError(
                            f"Idempotency key '{options.idempotency_key}' "
                            "used with different request"
                        )
                    return cached_result["result"]
            except Exception as e:
                if not isinstance(e, ConflictError):
                    # Log but continue if idempotency check fails
                    logger.warning(f"Idempotency check failed: {e}")
        
        # Prepare request dict
        if isinstance(request, str):
            request_dict = {"query": request}
        else:
            request_dict = request
        
        # Add options to request for planner
        request_dict["options"] = {
            "budget": options.budget,
            "quality": options.quality_requirements
        }
        
        # Plan tool execution
        if not tool_name:
            planning_result = await self._plan_execution(
                request_dict, options
            )
            tool_name = planning_result.selected_tool
            
            # Merge planned options with provided options
            if tool_options:
                tool_options.update(planning_result.tool_options)
            else:
                tool_options = planning_result.tool_options
            
            # Extract fallback tools
            fallback_tool_names = planning_result.fallback_tools
        else:
            # Manual tool selection, no fallbacks
            fallback_tool_names = []
        
        # Get tools
        tool = self.registry.get_tool(tool_name)
        if not tool:
            raise ValueError(
                f"Tool '{tool_name}' not found. "
                f"Available tools: {list(self.registry.list_tools().keys())}"
            )
        
        fallback_tools = [
            self.registry.get_tool(name)
            for name in fallback_tool_names
            if self.registry.has_tool(name)
        ]
        
        # Setup event management
        orch_events = OrchestratorEventManager(event_manager, options.redactor_cb)
        
        # Emit orchestration start
        if options.streaming and event_manager:
            await orch_events.emit_orchestrator_start(
                tool_name=tool_name,
                tool_version=tool.version,
                request_id=options.request_id
            )
        
        # Merge tool options with orchestrator options
        merged_tool_options = {
            **(tool_options or {}),
            "max_parallel": options.max_parallel,
            "trace_id": options.trace_id,
            "request_id": options.request_id,
        }
        
        # Add idempotency key for tool
        if options.idempotency_key:
            merged_tool_options["idempotency_key"] = f"{options.idempotency_key}:{tool_name}"
        
        # Add budget if specified
        if options.budget:
            merged_tool_options["global_budget"] = options.budget
        
        # Add timeout if specified
        if options.timeout_ms:
            merged_tool_options["timeout_ms"] = options.timeout_ms
        
        # Execute with reliability
        try:
            # Execute tool with retry and circuit breaker
            tool_result = await self.reliable_executor.execute_with_reliability(
                tool=tool,
                request=request_dict,
                options=merged_tool_options,
                event_manager=orch_events.create_tool_manager(tool_name) if options.streaming else None,
                fallback_tools=fallback_tools
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
        
        # Build result
        result = OrchestratorResult(
            content=content,
            usage=usage,
            cost_usd=cost,
            cost_breakdown={tool_name: cost} if cost else {},
            elapsed_ms=elapsed_ms,
            per_agent={tool_name: {"content": content, "usage": usage}},
            status="succeeded",
            errors=None,
            metadata=final_metadata
        )
        
        # Store in idempotency cache
        if options.idempotency_key:
            try:
                await self.idempotency_manager.store(
                    options.idempotency_key,
                    {
                        "request": request,
                        "result": result
                    }
                )
            except Exception as e:
                # Log but don't fail if cache store fails
                logger.warning(f"Failed to store idempotency result: {e}")
        
        return result
    
    async def _plan_execution(
        self,
        request: Dict[str, Any],
        options: OrchestratorOptions
    ) -> PlanningResult:
        """Plan tool execution using the planner.
        
        Args:
            request: Request data
            options: Orchestration options
            
        Returns:
            PlanningResult with selected tool and options
        """
        # Build planning context
        context = PlanningContext(
            budget=options.budget,
            quality_requirements=options.quality_requirements,
            # Get circuit breaker states
            circuit_breaker_states=self._get_circuit_breaker_states()
        )
        
        # Get available tools metadata
        tool_metadata = self.registry.get_tool_metadata()
        
        # Plan execution
        return await self.planner.plan(
            request=request,
            available_tools=tool_metadata,
            context=context
        )
    
    def _get_circuit_breaker_states(self) -> Dict[str, str]:
        """Get current circuit breaker states for planning.
        
        Returns:
            Dict mapping tool/provider names to breaker states
        """
        states = {}
        
        # Get all breakers from the manager
        breakers = self.reliable_executor.circuit_breaker_manager.get_all_breakers()
        
        for key, breaker in breakers.items():
            states[key] = breaker.state.value
        
        return states