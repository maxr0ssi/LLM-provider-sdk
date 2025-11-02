# OpenAI Agents Adapter Bug Fixes - Executive Summary

**Document**: Design Phase Complete
**Location**: `/Users/maxrossi/Documents/Prometheus/LLM-provider-sdk/docs/designs/openai-agents-bugfix/DESIGN.md`
**Status**: Ready for Implementation
**Priority**: HIGH (Adapter is non-functional)

---

## Overview

The OpenAI Agents adapter has 5 critical bugs that prevent it from working with the actual `openai-agents` SDK. These bugs were undetected because tests use mocks instead of the real SDK.

---

## The 5 Bugs

### 1. **Wrong Import Path** (Line 31)
- **Current**: `from agents.guardrails import GuardrailFunctionOutput`
- **Correct**: `from agents import GuardrailFunctionOutput`
- **Impact**: ImportError - module doesn't exist

### 2. **Wrong Parameter Name** (Line 194)
- **Current**: `guardrails=guardrails`
- **Correct**: `output_guardrails=guardrails`
- **Impact**: TypeError - unexpected keyword argument

### 3. **Wrong Async Pattern** (Lines 234-237)
- **Current**: Uses `loop.run_in_executor(None, partial(Runner.run_sync, ...))`
- **Correct**: `await Runner.run(agent, input)`
- **Impact**: Event loop conflicts, unnecessary overhead

### 4. **Type Mismatch** (Lines 133-150)
- **Current**: Creates dict for model_settings
- **Correct**: Create `ModelSettings(...)` object
- **Impact**: Type errors, unexpected behavior

### 5. **Model Location Error** (Line 134)
- **Current**: Includes `model` in ModelSettings dict
- **Correct**: Pass `model` directly to `Agent()`, not in ModelSettings
- **Impact**: Missing required parameter, wrong data structure

---

## Fix Summary

### Code Changes Required

**File**: `steer_llm_sdk/integrations/agents/openai/adapter.py`

1. **Imports** (Lines 28-38):
   ```python
   # Add to imports
   from agents import Agent, Runner, function_tool, GuardrailFunctionOutput, ModelSettings
   ```

2. **ModelSettings Construction** (Lines 132-154):
   ```python
   # Create object, not dict
   model_settings_kwargs = {}
   # ... populate kwargs ...
   model_settings = ModelSettings(**model_settings_kwargs) if model_settings_kwargs else None
   ```

3. **Agent Instantiation** (Lines 188-195):
   ```python
   agent = Agent(
       name="Assistant",
       model=definition.model,  # ADD THIS
       instructions=definition.system,
       tools=sdk_tools,
       model_settings=model_settings,  # Now ModelSettings object
       output_guardrails=guardrails if guardrails else None  # FIX NAME
   )
   ```

4. **Async Execution** (Lines 232-239):
   ```python
   # Replace executor code with:
   result = await Runner.run(prepared.agent, user_input)
   ```

---

## Testing Strategy

### New Integration Tests Required

Create `tests/integration/agents/test_openai_agents_real_sdk.py`:

- Test agent creation with real SDK
- Test ModelSettings object creation
- Test output_guardrails parameter
- Test Runner.run() async method
- Test end-to-end execution

**Mark tests**: `@pytest.mark.integration`

### Manual Verification

```bash
# Install SDK
pip install openai-agents>=0.1.0

# Set API key
export OPENAI_API_KEY=sk-...

# Run integration tests
pytest -m integration tests/integration/agents/test_openai_agents_real_sdk.py
```

---

## Risk Assessment

**Overall Risk**: LOW

- Changes are localized to one file
- No public API changes
- Well-defined SDK contract
- Integration tests will verify correctness

**Risks Identified**:
1. SDK version differences → Mitigated by version pinning
2. Model parameter compatibility → Verified in docs
3. Breaking existing users → Non-issue (adapter currently broken)

---

## Implementation Checklist

- [ ] Update imports
- [ ] Fix ModelSettings construction
- [ ] Fix Agent instantiation
- [ ] Fix Runner usage
- [ ] Create integration tests
- [ ] Update unit test mocks
- [ ] Run manual verification
- [ ] Update CHANGELOG.md
- [ ] Bump version to 0.3.3
- [ ] Document in release notes

---

## Success Criteria

### Before Fix
- ❌ ImportError when loading adapter
- ❌ TypeError when creating Agent
- ❌ Event loop conflicts during execution
- ❌ Type checking failures

### After Fix
- ✅ All imports succeed
- ✅ Agent instantiation works
- ✅ Async execution succeeds
- ✅ Type checking passes
- ✅ Integration tests pass
- ✅ Manual verification succeeds

---

## Next Steps

1. **Review**: Team reviews design document
2. **Approval**: Sign-off to proceed
3. **Implementation**: Apply fixes to adapter.py
4. **Testing**: Create and run integration tests
5. **Verification**: Manual testing with real SDK
6. **Release**: Version 0.3.3 with bug fixes

---

## Documentation Links

- **Full Design Document**: `docs/designs/openai-agents-bugfix/DESIGN.md`
- **Current Adapter**: `steer_llm_sdk/integrations/agents/openai/adapter.py`
- **Current Tests**: `tests/unit/integrations/agents/test_openai_agents_adapter.py`
- **OpenAI SDK Docs**: https://openai.github.io/openai-agents-python/

---

**Estimated Effort**: 2-4 hours
**Complexity**: Medium
**Impact**: High (Makes adapter functional)
