# OpenAI Agents SDK Integration — Configuration

Reference: [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)

## Installation

```bash
pip install openai-agents
```

## Environment

- `OPENAI_API_KEY`: required for all calls

## Runtime settings (recommended defaults)

- Temperature: 0.7 (omit or clamp where model requires fixed values)
- Max tokens: set based on task; ensure model’s context limits are respected
- Strict JSON: enable where structured outputs are critical (models supporting strict schema)

## Streaming options (light)

- Enable streaming for latency-sensitive tasks
- Optionally collect TTFT (time-to-first-token)
- Keep event callbacks lightweight to avoid backpressure

## Observability (pre-production)

- Keep metrics minimal; record duration and optional TTFT only
- Use `request_id` and `trace_id` to correlate logs and results


