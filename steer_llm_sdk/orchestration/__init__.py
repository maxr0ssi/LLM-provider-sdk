"""Orchestration module for tool-based execution."""

from .orchestrator import Orchestrator, OrchestratorResult
from .options import OrchestratorOptions
from .tool_registry import Tool, ToolRegistry, get_global_registry
from .tools import BundleTool, BundleOptions
from .models import (
    EvidenceBundle,
    Replicate,
    ReplicateQuality,
    BundleMeta,
    BundleSummary,
    Disagreement
)
from .errors import (
    OrchestratorError,
    BudgetExceeded,
    ConflictError
)

__all__ = [
    # Core orchestration
    "Orchestrator",
    "OrchestratorResult",
    "OrchestratorOptions",
    
    # Tool infrastructure
    "Tool",
    "ToolRegistry",
    "get_global_registry",
    "BundleTool",
    "BundleOptions",
    
    # Evidence Bundle models
    "EvidenceBundle",
    "Replicate",
    "ReplicateQuality",
    "BundleMeta",
    "BundleSummary",
    "Disagreement",
    
    # Errors
    "OrchestratorError",
    "BudgetExceeded",
    "ConflictError",
]