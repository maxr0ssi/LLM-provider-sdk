from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional, Union

from ...core.capabilities import get_capabilities_for_model
from ...core.routing import LLMRouter, get_config
from ...integrations.agents import AgentRunOptions, get_agent_runtime
from ...observability import AgentMetrics, MetricsSink
from ...observability.models import RequestMetrics, ReliabilityMetrics
from ...providers.base import ProviderError
from ...reliability.budget import clamp_params_to_budget
from ...reliability.idempotency import IdempotencyManager
from ...reliability.retry import RetryConfig, RetryManager
from ...streaming.adapter import StreamAdapter
from ...streaming.manager import EventManager
from ...streaming.helpers import StreamingHelper
from ..models.agent_definition import AgentDefinition
from ..models.agent_options import AgentOptions
from ..models.agent_result import AgentResult
from ..validators.json_schema import validate_json_schema
from .determinism import apply_deterministic_policy


class AgentRunner:
    def __init__(self, metrics_sink: MetricsSink | None = None) -> None:
        self.router = LLMRouter()
        self.adapter = StreamAdapter("generic")
        self.idempotency = IdempotencyManager()
        self.metrics_sink = metrics_sink

    async def run(self, definition: AgentDefinition, variables: Dict[str, Any], options: Union[Dict[str, Any], AgentOptions]) -> AgentResult:
        opts = options if isinstance(options, AgentOptions) else AgentOptions(**options)
        
        # Check if runtime is specified
        runtime_name = None
        if isinstance(options, dict):
            runtime_name = options.get("runtime")
        elif hasattr(opts, "runtime"):
            runtime_name = opts.runtime
        
        # If runtime specified, delegate to runtime adapter
        if runtime_name:
            return await self._run_with_runtime(definition, variables, opts, runtime_name)
        
        # Otherwise, use existing router-based implementation
        caps = get_capabilities_for_model(definition.model)

        # Render user message (simple format; Jinja2 can be wired if needed)
        user_text = definition.user_template.format(**variables)
        messages = [
            {"role": "system", "content": definition.system},
            {"role": "user", "content": user_text},
        ]

        # Apply deterministic policy
        params: Dict[str, Any] = apply_deterministic_policy(dict(definition.parameters), definition.model) if opts.deterministic else dict(definition.parameters)

        # Enforce token budget by clamping params centrally
        budget = opts.budget or {}
        params = clamp_params_to_budget(params, budget)

        # Attach schema request when supported
        if definition.json_schema and caps.supports_json_schema:
            rf = {"type": "json_schema", "json_schema": definition.json_schema}
            # Optional strict from metadata
            strict_flag = None
            if isinstance(opts.metadata, dict):
                strict_flag = opts.metadata.get("strict")
            if strict_flag is not None:
                rf["strict"] = bool(strict_flag)
            params["response_format"] = rf

        # Optional Responses API flags from metadata
        if isinstance(opts.metadata, dict) and opts.metadata.get("responses_use_instructions"):
            params["responses_use_instructions"] = True

        start = time.time()

        # Idempotency: return cached result if key provided and present
        if opts.idempotency_key:
            cached = self.idempotency.check_duplicate(opts.idempotency_key)
            if cached is not None:
                return cached

        if opts.streaming:
            # Configure adapter with model and response format
            config = get_config(definition.model)
            provider_name = config.provider.value if hasattr(config.provider, 'value') else str(config.provider)
            self.adapter = StreamAdapter(provider_name)
            self.adapter.model = definition.model
            if definition.json_schema and caps.supports_json_schema:
                self.adapter.response_format = {"type": "json_object"}
            
            # Create EventManager for callbacks
            events = EventManager(
                on_start=opts.metadata.get("on_start"),
                on_delta=opts.metadata.get("on_delta"),
                on_usage=opts.metadata.get("on_usage"),
                on_complete=opts.metadata.get("on_complete"),
                on_error=opts.metadata.get("on_error"),
            )
            
            # Stream with soft wall-clock budget
            ms_budget = None
            if isinstance(budget, dict) and "ms" in budget:
                ms_budget = int(budget["ms"])
            
            try:
                # Create a generator that respects the budget
                async def budget_aware_stream():
                    stream_start = time.time()
                    async for item in self.router.generate_stream(messages, definition.model, params, return_usage=True):
                        yield item
                        if ms_budget is not None and (time.time() - stream_start) * 1000 >= ms_budget:
                            break
                
                # Use StreamingHelper to handle the streaming
                text, usage_data, metrics = await StreamingHelper.collect_with_usage(
                    budget_aware_stream(),
                    self.adapter,
                    events
                )
                
                # Handle JSON schema validation
                content: Any = text
                if definition.json_schema:
                    try:
                        parsed = json.loads(text)
                        validate_json_schema(parsed, definition.json_schema)
                        content = parsed
                    except Exception:
                        # Leave as text; caller may use local tools to repair
                        content = text
                
                result = AgentResult(
                    content=content,
                    usage=usage_data or {},
                    model=definition.model,
                    elapsed_ms=int((time.time() - start) * 1000),
                    provider_metadata={},
                    trace_id=opts.trace_id,
                )
            except ProviderError:
                raise  # Re-raise provider errors as-is
            except Exception as e:
                config = get_config(definition.model)
                provider = config.provider.value if hasattr(config.provider, 'value') else str(config.provider)
                raise ProviderError(str(e), provider=provider)
            
            # Metrics (best-effort)
            if self.metrics_sink:
                usage = usage_data or {}
                # Get provider from model config
                config = get_config(definition.model)
                # Create modern RequestMetrics
                request_metrics = RequestMetrics(
                    provider=config.provider.value if hasattr(config.provider, 'value') else str(config.provider),
                    model=definition.model,
                    request_id=None,
                    duration_ms=float(result.elapsed_ms),
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                    cached_tokens=int(usage.get("cache_info", {}).get("cached_tokens", 0)) if isinstance(usage.get("cache_info", {}), dict) else 0,
                    successful=True,
                    error_type=None,
                    method="agent.run"
                )
                # Convert to AgentMetrics for backward compatibility
                agent_metrics = AgentMetrics.from_request_metrics(request_metrics)
                agent_metrics.trace_id = opts.trace_id
                agent_metrics.tools_used = [t.name for t in (definition.tools or [])]
                try:
                    await self.metrics_sink.record(agent_metrics)
                except Exception:
                    pass
            if opts.idempotency_key:
                self.idempotency.store_result(opts.idempotency_key, result)
            return result

        # Non-streaming path (enforce ms budget with wait_for if present)
        ms_budget = None
        if isinstance(budget, dict) and "ms" in budget:
            ms_budget = int(budget["ms"]) / 1000.0

        async def _call_router():
            try:
                return await self.router.generate(messages, definition.model, params)
            except ProviderError:
                raise  # Re-raise provider errors as-is
            except Exception as e:
                config = get_config(definition.model)
                provider = config.provider.value if hasattr(config.provider, 'value') else str(config.provider)
                raise ProviderError(str(e), provider=provider)

        retry_mgr = RetryManager()
        retry_cfg = RetryConfig(max_attempts=2, backoff_factor=2.0, retryable_errors=(ProviderError,))
        if ms_budget is not None and ms_budget > 0:
            response = await asyncio.wait_for(retry_mgr.execute_with_retry(_call_router, retry_cfg), timeout=ms_budget)
        else:
            response = await retry_mgr.execute_with_retry(_call_router, retry_cfg)
        content: Any = response.text
        if definition.json_schema:
            try:
                parsed = json.loads(response.text)
                validate_json_schema(parsed, definition.json_schema)
                content = parsed
            except Exception:
                content = response.text

        result = AgentResult(
            content=content,
            usage=response.usage,
            model=definition.model,
            elapsed_ms=int((time.time() - start) * 1000),
            provider_metadata={"finish_reason": response.finish_reason},
            trace_id=opts.trace_id,
        )
        if self.metrics_sink:
            usage = response.usage or {}
            # Get provider from model config
            config = get_config(definition.model)
            # Create modern RequestMetrics
            request_metrics = RequestMetrics(
                provider=config.provider.value if hasattr(config.provider, 'value') else str(config.provider),
                model=definition.model,
                request_id=None,
                duration_ms=float(result.elapsed_ms),
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                cached_tokens=int(usage.get("cache_info", {}).get("cached_tokens", 0)) if isinstance(usage.get("cache_info", {}), dict) else 0,
                successful=True,
                error_type=None,
                method="agent.run"
            )
            # Convert to AgentMetrics for backward compatibility
            agent_metrics = AgentMetrics.from_request_metrics(request_metrics)
            agent_metrics.trace_id = opts.trace_id
            agent_metrics.tools_used = [t.name for t in (definition.tools or [])]
            try:
                await self.metrics_sink.record(agent_metrics)
            except Exception:
                pass
        if opts.idempotency_key:
            self.idempotency.store_result(opts.idempotency_key, result)
        return result
    
    async def _run_with_runtime(
        self,
        definition: AgentDefinition,
        variables: Dict[str, Any],
        opts: AgentOptions,
        runtime_name: str
    ) -> AgentResult:
        """Run agent using specified runtime adapter."""
        # Get runtime adapter
        runtime = get_agent_runtime(runtime_name)
        
        # Convert AgentOptions to AgentRunOptions
        run_options = AgentRunOptions(
            runtime=runtime_name,
            streaming=opts.streaming,
            deterministic=opts.deterministic,
            seed=opts.metadata.get("seed") if opts.metadata else None,
            strict=opts.metadata.get("strict") if opts.metadata else None,
            responses_use_instructions=opts.metadata.get("responses_use_instructions", False) if opts.metadata else False,
            budget=dict(opts.budget) if opts.budget else None,
            idempotency_key=opts.idempotency_key,
            trace_id=opts.trace_id,
            request_id=opts.metadata.get("request_id") if opts.metadata else None,
            streaming_options=opts.metadata.get("streaming_options") if opts.metadata else None,
            metadata=opts.metadata or {}
        )
        
        # Check idempotency
        if opts.idempotency_key:
            cached = self.idempotency.check_duplicate(opts.idempotency_key)
            if cached is not None:
                return cached
        
        start_time = time.time()
        
        try:
            # Prepare agent
            prepared = await runtime.prepare(definition, run_options)
            
            if opts.streaming:
                # Streaming mode
                events = EventManager(
                    on_start=opts.metadata.get("on_start"),
                    on_delta=opts.metadata.get("on_delta"),
                    on_usage=opts.metadata.get("on_usage"),
                    on_complete=opts.metadata.get("on_complete"),
                    on_error=opts.metadata.get("on_error"),
                )
                
                # Create a result collector to aggregate streaming data
                from ...integrations.agents.streaming import AgentStreamingBridge
                result_collector = None
                
                # Run streaming (yields nothing, emits events)
                async for _ in runtime.run_stream(prepared, variables, events):
                    pass
                
                # Get the bridge instance from runtime to collect results
                # The runtime should expose the bridge for result collection
                if hasattr(runtime, '_last_bridge'):
                    result_collector = runtime._last_bridge
                
                # Collect the streamed content and usage
                content = ""
                usage = {}
                
                if result_collector:
                    content = result_collector.get_collected_text()
                    usage = result_collector.get_final_usage() or {}
                    
                    # Parse JSON if schema provided
                    if definition.json_schema and content:
                        try:
                            from ..validators.json_schema import validate_json_schema
                            parsed = json.loads(content)
                            validate_json_schema(parsed, definition.json_schema)
                            content = parsed  # Return parsed content
                        except Exception:
                            # Keep as string if parsing/validation fails
                            pass
                
                result = AgentResult(
                    content=content,
                    usage=usage,
                    model=definition.model,
                    elapsed_ms=int((time.time() - start_time) * 1000),
                    provider_metadata={"runtime": runtime_name},
                    trace_id=opts.trace_id
                )
            else:
                # Non-streaming mode
                runtime_result = await runtime.run(prepared, variables)
                
                # Convert runtime result to AgentResult
                result = AgentResult(
                    content=runtime_result.content,
                    usage=runtime_result.usage,
                    model=runtime_result.model,
                    elapsed_ms=runtime_result.elapsed_ms,
                    provider_metadata=runtime_result.provider_metadata,
                    trace_id=runtime_result.trace_id,
                    confidence=runtime_result.confidence,
                    cost_usd=runtime_result.cost_usd,
                    cost_breakdown=runtime_result.cost_breakdown,
                    error=runtime_result.error,
                    status=runtime_result.status
                )
            
            # Record metrics
            if self.metrics_sink:
                usage = result.usage or {}
                # Get provider from model config
                config = get_config(definition.model)
                # Create modern RequestMetrics
                request_metrics = RequestMetrics(
                    provider=config.provider.value if hasattr(config.provider, 'value') else str(config.provider),
                    model=definition.model,
                    request_id=run_options.request_id,
                    duration_ms=float(result.elapsed_ms),
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                    cached_tokens=int(usage.get("cache_info", {}).get("cached_tokens", 0)) if isinstance(usage.get("cache_info", {}), dict) else 0,
                    successful=True,
                    error_type=None,
                    method=f"agent.run.{runtime_name}"
                )
                # Convert to AgentMetrics for backward compatibility
                agent_metrics = AgentMetrics.from_request_metrics(request_metrics)
                agent_metrics.trace_id = result.trace_id
                agent_metrics.tools_used = [t.name for t in (definition.tools or [])]
                try:
                    await self.metrics_sink.record(agent_metrics)
                except Exception:
                    pass
            
            # Store in idempotency cache
            if opts.idempotency_key:
                self.idempotency.store_result(opts.idempotency_key, result)
            
            return result
            
        except Exception as e:
            # Record error metrics
            if self.metrics_sink:
                # Get provider from model config
                config = get_config(definition.model)
                # Create modern RequestMetrics for error case
                request_metrics = RequestMetrics(
                    provider=config.provider.value if hasattr(config.provider, 'value') else str(config.provider),
                    model=definition.model,
                    request_id=run_options.request_id,
                    duration_ms=float((time.time() - start_time) * 1000),
                    prompt_tokens=0,
                    completion_tokens=0,
                    cached_tokens=0,
                    successful=False,
                    error_type=type(e).__name__,
                    method=f"agent.run.{runtime_name}"
                )
                # Convert to AgentMetrics for backward compatibility
                agent_metrics = AgentMetrics.from_request_metrics(request_metrics)
                agent_metrics.trace_id = opts.trace_id
                agent_metrics.tools_used = [t.name for t in (definition.tools or [])]
                try:
                    await self.metrics_sink.record(agent_metrics)
                except Exception:
                    pass
            
            # Re-raise as ProviderError
            raise ProviderError(str(e), provider=runtime_name)


