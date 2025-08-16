# OpenAI Agents SDK Integration — Technical Design

Reference: [OpenAI Agents SDK docs](https://openai.github.io/openai-agents-python/)

## Architecture

```
+--------------------------+          +----------------------------------+
|  User / Orchestrator     |  calls   |  SDK Agents Runtime (OpenAI)     |
+--------------------------+  ----->  +----------------+-----------------+
                                               |               |
                                               v               v
                                      +--------------+   +-----------+
                                      |  Agent (OA)  |   |  Runner   |
                                      +------+-------+   +-----+-----+
                                             |                 |
                                             v                 v
                                       Tools (functions)   Streaming events
                                                             |   |   |  
                                                             v   v   v  
                                              start / delta / usage / complete
```

## Components

- Agents runtime adapter (OpenAI):
  - Creates an OpenAI Agent from our definition (instructions, tools, model, settings)
  - Executes via Runner for non-streaming and streaming
  - Bridges OpenAI streaming events to our event callbacks
- Tools:
  - Python callables exposed with JSON-schema parameter definitions
  - Deterministic by default (no external side effects)
- Guardrails and schema:
  - Structured outputs use strict JSON schema where supported
  - Always post-validate final outputs against the provided schema

## Policies (capability-driven)

- Temperature: omit or clamp depending on model capabilities; some models may require `temperature=1.0`
- Token limits: map `max_tokens` to provider-required fields (e.g., `max_output_tokens` where applicable)
- Seed: forward `seed` only when supported by the model

## Observability (pre-production)

- Minimal metrics: request duration, optional TTFT for streaming
- Correlation: support `request_id` and `trace_id` propagation through events and results
- Defaults: observability is light; heavy sinks and exporters are out of scope initially

## Error model

- Normalize errors to a small set of categories: authentication, rate limit, invalid request, timeout, server error, schema
- Preserve the original exception for diagnostics; mark retryability where appropriate

## Usage and cost

- Usage: prefer provider-supplied usage; otherwise aggregate at end of stream as a fallback
- Cost: compute from known per-model pricing when available; otherwise omit

## Acceptance criteria

- Agents SDK is required (no fallback)
- Normalized events: start, delta, usage (once), complete, error
- Structured outputs validated (strict where supported)
- Minimal, opt-in metrics are emitted without significant overhead


