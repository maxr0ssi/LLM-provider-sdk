Doing a focused repo audit for redundancies, legacy, and architectural rough edges. Highlighting concrete hotspots and recommended fixes.

### High‑impact issues to clean before release
- Duplicate models in `agents` (Tool, AgentDefinition)
  - Two `Tool` and two `AgentDefinition` definitions exist in `agents/models/agent_definition.py`. This is a clear duplication and can cause conflicting imports.
  - Evidence:
```12:64:steer_llm_sdk/agents/models/agent_definition.py
class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    handler: Callable
    deterministic: bool = True

class AgentDefinition(BaseModel):
    system: str
    user_template: str
...
class Tool(BaseModel):
    """Tool definition for local deterministic functions."""
...
class AgentDefinition(BaseModel):
    """Definition of an agent with its configuration."""
```
  - There is also a separate `Tool` in `agents/tools/tool_definition.py`, making three places defining a Tool schema:
```1:15:steer_llm_sdk/agents/tools/tool_definition.py
class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    handler: Callable
    deterministic: bool = True
```
  - Action: Keep a single `Tool` definition (recommend `agents/tools/tool_definition.py`) and import it everywhere. In `agents/models/agent_definition.py`, remove the duplicated lightweight `Tool`/`AgentDefinition` blocks and use only the richer, final models.

- API client return type mismatch
  - `SteerLLMClient.generate` is annotated and documented as returning `str` but returns a `GenerationResponse`. This is a correctness and typing issue.
```54:123:steer_llm_sdk/api/client.py
async def generate(... ) -> str:
    """Generate text ..."""
    ...
    return response
```
  - Action: Change signature to return `GenerationResponse` and update docstring; or actually return `response.text` if you want to keep the `str` API (but that would break current callers using usage/cost).

- Core router coupled to FastAPI at the wrong layer
  - `LLMRouter` is a core SDK class but imports FastAPI types and raises `HTTPException` from deep inside the core. This leaks HTTP concerns into library code and forces `fastapi` as a hard dependency.
```1:27:steer_llm_sdk/core/routing/router.py
from fastapi import APIRouter, Depends, HTTPException
...
class LLMRouter:
...
    raise HTTPException(status_code=400, detail=...)
```
  - Action:
    - Remove FastAPI from the core router: raise `ProviderError` or SDK errors internally. Only the HTTP wrapper should translate to `HTTPException`.
    - Move FastAPI endpoints into a thin optional module (e.g., `steer_llm_sdk/http/api.py`) behind an extra (e.g., extras_require["http"]) to avoid hard dependency in the SDK package.

- Streaming logic duplicated across three surfaces
  - Three overlapping paths: `EventManager` callbacks, `streaming/processor` pipeline, and `StreamingHelper` orchestrators. `AgentRunner` implements its own streaming loop instead of reusing `StreamingHelper`, and the API client wires `EventProcessor` while `AgentRunner` does manual `EventManager` emission.
```18:173:steer_llm_sdk/streaming/helpers.py
class StreamingHelper: collect_with_usage(...), stream_with_events(...)
```
```17:174:steer_llm_sdk/streaming/manager.py
class EventManager: ... emit_* + create_* factory
```
```1:527:steer_llm_sdk/streaming/processor.py
class EventProcessor ... create_event_processor(...)
```
  - Action: Pick one orchestration path:
    - Recommend: unify on `StreamingHelper` + `StreamAdapter` for loops, and make both `AgentRunner` and `LLMRouter` streaming path call into it; optionally mount `EventProcessor` as an `adapter.set_event_processor(...)` to standardize event emission. Remove duplicate manual event wiring.

- Deprecated error module left in tree
  - `steer_llm_sdk/reliability/errors.py` is explicitly marked deprecated and unused.
```1:36:steer_llm_sdk/reliability/errors.py
"""Deprecated error module."""
```
  - Action: Remove it before release, or at minimum add `warnings.warn(DeprecationWarning)` on import and hide it from public exports.

- Observability duplication (“legacy” AgentMetrics)
  - `AgentMetrics` is marked “Legacy” but is still used in `AgentRunner`. Meanwhile, a richer metrics model exists (`RequestMetrics`, `StreamingMetrics`, etc.).
```158:186:steer_llm_sdk/observability/models.py
class AgentMetrics: """Legacy agent metrics for backward compatibility."""
```
  - Action: Replace `AgentRunner`’s usage of `AgentMetrics` with `RequestMetrics`/`StreamingMetrics` where appropriate, or provide an adapter that converts modern metrics to legacy only at sinks that require it.

### Medium‑impact cleanups
- Packaging redundancy and heavyweight deps
  - Both `pyproject.toml` and `setup.py` define package metadata. Prefer pyproject-only builds (PEP 517) and remove `setup.py` to prevent divergence.
  - `fastapi` is listed as a core dependency; if you move HTTP to an optional module, shift it to an extra to slim the base install.
