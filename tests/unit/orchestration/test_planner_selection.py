"""Test planning and tool selection functionality."""

import pytest
from steer_llm_sdk.orchestration.planning import (
    Planner,
    PlanRequest,
    PlanDecision,
    ToolMetadata,
    RuleBasedPlanner,
    PlanningRule,
    RuleCondition,
    RuleAction,
    ExecutionStrategy
)
from steer_llm_sdk.orchestration.planning.rule_based import (
    create_type_based_rule,
    create_keyword_based_rule,
    create_budget_aware_rule
)


class TestRuleBasedPlanner:
    """Test rule-based planning functionality."""
    
    @pytest.fixture
    def sample_tools(self):
        """Create sample tool metadata."""
        return {
            "analysis_bundle": ToolMetadata(
                name="analysis_bundle",
                version="1.0.0",
                description="Analyze data with multiple replicates",
                supported_models=["gpt-4o-mini", "claude-3-haiku"],
                default_options={"k": 3, "epsilon": 0.2},
                capabilities=["analysis", "statistics"],
                resource_requirements={
                    "estimated_cost_per_run": 0.05,
                    "estimated_duration_ms": 2000
                }
            ),
            "quick_check": ToolMetadata(
                name="quick_check",
                version="1.0.0",
                description="Quick single-pass check",
                supported_models=["gpt-4o-mini"],
                default_options={"k": 1},
                capabilities=["validation"],
                resource_requirements={
                    "estimated_cost_per_run": 0.01,
                    "estimated_duration_ms": 500
                }
            ),
            "deep_analysis": ToolMetadata(
                name="deep_analysis",
                version="1.0.0",
                description="Deep analysis with high confidence",
                supported_models=["gpt-4", "claude-3-opus"],
                default_options={"k": 5, "epsilon": 0.1},
                capabilities=["analysis", "statistics", "deep"],
                resource_requirements={
                    "estimated_cost_per_run": 0.20,
                    "estimated_duration_ms": 5000
                }
            )
        }
    
    @pytest.mark.asyncio
    async def test_basic_rule_matching(self, sample_tools):
        """Test basic rule matching and tool selection."""
        # Create planner with simple rules
        planner = RuleBasedPlanner([
            create_type_based_rule("analysis", "analysis_bundle", priority=10),
            create_type_based_rule("validation", "quick_check", priority=10),
        ])
        
        # Test analysis request
        result = await planner.plan(
            {"type": "analysis", "query": "Analyze this data"},
            sample_tools
        )
        
        assert result.selected_tool == "analysis_bundle"
        assert result.tool_options["k"] == 3  # Default from tool
        assert result.reasoning == "Matched rule: type_analysis"
        
        # Test validation request
        result = await planner.plan(
            {"type": "validation", "query": "Check this"},
            sample_tools
        )
        
        assert result.selected_tool == "quick_check"
        assert result.tool_options["k"] == 1
    
    @pytest.mark.asyncio
    async def test_rule_priority(self, sample_tools):
        """Test that higher priority rules are evaluated first."""
        planner = RuleBasedPlanner([
            PlanningRule(
                name="low_priority",
                priority=1,
                conditions=[],  # Always matches
                action=RuleAction(tool_name="quick_check")
            ),
            PlanningRule(
                name="high_priority",
                priority=10,
                conditions=[],  # Always matches
                action=RuleAction(tool_name="analysis_bundle")
            ),
        ])
        
        result = await planner.plan({}, sample_tools)
        
        # Should select high priority rule
        assert result.selected_tool == "analysis_bundle"
        assert result.metadata["matched_rule"] == "high_priority"
    
    @pytest.mark.asyncio
    async def test_keyword_matching(self, sample_tools):
        """Test keyword-based rule matching."""
        planner = RuleBasedPlanner([
            create_keyword_based_rule(
                ["deep", "thorough", "comprehensive"],
                "query",
                "deep_analysis",
                priority=15
            ),
            create_type_based_rule("analysis", "analysis_bundle", priority=10),
        ])
        
        # Request with keyword should select deep analysis
        result = await planner.plan(
            {"type": "analysis", "query": "Do a deep analysis of this"},
            sample_tools
        )
        
        assert result.selected_tool == "deep_analysis"
        assert result.tool_options["k"] == 5  # Default from deep_analysis tool
        assert result.tool_options["epsilon"] == 0.1
    
    @pytest.mark.asyncio
    async def test_complex_conditions(self, sample_tools):
        """Test rules with multiple conditions."""
        planner = RuleBasedPlanner([
            PlanningRule(
                name="high_quality_analysis",
                priority=20,
                conditions=[
                    RuleCondition("type", "equals", "analysis"),
                    RuleCondition("metadata.quality", "equals", "high"),
                    RuleCondition("metadata.budget", "gt", 0.15)
                ],
                action=RuleAction(
                    tool_name="deep_analysis",
                    tool_options={"k": 7, "epsilon": 0.05}
                )
            )
        ])
        
        # Request that matches all conditions
        result = await planner.plan(
            {
                "type": "analysis",
                "query": "Analyze",
                "metadata": {
                    "quality": "high",
                    "budget": 0.20
                }
            },
            sample_tools
        )
        
        assert result.selected_tool == "deep_analysis"
        assert result.tool_options["k"] == 7  # Custom value from rule
        assert result.tool_options["epsilon"] == 0.05
    
    @pytest.mark.asyncio
    async def test_fallback_tools(self, sample_tools):
        """Test fallback tool selection."""
        planner = RuleBasedPlanner([
            PlanningRule(
                name="with_fallbacks",
                priority=10,
                conditions=[],
                action=RuleAction(
                    tool_name="primary_tool",  # Doesn't exist
                    fallback_tools=["deep_analysis", "analysis_bundle"]
                )
            )
        ])
        
        result = await planner.plan({}, sample_tools)
        
        # Should fall back to first available tool
        assert result.selected_tool == "deep_analysis"
        assert result.fallback_tools == ["deep_analysis", "analysis_bundle"]
    
    @pytest.mark.asyncio
    async def test_budget_aware_rule(self, sample_tools):
        """Test budget-aware rule with dynamic options."""
        planner = RuleBasedPlanner([
            create_budget_aware_rule("analysis_bundle", low_budget_k=2, high_budget_k=5),
        ])
        
        # Low budget request
        result = await planner.plan(
            {"options": {"budget": {"tokens": 1000}}},
            sample_tools
        )
        assert result.tool_options["k"] == 2
        
        # High budget request
        result = await planner.plan(
            {"options": {"budget": {"tokens": 5000}}},
            sample_tools
        )
        assert result.tool_options["k"] == 5
    
    @pytest.mark.asyncio
    async def test_context_aware_planning(self, sample_tools):
        """Test planning with context (circuit breakers, failures)."""
        context = PlanRequest(
            circuit_breaker_states={
                "deep_analysis": "open",  # Circuit broken
                "analysis_bundle": "closed"
            },
            previous_failures=["deep_analysis"],
            budget={"cost_usd": 0.10}
        )
        
        planner = RuleBasedPlanner([
            create_type_based_rule("analysis", "deep_analysis", priority=20),
            create_type_based_rule("analysis", "analysis_bundle", priority=10),
        ])
        
        result = await planner.plan(
            {"type": "analysis"},
            sample_tools,
            context
        )
        
        # Should skip circuit-broken tool
        assert result.selected_tool == "analysis_bundle"
        assert "deep_analysis" not in result.fallback_tools
    
    @pytest.mark.asyncio
    async def test_cost_estimation(self, sample_tools):
        """Test cost and duration estimation."""
        planner = RuleBasedPlanner([
            PlanningRule(
                name="test",
                conditions=[],
                action=RuleAction(
                    tool_name="analysis_bundle",
                    tool_options={"k": 4}
                )
            )
        ])
        
        result = await planner.plan({}, sample_tools)
        
        # Cost should be base cost * k
        assert result.estimated_cost == 0.05 * 4  # 0.20
        
        # Duration should consider parallelism
        assert result.estimated_duration_ms == 2000  # All in parallel
    
    @pytest.mark.asyncio
    async def test_default_planning(self, sample_tools):
        """Test default planning when no rules match."""
        planner = RuleBasedPlanner([
            PlanningRule(
                name="never_matches",
                conditions=[RuleCondition("impossible", "equals", True)],
                action=RuleAction(tool_name="analysis_bundle")
            )
        ])
        
        result = await planner.plan({}, sample_tools)
        
        # Should use default planning
        assert result.selected_tool in sample_tools
        assert result.confidence == 0.5  # Lower confidence for default
        assert result.reasoning == "No matching rules, using default selection"
        assert result.metadata["selection_method"] == "default"
    
    @pytest.mark.asyncio
    async def test_regex_condition(self, sample_tools):
        """Test regex pattern matching in conditions."""
        planner = RuleBasedPlanner([
            PlanningRule(
                name="pattern_match",
                priority=10,
                conditions=[
                    RuleCondition(
                        "query",
                        "regex",
                        r"analyz[es]|evaluat[es]|assess"
                    )
                ],
                action=RuleAction(tool_name="analysis_bundle")
            )
        ])
        
        # Test various patterns
        for query in ["analyze this", "evaluates data", "assess quality"]:
            result = await planner.plan({"query": query}, sample_tools)
            assert result.selected_tool == "analysis_bundle"
    
    @pytest.mark.asyncio
    async def test_custom_matcher(self, sample_tools):
        """Test custom matcher function in conditions."""
        def is_urgent(value):
            return value and "urgent" in str(value).lower()
        
        planner = RuleBasedPlanner([
            PlanningRule(
                name="urgent_requests",
                priority=100,  # Very high priority
                conditions=[
                    RuleCondition(
                        "metadata.tags",
                        "exists",
                        None,
                        custom_matcher=is_urgent
                    )
                ],
                action=RuleAction(
                    tool_name="quick_check",
                    tool_options={"timeout_ms": 1000}
                )
            )
        ])
        
        result = await planner.plan(
            {"metadata": {"tags": ["urgent", "priority"]}},
            sample_tools
        )
        
        assert result.selected_tool == "quick_check"
        assert result.tool_options["timeout_ms"] == 1000
    
    @pytest.mark.asyncio
    async def test_no_tools_available(self):
        """Test error when no tools are available."""
        planner = RuleBasedPlanner()
        
        with pytest.raises(ValueError, match="No tools available"):
            await planner.plan({}, {})
    
    @pytest.mark.asyncio
    async def test_rule_with_no_action(self, sample_tools):
        """Test error handling for rule with no action."""
        planner = RuleBasedPlanner([
            PlanningRule(
                name="broken_rule",
                conditions=[],
                action=None  # No action defined
            )
        ])
        
        # Should skip broken rule and use default
        result = await planner.plan({}, sample_tools)
        assert result.metadata["selection_method"] == "default"