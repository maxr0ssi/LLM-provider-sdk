"""Reliability configuration and integration for orchestrator."""

from typing import Dict, Optional, List, Any, Callable, TypeVar
import asyncio
import logging
from dataclasses import dataclass, field

from ..reliability import (
    AdvancedRetryManager,
    RetryPolicy,
    CircuitBreakerManager,
    CircuitBreakerConfig,
    ErrorClassifier,
    ErrorCategory
)
from ..reliability.circuit_breaker import CircuitState
from ..providers.base import ProviderError
from .errors import OrchestratorError, ConflictError, ToolExecutionError
from .tool_registry import Tool

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class ReliabilityConfig:
    """Configuration for orchestrator reliability features."""
    
    # Retry configuration
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    
    # Circuit breaker configuration by provider
    circuit_breaker_configs: Dict[str, CircuitBreakerConfig] = field(
        default_factory=lambda: {
            "openai": CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60.0,
                window_size=300.0,
                success_threshold=2
            ),
            "anthropic": CircuitBreakerConfig(
                failure_threshold=3,
                timeout=120.0,
                window_size=300.0,
                success_threshold=1
            ),
            "xai": CircuitBreakerConfig(
                failure_threshold=4,
                timeout=90.0,
                window_size=300.0,
                success_threshold=2
            ),
            # Default for unknown providers
            "default": CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60.0,
                window_size=300.0,
                success_threshold=2
            )
        }
    )
    
    # Fallback configuration
    enable_fallback: bool = True
    max_fallback_attempts: int = 2
    
    # Global limits
    max_total_retry_time: float = 300.0  # 5 minutes
    max_total_attempts: int = 10  # Across all tools/fallbacks


class ReliableToolExecutor:
    """Executes tools with retry and circuit breaker logic."""
    
    def __init__(
        self,
        config: Optional[ReliabilityConfig] = None,
        retry_manager: Optional[AdvancedRetryManager] = None,
        circuit_breaker_manager: Optional[CircuitBreakerManager] = None
    ):
        """Initialize with reliability components."""
        self.config = config or ReliabilityConfig()
        self.retry_manager = retry_manager or AdvancedRetryManager()
        self.circuit_breaker_manager = circuit_breaker_manager or CircuitBreakerManager()
        self._provider_cache: Dict[str, str] = {}
    
    async def execute_with_reliability(
        self,
        tool: Tool,
        request: Dict[str, Any],
        options: Dict[str, Any],
        event_manager: Optional[Any] = None,
        fallback_tools: Optional[List[Tool]] = None
    ) -> Dict[str, Any]:
        """Execute tool with retry and circuit breaker protection.
        
        Args:
            tool: Primary tool to execute
            request: Request data
            options: Tool options
            event_manager: Optional event manager
            fallback_tools: Optional fallback tools to try
            
        Returns:
            Tool execution result
            
        Raises:
            OrchestratorError: If all attempts fail
        """
        primary_error = None
        total_attempts = 0
        
        # Try primary tool
        try:
            return await self._execute_single_tool(
                tool, request, options, event_manager
            )
        except Exception as e:
            primary_error = e
            total_attempts += self._get_retry_attempts(e)
            
            # If not retryable or fallback disabled, raise immediately
            if not self._is_retryable_error(e) or not self.config.enable_fallback:
                raise
        
        # Try fallback tools
        if fallback_tools and self.config.enable_fallback:
            for i, fallback_tool in enumerate(fallback_tools[:self.config.max_fallback_attempts]):
                if total_attempts >= self.config.max_total_attempts:
                    break
                    
                try:
                    logger.info(
                        f"Attempting fallback tool '{fallback_tool.name}' "
                        f"(fallback {i+1}/{min(len(fallback_tools), self.config.max_fallback_attempts)})"
                    )
                    
                    return await self._execute_single_tool(
                        fallback_tool, request, options, event_manager
                    )
                except Exception as e:
                    total_attempts += self._get_retry_attempts(e)
                    # Continue to next fallback
                    continue
        
        # All attempts failed
        raise OrchestratorError(
            f"All tool attempts failed. Primary error: {primary_error}"
        )
    
    async def _execute_single_tool(
        self,
        tool: Tool,
        request: Dict[str, Any],
        options: Dict[str, Any],
        event_manager: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Execute a single tool with retry and circuit breaker."""
        # Get provider from tool response or metadata
        provider = self._get_tool_provider(tool, options)
        
        # Check circuit breaker
        breaker_key = f"{provider}:{tool.name}"
        breaker = self._get_or_create_breaker(breaker_key, provider)
        
        # Execute with retry and circuit breaker
        async def execute_with_breaker():
            # The circuit breaker's call method will handle state checking
            # and success/failure recording automatically
            async def execute_fn():
                result = await tool.execute(request, options, event_manager)
                
                # Extract provider from result if available
                if isinstance(result, dict) and "provider" in result:
                    self._update_tool_provider_mapping(tool.name, result["provider"])
                
                return result
            
            # Use circuit breaker's call method
            return await breaker.call(execute_fn)
        
        # Wrap in retry logic
        async def retry_wrapper():
            try:
                return await execute_with_breaker()
            except Exception as e:
                # Classify error
                category = self._classify_error(e)
                
                # Determine if retryable based on category
                if self.config.retry_policy.should_retry_category(category):
                    raise
                else:
                    # Non-retryable error
                    raise ToolExecutionError(
                        tool.name,
                        e,
                        is_retryable=False,
                        metadata={"error_category": category.value}
                    ) from e
        
        # Apply retry logic
        return await self.retry_manager.execute_with_retry(
            retry_wrapper,
            request_id=options.get('request_id', f'{tool.name}_{id(request)}'),
            provider=provider,
            policy=self.config.retry_policy
        )
    
    def _get_tool_provider(self, tool: Tool, options: Dict[str, Any]) -> str:
        """Determine provider for a tool."""
        # Check if tool has provider metadata
        if hasattr(tool, "provider"):
            return tool.provider
        
        # Check if specified in options
        if "provider" in options:
            return options["provider"]
        
        # Check if we have a cached mapping
        provider = self._provider_cache.get(tool.name)
        if provider:
            return provider
        
        # Default to tool name as provider (will use default breaker config)
        return "default"
    
    def _get_or_create_breaker(self, key: str, provider: str) -> Any:
        """Get or create circuit breaker for key."""
        config = self.config.circuit_breaker_configs.get(
            provider,
            self.config.circuit_breaker_configs["default"]
        )
        
        return self.circuit_breaker_manager.get_or_create(key, config)
    
    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify error using error classifier."""
        if isinstance(error, ProviderError):
            classification = ErrorClassifier.classify_error(
                error,
                error.provider
            )
            return classification.category
        else:
            # Generic classification - use "unknown" provider
            classification = ErrorClassifier.classify_error(
                error,
                "unknown"
            )
            return classification.category
    
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Quick check if error is potentially retryable."""
        if hasattr(error, "is_retryable"):
            return error.is_retryable
        
        category = self._classify_error(error)
        return self.config.retry_policy.should_retry_category(category)
    
    def _get_retry_attempts(self, error: Exception) -> int:
        """Get number of retry attempts from error."""
        if hasattr(error, "retry_state") and error.retry_state:
            return error.retry_state.attempts
        return 1
    
    def _update_tool_provider_mapping(self, tool_name: str, provider: str):
        """Update cached tool to provider mapping."""
        self._provider_cache[tool_name] = provider