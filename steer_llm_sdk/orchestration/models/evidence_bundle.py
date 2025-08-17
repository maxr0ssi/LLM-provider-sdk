"""Evidence Bundle models for orchestration.

Defines the contract for Evidence Bundles returned by bundle tools.
These contain raw replicates plus computed statistics for the
orchestrator to reason over.
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class ReplicateQuality(BaseModel):
    """Quality assessment for a single replicate."""
    
    valid: bool = Field(
        ...,
        description="Whether the replicate passed validation"
    )
    
    errors: Optional[List[str]] = Field(
        default=None,
        description="Validation errors if any"
    )
    
    warnings: Optional[List[str]] = Field(
        default=None,
        description="Non-fatal warnings"
    )
    
    schema_version: Optional[str] = Field(
        default=None,
        description="Schema version used for validation"
    )


class Replicate(BaseModel):
    """A single replicate result from a sub-agent."""
    
    id: str = Field(
        ...,
        description="Unique identifier for this replicate (e.g., 'r1')"
    )
    
    data: Union[Dict[str, Any], str] = Field(
        ...,
        description="The replicate's output (JSON or text)"
    )
    
    quality: ReplicateQuality = Field(
        ...,
        description="Quality assessment of this replicate"
    )
    
    usage: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Token usage for this replicate"
    )
    
    elapsed_ms: Optional[int] = Field(
        default=None,
        description="Execution time in milliseconds"
    )
    
    seed: Optional[int] = Field(
        default=None,
        description="Random seed used for this replicate"
    )
    
    model: Optional[str] = Field(
        default=None,
        description="Model used for this replicate"
    )


class Disagreement(BaseModel):
    """A disagreement between replicates on a specific field."""
    
    field: str = Field(
        ...,
        description="Field path where disagreement occurred"
    )
    
    values: List[Any] = Field(
        ...,
        description="Different values from replicates"
    )
    
    replicate_ids: Optional[List[str]] = Field(
        default=None,
        description="Which replicates had which values"
    )


class BundleSummary(BaseModel):
    """Statistical summary across all replicates."""
    
    consensus: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Field-wise consensus where unambiguous"
    )
    
    disagreements: List[Disagreement] = Field(
        default_factory=list,
        description="Fields where replicates disagreed"
    )
    
    pairwise_distance: Optional[List[List[float]]] = Field(
        default=None,
        description="Pairwise distance matrix between replicates"
    )
    
    distributions: Optional[Dict[str, Dict[str, float]]] = Field(
        default=None,
        description="Statistical distributions for numeric fields"
    )
    
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall confidence score"
    )
    
    truncated: bool = Field(
        default=False,
        description="Whether results were truncated due to size limits"
    )
    
    truncation_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Details about what was truncated"
    )


class BundleMeta(BaseModel):
    """Metadata about the bundle execution."""
    
    task: str = Field(
        ...,
        description="Task type (e.g., 'feasibility', 'scoring')"
    )
    
    k: int = Field(
        ...,
        description="Number of replicates requested"
    )
    
    k_completed: Optional[int] = Field(
        default=None,
        description="Number of replicates that completed"
    )
    
    model: str = Field(
        ...,
        description="Model identifier (e.g., 'openai:gpt-4')"
    )
    
    seeds: List[int] = Field(
        ...,
        description="Seeds used for replicates"
    )
    
    early_stopped: bool = Field(
        default=False,
        description="Whether execution was early-stopped"
    )
    
    early_stop_reason: Optional[str] = Field(
        default=None,
        description="Reason for early stopping"
    )
    
    total_elapsed_ms: Optional[int] = Field(
        default=None,
        description="Total execution time"
    )
    
    schema_uri: Optional[str] = Field(
        default=None,
        description="Schema used for validation"
    )


class EvidenceBundle(BaseModel):
    """Complete evidence bundle returned by bundle tools.
    
    Contains raw replicates plus computed statistics for the
    orchestrator to reason over in a single atomic context.
    """
    
    meta: BundleMeta = Field(
        ...,
        description="Metadata about bundle execution"
    )
    
    replicates: List[Replicate] = Field(
        ...,
        description="Raw replicate results"
    )
    
    summary: BundleSummary = Field(
        ...,
        description="Statistical summary across replicates"
    )
    
    usage_total: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Aggregated usage across all replicates"
    )
    
    cost_total_usd: Optional[float] = Field(
        default=None,
        description="Total cost in USD"
    )
    
    cost_breakdown: Optional[Dict[str, float]] = Field(
        default=None,
        description="Cost per replicate"
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )