"""Agent runtime integrations.

This module provides adapters for vendor-native agent SDKs,
starting with OpenAI Agents SDK integration.
"""

from typing import Optional, Dict
import importlib

# Registry of available runtimes
_RUNTIME_REGISTRY: Dict[str, str] = {
    "openai_agents": "steer_llm_sdk.integrations.agents.openai.adapter.OpenAIAgentAdapter",
}


def get_agent_runtime(name: str) -> "AgentRuntimeAdapter":
    """Get an agent runtime adapter by name.
    
    Args:
        name: Runtime name (e.g., "openai_agents")
        
    Returns:
        AgentRuntimeAdapter instance
        
    Raises:
        ValueError: If runtime not found
        ImportError: If runtime dependencies not installed
    """
    if name not in _RUNTIME_REGISTRY:
        available = ", ".join(_RUNTIME_REGISTRY.keys())
        raise ValueError(f"Unknown runtime: {name}. Available: {available}")
    
    module_path = _RUNTIME_REGISTRY[name]
    module_name, class_name = module_path.rsplit(".", 1)
    
    try:
        module = importlib.import_module(module_name)
        adapter_class = getattr(module, class_name)
        return adapter_class()
    except ImportError as e:
        if "openai" in str(e) and name == "openai_agents":
            raise ImportError(
                "OpenAI Agents SDK not installed. "
                "Install with: pip install steer-llm-sdk[openai-agents]"
            ) from e
        raise


# Re-export base classes
from .base import AgentRuntimeAdapter, AgentRunOptions, PreparedRun, AgentRunResult

__all__ = [
    "get_agent_runtime",
    "AgentRuntimeAdapter", 
    "AgentRunOptions",
    "PreparedRun",
    "AgentRunResult",
]