# OpenAI Agents SDK Integration — Implementation Guide

This guide shows how to adopt the OpenAI Agents SDK in our SDK runtime and how to run agents with streaming.

Reference: [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)

## Prerequisites

- Install dependencies: `pip install openai-agents`
- Set `OPENAI_API_KEY`

## Define an agent

1) Specify `instructions` (system), a `user_template`, and model.
2) Define tools as Python functions and provide JSON-schema parameters.
3) (Optional) Provide a JSON schema for structured output; strict mode where supported.

## Run non-streaming

High level flow:

1) Create an OpenAI Agent from your definition (instructions + tools + model settings)
2) Execute with the Agents SDK Runner
3) Normalize the result to include: content (text or JSON), usage (if available), model, elapsed_ms, provider metadata, optional cost

## Run with streaming

1) Execute `run_stream` with the Runner
2) Bridge events to your callbacks:
   - on_start(metadata)
   - on_delta(delta)
   - on_usage(usage) — emitted once; may be estimated if not provided
   - on_complete(result)
   - on_error(error)

## Structured outputs

- Use a JSON schema with root `additionalProperties: false` for strictness
- Validate produced outputs post-hoc even when strict mode is enabled

## Determinism

- Clamp temperature/top_p per capability policy
- Forward `seed` only when supported by the model

## Minimal metrics (optional)

- Record request duration and optional TTFT for streaming runs
- Use `request_id` / `trace_id` for correlation

## Troubleshooting

- ImportError: ensure `openai-agents` is installed and Python environment is active
- Authentication: check `OPENAI_API_KEY`
- Schema errors: ensure your JSON schema is valid and strict mode is appropriate for the model


