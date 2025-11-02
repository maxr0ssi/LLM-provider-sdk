# OpenAI Agents Adapter - Visual Changes Guide

**Purpose**: Side-by-side comparison of all changes
**For**: Code reviewers and implementers

---

## Change #1: Fix Imports

### Before (BROKEN)
```python
# Lazy import for optional dependency
try:
    from agents import Agent, Runner, function_tool
    from agents.guardrails import GuardrailFunctionOutput  # ❌ WRONG MODULE
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    Agent = None
    Runner = None
    function_tool = None
    GuardrailFunctionOutput = None
    # Missing ModelSettings = None
```

### After (FIXED)
```python
# Lazy import for optional dependency
try:
    from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings  # ✅ CORRECT
    AGENTS_SDK_AVAILABLE = True
except ImportError:
    AGENTS_SDK_AVAILABLE = False
    Agent = None
    Runner = None
    function_tool = None
    GuardrailFunctionOutput = None
    ModelSettings = None  # ✅ ADDED
```

**Changes**:
- ❌ Remove: `from agents.guardrails import GuardrailFunctionOutput`
- ✅ Add: `GuardrailFunctionOutput, ModelSettings` to main import
- ✅ Add: `ModelSettings = None` fallback

---

## Change #2: Fix ModelSettings Construction

### Before (BROKEN)
```python
# Extract model settings for Agent
model_settings = {                                    # ❌ Creating dict, not object
    "model": definition.model,                        # ❌ model doesn't belong here
}

# Map normalized parameters to Agent settings
if "temperature" in normalized_params:
    model_settings["temperature"] = normalized_params["temperature"]
if "top_p" in normalized_params:
    model_settings["top_p"] = normalized_params["top_p"]

# Handle max tokens - normalization already maps to the correct field name
# The OpenAI Agents SDK specifically expects "max_output_tokens" regardless
# of what field name the normalization layer provides. This is different from
# the Chat Completions API which uses model-specific field names.
for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
    if field in normalized_params:
        # OpenAI Agents SDK expects max_output_tokens
        model_settings["max_output_tokens"] = normalized_params[field]  # ❌ WRONG FIELD
        break

if options.seed and capabilities.supports_seed:
    model_settings["seed"] = options.seed              # ❌ seed not a ModelSettings field
```

### After (FIXED)
```python
# Build ModelSettings object for Agent
# Note: 'model' is NOT part of ModelSettings - it's passed separately to Agent()
model_settings_kwargs = {}                             # ✅ Kwargs dict for building object

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
        model_settings_kwargs["max_tokens"] = normalized_params[field]  # ✅ CORRECT FIELD
        break

# Handle seed via extra_args (seed is not a standard ModelSettings field)
if options.seed and capabilities.supports_seed:
    if "extra_args" not in model_settings_kwargs:
        model_settings_kwargs["extra_args"] = {}
    model_settings_kwargs["extra_args"]["seed"] = options.seed  # ✅ Use extra_args

# Create ModelSettings object (or None if no settings)
model_settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None  # ✅ OBJECT
```

**Changes**:
- ❌ Remove: `model_settings = {` (dict)
- ✅ Add: `model_settings_kwargs = {}` (temp dict)
- ❌ Remove: `"model": definition.model,` from settings
- ❌ Remove: `model_settings["max_output_tokens"]`
- ✅ Add: `model_settings_kwargs["max_tokens"]`
- ❌ Remove: `model_settings["seed"] = options.seed`
- ✅ Add: Seed via `extra_args` pattern
- ✅ Add: `ModelSettings(**model_settings_kwargs)` object creation

---

## Change #3: Fix Agent Instantiation

### Before (BROKEN)
```python
# Create the OpenAI Agent
agent = Agent(
    name="Assistant",
    # Missing: model parameter                         # ❌ model not passed
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,                     # ❌ Passing dict
    guardrails=guardrails if guardrails else None      # ❌ WRONG PARAMETER NAME
)
```

### After (FIXED)
```python
# Create the OpenAI Agent
agent = Agent(
    name="Assistant",
    model=definition.model,                            # ✅ ADDED: model as direct parameter
    instructions=definition.system,
    tools=sdk_tools,
    model_settings=model_settings,                     # ✅ Now ModelSettings object (or None)
    output_guardrails=guardrails if guardrails else None  # ✅ CORRECT PARAMETER NAME
)
```