- Manifest rules are over‑broad for Markdown
  - `MANIFEST.in` globally excludes all `*.md` then re-includes `README.md`. This is fine to keep docs out of the wheel, but verify you don’t need any runtime `.md` assets; you already include `README.md` explicitly twice (line 1 and global-include). You can drop the duplicate include.
```1:18:MANIFEST.in
include README.md
...
global-exclude *.md
global-include README.md
```
- Legacy pricing compatibility blocks scattered
  - Several “legacy blended pricing” fallbacks remain in selector/router/models. They’re guarded, but consider consolidating into a single compatibility shim to simplify removal later.
```145:175:steer_llm_sdk/core/routing/selector.py
# Fallback: blended single-rate pricing if available (legacy tests)
```
```146:172:steer_llm_sdk/core/routing/router.py
# Fallback approximation for legacy pricing
```
```85:91:steer_llm_sdk/models/generation.py
# Legacy blended pricing support for tests
```
  - Action: Centralize into one helper and reference it from the few call sites.

- Basic retry vs enhanced retry surface
  - `EnhancedRetryManager` maintains a `execute_with_retry_legacy` wrapper to the base manager.
```337:347:steer_llm_sdk/reliability/enhanced_retry.py
async def execute_with_retry_legacy(...):
    """Legacy method for backward compatibility."""
```
  - Action: Grep usages and eliminate the legacy path if unused.

- Router exception model consistency
  - `LLMRouter.generate()` and `generate_stream()` sometimes catch `ProviderError` and translate to `HTTPException`, sometimes catch generic `Exception`. After decoupling HTTP, convert to consistent SDK exceptions and let the HTTP layer map them.

- Stream retry error classification in `StreamAdapter`
  - `_is_retryable_error` does a simple name check; you already have robust error mappers/classifier. Use that for consistency.

### Low‑impact polish
- `print()` in CLI and examples is fine, but ensure no stray prints are in library paths (grep shows only examples/cli/tests).
- Optional: tighten `EventManager` typing by removing legacy `Any` callback option now that typed events exist, or deprecate the `Any` signatures.

### Suggested concrete changes (minimal, surgical)
- Remove duplicate definitions and fix API typing:
  - Unify Tool/AgentDefinition:
    - Delete the first minimal `Tool` and `AgentDefinition` blocks in `agents/models/agent_definition.py` and import `Tool` from `agents/tools/tool_definition.py`.
  - Fix API client typing:
    - Change `SteerLLMClient.generate` signature to return `GenerationResponse` and update docstring.
- Decouple HTTP from core:
  - Extract the FastAPI endpoints from `core/routing/router.py` into `steer_llm_sdk/http/api.py` (or similar). Replace `HTTPException` raises in router with SDK errors; keep a tiny FastAPI layer that maps them.
  - Move `fastapi` to an optional extra.
- Consolidate streaming paths:
  - Refactor `AgentRunner` streaming branch to use `StreamingHelper.stream_with_events` and `StreamAdapter` to avoid duplicate loop and event emission logic. Keep `EventProcessor` integration by setting it on the adapter when provided.
- Remove deprecated/legacy:
  - Delete `steer_llm_sdk/reliability/errors.py` and any dead legacy helpers that greps show as unused.
  - Replace `AgentMetrics` production with modern metrics models; optionally keep a converter for sinks that still expect legacy.
- Tidy pricing legacy code:
  - Wrap the legacy blended-pricing fallbacks into one helper and reference it from router/selector/models. Keep the override system as-is (it’s already behind an env guard).

If you want, I can implement the minimal, high-impact edits (Tool/AgentDefinition unification and `SteerLLMClient.generate` type fix) in a branch to keep momentum.

- Unification targets: `steer_llm_sdk/agents/models/agent_definition.py`, `steer_llm_sdk/agents/tools/tool_definition.py`
- API client target: `steer_llm_sdk/api/client.py`
- Optional extraction target: `steer_llm_sdk/core/routing/router.py` (HTTP decoupling)

- Consolidated highlights:
  - Duplicate `Tool`/`AgentDefinition` definitions exist and should be unified.
  - `SteerLLMClient.generate` returns `GenerationResponse` but is typed/docs as `str`.
  - Core routing is coupled to FastAPI and throws `HTTPException`; move HTTP to optional layer.
  - Streaming/event flow is duplicated; centralize on `StreamingHelper` + `StreamAdapter` and use `EventProcessor` via adapter.
  - Deprecated `reliability/errors.py` remains; remove.
  - Metrics has legacy and modern models; prefer modern and convert only at sinks.
  - Legacy pricing scaffolding exists in multiple places; centralize for easier future removal.