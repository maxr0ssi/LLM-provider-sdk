"""Streaming event management for orchestration."""

from typing import Optional, Dict, Any, Callable, Awaitable
from ..streaming.manager import EventManager
from ..models.events import (
    StreamStartEvent,
    StreamDeltaEvent,
    StreamUsageEvent,
    StreamCompleteEvent,
    StreamErrorEvent
)


class OrchestratorEventManager:
    """Wraps EventManager to add source tagging for orchestration."""
    
    def __init__(
        self,
        base_manager: Optional[EventManager] = None,
        redactor_cb: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    ):
        """Initialize orchestrator event manager.
        
        Args:
            base_manager: Base EventManager to wrap (creates new if None)
            redactor_cb: Optional callback to redact sensitive data
        """
        self.base_manager = base_manager or EventManager()
        self.redactor_cb = redactor_cb
    
    def create_tool_manager(
        self,
        tool_name: str,
        tool_version: Optional[str] = None
    ) -> EventManager:
        """Create an EventManager for a specific tool.
        
        Args:
            tool_name: Name of the tool
            tool_version: Tool version (optional)
            
        Returns:
            EventManager that tags all events with tool source
        """
        # Create wrapper callbacks that add source tagging
        async def on_start_wrapper(event: StreamStartEvent) -> None:
            # Add source to metadata
            event.metadata = event.metadata or {}
            event.metadata['source'] = tool_name
            event.metadata['tool_type'] = 'bundle'
            if tool_version:
                event.metadata['tool_version'] = tool_version
            
            # Apply redaction if configured
            if self.redactor_cb:
                event.metadata = self.redactor_cb(event.metadata)
            
            # Forward to base manager
            if self.base_manager.on_start:
                await self.base_manager.on_start(event)
        
        async def on_delta_wrapper(event: StreamDeltaEvent) -> None:
            # Add source to metadata
            event.metadata = event.metadata or {}
            event.metadata['source'] = tool_name
            
            # Handle tool-specific events
            if isinstance(event.delta, dict) and 'event_type' in event.delta:
                event.metadata['event_type'] = event.delta['event_type']
            
            # Apply redaction if configured
            if self.redactor_cb:
                event.metadata = self.redactor_cb(event.metadata)
                # Also redact delta content if it's a dict
                if isinstance(event.delta, dict):
                    event.delta = self.redactor_cb(event.delta)
            
            # Forward to base manager
            if self.base_manager.on_delta:
                await self.base_manager.on_delta(event)
        
        async def on_usage_wrapper(event: StreamUsageEvent) -> None:
            # Add source to metadata
            event.metadata = event.metadata or {}
            event.metadata['source'] = tool_name
            
            # Apply redaction if configured
            if self.redactor_cb:
                event.metadata = self.redactor_cb(event.metadata)
            
            # Forward to base manager
            if self.base_manager.on_usage:
                await self.base_manager.on_usage(event)
        
        async def on_complete_wrapper(event: StreamCompleteEvent) -> None:
            # Add source to metadata
            event.metadata = event.metadata or {}
            event.metadata['source'] = tool_name
            if tool_version:
                event.metadata['tool_version'] = tool_version
            
            # Apply redaction if configured
            if self.redactor_cb:
                event.metadata = self.redactor_cb(event.metadata)
            
            # Forward to base manager
            if self.base_manager.on_complete:
                await self.base_manager.on_complete(event)
        
        async def on_error_wrapper(event: StreamErrorEvent) -> None:
            # Add source to metadata
            event.metadata = event.metadata or {}
            event.metadata['source'] = tool_name
            
            # Apply redaction if configured
            if self.redactor_cb:
                event.metadata = self.redactor_cb(event.metadata)
            
            # Forward to base manager
            if self.base_manager.on_error:
                await self.base_manager.on_error(event)
        
        # Create new EventManager with wrapped callbacks
        return EventManager(
            on_start=on_start_wrapper if self.base_manager.on_start else None,
            on_delta=on_delta_wrapper if self.base_manager.on_delta else None,
            on_usage=on_usage_wrapper if self.base_manager.on_usage else None,
            on_complete=on_complete_wrapper if self.base_manager.on_complete else None,
            on_error=on_error_wrapper if self.base_manager.on_error else None,
            request_id=self.base_manager.request_id,
            trace_id=self.base_manager.trace_id,
            sdk_version=self.base_manager.sdk_version
        )
    
    async def emit_orchestrator_start(
        self,
        tool_name: str,
        tool_version: str,
        request_id: Optional[str] = None
    ) -> None:
        """Emit start event for orchestration.
        
        Args:
            tool_name: Name of the tool being executed
            tool_version: Version of the tool
            request_id: Request ID
        """
        if self.base_manager.on_start:
            event = StreamStartEvent(
                provider="orchestrator",
                model="orchestrator",
                request_id=request_id,
                metadata={
                    'tool_name': tool_name,
                    'tool_version': tool_version,
                    'orchestration': True
                }
            )
            
            # Apply redaction
            if self.redactor_cb:
                event.metadata = self.redactor_cb(event.metadata)
            
            await self.base_manager.on_start(event)
    
    async def emit_orchestrator_complete(
        self,
        tool_name: str,
        tool_version: str,
        elapsed_ms: float,
        usage: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> None:
        """Emit completion event for orchestration.
        
        Args:
            tool_name: Name of the tool that completed
            tool_version: Version of the tool
            elapsed_ms: Total duration
            usage: Usage data from tool
            request_id: Request ID
        """
        if self.base_manager.on_complete:
            event = StreamCompleteEvent(
                provider="orchestrator",
                model="orchestrator",
                request_id=request_id,
                total_chunks=1,  # One tool execution
                duration_ms=elapsed_ms,
                final_usage=usage,
                metadata={
                    'tool_name': tool_name,
                    'tool_version': tool_version,
                    'orchestration': True
                }
            )
            
            # Apply redaction
            if self.redactor_cb:
                event.metadata = self.redactor_cb(event.metadata)
            
            await self.base_manager.on_complete(event)
    
    async def emit_orchestrator_error(
        self,
        tool_name: str,
        error: Dict[str, Any],
        elapsed_ms: float,
        request_id: Optional[str] = None
    ) -> None:
        """Emit error event for orchestration.
        
        Args:
            tool_name: Name of the tool that failed
            error: Error information
            elapsed_ms: Duration before error
            request_id: Request ID
        """
        if self.base_manager.on_error:
            from ..models.events import StreamErrorEvent
            
            event = StreamErrorEvent(
                error=Exception(error.get('message', 'Tool execution failed')),
                error_type=error.get('type', 'ToolError'),
                provider="orchestrator",
                model="orchestrator",
                request_id=request_id,
                metadata={
                    'tool_name': tool_name,
                    'error_details': error,
                    'elapsed_ms': elapsed_ms,
                    'orchestration': True
                }
            )
            
            # Apply redaction
            if self.redactor_cb:
                event.metadata = self.redactor_cb(event.metadata)
            
            await self.base_manager.on_error(event)