**Changes**:
- ✅ Add: `model=definition.model,` parameter
- ✅ Change: `guardrails=` → `output_guardrails=`
- ✅ Fix: `model_settings` now receives object, not dict

---

## Change #4: Fix Runner Execution

### Before (BROKEN)
```python
# Run the agent synchronously
try:
    # Convert to sync execution in thread pool
    loop = asyncio.get_event_loop()                    # ❌ Unnecessary
    result = await loop.run_in_executor(               # ❌ Wrong pattern
        None,
        partial(Runner.run_sync, prepared.agent, user_input)  # ❌ run_sync in async!
    )
```

### After (FIXED)
```python
# Run the agent asynchronously
try:
    # Use native async Runner.run() method
    result = await Runner.run(prepared.agent, user_input)  # ✅ Simple, correct, async
```

**Changes**:
- ❌ Remove: `loop = asyncio.get_event_loop()`
- ❌ Remove: `loop.run_in_executor(...)`
- ❌ Remove: `partial(Runner.run_sync, ...)`
- ✅ Add: `await Runner.run(prepared.agent, user_input)`

---

## Summary of All Changes

### Imports Section
```diff
- from agents import Agent, Runner, function_tool
- from agents.guardrails import GuardrailFunctionOutput
+ from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings

  except ImportError:
      AGENTS_SDK_AVAILABLE = False
      Agent = None
      Runner = None
      function_tool = None
      GuardrailFunctionOutput = None
+     ModelSettings = None
```

### ModelSettings Construction Section
```diff
- # Extract model settings for Agent
- model_settings = {
-     "model": definition.model,
- }
+ # Build ModelSettings object for Agent
+ # Note: 'model' is NOT part of ModelSettings - it's passed separately to Agent()
+ model_settings_kwargs = {}

  # Map normalized parameters to Agent settings
  if "temperature" in normalized_params:
-     model_settings["temperature"] = normalized_params["temperature"]
+     model_settings_kwargs["temperature"] = normalized_params["temperature"]
  if "top_p" in normalized_params:
-     model_settings["top_p"] = normalized_params["top_p"]
+     model_settings_kwargs["top_p"] = normalized_params["top_p"]

- # Handle max tokens - normalization already maps to the correct field name
- # The OpenAI Agents SDK specifically expects "max_output_tokens" regardless
- # of what field name the normalization layer provides. This is different from
- # the Chat Completions API which uses model-specific field names.
+ # Handle max tokens - SDK ModelSettings uses 'max_tokens' field
+ # Our normalization layer may return max_tokens, max_completion_tokens, or max_output_tokens
+ # depending on the model, but ModelSettings expects 'max_tokens'
  for field in ["max_tokens", "max_completion_tokens", "max_output_tokens"]:
      if field in normalized_params:
-         # OpenAI Agents SDK expects max_output_tokens
-         model_settings["max_output_tokens"] = normalized_params[field]
+         model_settings_kwargs["max_tokens"] = normalized_params[field]
          break

+ # Handle seed via extra_args (seed is not a standard ModelSettings field)
  if options.seed and capabilities.supports_seed:
-     model_settings["seed"] = options.seed
+     if "extra_args" not in model_settings_kwargs:
+         model_settings_kwargs["extra_args"] = {}
+     model_settings_kwargs["extra_args"]["seed"] = options.seed
+
+ # Create ModelSettings object (or None if no settings)
+ model_settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None
```

### Agent Instantiation Section
```diff
  # Create the OpenAI Agent
  agent = Agent(
      name="Assistant",
+     model=definition.model,
      instructions=definition.system,
      tools=sdk_tools,
      model_settings=model_settings,
-     guardrails=guardrails if guardrails else None
+     output_guardrails=guardrails if guardrails else None
  )
```

### Runner Execution Section
```diff
- # Run the agent synchronously
+ # Run the agent asynchronously
  try:
-     # Convert to sync execution in thread pool
-     loop = asyncio.get_event_loop()
-     result = await loop.run_in_executor(
-         None,
-         partial(Runner.run_sync, prepared.agent, user_input)
-     )
+     # Use native async Runner.run() method
+     result = await Runner.run(prepared.agent, user_input)
```

