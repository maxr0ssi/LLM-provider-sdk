# OpenAI Agents Adapter Bug Fixes - Technical Design

**Status**: Design Phase
**Created**: 2025-11-01
**Target Version**: 0.3.3
**Related Files**:
- `/Users/maxrossi/Documents/Prometheus/LLM-provider-sdk/steer_llm_sdk/integrations/agents/openai/adapter.py`
- `/Users/maxrossi/Documents/Prometheus/LLM-provider-sdk/tests/unit/integrations/agents/test_openai_agents_adapter.py`

---

## Executive Summary

The OpenAI Agents adapter at `steer_llm_sdk/integrations/agents/openai/adapter.py` contains 5 critical bugs that prevent it from functioning with the actual `openai-agents` SDK (>=0.1.0). These bugs went undetected because the unit tests use mocks instead of the real SDK. This design document specifies the exact fixes required to make the adapter compatible with the real openai-agents SDK API.

**Impact**: HIGH - The adapter is completely non-functional with the real SDK
**Complexity**: MEDIUM - Straightforward API corrections, but requires careful type handling
**Risk**: LOW - Changes are localized and well-defined

### Key Issues Identified

1. **Wrong Import Path** (Line 31): Importing from wrong module
2. **Wrong Parameter Name** (Line 194): Using `guardrails=` instead of `output_guardrails=`
3. **Incorrect Async Pattern** (Lines 234-237): Using `run_in_executor` with sync method instead of native async
4. **Type Mismatch** (Lines 133-150): Creating dict instead of ModelSettings object
5. **Model Field Misplacement** (Line 134): Including model in ModelSettings instead of Agent()

---

## Current State Analysis

### Bug #1: Wrong Import Path (Line 31)

**Current Code:**
```python
from agents.guardrails import GuardrailFunctionOutput
```

**Issue**: The `GuardrailFunctionOutput` class is exported from the top-level `agents` module, not from a `guardrails` submodule.

**Evidence**:
- Official SDK documentation shows: `from agents import GuardrailFunctionOutput`
- Web search confirmed this is the correct import pattern
- The current import will raise `ModuleNotFoundError: No module named 'agents.guardrails'`

**Actual SDK API:**
```python
# Correct import
from agents import GuardrailFunctionOutput
```

---

### Bug #2: Wrong Parameter Name (Line 194)

**Current Code:**
```python
agent = Agent(
    name="Assistant",
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,
    guardrails=guardrails if guardrails else None  # WRONG
)
```

**Issue**: The `Agent` class expects `output_guardrails`, not `guardrails`.

**Evidence**:
- GitHub issue #1912 shows usage: `output_guardrails=[OutputGuardrail(...)]`
- The SDK distinguishes between input and output guardrails
- Using wrong parameter name causes TypeError: "unexpected keyword argument 'guardrails'"

**Actual SDK API:**
```python
agent = Agent(
    name="Assistant",
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,
    output_guardrails=guardrails if guardrails else None  # CORRECT
)
```

---

### Bug #3: Incorrect Async Pattern (Lines 234-237)

**Current Code:**
```python
# Convert to sync execution in thread pool
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(
    None,
    partial(Runner.run_sync, prepared.agent, user_input)
)
```

**Issue**: The code unnecessarily wraps `Runner.run_sync()` in an executor when `Runner.run()` is the native async method.

**Problems**:
1. `Runner.run()` is already async - no need for executor
2. `Runner.run_sync()` explicitly doesn't work in async contexts (per docs: "will not work if there's already an event loop")
3. Using `run_in_executor` with `run_sync` may cause event loop conflicts
4. Performance overhead from unnecessary thread pool execution

**Evidence**:
- SDK docs: "Runner.run() is an asynchronous method that runs a workflow"
- SDK docs: "Runner.run_sync() will not work if there's already an event loop (e.g. inside an async function)"
- This code is already in an async function (`async def run()`)

**Actual SDK API:**
```python
# Native async - no executor needed
result = await Runner.run(prepared.agent, user_input)
```

---

### Bug #4: Type Mismatch - Dict Instead of ModelSettings (Lines 133-150)

**Current Code:**
```python
# Extract model settings for Agent
model_settings = {
    "model": definition.model,  # Wrong location
}

# Map normalized parameters to Agent settings
if "temperature" in normalized_params:
    model_settings["temperature"] = normalized_params["temperature"]
if "top_p" in normalized_params:
    model_settings["top_p"] = normalized_params["top_p"]

# ... more dict assignments ...

# Later passed to Agent
agent = Agent(
    # ...
    model_settings=model_settings,  # Passing dict instead of ModelSettings object
    # ...
)
```

