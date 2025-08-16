# Directory Restructuring Plan for Layered-Modular Architecture

## Current Structure Issues
The current structure mixes concerns and doesn't clearly reflect the layered architecture:
- Providers are buried under `llm/providers/`
- Agents are at the top level but should be in a specific layer
- No clear separation between layers
- Normalization is under `llm/` but should be in its own layer

## Proposed New Structure

```
steer_llm_sdk/
├── api/                          # Layer 1: Public API Layer
│   ├── __init__.py
│   ├── client.py                 # SteerLLMClient (moved from main.py; main.py becomes shim)
│   ├── agents.py                 # Agent API exports
│   └── cli.py                    # CLI interface
│
├── core/                         # Layer 2-4: Core Business Logic (provider-agnostic)
│   ├── __init__.py
│   ├── decision/                 # Layer 2: Decision & Normalization
│   │   ├── __init__.py
│   │   ├── router.py            # Decides Agent vs Direct path
│   │   └── message_shaper.py   # Message formatting logic
│   │
│   ├── normalization/           # Layer 2: Normalization (moved from llm/normalizers)
│   │   ├── __init__.py
│   │   ├── params.py
│   │   ├── usage.py
│   │   └── streaming.py         # NEW: Stream event normalization
│   │
│   ├── capabilities/            # Layer 3: Capability & Policy
│   │   ├── __init__.py
│   │   ├── registry.py          # Model capability registry
│   │   ├── models.py            # ProviderCapabilities model
│   │   ├── policy.py            # Determinism, budget/parameter clamping
│   │   └── loader.py            # Load capabilities from config
│   │
│   └── routing/                 # Layer 4: Routing
│       ├── __init__.py
│       ├── router.py            # Provider-agnostic router
│       └── selector.py          # Provider selection logic
│
├── providers/                    # Layer 5: Provider Adapters
│   ├── __init__.py
│   ├── base.py                  # ProviderAdapter ABC
│   ├── openai/
│   │   ├── __init__.py
│   │   ├── adapter.py           # OpenAI adapter implementation
│   │   ├── chat.py              # Chat Completions specific
│   │   └── responses.py         # Responses API specific (JSON schema via text.format)
│   ├── anthropic/
│   │   ├── __init__.py
│   │   └── adapter.py
│   ├── xai/
│   │   ├── __init__.py
│   │   └── adapter.py
│   └── local/                   # Future: Local/on-prem adapters
│       └── __init__.py
│
├── streaming/                    # Layer 6: Streaming & Events
│   ├── __init__.py
│   ├── events.py                # Event definitions
│   ├── adapter.py               # StreamAdapter (delta normalization)
│   ├── types.py                 # StreamDelta and related types
│   └── manager.py               # EventManager (on_start/on_delta/...)
│
├── reliability/                  # Layer 7: Errors, Retries & Idempotency
│   ├── __init__.py
│   ├── errors.py                # Typed errors
│   ├── retry.py                 # RetryManager
│   └── idempotency.py           # IdempotencyManager
│   └── budget.py                # Token/time budget enforcement
│
├── observability/               # Layer 8: Metrics & Observability
│   ├── __init__.py
│   ├── metrics.py               # AgentMetrics
│   ├── sinks/
│   │   ├── __init__.py
│   │   ├── base.py              # MetricsSink interface
│   │   └── otlp.py              # OTLP implementation
│   └── collector.py             # Metrics collection logic
│
├── agents/                      # Agent Framework (uses layers above)
│   ├── __init__.py
│   ├── models/                  # Agent models
│   │   ├── __init__.py
│   │   ├── definition.py        # AgentDefinition
│   │   ├── options.py           # AgentOptions
│   │   └── result.py            # AgentResult
│   ├── runner/                  # Agent execution
│   │   ├── __init__.py
│   │   └── runner.py            # Applies policy, routes, manages streaming
│   ├── tools/                   # Tool framework
│   │   ├── __init__.py
│   │   ├── definition.py
│   │   ├── executor.py
│   │   ├── builtins.py
│   │   └── schema_utils.py
│   └── validators/              # Validation
│       ├── __init__.py
│       └── json_schema.py
│
├── models/                      # Shared data models
│   ├── __init__.py
│   ├── generation.py            # GenerationParams, Response
│   ├── conversation.py          # ConversationMessage
│   └── config.py                # ModelConfig
│
├── config/                      # Configuration
│   ├── __init__.py
│   ├── models.py                # Model configurations
│   └── constants.py             # LLMConstants
│
├── integrations/                # Optional Provider-Native Adapters
│   ├── __init__.py
│   └── openai_agents/           # OpenAI Agents SDK adapter
│       ├── __init__.py
│       └── adapter.py
│
└── __init__.py                  # Package exports
```

