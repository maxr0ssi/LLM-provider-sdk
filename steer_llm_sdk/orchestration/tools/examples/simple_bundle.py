"""Simple bundle tool example.

This demonstrates how host applications can implement bundle tools
that execute multiple sub-agents in parallel and compute statistics.
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
import random

from ..base import BundleTool, BundleOptions
from ...models.evidence_bundle import (
    EvidenceBundle,
    Replicate,
    ReplicateQuality,
    BundleMeta,
    BundleSummary,
    Disagreement
)
from ....agents.runner.agent_runner import AgentRunner
from ....agents.models.agent_definition import AgentDefinition
from ....agents.models.agent_result import AgentResult


class SimpleBundleTool(BundleTool):
    """A simple bundle tool for demonstration.
    
    This tool shows the basic pattern for implementing bundle tools:
    1. Run K replicates of a sub-agent in parallel
    2. Validate outputs
    3. Compute basic statistics
    4. Return an Evidence Bundle
    
    In production, tools would implement domain-specific logic,
    schema validation, and sophisticated statistical analysis.
    """
    
    @property
    def name(self) -> str:
        return "simple_bundle"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Simple bundle tool that runs parallel replicates"
    
    def __init__(self, agent_runner: Optional[AgentRunner] = None):
        """Initialize the tool.
        
        Args:
            agent_runner: Optional AgentRunner instance for sub-agent execution
        """
        super().__init__()
        self.agent_runner = agent_runner or AgentRunner()
    
    async def _execute_bundle(
        self,
        request: Dict[str, Any],
        options: BundleOptions,
        event_manager: Optional[Any] = None
    ) -> EvidenceBundle:
        """Execute the bundle tool logic.
        
        This simple implementation:
        1. Creates K sub-agent definitions with different seeds
        2. Runs them in parallel
        3. Validates outputs (basic check)
        4. Computes simple statistics
        5. Returns Evidence Bundle
        """
        start_time = time.time()
        
        # Emit start event
        await self.emit_event(
            event_manager,
            "bundle_started",
            {"k": options.k, "request": request}
        )
        
        # Create sub-agent definition
        agent_def = AgentDefinition(
            system="You are a helpful assistant analyzing data.",
            user_template="Analyze this request: {query}",
            model=request.get("model", "gpt-4o-mini"),
            parameters=request.get("parameters", {})
        )
        
        # Run K replicates in parallel
        tasks = []
        for i in range(options.k):
            seed = options.seeds[i] if options.seeds else self._generate_seeds(options.k)[i]
            task = self._run_replicate(
                f"r{i+1}",
                agent_def,
                request,
                seed,
                options,
                event_manager
            )
            tasks.append(task)
        
        # Execute with semaphore for concurrency control
        semaphore = asyncio.Semaphore(options.max_parallel)
        
        async def run_with_semaphore(task):
            async with semaphore:
                return await task
        
        # Gather results
        replicate_results = await asyncio.gather(
            *[run_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        # Process replicates
        replicates = []
        valid_outputs = []
        
        for i, result in enumerate(replicate_results):
            replicate_id = f"r{i+1}"
            
            if isinstance(result, Exception):
                # Failed replicate
                replicate = Replicate(
                    id=replicate_id,
                    data={"error": str(result)},
                    quality=ReplicateQuality(
                        valid=False,
                        errors=[str(result)]
                    ),
                    seed=options.seeds[i] if options.seeds else None
                )
            else:
                # Successful replicate
                agent_result: AgentResult = result
                
                # Basic validation (in production, use schema validation)
                is_valid = bool(agent_result.content)
                
                replicate = Replicate(
                    id=replicate_id,
                    data=agent_result.content,
                    quality=ReplicateQuality(
                        valid=is_valid,
                        errors=[] if is_valid else ["Empty content"]
                    ),
                    usage=agent_result.usage,
                    elapsed_ms=agent_result.elapsed_ms,
                    seed=options.seeds[i] if options.seeds else None,
                    model=agent_result.model
                )
                
                if is_valid:
                    valid_outputs.append(agent_result.content)
            
            replicates.append(replicate)
            
            # Emit replicate done event
            await self.emit_event(
                event_manager,
                "replicate_done",
                {
                    "replicate_id": replicate_id,
                    "valid": replicate.quality.valid,
                    "elapsed_ms": replicate.elapsed_ms
                }
            )
        
        # Compute simple statistics
        summary = self._compute_summary(replicates, valid_outputs, options)
        
        # Emit partial summary after K=2 if applicable
        if options.k > 2 and len(valid_outputs) >= 2:
            await self.emit_event(
                event_manager,
                "partial_summary",
                {"confidence": summary.confidence}
            )
        
        # Aggregate usage and cost
        total_usage = self._aggregate_usage(replicates)
        total_cost = self._calculate_cost(replicates)
        
        # Create Evidence Bundle
        bundle = EvidenceBundle(
            meta=BundleMeta(
                task="simple_analysis",
                k=options.k,
                k_completed=len(replicates),
                model=request.get("model", "gpt-4o-mini"),
                seeds=options.seeds or self._generate_seeds(options.k),
                early_stopped=False,  # Simple example doesn't implement early stop
                total_elapsed_ms=int((time.time() - start_time) * 1000),
                schema_uri=options.schema_uri
            ),
            replicates=replicates,
            summary=summary,
            usage_total=total_usage,
            cost_total_usd=total_cost,
            metadata={
                "tool": self.name,
                "version": self.version
            }
        )
        
        # Emit bundle ready event
        await self.emit_event(
            event_manager,
            "bundle_ready",
            {
                "replicate_count": len(replicates),
                "valid_count": len(valid_outputs),
                "confidence": summary.confidence
            }
        )
        
        return bundle
    
    async def _run_replicate(
        self,
        replicate_id: str,
        agent_def: AgentDefinition,
        request: Dict[str, Any],
        seed: int,
        options: BundleOptions,
        event_manager: Optional[Any] = None
    ) -> AgentResult:
        """Run a single replicate."""
        # Configure agent options
        agent_options = {
            "runtime": "openai_agents",  # Always use openai_agents
            "seed": seed,
            "deterministic": True,
            "streaming": False,  # Disable streaming for replicates
            "metadata": {
                "replicate_id": replicate_id,
                "bundle_tool": self.name
            }
        }
        
        # Add budget if specified
        if options.per_replicate_budget:
            agent_options["budget"] = options.per_replicate_budget
        
        # Prepare variables
        variables = {"query": request.get("query", "")}
        
        # Run the agent
        return await self.agent_runner.run(
            agent_def,
            variables,
            agent_options
        )
    
    def _compute_summary(
        self,
        replicates: List[Replicate],
        valid_outputs: List[Any],
        options: BundleOptions
    ) -> BundleSummary:
        """Compute simple statistics across replicates.
        
        This is a simplified example. Production implementations would:
        - Compute proper consensus across fields
        - Calculate semantic distances
        - Detect disagreements with context
        - Build distributions for numeric fields
        """
        # Simple confidence based on agreement
        if len(valid_outputs) < 2:
            confidence = 0.5 if len(valid_outputs) == 1 else 0.0
        else:
            # Check if all valid outputs are similar (simple string comparison)
            if all(str(output) == str(valid_outputs[0]) for output in valid_outputs):
                confidence = 0.95
            else:
                confidence = 0.7
        
        # Simple disagreement detection
        disagreements = []
        if len(valid_outputs) > 1:
            # Check if outputs differ
            unique_outputs = list(set(str(o) for o in valid_outputs))
            if len(unique_outputs) > 1:
                disagreements.append(Disagreement(
                    field="content",
                    values=unique_outputs[:3],  # Limit to 3 for demo
                    replicate_ids=[r.id for r in replicates if r.quality.valid][:3]
                ))
        
        # Simple pairwise distance (0 if same, 1 if different)
        num_replicates = len(replicates)
        pairwise_distance = [[0.0] * num_replicates for _ in range(num_replicates)]
        
        for i in range(num_replicates):
            for j in range(i + 1, num_replicates):
                if (replicates[i].quality.valid and 
                    replicates[j].quality.valid and
                    str(replicates[i].data) != str(replicates[j].data)):
                    pairwise_distance[i][j] = 1.0
                    pairwise_distance[j][i] = 1.0
        
        return BundleSummary(
            consensus=valid_outputs[0] if len(valid_outputs) == 1 else None,
            disagreements=disagreements,
            pairwise_distance=pairwise_distance,
            distributions={},  # Not implemented in simple example
            confidence=confidence,
            truncated=False
        )
    
    def _aggregate_usage(self, replicates: List[Replicate]) -> Dict[str, Any]:
        """Aggregate usage across replicates."""
        total_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
        
        for replicate in replicates:
            if replicate.usage:
                total_usage["prompt_tokens"] += replicate.usage.get("prompt_tokens", 0)
                total_usage["completion_tokens"] += replicate.usage.get("completion_tokens", 0)
                total_usage["total_tokens"] += replicate.usage.get("total_tokens", 0)
        
        return total_usage
    
    def _calculate_cost(self, replicates: List[Replicate]) -> Optional[float]:
        """Calculate total cost (simplified)."""
        # In production, use proper cost calculation
        # For demo, estimate based on tokens
        total_tokens = sum(
            r.usage.get("total_tokens", 0) 
            for r in replicates 
            if r.usage
        )
        
        # Rough estimate: $0.001 per 1k tokens
        if total_tokens > 0:
            return total_tokens * 0.001 / 1000
        
        return None