**Issue**: The code creates a dictionary and passes it to `model_settings=`, but the SDK expects a `ModelSettings` object.

**Evidence**:
- SDK documentation shows `ModelSettings` is a dataclass
- Type signature: `model_settings: ModelSettings | None`
- Passing a dict will cause type errors or unexpected behavior

**Actual SDK API:**
```python
from agents import ModelSettings

# Create ModelSettings object
model_settings = ModelSettings(
    temperature=normalized_params.get("temperature"),
    top_p=normalized_params.get("top_p"),
    max_tokens=normalized_params.get("max_tokens"),
    # ... other parameters
)
```

---

### Bug #5: Model Field Location (Line 134)

**Current Code:**
```python
model_settings = {
    "model": definition.model,  # WRONG - model doesn't belong in ModelSettings
}

agent = Agent(
    name="Assistant",
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,  # model is inside here
    # ...
)
```

**Issue**: The `model` parameter should be passed directly to `Agent()`, not included in `ModelSettings`.

**Evidence**:
- SDK documentation shows usage: `Agent(model="gpt-5-nano", ...)`
- `ModelSettings` documentation lists all fields - `model` is not among them
- ModelSettings parameters: temperature, top_p, frequency_penalty, presence_penalty, tool_choice, parallel_tool_calls, truncation, max_tokens, etc.

**Actual SDK API:**
```python
agent = Agent(
    name="Assistant",
    model=definition.model,  # CORRECT - model is a direct Agent parameter
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=ModelSettings(...),  # No 'model' field inside
    # ...
)
```

---

## Proposed Architecture Changes

### 1. Import Corrections

**Location**: Lines 28-31

**Before:**
```python
try:
    from agents import Agent, Runner, function_tool
    from agents.guardrails import GuardrailFunctionOutput  # WRONG
    AGENTS_SDK_AVAILABLE = True
```

**After:**
```python
try:
    from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings
    AGENTS_SDK_AVAILABLE = True
```

**Rationale**:
- Import all SDK primitives from top-level `agents` module
- Add `ModelSettings` to imports for proper type usage
- Consolidate imports for clarity

---

### 2. ModelSettings Construction

**Location**: Lines 132-154

**Before:**
```python
# Extract model settings for Agent
model_settings = {
    "model": definition.model,
}

# Map normalized parameters to Agent settings
if "temperature" in normalized_params:
    model_settings["temperature"] = normalized_params["temperature"]
if "top_p" in normalized_params:
    model_settings["top_p"] = normalized_params["top_p"]

# Handle max tokens
for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
    if field in normalized_params:
        model_settings["max_output_tokens"] = normalized_params[field]
        break

if options.seed and capabilities.supports_seed:
    model_settings["seed"] = options.seed
```

**After:**
```python
# Build ModelSettings object for Agent
# Note: ModelSettings does NOT include 'model' - that's passed separately to Agent()
model_settings_kwargs = {}

# Map normalized parameters to ModelSettings fields
if "temperature" in normalized_params:
    model_settings_kwargs["temperature"] = normalized_params["temperature"]
if "top_p" in normalized_params:
    model_settings_kwargs["top_p"] = normalized_params["top_p"]

# Handle max tokens - SDK uses 'max_tokens' field
for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
    if field in normalized_params:
        model_settings_kwargs["max_tokens"] = normalized_params[field]
        break

# Create ModelSettings object
model_settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None
```