---

## Line-by-Line Change Summary

| Line(s) | Change Type | Description |
|---------|-------------|-------------|
| 30 | Modify | Update import statement |
| 31 | Remove | Delete wrong import line |
| 38 | Add | Add ModelSettings = None fallback |
| 133 | Modify | Change `model_settings = {` to `model_settings_kwargs = {}` |
| 134 | Remove | Delete `"model": definition.model,` |
| 138-142 | Modify | Update dict keys to use `_kwargs` suffix |
| 150 | Modify | Change `max_output_tokens` to `max_tokens` |
| 152-157 | Replace | Replace seed dict assignment with extra_args pattern |
| 159 | Add | Add ModelSettings object instantiation |
| 191 | Add | Add `model=definition.model,` parameter |
| 194 | Modify | Change `guardrails=` to `output_guardrails=` |
| 234-238 | Replace | Replace executor code with `await Runner.run()` |

**Total Changes**: ~15 locations
**Lines Modified**: ~20 lines
**Lines Added**: ~10 lines
**Lines Removed**: ~8 lines

---

## Testing the Changes

### Before Fix - Expected Failures

```python
# This will fail
from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter

adapter = OpenAIAgentAdapter()  # ❌ ImportError: No module named 'agents.guardrails'
```

### After Fix - Expected Success

```python
# This will succeed
from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition
from steer_llm_sdk.integrations.agents.base import AgentRunOptions

adapter = OpenAIAgentAdapter()  # ✅ Success

definition = AgentDefinition(
    system="Test",
    user_template="{q}",
    model="gpt-4o-mini",
    parameters={"temperature": 0.7}
)

options = AgentRunOptions(runtime="openai_agents")

prepared = await adapter.prepare(definition, options)  # ✅ Success
result = await adapter.run(prepared, {"q": "test"})    # ✅ Success
```

---

## Verification Checklist

After applying changes, verify:

- [ ] ✅ No `from agents.guardrails` import anywhere
- [ ] ✅ `ModelSettings` imported from `agents`
- [ ] ✅ `model_settings_kwargs` dict created
- [ ] ✅ `ModelSettings(**model_settings_kwargs)` called
- [ ] ✅ No `"model"` in model_settings_kwargs
- [ ] ✅ `max_tokens` field used (not `max_output_tokens`)
- [ ] ✅ `seed` in `extra_args` (not direct field)
- [ ] ✅ `model=definition.model` in Agent()
- [ ] ✅ `output_guardrails=` in Agent() (not `guardrails=`)
- [ ] ✅ `await Runner.run()` used
- [ ] ✅ No `run_in_executor` code
- [ ] ✅ No `partial` import from functools (if unused elsewhere)

---

## Common Review Comments

### "Why not use ModelSettings directly in the dict?"
**Answer**: ModelSettings is a dataclass that must be instantiated. You can't pass a dict to a parameter expecting a ModelSettings object. Python's duck typing might not catch this at runtime, but it's wrong and will cause issues.

### "Why move seed to extra_args?"
**Answer**: The ModelSettings API spec doesn't list `seed` as a standard field. The `extra_args` dict is specifically designed for provider-specific parameters like seed.

### "Why is model not in ModelSettings?"
**Answer**: Per the SDK docs, `model` is a direct parameter of `Agent()`, not part of ModelSettings. ModelSettings is for tuning parameters only (temperature, top_p, etc.).

### "Why not use run_sync in a thread pool?"
**Answer**: The SDK docs explicitly state run_sync "will not work if there's already an event loop" (like in an async function). Runner.run() is the native async method and works correctly in async contexts.

### "Is output_guardrails really the right parameter name?"
**Answer**: Yes, confirmed in GitHub issue #1912 and SDK examples. The SDK distinguishes between input_guardrails and output_guardrails.

---

## Related Files

- **Main Design**: `DESIGN.md` - Full specifications
- **Quick Guide**: `QUICK_FIX_GUIDE.md` - Implementation steps
- **Tests**: `TEST_SPECIFICATION.md` - Test requirements
- **Summary**: `SUMMARY.md` - Executive overview
- **Index**: `README.md` - Navigation

---

**Ready to Apply**: All changes are well-defined and documented.
