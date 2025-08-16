# OpenAI Agents SDK — Architecture & Flows (ASCII)

## Components map

```text
+----------------------------+        +-----------------------------------+
|  User / Orchestrator       |  --->  |  Agents Runtime (OpenAI)          |
+----------------------------+        +-------------------+---------------+
                                                |           |
                                                v           v
                                         +--------+   +-----------+
                                         | Agent  |   |  Runner   |
                                         +---+----+   +-----+-----+
                                             |              |
                                             v              v
                                    Tools (functions)   Streaming events
```

## Non-stream run

```text
User → Build Agent → Runner.run → Result
                      |            └─ content, usage?, model, elapsed_ms
                      └─ executes agent loop (tools, guardrails)
```

## Streaming run

```text
User → Build Agent → Runner.run_stream ── emits → start → delta* → usage? → complete
                                        (normalize events; emit usage once)
```

## Structured outputs

```text
JSON schema (strict) → model supports strict schema → enforce during run
                                └→ additionally validate result post-hoc
```

## Determinism & policy

```text
Temperature policy (omit/1.0/clamp) + seed (if supported) + token-field mapping
```

## Error categories (normalized)

```text
auth | rate_limit | invalid_request | timeout | server_error | schema
```

## Error Flow - Non-Streaming

```text
┌─────────────┐     ┌───────────────┐     ┌──────────────┐
│ Agent.run() │ --> │ SDK Exception │ --> │ map_openai_  │
└─────────────┘     └───────────────┘     │ agents_error │
                                          └──────┬───────┘
                                                 │
                                                 v
                                          ┌──────────────┐
                                          │ Categorized  │
                                          │ ProviderErr  │
                                          └──────┬───────┘
                                                 │
                                                 v
                                          ┌──────────────┐
                                          │ Re-raise to  │
                                          │    caller    │
                                          └──────────────┘

Error Mapping Examples:
- "Rate limit exceeded" → RateLimitError (retryable=True)
- "Invalid API key" → AuthenticationError (retryable=False)
- "Guardrail blocked output" → SchemaError (retryable=False)
- "Tool execution failed" → InvalidRequestError (retryable=False)
```

## Error Flow - Streaming

```text
┌────────────────┐     ┌───────────────┐     ┌──────────────┐
│ Runner.stream  │ --> │ SDK Exception │ --> │ map_openai_  │
└────────────────┘     └───────────────┘     │ agents_error │
                                              └──────┬───────┘
                                                     │
                                                     v
                                              ┌──────────────┐
                                              │   Bridge     │
                                              │ on_error()   │
                                              └──────┬───────┘
                                                     │
                                                     v
                                              ┌──────────────┐
                                              │StreamError   │
                                              │   Event      │
                                              └──────┬───────┘
                                                     │
                                                     v
                                              ┌──────────────┐
                                              │EventManager  │
                                              │ emit_error() │
                                              └──────┬───────┘
                                                     │
                                                     v
                                              ┌──────────────┐
                                              │ Re-raise to  │
                                              │    caller    │
                                              └──────────────┘

The streaming error flow ensures:
1. Errors are mapped to our categories
2. Error events are emitted through the bridge
3. Callbacks receive typed StreamErrorEvent
4. Original error is re-raised for handling
```

## Event Mapping Flow

```text
OpenAI SDK Events              Bridge Methods              Our Events
─────────────────              ──────────────              ──────────
(start of stream)      -->     on_start()          -->     StreamStartEvent
content event          -->     on_delta(text)      -->     StreamDeltaEvent
tool_call event        -->     on_delta(metadata)  -->     StreamDeltaEvent
usage event            -->     on_usage()          -->     StreamUsageEvent
(end of stream)        -->     on_complete()       -->     StreamCompleteEvent
exception              -->     on_error()          -->     StreamErrorEvent

The AgentStreamingBridge:
- Normalizes all provider events
- Aggregates content and usage
- Tracks TTFT and metrics
- Handles JSON parsing if schema provided
- Sets self._last_bridge for result collection
```


