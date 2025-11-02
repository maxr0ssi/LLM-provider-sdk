"""OpenAI Agents SDK adapter implementation.

This module provides the integration between our agent framework
and the OpenAI Agents SDK, handling agent creation, execution, and streaming.
"""

import asyncio
import json
import os
import time
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from ....agents.models.agent_definition import AgentDefinition, Tool
from ....agents.validators.json_schema import validate_json_schema
from ....core.capabilities import get_capabilities_for_model
from ....core.normalization.params import normalize_params
from ....core.normalization.usage import normalize_usage
from ....core.routing.selector import calculate_exact_cost
from ....models.generation import GenerationParams
from ....reliability.budget import clamp_params_to_budget
from ....streaming.manager import EventManager
from ..base import AgentRunOptions, AgentRunResult, AgentRuntimeAdapter, PreparedRun
from ..errors import SchemaError, map_openai_agents_error
from ..streaming import AgentStreamingBridge
from .tools import convert_tools_to_sdk_format, extract_tool_results, validate_tool_compatibility

# Lazy import for optional dependency
try:
    from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    Agent = None
    Runner = None
    function_tool = None
    GuardrailFunctionOutput = None
    ModelSettings = None


class OpenAIAgentAdapter(AgentRuntimeAdapter):
    """Adapter for OpenAI Agents SDK integration.
    
    This adapter uses the official OpenAI Agents SDK (openai-agents package)
    to provide agent runtime capabilities. It maps our agent definitions to
    OpenAI SDK primitives and bridges events for streaming.
    
    Features:
    - Native agent loop with tool execution
    - JSON schema enforcement via guardrails
    - Streaming event bridging
    - Cost tracking and observability
    
    Requires:
    - pip install openai-agents
    - OPENAI_API_KEY environment variable
    """
    
    def __init__(self):
        """Initialize the OpenAI Agents adapter."""
        if not AGENTS_SDK_AVAILABLE:
            raise ImportError(
                "OpenAI Agents SDK not available. "
                "Please install it with: pip install openai-agents"
            )
        
        # Check for API key
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable not set")
    
    def supports_schema(self) -> bool:
        """OpenAI Agents SDK supports JSON schema via guardrails."""
        return True
    
    def supports_tools(self) -> bool:
        """OpenAI Agents SDK has native tool support."""
        return True
    
    async def prepare(
        self, 
        definition: AgentDefinition, 
        options: AgentRunOptions
    ) -> PreparedRun:
        """Prepare an OpenAI Agent for execution.
        
        This converts our agent definition to an OpenAI SDK Agent with:
        - Instructions from system prompt
        - Tools converted to function_tool format
        - Model settings with capability-driven normalization
        - Optional guardrails for structured outputs
        """
        start_time = time.time()
        
        # Convert tools to OpenAI SDK format
        sdk_tools = []
        tool_warnings = []
        
        if definition.tools:
            # Validate tools
            for tool in definition.tools:
                warnings = validate_tool_compatibility(tool)
                if warnings:
                    tool_warnings.extend(warnings)
            
            # Convert to SDK format
            sdk_tools = convert_tools_to_sdk_format(definition.tools)
        
        # Get model capabilities for normalization
        capabilities = get_capabilities_for_model(definition.model)
        
        # Create GenerationParams for normalization
        gen_params = GenerationParams(
            model=definition.model,
            **definition.parameters
        )
        
        # Normalize parameters
        normalized_params = normalize_params(
            gen_params,
            definition.model,
            "openai",
            capabilities
        )
        
        # Apply budget constraints if specified
        if options.budget:
            normalized_params = clamp_params_to_budget(
                normalized_params,
                options.budget
            )
        
        # Build ModelSettings object for Agent
        # Note: 'model' is NOT part of ModelSettings - it's passed separately to Agent()
        model_settings_kwargs = {}

        # Map normalized parameters to ModelSettings fields
        if "temperature" in normalized_params:
            model_settings_kwargs["temperature"] = normalized_params["temperature"]
        if "top_p" in normalized_params:
            model_settings_kwargs["top_p"] = normalized_params["top_p"]

        # Handle max tokens - SDK ModelSettings uses 'max_tokens' field
        for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
            if field in normalized_params:
                model_settings_kwargs["max_tokens"] = normalized_params[field]
                break

        # Handle seed via extra_args (seed is not a standard ModelSettings field)
        if options.seed and capabilities.supports_seed:
            if "extra_args" not in model_settings_kwargs:
                model_settings_kwargs["extra_args"] = {}
            model_settings_kwargs["extra_args"]["seed"] = options.seed

        # Create ModelSettings object (or None if no settings)
        model_settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None
        
        # Create guardrails for structured output if schema provided
        guardrails = []
        if definition.json_schema and options.strict:
            # Create a guardrail that validates against the schema
            async def schema_guardrail(ctx, agent, result):
                """Validate output against JSON schema."""
                try:
                    # Parse the output as JSON
                    if isinstance(result, str):
                        output_data = json.loads(result)
                    else:
                        output_data = result
                    
                    # Validate against schema
                    validate_json_schema(output_data, definition.json_schema)
                    
                    # Return the output in the format the SDK expects
                    # If the result is already a string (JSON), keep it as is
                    # If it's a dict/list, the SDK can handle structured data directly
                    return GuardrailFunctionOutput(
                        output=result,  # SDK handles both string and structured formats
                        should_block=False
                    )
                except Exception as e:
                    # Block if validation fails
                    return GuardrailFunctionOutput(
                        output=None,
                        should_block=True,
                        error_message=f"Schema validation failed: {str(e)}"
                    )
            
            guardrails.append(schema_guardrail)
        
        # Create the OpenAI Agent
        agent = Agent(
            name="Assistant",
            model=definition.model,
            instructions=definition.system,
            tools=sdk_tools,
            model_settings=model_settings,
            output_guardrails=guardrails if guardrails else None
        )
        
        # Store prepared state
        prepared = PreparedRun(
            runtime="openai_agents",
            agent=agent,
            config={
                "model": definition.model,
                "normalized_params": normalized_params,
                "user_template": definition.user_template,
                "json_schema": definition.json_schema,
                "strict": options.strict,
                "trace_id": options.trace_id,
                "request_id": options.request_id,
                "streaming_options": options.streaming_options,  # Pass through for bridge
                "tools": definition.tools  # Store original tools for reference
            },
            metadata={
                "prepare_time_ms": int((time.time() - start_time) * 1000),
                "capabilities": capabilities,
                "tool_warnings": tool_warnings
            }
        )
        
        return prepared
    
    async def run(
        self,
        prepared: PreparedRun,
        variables: Dict[str, Any]
    ) -> AgentRunResult:
        """Execute a non-streaming agent run using Runner.run."""
        start_time = time.time()

        # Format user input with variables
        user_input = prepared.config["user_template"].format(**variables)

        # Run the agent asynchronously
        try:
            # Use native async Runner.run() method
            result = await Runner.run(prepared.agent, user_input)
            
            # Extract content and usage
            content = result.final_output
            
            # Parse JSON if schema was provided
            final_json = None
            if prepared.config.get("json_schema"):
                try:
                    final_json = json.loads(content)
                except json.JSONDecodeError:
                    pass
            
            # Extract tool execution info
            tool_info = extract_tool_results(result)
            
            # Extract usage data from result
            usage = {}
            if hasattr(result, 'usage'):
                usage = normalize_usage(result.usage, "openai")
            else:
                # Estimate usage if not provided
                usage = {
                    "prompt_tokens": len(user_input.split()) * 2,  # Rough estimate
                    "completion_tokens": len(content.split()) * 2,  # Rough estimate
                    "total_tokens": 0,
                    "cache_info": {}
                }
                usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
            
            # Calculate cost
            model = prepared.config["model"]
            cost_usd = calculate_exact_cost(usage, model)  # Returns float or None
            
            # Build result
            return AgentRunResult(
                content=final_json if final_json else content,
                usage=usage,
                model=model,
                elapsed_ms=int((time.time() - start_time) * 1000),
                provider="openai",
                runtime="openai_agents",
                provider_metadata={
                    "agent_name": prepared.agent.name,
                    "tools_called": tool_info["tools_called"],
                    "tool_results": tool_info["tool_results"],
                    "trace_id": prepared.config.get("trace_id"),
                    "request_id": prepared.config.get("request_id"),
                    "usage_estimated": not hasattr(result, 'usage')  # Mark if usage was estimated
                },
                trace_id=prepared.config.get("trace_id"),
                request_id=prepared.config.get("request_id"),
                final_json=final_json,
                finish_reason="stop",
                cost_usd=cost_usd
            )
            
        except Exception as e:
            # Map error and re-raise
            provider_error = map_openai_agents_error(e)
            raise provider_error
    
    async def run_stream(
        self, 
        prepared: PreparedRun, 
        variables: Dict[str, Any],
        events: EventManager
    ) -> AsyncIterator[None]:
        """Execute a streaming agent run using Runner.run_streamed."""
        start_time = time.time()
        ttft = None
        
        # Format user input with variables
        user_input = prepared.config["user_template"].format(**variables)
        
        # Create streaming bridge
        bridge = AgentStreamingBridge(
            events=events,
            provider="openai",
            model=prepared.config["model"],
            request_id=prepared.config.get("request_id"),
            streaming_options=prepared.config.get("streaming_options"),
            response_format={"type": "json_schema", "json_schema": prepared.config["json_schema"]} if prepared.config.get("json_schema") else None
        )
        
        # Store bridge for AgentRunner to collect results
        self._last_bridge = bridge
        
        # Emit start event through bridge
        await bridge.on_start({
            "runtime": "openai_agents",
            "trace_id": prepared.config.get("trace_id"),
            "request_id": prepared.config.get("request_id")
        })
        
        try:
            # Collect tool usage for metadata
            tools_used = []
            usage_was_estimated = False
            
            # Run the agent with streaming
            # Note: OpenAI Agents SDK emits different event types than expected
            # - raw_response_event: Contains raw OpenAI API events
            # - run_item_stream_event: Semantic events (tool calls, messages, etc.)
            # - agent_updated_stream_event: Agent handoff notifications
            async for event in Runner.run_streamed(prepared.agent, user_input):
                # Map OpenAI SDK events to our events through bridge
                if hasattr(event, 'type'):
                    if event.type == "raw_response_event":
                        # Extract content from raw OpenAI response events
                        if hasattr(event, 'data'):
                            data = event.data
                            # Handle different raw event types
                            if hasattr(data, 'choices') and data.choices:
                                for choice in data.choices:
                                    if hasattr(choice, 'delta'):
                                        delta = choice.delta
                                        if hasattr(delta, 'content') and delta.content:
                                            if ttft is None:
                                                ttft = int((time.time() - start_time) * 1000)
                                            await bridge.on_delta(delta.content)
                            
                            # Extract usage if present
                            if hasattr(data, 'usage') and data.usage:
                                usage = normalize_usage(data.usage, "openai")
                                await bridge.on_usage(usage, is_estimated=False)
                    
                    elif event.type == "run_item_stream_event":
                        # Handle semantic events
                        if hasattr(event, 'name'):
                            if event.name == "tool_called":
                                # Extract tool info from the event
                                tool_name = "unknown"
                                if hasattr(event, 'item') and hasattr(event.item, 'tool_name'):
                                    tool_name = event.item.tool_name
                                tools_used.append(tool_name)
                                
                                # Send as metadata-only delta
                                await bridge.on_delta({
                                    "type": "tool_call",
                                    "tool": tool_name,
                                    "event_name": event.name
                                })
                            
                            elif event.name in ["message_output_created", "reasoning_item_created"]:
                                # These might contain content to display
                                await bridge.on_delta({
                                    "type": "semantic_event",
                                    "event_name": event.name,
                                    "item": str(getattr(event, 'item', ''))
                                })
                    
                    elif event.type == "agent_updated_stream_event":
                        # Track agent changes
                        await bridge.on_delta({
                            "type": "agent_update",
                            "new_agent": getattr(event, 'new_agent', {})
                        })
                
                # Handle unexpected event formats
                else:
                    # Generic event handling as metadata
                    await bridge.on_delta({
                        "type": "unknown",
                        "raw_event": str(event)
                    })
            
            # Get final usage from bridge if not already emitted
            if not bridge._usage_emitted:
                # Estimate usage
                usage_was_estimated = True
                final_content = bridge.get_collected_text()
                estimated_usage = {
                    "prompt_tokens": len(user_input.split()) * 2,
                    "completion_tokens": len(final_content.split()) * 2,
                    "total_tokens": 0,
                    "cache_info": {}
                }
                estimated_usage["total_tokens"] = estimated_usage["prompt_tokens"] + estimated_usage["completion_tokens"]
                await bridge.on_usage(estimated_usage, is_estimated=True)
            
            # Calculate cost using the final usage
            final_usage = bridge.get_final_usage() or {}
            model = prepared.config["model"]
            cost_usd = calculate_exact_cost(final_usage, model)
            
            # Complete the stream with metadata
            await bridge.on_complete({
                "final_json": bridge.get_final_json(),
                "tools_used": tools_used,
                "cost_usd": cost_usd,
                "ttft_ms": ttft,
                "finish_reason": "stop",
                "trace_id": prepared.config.get("trace_id"),
                "request_id": prepared.config.get("request_id"),
                "is_estimated": usage_was_estimated  # Clear flag for whether usage was estimated
            })
            
        except Exception as e:
            # Map error and handle through bridge
            provider_error = map_openai_agents_error(e)
            await bridge.on_error(provider_error)
            raise provider_error
        
        # This is an async generator that yields nothing
        yield