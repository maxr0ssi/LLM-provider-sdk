"""Orchestration module for tool-based execution."""

from .orchestrator import Orchestrator, OrchestrationOutput
from .options import OrchestrationConfig
from .tool_registry import Tool, ToolRegistry, get_global_registry
from .tools import BundleTool, BundleOptions
from .models import (
    EvidenceBundle,
    Replicate,
    ReplicateQuality,
    BundleMetadata,
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
    PlanRequest,
    PlanDecision,
    RuleBasedPlanner,
    PlanningRule
)

__all__ = [
    # Core orchestration
    "Orchestrator",
    "OrchestrationOutput",
    "OrchestrationConfig",
    
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
    "BundleMetadata",
    "BundleSummary",
    "Disagreement",
    
    # Errors
    "OrchestratorError",
    "BudgetExceeded",
    "ConflictError",
    
    # Planning
    "Planner",
    "PlanRequest",
    "PlanDecision",
    "RuleBasedPlanner",
    "PlanningRule",
]

# Import reliability features
from .reliable_orchestrator import ReliableOrchestrator
__all__.append("ReliableOrchestrator")