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
from .planning import (
    Planner,
    PlanningContext,
    PlanningResult,
    RuleBasedPlanner,
    PlanningRule
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
    
    # Planning
    "Planner",
    "PlanningContext",
    "PlanningResult",
    "RuleBasedPlanner",
    "PlanningRule",
]

# Import enhanced orchestrator for easier access
try:
    from .orchestrator_v2 import EnhancedOrchestrator
    __all__.append("EnhancedOrchestrator")
except ImportError:
    # M1 features not available if dependencies missing
    pass