# Agent SDK Guide (v1)

Purpose: Provide a thin, repeatable scaffold for building Stage/Dimension Agents.

## Features
- FastAPI endpoint templates: POST /task_offer and POST /task_result
- Strict Pydantic schemas for A2A envelopes and payloads
- Constrained JSON helpers (grammar/toolcall) to reduce parse failures
- Self-check validator for verdicts (annotation schema, score bounds)
- Replica merge helper (confidence-weighted, trimmed mean)

## Skeleton
```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Envelope(BaseModel):
    version: str
    message_type: str
    task_id: str
    trace_id: str
    issued_at: str
    ttl: int
    idempotency_key: str
    agent_version: str

class Offer(Envelope):
    prompt: str
    # add: dimension, scoring_contract, run_id, seed for dimension agents

class Result(Envelope):
    verdict: dict | None = None
    elapsed_ms: int | None = None
    model: str | None = None

@app.post("/task_offer")
async def task_offer(offer: Offer):
    # validate offer → run worker → build verdict → return
    return Result(
        version=offer.version,
        message_type="task_result",
        task_id=offer.task_id,
        trace_id=offer.trace_id,
        issued_at=offer.issued_at,
        ttl=offer.ttl,
        idempotency_key=offer.idempotency_key,
        agent_version="clarity@0.1.0",
        verdict={"dimension":"clarity","run_id":"r1","score":58,"annotations":[],"confidence":0.72},
        elapsed_ms=812,
        model="gpt-4.1-mini"
    )

## Best Practices
- Deterministic mode flag (seed) for tests/CI
- Enforce schema before returning; no N/A placeholders
- Timeouts + graceful degradation (return partial verdict with confidence)
- Version pinning via agent_version

## SDK Boundaries (non-Steer, provider-agnostic)
- Provides: provider clients (Responses API), AgentDefinition, AgentRunner, Tool interface, streaming adapters.
- Does NOT provide: OA logic, K×D orchestration, Steer prompts/policies.
- Anyone can define agents (system/user/schema/tools/model/params) and run them.

## What to Expect from the SDK
- Consistent agent execution API across providers (e.g., OpenAI Responses, Anthropic, etc.)
- Structured outputs via JSON schema enforcement (`response_format` where supported)
- Optional streaming adapter that yields normalized deltas/events
- Optional local tool-calling integration (deterministic functions) per agent
- Capability registry that advertises provider/model features (streaming, json schema, seed)
- Normalized usage (input/output tokens) and request identifiers for observability

## How to Interact with It (conceptual)
1) Define an AgentDefinition
   - system message, user template, json schema, model name, params, tools[] (optional)
2) Call AgentRunner.run(definition, variables, options)
   - options: streaming (on/off), deterministic (on/off), budget (tokens/ms)
3) Receive: structured result (validated), usage metrics, provider metadata
4) (Optional) Subscribe to streaming callbacks to render progressive output

Note: The SDK does not orchestrate multi-stage flows; Steer (OA) composes agents and order.

## Stage Defaults (MVP)
- Intent: tools disabled (enable only normalize/dedupe if needed)
- Lightning: no tools
- Dimensions: tools disabled (enable local dedup/regex if needed)
- Referee: no tools
