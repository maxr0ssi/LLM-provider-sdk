# Nexus – Engineer Entry Point

## What this is
- Agent‑mesh refactor to improve evaluation quality and UX with an Orchestrator Agent (OA) calling stateless sub‑agents.
- MVP prioritizes token‑thrifty, deterministic, contract‑driven stages.

## System model (at a glance)
- Stages: Static (python local) → Intent (+ additional contract) → Lightning (caps) → Dimensions (K×D) → Referee (optional) → Aggregate.
- OA orchestrates via HTTP (A2A v1); TUI receives Streaming v2 events.

## MVP scope
- dims=[clarity, structure, feasibility], K=2, deterministic=true, referee off (auto only on large gaps).
- Providers: GPT‑5 mini (Responses API) for Intent/Lightning; fallback to 4.1‑mini.

## How to implement (high level)
1) Implement Intent Agent against `intent-contract.md` (Responses API + json schema).
2) Implement Lightning Agent (caps) and wire caps to OA.
3) Implement one Dimension Agent (clarity) with K=2; OA aggregates median/trim.
4) Stream stage events per `streaming-v2.md`.

## Consolidated index (start here)
- Overview & plan
  - `overview.md` – executive overview and architecture
  - `product-quality-plan.md` – quality plan, MVP mode, readiness checklist
  - `decisions.md` – key choices and rationale
  - `glossary.md` – terms used across specs
- Protocols & streaming
  - `protocol-a2a-v1.md` – envelopes, offers/results, partials (drip‑feed)
  - `streaming-v2.md` – event types, ordering, payload hints
- Orchestrator & SDK
  - `orchestrator-spec.md` – OA responsibilities, blackboard, drip‑feed
  - `agent-sdk-guide.md` – SDK boundaries, expectations, interaction model
  - `sdk-deliverables.md` – deliverables, capability matrix, interfaces, tests, rollout
- Contracts (agents consume/produce)
  - `intent-contract.md` – IntentPacket + ScoringContract schemas
- Diagrams
  - `diagrams.md` – topology, macro flow, replica flow

## Core requirements (build contract)
- Stage order (frozen for MVP)
  - Static (local) → Intent (required) → Lightning (on) → Dims [clarity,structure,feasibility], K=2 → Referee (off; auto only on large gaps)
- Contracts (freeze)
  - IntentPacket + ScoringContract (see `intent-contract.md`)
  - Lightning result (caps + critical_issues + world_class + confidence)
  - Dimension verdict (score, annotations per schema, capped, confidence)
  - Referee decision (accept/partial/reject) – optional in MVP
- A2A protocol (freeze)
  - Envelope: version, message_type, task_id, trace_id, issued_at, ttl, idempotency_key, agent_version
  - Results: `status=partial|final` for drip‑feed; early_result/arbitration_hint payloads
- Streaming (freeze)
  - Events: STATIC_CHECK_COMPLETE, INTENT_EXTRACTION_COMPLETE, LIGHTNING_COMPLETE, REPLICA_COMPLETE, DIMENSION_EARLY_RESULT (optional), DIMENSION_COMPLETE, FINAL
  - Ordered by sequence_id; OA throttles EARLY_RESULT
- OA policies (defaults)
  - Early‑exit when |r1−r2| ≤ 8; third replica only if conflict_risk ≥ 0.7; referee off by default
  - Caps enforcement order: lightning caps → contract caps → aggregation clamp
- SDK boundaries
  - SDK is provider‑agnostic plumbing (Responses API, json schema, streaming, optional local tools)
  - No Steer business logic in SDK; OA composes agents and policies
- Provider defaults
  - Intent/Lightning: GPT‑5 mini via Responses; fallback to 4.1‑mini; deterministic mode on

## Flags (MVP defaults)
- deterministic=true
- dims=clarity,structure,feasibility
- k=2
- budgets: tokens≤1500, p95≤5s
- drip_feed.enabled=false

## Context & why
- OA + drip‑feed gives earlier, smarter decisions (adaptive K) without side‑channels.
- Intent‑first contract aligns all stages and reduces rubric drift.
- JSON schema enforcement cuts parse failures; deterministic mode stabilizes CI.
