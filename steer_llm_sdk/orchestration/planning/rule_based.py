"""Rule-based planner implementation for tool selection."""

from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
import re
from .planner import (
    Planner,
    PlanningContext,
    PlanningResult,
    ToolMetadata,
    ExecutionStrategy
)


@dataclass
class RuleCondition:
    """Condition for rule matching."""
    
    # Request attribute to check
    attribute_path: str  # e.g., "type", "metadata.domain", "query"
    
    # Condition type
    operator: str  # "equals", "contains", "regex", "exists", "gt", "lt"
    
    # Value to compare against
    value: Any
    
    # Optional custom matcher function
    custom_matcher: Optional[Callable[[Any], bool]] = None
    
    def matches(self, request: Dict[str, Any]) -> bool:
        """Check if condition matches the request."""
        # Extract value from request using attribute path
        value = self._get_nested_value(request, self.attribute_path)
        
        if self.custom_matcher:
            return self.custom_matcher(value)
        
        if self.operator == "exists":
            return value is not None
        
        if value is None:
            return False
            
        if self.operator == "equals":
            return value == self.value
        elif self.operator == "contains":
            return self.value in str(value)
        elif self.operator == "regex":
            return bool(re.search(self.value, str(value)))
        elif self.operator == "gt":
            return value > self.value
        elif self.operator == "lt":
            return value < self.value
        else:
            raise ValueError(f"Unknown operator: {self.operator}")
    
    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """Extract nested value from dictionary using dot notation."""
        parts = path.split(".")
        current = obj
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
                
        return current


