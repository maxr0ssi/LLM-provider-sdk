"""Orchestration-specific error definitions."""

from typing import Optional, Dict, Any, List


class OrchestratorError(Exception):
    """Base exception for orchestration errors."""
    pass


class ToolExecutionError(OrchestratorError):
    """Exception raised when a tool execution fails."""
    
    def __init__(
        self,
        tool_name: str,
        original_error: Exception,
        is_retryable: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.tool_name = tool_name
        self.original_error = original_error
        self.is_retryable = is_retryable
        self.metadata = metadata or {}
        
        message = f"Tool '{tool_name}' failed: {str(original_error)}"
        super().__init__(message)


class BudgetExceeded(OrchestratorError):
    """Exception raised when resource budget is exceeded."""
    
    def __init__(
        self,
        budget_type: str,  # "time", "tokens", "cost"
        limit: float,
        actual: float,
        affected_agents: Optional[List[str]] = None
    ):
        self.budget_type = budget_type
        self.limit = limit
        self.actual = actual
        self.affected_agents = affected_agents or []
        
        message = f"Budget exceeded: {budget_type} limit {limit}, actual {actual}"
        if affected_agents:
            message += f" (affected agents: {', '.join(affected_agents)})"
        super().__init__(message)


class ConflictError(OrchestratorError):
    """Exception raised for idempotency conflicts."""
    
    def __init__(
        self,
        idempotency_key: str,
        message: str = "Request with same key but different payload already exists"
    ):
        self.idempotency_key = idempotency_key
        super().__init__(f"Idempotency conflict for key '{idempotency_key}': {message}")


class MergeError(OrchestratorError):
    """Exception raised when result merging fails."""
    
    def __init__(
        self,
        merge_strategy: str,
        reason: str,
        agent_results: Optional[Dict[str, Any]] = None
    ):
        self.merge_strategy = merge_strategy
        self.reason = reason
        self.agent_results = agent_results or {}
        
        message = f"Failed to merge results using {merge_strategy}: {reason}"
        super().__init__(message)