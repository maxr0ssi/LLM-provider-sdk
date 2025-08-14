from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict

from ...core.capabilities import get_capabilities_for_model
from ...core.routing import LLMRouter
from ...reliability.errors import ProviderError
from ...observability import AgentMetrics, MetricsSink
from ..models.agent_definition import AgentDefinition
from ..models.agent_options import AgentOptions
from ..models.agent_result import AgentResult
from ...reliability.retry import RetryConfig, RetryManager
from ..validators.json_schema import validate_json_schema
from .determinism import apply_deterministic_policy
from ...streaming.manager import EventManager
from ...reliability.idempotency import IdempotencyManager
from ...streaming.adapter import StreamAdapter
from ...reliability.budget import clamp_params_to_budget


class AgentRunner:
    def __init__(self, metrics_sink: MetricsSink | None = None) -> None:
        self.router = LLMRouter()
        self.adapter = StreamAdapter("generic")
        self.idempotency = IdempotencyManager()
        self.metrics_sink = metrics_sink

    async def run(self, definition: AgentDefinition, variables: Dict[str, Any], options: Dict[str, Any] | AgentOptions) -> AgentResult:
        opts = options if isinstance(options, AgentOptions) else AgentOptions(**options)
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
            events = EventManager(
                on_start=opts.metadata.get("on_start"),
                on_delta=opts.metadata.get("on_delta"),
                on_usage=opts.metadata.get("on_usage"),
                on_complete=opts.metadata.get("on_complete"),
                on_error=opts.metadata.get("on_error"),
            )
            await events.emit_start({"model": definition.model})

            final_usage = None
            collected = []
            # Stream with soft wall-clock budget
            ms_budget = None
            if isinstance(budget, dict) and "ms" in budget:
                ms_budget = int(budget["ms"])

            try:
                async for item in self.router.generate_stream(messages, definition.model, params, return_usage=True):
                    if isinstance(item, tuple):
                        chunk, usage_data = item
                        if chunk is not None:
                            await events.emit_delta(self.adapter.normalize_delta(chunk))
                            collected.append(chunk)
                        if usage_data is not None:
                            final_usage = usage_data["usage"]
                            await events.emit_usage(final_usage)
                    else:
                        await events.emit_delta(self.adapter.normalize_delta(item))
                        collected.append(item)

                    if ms_budget is not None and (time.time() - start) * 1000 >= ms_budget:
                        break
            except Exception as e:
                await events.emit_error(e)
                raise ProviderError(str(e))

            text = "".join(collected)
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
                usage=final_usage or {},
                model=definition.model,
                elapsed_ms=int((time.time() - start) * 1000),
                provider_metadata={},
                trace_id=opts.trace_id,
            )
            if final_usage is None:
                await events.emit_usage({})
            await events.emit_complete(result)
            # Metrics (best-effort)
            if self.metrics_sink:
                usage = final_usage or {}
                metrics = AgentMetrics(
                    request_id=None,
                    trace_id=opts.trace_id,
                    model=definition.model,
                    latency_ms=result.elapsed_ms,
                    input_tokens=int(usage.get("prompt_tokens", 0)),
                    output_tokens=int(usage.get("completion_tokens", 0)),
                    cached_tokens=int(usage.get("cache_info", {}).get("cached_tokens", 0)) if isinstance(usage.get("cache_info", {}), dict) else 0,
                    retries=0,
                    error_class=None,
                    tools_used=[t.name for t in (definition.tools or [])],
                )
                try:
                    await self.metrics_sink.record(metrics)
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
            except Exception as e:
                raise ProviderError(str(e))

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
            metrics = AgentMetrics(
                request_id=None,
                trace_id=opts.trace_id,
                model=definition.model,
                latency_ms=result.elapsed_ms,
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                cached_tokens=int(usage.get("cache_info", {}).get("cached_tokens", 0)) if isinstance(usage.get("cache_info", {}), dict) else 0,
                retries=0,
                error_class=None,
                tools_used=[t.name for t in (definition.tools or [])],
            )
            try:
                await self.metrics_sink.record(metrics)
            except Exception:
                pass
        if opts.idempotency_key:
            self.idempotency.store_result(opts.idempotency_key, result)
        return result


