# OpenAI Agents Adapter - Quick Fix Guide

**For**: Implementation Team
**Time**: 30 minutes (code changes only)

---

## The 5 Fixes (In Order)

### Fix #1: Update Imports (Lines 28-38)

**Find**:
```python
try:
    from agents import Agent, Runner, function_tool
    from agents.guardrails import GuardrailFunctionOutput  # ❌ WRONG
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    Agent = None
    Runner = None
    function_tool = None
    GuardrailFunctionOutput = None
```

**Replace with**:
```python
try:
    from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings  # ✅
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    Agent = None
    Runner = None
    function_tool = None
    GuardrailFunctionOutput = None
    ModelSettings = None  # ✅ ADD THIS
```

---

### Fix #2: ModelSettings Construction (Lines 132-154)

**Find**:
```python
# Extract model settings for Agent
model_settings = {
    "model": definition.model,  # ❌ WRONG - model doesn't go here
}

# Map normalized parameters to Agent settings
if "temperature" in normalized_params:
    model_settings["temperature"] = normalized_params["temperature"]
if "top_p" in normalized_params:
    model_settings["top_p"] = normalized_params["top_p"]

# Handle max tokens
for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
    if field in normalized_params:
        model_settings["max_output_tokens"] = normalized_params[field]  # ❌ WRONG field name
        break

if options.seed and capabilities.supports_seed:
    model_settings["seed"] = options.seed  # ❌ WRONG - seed not in ModelSettings
```

**Replace with**:
```python
# Build ModelSettings object for Agent
# Note: 'model' is NOT part of ModelSettings - it's passed separately to Agent()
model_settings_kwargs = {}  # ✅ Use kwargs dict first

# Map normalized parameters to ModelSettings fields
if "temperature" in normalized_params:
    model_settings_kwargs["temperature"] = normalized_params["temperature"]
if "top_p" in normalized_params:
    model_settings_kwargs["top_p"] = normalized_params["top_p"]

# Handle max tokens - SDK ModelSettings uses 'max_tokens' field
for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
    if field in normalized_params:
        model_settings_kwargs["max_tokens"] = normalized_params[field]  # ✅ Correct field
        break

# Handle seed via extra_args (seed is not a standard ModelSettings field)
if options.seed and capabilities.supports_seed:
    if "extra_args" not in model_settings_kwargs:
        model_settings_kwargs["extra_args"] = {}
    model_settings_kwargs["extra_args"]["seed"] = options.seed  # ✅ Use extra_args

# Create ModelSettings object (or None if no settings)
model_settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None  # ✅
```

---

### Fix #3: Agent Construction (Lines 188-195)

**Find**:
```python
# Create the OpenAI Agent
agent = Agent(
    name="Assistant",
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,  # This is now wrong type (dict)
    guardrails=guardrails if guardrails else None  # ❌ WRONG parameter name
)
```

**Replace with**:
```python
# Create the OpenAI Agent
agent = Agent(
    name="Assistant",
    model=definition.model,  # ✅ ADD THIS - model is a direct parameter
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,  # ✅ Now a ModelSettings object (or None)
    output_guardrails=guardrails if guardrails else None  # ✅ Correct parameter name
)
```

---

### Fix #4: Runner Execution (Lines 232-239)

**Find**:
```python
# Run the agent synchronously
try:
    # Convert to sync execution in thread pool
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        partial(Runner.run_sync, prepared.agent, user_input)  # ❌ WRONG approach
    )
```

**Replace with**:
```python
# Run the agent asynchronously
try:
    # Use native async Runner.run() method
    result = await Runner.run(prepared.agent, user_input)  # ✅ Simple and correct
```

---

### Fix #5: Remove Unused Import (Top of file)

**Find** (if present):
```python
from functools import partial  # ❌ No longer needed
```

**Action**: Can be removed if not used elsewhere

---

## Testing After Fixes

### Quick Smoke Test

```python
# test_quick.py
import asyncio
from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition
from steer_llm_sdk.integrations.agents.base import AgentRunOptions

async def test():
    adapter = OpenAIAgentAdapter()

    definition = AgentDefinition(
        system="You are helpful.",
        user_template="{q}",
        model="gpt-4o-mini",
        parameters={"temperature": 0.7}
    )

    options = AgentRunOptions(runtime="openai_agents")

    prepared = await adapter.prepare(definition, options)
    print(f"✓ Agent model: {prepared.agent.model}")
    print(f"✓ ModelSettings type: {type(prepared.agent.model_settings)}")

asyncio.run(test())
```

**Run**:
```bash
export OPENAI_API_KEY=sk-...
python test_quick.py
```

**Expected**:
```
✓ Agent model: gpt-4o-mini
✓ ModelSettings type: <class 'agents.model_settings.ModelSettings'>
```

---

## Verification Checklist

After applying all fixes:

- [ ] No `from agents.guardrails` import
- [ ] `ModelSettings` in imports
- [ ] `model_settings_kwargs` dict created
- [ ] `ModelSettings(**model_settings_kwargs)` instantiated
- [ ] `model` removed from ModelSettings kwargs
- [ ] `max_tokens` used (not `max_output_tokens`)
- [ ] `seed` in `extra_args` (not direct field)
- [ ] `model=definition.model` in Agent()
- [ ] `output_guardrails=` in Agent() (not `guardrails=`)
- [ ] `await Runner.run()` used (not executor)
- [ ] No `run_in_executor` code
- [ ] Quick test runs without errors

---

## Common Mistakes to Avoid

1. ❌ Don't import from `agents.guardrails`
2. ❌ Don't pass dict to `model_settings=`
3. ❌ Don't put `model` inside ModelSettings
4. ❌ Don't use `guardrails=` parameter name
5. ❌ Don't use `Runner.run_sync()` in async function
6. ❌ Don't use `max_output_tokens` in ModelSettings

---

## Questions?

- See full design: `docs/designs/openai-agents-bugfix/DESIGN.md`
- SDK docs: https://openai.github.io/openai-agents-python/
- ModelSettings API: https://openai.github.io/openai-agents-python/ref/model_settings/