**Rationale**:
- `ModelSettings` is a dataclass - must be instantiated properly
- Remove `model` from settings (it's an Agent parameter, not ModelSettings)
- Use `max_tokens` field name (per ModelSettings API spec)
- Create object only if we have parameters (None is valid for Agent)
- Note: `seed` is NOT a ModelSettings parameter - it should be passed via `extra_args` if needed

**Interface Contract**:
```python
# ModelSettings fields (all optional):
ModelSettings(
    temperature: float | None = None,
    top_p: float | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
    max_tokens: int | None = None,
    tool_choice: ToolChoice | None = None,
    parallel_tool_calls: bool | None = None,
    truncation: Literal["auto", "disabled"] | None = None,
    # ... and many more optional fields
    extra_args: dict[str, Any] | None = None,  # For provider-specific params like seed
)
```

---

### 3. Agent Construction with Correct Parameters

**Location**: Lines 188-195

**Before:**
```python
# Create the OpenAI Agent
agent = Agent(
    name="Assistant",
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,  # Dict passed, missing model param
    guardrails=guardrails if guardrails else None  # WRONG parameter name
)
```

**After:**
```python
# Create the OpenAI Agent
agent = Agent(
    name="Assistant",
    model=definition.model,  # ADDED: model is a direct parameter
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,  # Now a ModelSettings object (or None)
    output_guardrails=guardrails if guardrails else None  # FIXED: correct parameter name
)
```

**Rationale**:
- `model` must be passed directly to Agent, not in ModelSettings
- Parameter name is `output_guardrails`, not `guardrails`
- `model_settings` now receives a proper ModelSettings object

**Interface Contract**:
```python
# Agent.__init__ signature (simplified)
Agent(
    name: str,
    model: str,  # Required - model identifier
    instructions: str | Callable,
    tools: list[Callable] | None = None,
    model_settings: ModelSettings | None = None,
    output_guardrails: list[OutputGuardrail] | None = None,
    # ... other parameters
)
```

---

### 4. Use Native Async Runner.run()

**Location**: Lines 232-239

**Before:**
```python
# Run the agent synchronously
try:
    # Convert to sync execution in thread pool
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        partial(Runner.run_sync, prepared.agent, user_input)
    )
```

**After:**
```python
# Run the agent asynchronously
try:
    # Use native async Runner.run() method
    result = await Runner.run(prepared.agent, user_input)
```

**Rationale**:
- `Runner.run()` is the proper async method
- `Runner.run_sync()` explicitly doesn't work in async contexts
- Removes unnecessary thread pool overhead
- Cleaner, more idiomatic async code

**Interface Contract**:
```python
# Runner.run signature
async def run(
    agent: Agent,
    input: str | TResponseInputItem | list[TResponseInputItem],
    context: RunContext | None = None,
) -> RunResult:
    """Run an agent asynchronously."""
    ...

# Runner.run_sync signature (DO NOT USE in async contexts)
def run_sync(
    agent: Agent,
    input: str | TResponseInputItem | list[TResponseInputItem],
    context: RunContext | None = None,
) -> RunResult:
    """Sync wrapper - will not work if event loop already exists."""
    ...
```

---

### 5. Seed Parameter Handling

**Issue**: The current code tries to add `seed` to `model_settings`, but `seed` is not a standard ModelSettings field.

**Current Code (Lines 152-153)**:
```python
if options.seed and capabilities.supports_seed:
    model_settings["seed"] = options.seed
```

**Proposed Solution**:

**Option A: Use extra_args (RECOMMENDED)**
```python
# In model_settings_kwargs construction
if options.seed and capabilities.supports_seed:
    if "extra_args" not in model_settings_kwargs:
        model_settings_kwargs["extra_args"] = {}
    model_settings_kwargs["extra_args"]["seed"] = options.seed
```

**Option B: Check if SDK supports seed directly**
```python
# Research needed: Does openai-agents SDK support seed at Agent level?
# If yes, pass to Agent directly:
agent = Agent(
    # ...
    seed=options.seed if (options.seed and capabilities.supports_seed) else None,
)
```

**Recommendation**: Use Option A (extra_args) as it's guaranteed to work per the ModelSettings API spec, which explicitly supports `extra_args` for provider-specific parameters.

---

## Detailed Implementation Specifications

### File: `steer_llm_sdk/integrations/agents/openai/adapter.py`

#### Change 1: Fix Imports (Lines 28-38)

```python
# Lazy import for optional dependency
try:
    from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    Agent = None
    Runner = None
    function_tool = None
    GuardrailFunctionOutput = None
    ModelSettings = None  # ADD THIS LINE
```

**Changes**:
1. Line 30: Add `GuardrailFunctionOutput, ModelSettings` to import statement
2. Line 31: Remove separate import line
3. Line 38: Add `ModelSettings = None` to fallback

---

#### Change 2: Fix ModelSettings Construction (Lines 132-154)

**Replace entire section with:**

```python
# Build ModelSettings object for Agent
# Note: 'model' is NOT part of ModelSettings - it's passed separately to Agent()
model_settings_kwargs = {}

# Map normalized parameters to ModelSettings fields
if "temperature" in normalized_params:
    model_settings_kwargs["temperature"] = normalized_params["temperature"]
if "top_p" in normalized_params:
    model_settings_kwargs["top_p"] = normalized_params["top_p"]

# Handle max tokens - SDK ModelSettings uses 'max_tokens' field
# Our normalization layer may return max_tokens, max_completion_tokens, or max_output_tokens
# depending on the model, but ModelSettings expects 'max_tokens'
for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
    if field in normalized_params:
        model_settings_kwargs["max_tokens"] = normalized_params[field]
        break

# Handle seed via extra_args (seed is not a standard ModelSettings field)
if options.seed and capabilities.supports_seed:
    if "extra_args" not in model_settings_kwargs:
        model_settings_kwargs["extra_args"] = {}
    model_settings_kwargs["extra_args"]["seed"] = options.seed

# Create ModelSettings object (or None if no settings)
model_settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None
```

**Line-by-line changes**:
- Line 133: Replace `model_settings = {` with `model_settings_kwargs = {}`
- Line 134: Remove `"model": definition.model,` (model goes to Agent, not ModelSettings)
- Line 150: Change `model_settings["max_output_tokens"]` to `model_settings_kwargs["max_tokens"]`
- Lines 152-153: Replace seed dict assignment with extra_args pattern
- Add new line 154: `model_settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None`

---

#### Change 3: Fix Agent Construction (Lines 188-195)

**Replace with:**

```python
# Create the OpenAI Agent
agent = Agent(
    name="Assistant",
    model=definition.model,  # Model is a direct Agent parameter
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,  # ModelSettings object (or None)
    output_guardrails=guardrails if guardrails else None  # Correct parameter name
)
```

**Line-by-line changes**:
- Add new line 191: `model=definition.model,`
- Line 194: Change `guardrails=` to `output_guardrails=`

---

#### Change 4: Fix Async Execution (Lines 232-239)

**Replace with:**

```python
# Run the agent asynchronously
try:
    # Use native async Runner.run() method
    result = await Runner.run(prepared.agent, user_input)
```

**Line-by-line changes**:
- Remove lines 234-238 (executor code)
- Replace with single line: `result = await Runner.run(prepared.agent, user_input)`

---

## Testing Strategy

### 1. Unit Tests with Real SDK

**Problem**: Current tests use mocks, which allowed bugs to persist.

**Solution**: Add integration tests that require the actual `openai-agents` SDK.

**Test File**: `tests/integration/agents/test_openai_agents_real_sdk.py`

**Test Structure**:

```python
"""Integration tests for OpenAI Agents adapter with real SDK.

These tests require:
- pip install openai-agents
- OPENAI_API_KEY environment variable

Mark as integration tests:
- pytest -m integration
"""

import pytest
import os
from agents import Agent, Runner, ModelSettings, GuardrailFunctionOutput

# Skip if SDK not available or no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)

@pytest.mark.integration
async def test_agent_creation_with_real_sdk():
    """Test that Agent can be created with correct parameters."""
    from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
    from steer_llm_sdk.agents.models.agent_definition import AgentDefinition
    from steer_llm_sdk.integrations.agents.base import AgentRunOptions

    adapter = OpenAIAgentAdapter()

    definition = AgentDefinition(
        system="You are a helpful assistant.",
        user_template="Answer: {query}",
        model="gpt-4",
        parameters={
            "temperature": 0.7,
            "max_tokens": 100
        }
    )

    options = AgentRunOptions(
        runtime="openai_agents",
        deterministic=True,
        seed=42
    )

    # This should not raise TypeError
    prepared = await adapter.prepare(definition, options)

    # Verify agent has correct attributes
    assert prepared.agent.model == "gpt-4"
    assert prepared.agent.name == "Assistant"
    assert isinstance(prepared.agent.model_settings, ModelSettings) or prepared.agent.model_settings is None


@pytest.mark.integration
async def test_modelSettings_object_creation():
    """Test that ModelSettings object is created correctly."""
    # Verify ModelSettings can be created with our parameters
    settings = ModelSettings(
        temperature=0.7,
        top_p=0.9,
        max_tokens=100
    )

    assert settings.temperature == 0.7
    assert settings.top_p == 0.9
    assert settings.max_tokens == 100


@pytest.mark.integration
async def test_guardrails_parameter_name():
    """Test that output_guardrails parameter works."""
    # This test verifies the parameter name is correct
    async def test_guardrail(ctx, agent, result):
        return GuardrailFunctionOutput(
            output=result,
            should_block=False
        )

    # Should not raise TypeError about unexpected keyword argument
    agent = Agent(
        name="Test",
        model="gpt-4",
        instructions="Test",
        output_guardrails=[test_guardrail]
    )

    assert agent.output_guardrails == [test_guardrail]


@pytest.mark.integration
async def test_runner_async_method():
    """Test that Runner.run() works in async context."""
    agent = Agent(
        name="Test",
        model="gpt-4o-mini",  # Use cheaper model for testing
        instructions="You are a test assistant. Respond with exactly 'test success'."
    )

    # This should work in async context
    result = await Runner.run(agent, "Please respond.")

    assert result is not None
    assert hasattr(result, 'final_output')


@pytest.mark.integration
async def test_end_to_end_execution():
    """Test complete flow from adapter.prepare() to adapter.run()."""
    from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
    from steer_llm_sdk.agents.models.agent_definition import AgentDefinition
    from steer_llm_sdk.integrations.agents.base import AgentRunOptions

    adapter = OpenAIAgentAdapter()

    definition = AgentDefinition(
        system="You are a helpful assistant. Be concise.",
        user_template="Question: {question}",
        model="gpt-4o-mini",
        parameters={"temperature": 0.5, "max_tokens": 50}
    )

    options = AgentRunOptions(runtime="openai_agents")

    prepared = await adapter.prepare(definition, options)
    result = await adapter.run(prepared, {"question": "What is 2+2?"})

    assert result is not None
    assert result.content is not None
    assert result.model == "gpt-4o-mini"
    assert result.runtime == "openai_agents"
```

---

### 2. Type Checking

**Add mypy validation**:

```bash
# In pyproject.toml or mypy.ini
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

# Run type checking
mypy steer_llm_sdk/integrations/agents/openai/adapter.py
```

**Expected**: No type errors about dict vs ModelSettings

---

### 3. Import Verification

**Test that imports work**:

```python
def test_imports():
    """Verify all SDK imports are correct."""
    try:
        from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings
        assert Agent is not None
        assert Runner is not None
        assert GuardrailFunctionOutput is not None
        assert ModelSettings is not None
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")
```

---

### 4. Smoke Tests

**Minimal SDK interaction tests**:

```python
@pytest.mark.integration
def test_sdk_available():
    """Verify SDK can be imported."""
    import agents
    assert hasattr(agents, 'Agent')
    assert hasattr(agents, 'Runner')
    assert hasattr(agents, 'ModelSettings')
    assert hasattr(agents, 'GuardrailFunctionOutput')


@pytest.mark.integration
def test_agent_signature_compatibility():
    """Verify Agent accepts our parameters."""
    from agents import Agent, ModelSettings

    # Should not raise TypeError
    agent = Agent(
        name="Test",
        model="gpt-4",
        instructions="Test",
        tools=[],
        model_settings=ModelSettings(temperature=0.7),
        output_guardrails=[]
    )

    assert agent.model == "gpt-4"
```

---

## Risk Analysis

### Risk 1: ModelSettings API Changes

**Risk**: ModelSettings API may differ between SDK versions

**Mitigation**:
- Pin SDK version in requirements: `openai-agents>=0.1.0,<0.5.0`
- Add version detection:
  ```python
  import agents
  SDK_VERSION = getattr(agents, '__version__', 'unknown')
  if SDK_VERSION < '0.1.0':
      raise ImportError(f"openai-agents {SDK_VERSION} is too old")
  ```
- Document supported versions in docstring

**Rollback**: Revert to dict-based approach if ModelSettings is unavailable

---

### Risk 2: Missing Model Parameter

**Risk**: If `model` parameter is not accepted by Agent, initialization fails

**Mitigation**:
- Verify with integration test before release
- Check SDK documentation for exact Agent signature
- Add try/except during Agent creation:
  ```python
  try:
      agent = Agent(model=definition.model, ...)
  except TypeError as e:
      if "model" in str(e):
          # Fallback: try without model parameter
          agent = Agent(...)
      else:
          raise
  ```

**Likelihood**: LOW - documentation clearly shows `model` as Agent parameter

---

### Risk 3: Guardrails API Differences

**Risk**: output_guardrails might expect different format in some SDK versions

**Mitigation**:
- Integration tests will catch format mismatches
- Keep guardrail creation flexible:
  ```python
  # Handle both list and None
  output_guardrails=guardrails if guardrails else None
  ```
- Document expected guardrail function signature in docstring

**Likelihood**: LOW - API is stable in SDK >=0.1.0

---

### Risk 4: Runner.run() Compatibility

**Risk**: Runner.run() behavior might differ from run_sync()

**Mitigation**:
- Both methods documented to return same RunResult type
- Integration tests verify result structure
- Add result validation:
  ```python
  result = await Runner.run(agent, input)
  assert hasattr(result, 'final_output'), "Unexpected RunResult format"
  ```

**Likelihood**: VERY LOW - async/sync are explicitly equivalent per docs

---

### Risk 5: Breaking Changes for Existing Users

**Risk**: Users with custom code depending on current (broken) behavior

**Impact**: MINIMAL - adapter is currently non-functional, so no working production usage

**Mitigation**:
- Version bump to 0.3.3 signals bug fix
- Add to CHANGELOG.md under "Bug Fixes"
- No API changes to adapter's public interface (prepare/run/run_stream)

---

## Migration Path

### For Library Users

**No migration needed** - The adapter's public API remains unchanged:

```python
# Usage stays the same
adapter = OpenAIAgentAdapter()
prepared = await adapter.prepare(definition, options)
result = await adapter.run(prepared, variables)
```

The fixes are internal implementation details.

---

### For Test Authors

**Update mock-based tests to use real SDK** (optional but recommended):

**Before**:
```python
with patch('...Agent', MockAgent):
    prepared = await adapter.prepare(...)
```

**After**:
```python
# Option 1: Use real SDK in integration tests
@pytest.mark.integration
async def test_with_real_sdk():
    prepared = await adapter.prepare(...)

# Option 2: Keep unit tests but update mocks to match real API
class MockAgent:
    def __init__(self, name, model, instructions, tools=None,
                 model_settings=None, output_guardrails=None):  # Updated signature
        self.name = name
        self.model = model  # Added
        self.model_settings = model_settings  # Now expects ModelSettings object
        self.output_guardrails = output_guardrails  # Renamed from guardrails
```

---

### Version Compatibility

**Supported SDK Versions**: `openai-agents>=0.1.0`

**Dependency Update** (pyproject.toml):
```toml
[project.optional-dependencies]
openai-agents = [
    "openai-agents>=0.1.0,<0.5.0",  # Upper bound for safety
]
```

**Version Detection**:
```python
try:
    import agents
    sdk_version = getattr(agents, '__version__', 'unknown')
    # Log for debugging
    logger.debug(f"Using openai-agents version: {sdk_version}")
except ImportError:
    pass
```

---

## Verification Criteria

### Fix Verification Checklist

Each bug fix must satisfy these criteria:

#### Bug #1: Import Path
- [ ] Code imports `GuardrailFunctionOutput` from `agents` module
- [ ] No import from `agents.guardrails`
- [ ] Import succeeds with real SDK: `python -c "from agents import GuardrailFunctionOutput"`
- [ ] No ImportError in adapter initialization

#### Bug #2: Parameter Name
- [ ] Agent initialization uses `output_guardrails=` parameter
- [ ] No `guardrails=` parameter in Agent() call
- [ ] No TypeError about unexpected keyword argument
- [ ] Guardrails are properly attached to agent object

#### Bug #3: Async Pattern
- [ ] Code uses `await Runner.run(agent, input)` directly
- [ ] No `loop.run_in_executor()` calls
- [ ] No `Runner.run_sync()` in async contexts
- [ ] Execution succeeds in async function
- [ ] No event loop warnings or errors

#### Bug #4: ModelSettings Type
- [ ] Code creates `ModelSettings(...)` object
- [ ] No dict passed to `model_settings=` parameter
- [ ] ModelSettings import present in file
- [ ] Type checking passes with mypy

#### Bug #5: Model Location
- [ ] `model` parameter passed to `Agent()` directly
- [ ] `model` NOT included in ModelSettings
- [ ] Agent object has `.model` attribute with correct value
- [ ] ModelSettings does not contain 'model' key/attribute

---

### Integration Test Success Criteria

All integration tests must pass:

```bash
# Run integration tests
pytest -m integration tests/integration/agents/test_openai_agents_real_sdk.py -v

# Expected output:
# test_agent_creation_with_real_sdk PASSED
# test_modelSettings_object_creation PASSED
# test_guardrails_parameter_name PASSED
# test_runner_async_method PASSED
# test_end_to_end_execution PASSED
```

---

### Manual Testing Checklist

**Prerequisites**:
- [ ] Install: `pip install openai-agents>=0.1.0`
- [ ] Set: `export OPENAI_API_KEY=sk-...`

**Test Script** (`test_manual.py`):
```python
import asyncio
from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition
from steer_llm_sdk.integrations.agents.base import AgentRunOptions

async def main():
    print("1. Creating adapter...")
    adapter = OpenAIAgentAdapter()
    print("✓ Adapter created (imports work)")

    print("\n2. Preparing agent...")
    definition = AgentDefinition(
        system="You are a helpful math tutor.",
        user_template="Question: {q}",
        model="gpt-4o-mini",
        parameters={"temperature": 0.5, "max_tokens": 100}
    )
    options = AgentRunOptions(runtime="openai_agents", seed=42)
    prepared = await adapter.prepare(definition, options)
    print(f"✓ Agent prepared: {prepared.agent.model}")
    print(f"  - Model: {prepared.agent.model}")
    print(f"  - ModelSettings type: {type(prepared.agent.model_settings)}")

    print("\n3. Running agent...")
    result = await adapter.run(prepared, {"q": "What is 5 + 7?"})
    print(f"✓ Agent ran successfully")
    print(f"  - Content: {result.content}")
    print(f"  - Model: {result.model}")
    print(f"  - Usage: {result.usage}")

    print("\n✓ ALL CHECKS PASSED")

if __name__ == "__main__":
    asyncio.run(main())
```

**Expected Output**:
```
1. Creating adapter...
✓ Adapter created (imports work)

2. Preparing agent...
✓ Agent prepared: gpt-4o-mini
  - Model: gpt-4o-mini
  - ModelSettings type: <class 'agents.model_settings.ModelSettings'>

3. Running agent...
✓ Agent ran successfully
  - Content: 5 + 7 = 12
  - Model: gpt-4o-mini
  - Usage: {'prompt_tokens': ..., 'completion_tokens': ..., ...}

✓ ALL CHECKS PASSED
```

**Failure Scenarios to Check**:
- [ ] No ImportError on adapter creation
- [ ] No TypeError during prepare()
- [ ] No TypeError during Agent() instantiation
- [ ] No event loop errors during run()
- [ ] Result has expected structure

---

### Code Review Checklist

Before merging:

- [ ] All 5 bugs addressed in code
- [ ] Imports updated and consolidated
- [ ] ModelSettings imported and used correctly
- [ ] Agent() receives `model` and `output_guardrails` parameters
- [ ] Runner.run() used instead of run_in_executor + run_sync
- [ ] No dict passed to model_settings (must be ModelSettings object or None)
- [ ] Integration tests added and passing
- [ ] Type hints correct (ModelSettings | None)
- [ ] Docstrings updated to reflect new usage
- [ ] CHANGELOG.md updated with bug fixes
- [ ] Version bumped to 0.3.3

---

## Implementation Checklist

### Phase 1: Code Fixes

- [ ] Update imports (lines 28-38)
  - [ ] Import GuardrailFunctionOutput from agents
  - [ ] Import ModelSettings
  - [ ] Update fallback assignments

- [ ] Fix ModelSettings construction (lines 132-154)
  - [ ] Create model_settings_kwargs dict
  - [ ] Remove 'model' from kwargs
  - [ ] Change max_output_tokens to max_tokens
  - [ ] Move seed to extra_args
  - [ ] Instantiate ModelSettings object

- [ ] Fix Agent instantiation (lines 188-195)
  - [ ] Add model parameter
  - [ ] Change guardrails to output_guardrails
  - [ ] Pass ModelSettings object (not dict)

- [ ] Fix Runner usage (lines 232-239)
  - [ ] Remove run_in_executor code
  - [ ] Use await Runner.run() directly

### Phase 2: Testing

- [ ] Create integration test file
  - [ ] test_agent_creation_with_real_sdk
  - [ ] test_modelSettings_object_creation
  - [ ] test_guardrails_parameter_name
  - [ ] test_runner_async_method
  - [ ] test_end_to_end_execution

- [ ] Update existing unit tests
  - [ ] Update mocks to match real API
  - [ ] Add ModelSettings to mocks
  - [ ] Update MockAgent signature

- [ ] Run manual verification script
- [ ] Verify with mypy type checking

### Phase 3: Documentation

- [ ] Update adapter docstring with correct SDK version
- [ ] Update CHANGELOG.md
- [ ] Update pyproject.toml dependencies
- [ ] Add migration notes if needed

### Phase 4: Release

- [ ] Bump version to 0.3.3
- [ ] Tag release
- [ ] Update documentation

---

## Success Metrics

### Before Fix
- ❌ Adapter cannot instantiate with real SDK (ImportError)
- ❌ Agent creation fails with TypeError (wrong parameters)
- ❌ Async execution fails (event loop conflicts)
- ❌ Type checking fails (dict vs ModelSettings)

### After Fix
- ✅ Adapter instantiates successfully
- ✅ Agent creation succeeds with proper types
- ✅ Async execution works in production
- ✅ Type checking passes
- ✅ Integration tests pass
- ✅ Manual verification succeeds
- ✅ No breaking changes to public API

---

## Appendix A: Complete Diff

### File: `adapter.py`

```diff
--- a/steer_llm_sdk/integrations/agents/openai/adapter.py
+++ b/steer_llm_sdk/integrations/agents/openai/adapter.py
@@ -28,13 +28,14 @@
 # Lazy import for optional dependency
 try:
-    from agents import Agent, Runner, function_tool
-    from agents.guardrails import GuardrailFunctionOutput
+    from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings
     AGENTS_SDK_AVAILABLE = True
 except ImportError:
     AGENTS_SDK_AVAILABLE = False
     Agent = None
     Runner = None
     function_tool = None
     GuardrailFunctionOutput = None
+    ModelSettings = None

@@ -130,24 +131,29 @@
             )

-        # Extract model settings for Agent
-        model_settings = {
-            "model": definition.model,
-        }
+        # Build ModelSettings object for Agent
+        # Note: 'model' is NOT part of ModelSettings - it's passed separately to Agent()
+        model_settings_kwargs = {}

         # Map normalized parameters to Agent settings
         if "temperature" in normalized_params:
-            model_settings["temperature"] = normalized_params["temperature"]
+            model_settings_kwargs["temperature"] = normalized_params["temperature"]
         if "top_p" in normalized_params:
-            model_settings["top_p"] = normalized_params["top_p"]
+            model_settings_kwargs["top_p"] = normalized_params["top_p"]

-        # Handle max tokens - normalization already maps to the correct field name
-        # The OpenAI Agents SDK specifically expects "max_output_tokens" regardless
-        # of what field name the normalization layer provides. This is different from
-        # the Chat Completions API which uses model-specific field names.
+        # Handle max tokens - SDK ModelSettings uses 'max_tokens' field
         for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
             if field in normalized_params:
-                # OpenAI Agents SDK expects max_output_tokens
-                model_settings["max_output_tokens"] = normalized_params[field]
+                model_settings_kwargs["max_tokens"] = normalized_params[field]
                 break
+
+        # Handle seed via extra_args (seed is not a standard ModelSettings field)
         if options.seed and capabilities.supports_seed:
-            model_settings["seed"] = options.seed
+            if "extra_args" not in model_settings_kwargs:
+                model_settings_kwargs["extra_args"] = {}
+            model_settings_kwargs["extra_args"]["seed"] = options.seed
+
+        # Create ModelSettings object (or None if no settings)
+        model_settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None

@@ -188,9 +194,10 @@
         # Create the OpenAI Agent
         agent = Agent(
             name="Assistant",
+            model=definition.model,
             instructions=definition.system,
             tools=sdk_tools,
             model_settings=model_settings,
-            guardrails=guardrails if guardrails else None
+            output_guardrails=guardrails if guardrails else None
         )

@@ -232,11 +239,8 @@

-        # Run the agent synchronously
+        # Run the agent asynchronously
         try:
-            # Convert to sync execution in thread pool
-            loop = asyncio.get_event_loop()
-            result = await loop.run_in_executor(
-                None,
-                partial(Runner.run_sync, prepared.agent, user_input)
-            )
+            # Use native async Runner.run() method
+            result = await Runner.run(prepared.agent, user_input)

```

---

## Appendix B: SDK API Reference

### Agent Class

```python
from agents import Agent, ModelSettings

agent = Agent(
    name: str,                              # Required: Agent identifier
    model: str,                             # Required: Model ID (e.g., "gpt-4")
    instructions: str | Callable,           # System prompt or dynamic function
    tools: list[Callable] | None = None,    # Function tools
    model_settings: ModelSettings | None = None,
    output_guardrails: list[OutputGuardrail] | None = None,
    # ... other parameters
)
```

### ModelSettings Class

```python
from agents import ModelSettings

settings = ModelSettings(
    temperature: float | None = None,
    top_p: float | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
    max_tokens: int | None = None,          # NOT max_output_tokens
    tool_choice: ToolChoice | None = None,
    parallel_tool_calls: bool | None = None,
    extra_args: dict[str, Any] | None = None,  # For custom params like seed
    # ... many other optional fields
)
```

### Runner Class

```python
from agents import Runner

# Async (use in async contexts)
result = await Runner.run(
    agent: Agent,
    input: str | TResponseInputItem | list[TResponseInputItem],
    context: RunContext | None = None,
) -> RunResult

# Sync (DO NOT use in async contexts or notebooks)
result = Runner.run_sync(
    agent: Agent,
    input: str,
    context: RunContext | None = None,
) -> RunResult
```

### GuardrailFunctionOutput

```python
from agents import GuardrailFunctionOutput

async def my_guardrail(ctx, agent, result):
    return GuardrailFunctionOutput(
        output=result,           # The output content
        should_block: bool,      # Whether to block this output
        error_message: str | None = None,
    )
```

---

## Appendix C: Related Documentation

- **OpenAI Agents SDK**: https://openai.github.io/openai-agents-python/
- **ModelSettings Reference**: https://openai.github.io/openai-agents-python/ref/model_settings/
- **Agent Reference**: https://openai.github.io/openai-agents-python/agents/
- **Running Agents**: https://openai.github.io/openai-agents-python/running_agents/
- **Guardrails**: https://openai.github.io/openai-agents-python/guardrails/

---

## Sign-off

**Design Author**: Claude Code (Designing Agent)
**Review Status**: Awaiting Review
**Target Implementation**: Phase 1 (Critical Bug Fix)

**Next Steps**:
1. Review by team/maintainer
2. Approval to proceed with implementation
3. Implementation by Development Agent
4. Testing by QA/Testing Agent
5. Documentation updates
6. Release as v0.3.3
