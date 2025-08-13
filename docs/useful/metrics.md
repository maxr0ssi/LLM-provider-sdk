## Metrics (pluggable sink)

### What this is
- A minimal hook so you can capture per-run metrics (latency, tokens, retries, etc.) without coupling the SDK to any vendor.

### Interface
```python
from steer_llm_sdk.agents.metrics import AgentMetrics, MetricsSink

class MySink(MetricsSink):
    async def record(self, metrics: AgentMetrics) -> None:
        # send to your backend
        ...
    async def flush(self) -> None:
        ...
```

### Enabling it in the runner
```python
from steer_llm_sdk.agents.runner.agent_runner import AgentRunner
from my_sinks import MySink

runner = AgentRunner(metrics_sink=MySink())
```

### Optional OTel sink
- Provided as best-effort reference: `steer_llm_sdk/agents/metrics_sink_otlp.py`.
- If `opentelemetry-api` is absent, calls are no-ops.

### Emitted fields (AgentMetrics)
- request_id, trace_id, model, latency_ms
- input_tokens, output_tokens, cached_tokens
- retries, error_class
- tools_used

### Notes
- Keep sinks lightweight and non-blocking in async contexts.
- You control sampling; the SDK does not batch or buffer by default.

