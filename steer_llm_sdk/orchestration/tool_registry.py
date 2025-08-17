"""Tool registry for orchestration.

The tool registry allows host applications to register tools that can be
used by the orchestrator. This enables domain-specific logic to be 
implemented outside the SDK while maintaining a clean interface.
"""

from typing import Dict, Optional, Type, Any
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class Tool(ABC):
    """Base class for all orchestration tools.
    
    Tools encapsulate complex operations that can be invoked by the orchestrator.
    They handle their own parallel execution, validation, and result aggregation.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this tool."""
        pass
    
    @property
    def version(self) -> str:
        """Tool version for compatibility tracking."""
        return "1.0.0"
    
    @property
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        return ""
    
    @abstractmethod
    async def execute(
        self,
        request: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        event_manager: Optional[Any] = None  # Avoid circular import
    ) -> Dict[str, Any]:
        """Execute the tool with given request.
        
        Args:
            request: Input data for the tool
            options: Tool-specific options
            event_manager: Optional event manager for streaming
            
        Returns:
            Tool-specific result (e.g., EvidenceBundle for BundleTools)
        """
        pass
    
    def validate_request(self, request: Dict[str, Any]) -> None:
        """Validate the request before execution.
        
        Override to add tool-specific validation.
        Raise ValueError if request is invalid.
        """
        pass


class ToolRegistry:
    """Registry for orchestration tools.
    
    Allows host applications to register tools at startup that can
    then be used by the orchestrator.
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        
    def register_tool(self, tool: Tool) -> None:
        """Register a tool instance.
        
        Args:
            tool: Tool instance to register
            
        Raises:
            ValueError: If tool with same name already registered
            TypeError: If tool doesn't implement Tool interface
        """
        if not isinstance(tool, Tool):
            raise TypeError(f"Tool must inherit from Tool base class, got {type(tool)}")
            
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' already registered. "
                f"Existing version: {self._tools[tool.name].version}, "
                f"New version: {tool.version}"
            )
        
        self._tools[tool.name] = tool
        logger.info(
            f"Registered tool '{tool.name}' version {tool.version}"
        )
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a registered tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)
    
    def list_tools(self) -> Dict[str, Dict[str, str]]:
        """List all registered tools.
        
        Returns:
            Dict mapping tool names to their metadata
        """
        return {
            name: {
                "version": tool.version,
                "description": tool.description
            }
            for name, tool in self._tools.items()
        }
    
    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool is registered
        """
        return name in self._tools
    
    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool (mainly for testing).
        
        Args:
            name: Tool name
            
        Returns:
            True if tool was unregistered, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Unregistered tool '{name}'")
            return True
        return False
    
    def clear(self) -> None:
        """Clear all registered tools (mainly for testing)."""
        self._tools.clear()
        logger.info("Cleared all registered tools")


# Global registry instance
_global_registry = ToolRegistry()


def get_global_registry() -> ToolRegistry:
    """Get the global tool registry instance.
    
    Returns:
        Global ToolRegistry instance
    """
    return _global_registry