### Why this tree (Nexus-aligned)

- Provider-agnostic core: Decisioning, normalization, capabilities, routing, streaming, reliability, and observability are isolated from provider code to keep the SDK generic and Steer-free.
- Provider isolation: All provider-specific logic is under `providers/`, enabling OpenAI Responses API evolution without touching core.
- Determinism/budgets centralized: Implemented in `core/capabilities/policy.py` and `reliability/budget.py` for consistent behavior across models.
- Clean Agent boundary: `agents/` composes lower layers (callbacks, tools) without embedding provider details.
- Optional native agent SDKs: `integrations/openai_agents/` lets orchestrators opt-in to OpenAI Agents SDK while keeping the core agnostic.
- Extensibility/testability: New providers or features land in their layer with minimal ripple effects.

## Migration Strategy (Executed)

### Phase 0.5: Directory Restructuring (Completed 2025-08-14)
1. Created new directory structure (api/, core/, providers/, streaming/, reliability/, observability/, integrations/)
2. Moved files with git mv to preserve history
3. Updated all imports across the codebase
4. Ensured tests still pass in the new structure

### Benefits of New Structure (Observed)
1. **Clear Layer Separation**: Each directory represents a distinct layer
2. **Provider Isolation**: All provider-specific code in one place
3. **Core Logic Centralized**: Business logic separated from adapters
4. **Extensibility**: Easy to add new providers/integrations
5. **Testability**: Each layer can be tested independently

### Import Examples After Restructuring (Confirmed)

```python
# Public API (what users import)
from steer_llm_sdk import SteerLLMClient
from steer_llm_sdk.agents import AgentDefinition, AgentRunner

# Internal imports follow layer hierarchy
from steer_llm_sdk.core.normalization import normalize_usage
from steer_llm_sdk.core.capabilities import get_model_capabilities
from steer_llm_sdk.providers.base import ProviderAdapter
from steer_llm_sdk.streaming import StreamAdapter
```

### Backward Compatibility Status (Post 0.5)
1. Legacy shims removed in 0.3.0 development cycle to reduce surface area
2. Old import paths are no longer supported; documented migration in `migration.md`
3. Public API remains stable (`SteerLLMClient`, generate/stream split preserved)
4. For any downstreams, update imports to the new layer paths

### Files to Move (Examples)

| Current Location | New Location | Notes |
|------------------|--------------|-------|
| `main.py` | `api/client.py` | Keep shim for compatibility |
| `cli.py` | `api/cli.py` | |
| `llm/router.py` | `core/routing/router.py` | |
| `llm/registry.py` | `core/routing/selector.py` | Split registry logic |
| `llm/capabilities.py` | `core/capabilities/loader.py` | |
| `llm/normalizers/*` | `core/normalization/*` | |
| `llm/providers/*` | `providers/*` | Flatten structure |
| `llm/base.py` | `providers/base.py` | |
| `agents/models/capabilities.py` | `core/capabilities/models.py` | |
| `agents/errors.py` | `reliability/errors.py` | |
| `agents/retry.py` | `reliability/retry.py` | |
| `agents/runner/idempotency.py` | `reliability/idempotency.py` | |
| `agents/runner/stream_adapter.py` | `streaming/adapter.py` | |
| `agents/runner/event_manager.py` | `streaming/manager.py` | |
| `agents/metrics*.py` | `observability/*` | |
| `LLMConstants.py` | `config/constants.py` | |

## Implementation Order

1. **Create Structure** (Week 0.5)
   - Create all new directories
   - Add __init__.py files
   - Set up layer documentation

2. **Move Core Components** (Week 1)
   - Move normalization modules
   - Move capability system
   - Move routing logic
   - Update imports

3. **Move Providers** (Week 1)
   - Restructure provider directory
   - Move base adapter
   - Update provider imports

4. **Move Support Systems** (Week 2)
   - Move streaming components
   - Move reliability components
   - Move observability components

5. **Move Agent Framework** (Week 2)
   - Keep agents as cohesive unit
   - Update internal imports
   - Ensure tools work

6. **Compatibility & Testing** (Week 2)
   - Add compatibility shims
   - Update all tests
   - Document migration

## Success Criteria
- All tests pass after restructuring
- Clear separation between layers
- No circular dependencies
- Easy to trace request flow through layers
- New provider can be added without touching core