@dataclass
class RuleAction:
    """Action to take when rule matches."""
    
    # Tool to select
    tool_name: str
    
    # Tool configuration
    tool_options: Dict[str, Any] = field(default_factory=dict)
    
    # Fallback tools in priority order
    fallback_tools: List[str] = field(default_factory=list)
    
    # Execution strategy
    execution_strategy: ExecutionStrategy = ExecutionStrategy.SINGLE
    
    # Optional transformer to modify tool options based on request
    option_transformer: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    
    def build_result(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Build the action result, potentially transforming options."""
        options = self.tool_options.copy()
        
        if self.option_transformer:
            options = self.option_transformer(request)
            
        return {
            "tool_name": self.tool_name,
            "tool_options": options,
            "fallback_tools": self.fallback_tools,
            "execution_strategy": self.execution_strategy
        }


@dataclass
class PlanningRule:
    """A single planning rule."""
    
    # Rule name for debugging
    name: str
    
    # Priority (higher = evaluated first)
    priority: int = 0
    
    # Conditions (all must match)
    conditions: List[RuleCondition] = field(default_factory=list)
    
    # Action to take if conditions match
    action: Optional[RuleAction] = None
    
    # Optional description
    description: Optional[str] = None
    
    def matches(self, request: Dict[str, Any], context: Optional[PlanningContext] = None) -> bool:
        """Check if all conditions match."""
        if not self.conditions:
            return True
            
        return all(condition.matches(request) for condition in self.conditions)
    
    def apply(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the rule action."""
        if not self.action:
            raise ValueError(f"Rule {self.name} has no action")
            
        return self.action.build_result(request)


class RuleBasedPlanner(Planner):
    """Planner that uses rules to select tools."""
    
    def __init__(self, rules: Optional[List[PlanningRule]] = None):
        """Initialize with a list of rules."""
        self.rules = sorted(rules or [], key=lambda r: r.priority, reverse=True)
        
    def add_rule(self, rule: PlanningRule) -> None:
        """Add a new rule and re-sort by priority."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    async def plan(
        self,
        request: Dict[str, Any],
        available_tools: Dict[str, ToolMetadata],
        context: Optional[PlanningContext] = None
    ) -> PlanningResult:
        """Plan tool execution based on rules."""
        context = context or PlanningContext()
        
        # Find first matching rule
        for rule in self.rules:
            if rule.matches(request, context):
                try:
                    result_dict = rule.apply(request)
                except ValueError:
                    # Skip rules with no action
                    continue
                
                # Check if tool is circuit-broken
                tool_name = result_dict["tool_name"]
                if context.circuit_breaker_states.get(tool_name) == "open":
                    continue  # Skip circuit-broken tools
                
                # Validate tool availability
                if not self.validate_tool_availability(tool_name, available_tools):
                    # Try fallback tools
                    for fallback in result_dict.get("fallback_tools", []):
                        # Skip circuit-broken fallbacks
                        if context.circuit_breaker_states.get(fallback) == "open":
                            continue
                        if self.validate_tool_availability(fallback, available_tools):
                            tool_name = fallback
                            break
                    else:
                        continue  # No available tool, try next rule
                
                # Build planning result
                tool_metadata = available_tools[tool_name]
                tool_options = result_dict.get("tool_options", {})
                
                # Apply defaults from tool metadata
                final_options = tool_metadata.default_options.copy()
                final_options.update(tool_options)
                
                return PlanningResult(
                    selected_tool=tool_name,
                    tool_options=final_options,
                    fallback_tools=result_dict.get("fallback_tools", []),
                    execution_strategy=result_dict.get("execution_strategy", ExecutionStrategy.SINGLE),
                    estimated_cost=self.estimate_cost(tool_name, final_options, tool_metadata),
                    estimated_duration_ms=self.estimate_duration(tool_name, final_options, tool_metadata),
                    confidence=1.0,
                    reasoning=f"Matched rule: {rule.name}",
                    metadata={"matched_rule": rule.name}
                )
        
        # No matching rule - try default behavior
        return await self._default_plan(request, available_tools, context)
    
    async def _default_plan(
        self,
        request: Dict[str, Any],
        available_tools: Dict[str, ToolMetadata],
        context: PlanningContext
    ) -> PlanningResult:
        """Default planning when no rules match."""
        # Simple default: pick first available tool
        if not available_tools:
            raise ValueError("No tools available for planning")
        
        # Filter out tools that are circuit-broken
        viable_tools = [
            (name, meta) for name, meta in available_tools.items()
            if context.circuit_breaker_states.get(name, "closed") != "open"
        ]
        
        if not viable_tools:
            # All tools are circuit-broken, try anyway
            viable_tools = list(available_tools.items())
        
        # Pick the first viable tool
        tool_name, tool_metadata = viable_tools[0]
        
        # Use sensible defaults
        default_options = {
            "k": 3,  # Default replicates
            "epsilon": 0.2,  # Default confidence threshold
            "max_parallel": 10
        }
        
        # Apply tool-specific defaults
        final_options = tool_metadata.default_options.copy()
        final_options.update(default_options)
        
        # Apply budget constraints if present
        if context.budget:
            if "tokens" in context.budget and context.budget["tokens"] < 1000:
                final_options["k"] = 2  # Reduce replicates for low budget
            if "cost_usd" in context.budget and context.budget["cost_usd"] < 0.05:
                final_options["k"] = 2
        
        return PlanningResult(
            selected_tool=tool_name,
            tool_options=final_options,
            fallback_tools=[name for name, _ in viable_tools[1:3]],  # Next 2 as fallbacks
            execution_strategy=ExecutionStrategy.SINGLE,
            estimated_cost=self.estimate_cost(tool_name, final_options, tool_metadata),
            estimated_duration_ms=self.estimate_duration(tool_name, final_options, tool_metadata),
            confidence=0.5,  # Lower confidence for default selection
            reasoning="No matching rules, using default selection",
            metadata={"selection_method": "default"}
        )


# Convenience functions for creating common rules
def create_type_based_rule(
    request_type: str,
    tool_name: str,
    priority: int = 10,
    **tool_options
) -> PlanningRule:
    """Create a rule that matches on request type."""
    return PlanningRule(
        name=f"type_{request_type}",
        priority=priority,
        conditions=[
            RuleCondition(
                attribute_path="type",
                operator="equals",
                value=request_type
            )
        ],
        action=RuleAction(
            tool_name=tool_name,
            tool_options=tool_options
        ),
        description=f"Use {tool_name} for {request_type} requests"
    )


def create_keyword_based_rule(
    keywords: List[str],
    attribute: str,
    tool_name: str,
    priority: int = 5,
    **tool_options
) -> PlanningRule:
    """Create a rule that matches on keywords (any keyword matches)."""
    # Create a custom matcher that checks if ANY keyword is present
    def keyword_matcher(value):
        if value is None:
            return False
        value_str = str(value).lower()
        return any(keyword.lower() in value_str for keyword in keywords)
    
    return PlanningRule(
        name=f"keywords_{tool_name}",
        priority=priority,
        conditions=[
            RuleCondition(
                attribute_path=attribute,
                operator="exists",  # Just check it exists
                value=None,
                custom_matcher=keyword_matcher
            )
        ],
        action=RuleAction(
            tool_name=tool_name,
            tool_options=tool_options
        ),
        description=f"Use {tool_name} when {attribute} contains any of: {keywords}"
    )


def create_budget_aware_rule(
    tool_name: str,
    low_budget_k: int = 2,
    high_budget_k: int = 5,
    priority: int = 8
) -> PlanningRule:
    """Create a rule that adjusts K based on budget."""
    def transform_options(request: Dict[str, Any]) -> Dict[str, Any]:
        budget = request.get("options", {}).get("budget", {})
        
        if "tokens" in budget and budget["tokens"] < 2000:
            return {"k": low_budget_k}
        elif "cost_usd" in budget and budget["cost_usd"] < 0.10:
            return {"k": low_budget_k}
        else:
            return {"k": high_budget_k}
    
    return PlanningRule(
        name=f"budget_aware_{tool_name}",
        priority=priority,
        conditions=[],  # Always matches
        action=RuleAction(
            tool_name=tool_name,
            option_transformer=transform_options
        ),
        description=f"Adjust {tool_name} K value based on budget"
    )