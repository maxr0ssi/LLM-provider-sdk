## Nexus SDK – Architecture (ASCII diagrams)

### Module layout
```
steer_llm_sdk/
  llm/
    providers/ (openai, anthropic, xai)
    capabilities.py
    router.py
  agents/
    models/ (AgentDefinition, AgentOptions, AgentResult)
    runner/ (agent_runner.py, event_manager.py, stream_adapter.py, determinism.py, idempotency.py)
    tools/ (tool_definition.py, tool_executor.py, builtins.py, schema_utils.py)
    metrics.py, metrics_sink_otlp.py
```

### Request flow (non‑stream)
```
Caller
  └─ AgentRunner.run(definition, variables, options)
       ├─ determinism.apply → params
       ├─ capabilities.get(model)
       ├─ if schema & supports_json_schema → Responses API path (OpenAI)
       ├─ router.generate(messages, model, params)
       │    └─ provider.generate(...)
       ├─ validate_json_schema(output)
       ├─ idempotency.store(if key)
       └─ metrics.record
```

### Streaming flow
```
Caller
  └─ AgentRunner.run(..., streaming=True)
       ├─ events.on_start
       ├─ for delta in router.generate_stream(..., return_usage=True):
       │     ├─ events.on_delta(stream_adapter.normalize_delta(delta))
       │     └─ events.on_usage(usage)   # emitted once when available
       ├─ validate (on completion)
       ├─ events.on_complete(result)
       └─ metrics.record
```

### OpenAI Responses mapping
```
params.response_format → text.format={ type: json_schema, name, schema[, strict] }
system → instructions (optional via responses_use_instructions)
max_tokens → max_output_tokens (per capability)
temperature → omitted on gpt‑5‑mini; fixed or supported per capability
```

### Determinism & idempotency
```
deterministic=True:
  temperature=0.0 (unless fixed or unsupported)
  top_p<=0.1
  seed propagated if supports_seed
idempotency:
  key → check_duplicate/store_result (TTL, LRU)
```

### Tools
```
Local, deterministic only:
  - extract_json(text)
  - json_repair(text, schema?)
  - format_validator(output, schema)
schema_from_callable(func) for parameter schemas
```

### Errors & retries
```
ProviderError raised by providers → retried by RetryManager (limited attempts)
```


