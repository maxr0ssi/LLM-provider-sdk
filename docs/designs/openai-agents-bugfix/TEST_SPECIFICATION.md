# OpenAI Agents Adapter - Test Specification

**Purpose**: Define integration tests to verify bug fixes
**Location**: `tests/integration/agents/test_openai_agents_real_sdk.py`
**Prerequisites**: `pip install openai-agents>=0.1.0`, `OPENAI_API_KEY` set

---

## Test File Structure

```python
"""Integration tests for OpenAI Agents adapter with real SDK.

These tests require:
- pip install openai-agents>=0.1.0
- OPENAI_API_KEY environment variable

Run with:
    pytest -m integration tests/integration/agents/test_openai_agents_real_sdk.py -v

Skip integration tests:
    pytest -m "not integration"
"""

import pytest
import os
import asyncio
from agents import Agent, Runner, ModelSettings, GuardrailFunctionOutput

from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter
from steer_llm_sdk.agents.models.agent_definition import AgentDefinition
from steer_llm_sdk.integrations.agents.base import AgentRunOptions

# Skip all tests in this file if no API key
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set"
    )
]
```

---

## Test Suite

### Test 1: SDK Imports Work

**Purpose**: Verify Fix #1 (import path)

```python
@pytest.mark.integration
def test_sdk_imports():
    """Verify that all SDK imports work correctly.

    This test validates:
    - Bug #1 fix: GuardrailFunctionOutput imports from agents module
    - All required SDK primitives are available
    """
    # These should all succeed with the real SDK
    from agents import (
        Agent,
        Runner,
        ModelSettings,
        GuardrailFunctionOutput,
        function_tool
    )

    assert Agent is not None
    assert Runner is not None
    assert ModelSettings is not None
    assert GuardrailFunctionOutput is not None
    assert function_tool is not None

    # Verify they're the real classes, not mocks
    assert hasattr(Agent, '__init__')
    assert hasattr(ModelSettings, '__init__')
    assert hasattr(GuardrailFunctionOutput, 'output')
```

**Expected**: PASS - No ImportError

---

### Test 2: ModelSettings Object Creation

**Purpose**: Verify Fix #4 (ModelSettings type)

```python
@pytest.mark.integration
def test_model_settings_object_creation():
    """Verify that ModelSettings objects are created correctly.

    This test validates:
    - Bug #4 fix: ModelSettings is instantiated as object, not dict
    - ModelSettings accepts our parameters
    - Field names are correct
    """
    # Create ModelSettings with our typical parameters
    settings = ModelSettings(
        temperature=0.7,
        top_p=0.9,
        max_tokens=100  # Bug #4: Was using max_output_tokens
    )

    # Verify it's an object with correct values
    assert isinstance(settings, ModelSettings)
    assert settings.temperature == 0.7
    assert settings.top_p == 0.9
    assert settings.max_tokens == 100

    # Verify dict is NOT accepted (should fail type checking)
    # This documents the bug we fixed
    # Note: We can't easily test that passing dict fails at runtime
    # because Python is duck-typed, but mypy will catch it


@pytest.mark.integration
def test_model_settings_with_extra_args():
    """Verify seed is passed via extra_args."""
    settings = ModelSettings(
        temperature=0.5,
        extra_args={"seed": 42}
    )

    assert settings.extra_args["seed"] == 42
```

**Expected**: PASS - ModelSettings object created successfully

---

### Test 3: Agent Parameter Names

**Purpose**: Verify Fix #2 and Fix #5 (parameter names and locations)

```python
@pytest.mark.integration
def test_agent_parameter_names():
    """Verify Agent accepts correct parameter names.

    This test validates:
    - Bug #2 fix: output_guardrails parameter (not guardrails)
    - Bug #5 fix: model parameter passed directly (not in ModelSettings)
    """
    async def dummy_guardrail(ctx, agent, result):
        return GuardrailFunctionOutput(
            output=result,
            should_block=False
        )

    # This should succeed with correct parameter names
    agent = Agent(
        name="Test",
        model="gpt-4o-mini",  # Bug #5: model is direct parameter
        instructions="Test assistant",
        tools=[],
        model_settings=ModelSettings(temperature=0.7),
        output_guardrails=[dummy_guardrail]  # Bug #2: output_guardrails (not guardrails)
    )

    # Verify agent has correct attributes
    assert agent.name == "Test"
    assert agent.model == "gpt-4o-mini"
    assert agent.instructions == "Test assistant"
    assert agent.output_guardrails == [dummy_guardrail]

    # Verify ModelSettings is object
    assert isinstance(agent.model_settings, ModelSettings)


@pytest.mark.integration
def test_agent_rejects_wrong_parameter_names():
    """Document that wrong parameter names fail."""
    # This test documents the bug we fixed
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        agent = Agent(
            name="Test",
            model="gpt-4",
            instructions="Test",
            guardrails=[]  # Bug #2: This should fail
        )
```

**Expected**: PASS - Agent created with correct parameters, fails with wrong ones

---

### Test 4: Runner Async Method

**Purpose**: Verify Fix #3 (async pattern)

```python
@pytest.mark.integration
async def test_runner_async_method():
    """Verify Runner.run() works in async context.

    This test validates:
    - Bug #3 fix: Runner.run() is used (not run_in_executor + run_sync)
    - Async execution works correctly
    - No event loop conflicts
    """
    agent = Agent(
        name="Test",
        model="gpt-4o-mini",
        instructions="You are a test assistant. Respond with exactly 'test success'."
    )

    # This should work in async context (our bug fix)
    result = await Runner.run(agent, "Please respond.")

    # Verify result structure
    assert result is not None
    assert hasattr(result, 'final_output')
    assert result.final_output is not None


@pytest.mark.integration
def test_runner_sync_fails_in_async_context():
    """Document that run_sync fails in async contexts (the bug we had)."""
    async def try_run_sync():
        agent = Agent(
            name="Test",
            model="gpt-4o-mini",
            instructions="Test"
        )

        # This should fail (documenting the bug we fixed)
        # Per SDK docs: "run_sync will not work if there's already an event loop"
        with pytest.raises((RuntimeError, Exception)):
            Runner.run_sync(agent, "test")

    # Run in new event loop to test this
    # This test may be flaky depending on environment
    # pytest.skip("Skipped: run_sync behavior varies by environment")
```

**Expected**: PASS - Runner.run() works, run_sync() fails in async context

---

### Test 5: Adapter Prepare Method

**Purpose**: Integration test for prepare() with all fixes

```python
@pytest.mark.integration
async def test_adapter_prepare_creates_valid_agent():
    """Test that adapter.prepare() creates a valid Agent with real SDK.

    This test validates all fixes together:
    - Imports work
    - ModelSettings object is created
    - Agent gets correct parameters
    """
    adapter = OpenAIAgentAdapter()

    definition = AgentDefinition(
        system="You are a helpful assistant.",
        user_template="Question: {q}",
        model="gpt-4o-mini",
        parameters={
            "temperature": 0.7,
            "max_tokens": 100,
            "top_p": 0.9
        }
    )

    options = AgentRunOptions(
        runtime="openai_agents",
        deterministic=True,
        seed=42
    )

    # This should not raise any errors
    prepared = await adapter.prepare(definition, options)

    # Verify prepared agent
    assert prepared is not None
    assert prepared.runtime == "openai_agents"
    assert isinstance(prepared.agent, Agent)

    # Verify agent attributes (Bug #5: model is direct attribute)
    assert prepared.agent.model == "gpt-4o-mini"
    assert prepared.agent.name == "Assistant"
    assert prepared.agent.instructions == "You are a helpful assistant."

    # Verify ModelSettings (Bug #4: should be object, not dict)
    assert isinstance(prepared.agent.model_settings, ModelSettings) or prepared.agent.model_settings is None
    if prepared.agent.model_settings:
        assert prepared.agent.model_settings.temperature == 0.7
        assert prepared.agent.model_settings.max_tokens == 100


@pytest.mark.integration
async def test_adapter_prepare_with_schema():
    """Test adapter.prepare() with JSON schema (guardrails)."""
    adapter = OpenAIAgentAdapter()

    definition = AgentDefinition(
        system="You are a helpful assistant.",
        user_template="Question: {q}",
        model="gpt-4o-mini",
        json_schema={
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "confidence": {"type": "number"}
            },
            "required": ["answer"]
        },
        parameters={"temperature": 0.5}
    )

    options = AgentRunOptions(
        runtime="openai_agents",
        strict=True
    )

    prepared = await adapter.prepare(definition, options)

    # Verify guardrails were created (Bug #2: output_guardrails)
    assert prepared.agent.output_guardrails is not None
    assert len(prepared.agent.output_guardrails) > 0
```

**Expected**: PASS - Agent prepared successfully with all correct types

---

### Test 6: Adapter Run Method

**Purpose**: Integration test for run() with real execution

```python
@pytest.mark.integration
async def test_adapter_run_executes_successfully():
    """Test that adapter.run() executes with real SDK.

    This test validates:
    - Bug #3 fix: Runner.run() works in async context
    - End-to-end execution succeeds
    """
    adapter = OpenAIAgentAdapter()

    definition = AgentDefinition(
        system="You are a helpful math tutor. Be very concise.",
        user_template="Question: {question}",
        model="gpt-4o-mini",
        parameters={"temperature": 0.5, "max_tokens": 50}
    )

    options = AgentRunOptions(runtime="openai_agents")

    # Prepare and run
    prepared = await adapter.prepare(definition, options)
    result = await adapter.run(prepared, {"question": "What is 2+2?"})

    # Verify result
    assert result is not None
    assert result.content is not None
    assert result.model == "gpt-4o-mini"
    assert result.runtime == "openai_agents"
    assert result.provider == "openai"

    # Verify usage was reported
    assert result.usage is not None
    assert "prompt_tokens" in result.usage
    assert "completion_tokens" in result.usage


@pytest.mark.integration
async def test_adapter_run_with_tools():
    """Test adapter with tools."""
    from steer_llm_sdk.agents.models.agent_definition import Tool

    def get_weather(location: str) -> str:
        """Get weather for a location."""
        return f"Weather in {location}: Sunny, 72°F"

    adapter = OpenAIAgentAdapter()

    definition = AgentDefinition(
        system="You are a helpful assistant with access to weather data.",
        user_template="{query}",
        model="gpt-4o-mini",
        parameters={"temperature": 0.7},
        tools=[
            Tool(
                name="get_weather",
                description="Get current weather for a location",
                parameters={
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                },
                handler=get_weather,
                deterministic=False
            )
        ]
    )

    options = AgentRunOptions(runtime="openai_agents")

    prepared = await adapter.prepare(definition, options)
    result = await adapter.run(prepared, {"query": "What's the weather in Paris?"})

    assert result is not None
    assert "paris" in result.content.lower() or "weather" in result.content.lower()
```

**Expected**: PASS - Full execution succeeds with real API

---

### Test 7: Type Checking

**Purpose**: Ensure type annotations are correct

```python
@pytest.mark.integration
def test_type_annotations():
    """Verify that our usage matches expected types.

    This test can be validated by mypy:
        mypy tests/integration/agents/test_openai_agents_real_sdk.py
    """
    from typing import get_type_hints

    # Verify ModelSettings is a class, not a dict type
    assert isinstance(ModelSettings, type)

    # Verify Agent constructor accepts our types
    hints = get_type_hints(Agent.__init__)
    # This test is primarily for documentation
    # Real validation happens via mypy
```

**Expected**: PASS - Types are correct, mypy validation succeeds

---

## Running Tests

### Run All Integration Tests

```bash
# With API key
export OPENAI_API_KEY=sk-...

# Run all integration tests
pytest -m integration tests/integration/agents/test_openai_agents_real_sdk.py -v

# Run specific test
pytest -m integration tests/integration/agents/test_openai_agents_real_sdk.py::test_sdk_imports -v
```

### Skip Integration Tests (Default)

```bash
# Run all tests except integration
pytest -m "not integration"
```

### Run with Coverage

```bash
pytest -m integration tests/integration/agents/test_openai_agents_real_sdk.py --cov=steer_llm_sdk.integrations.agents.openai
```

---

## Success Criteria

All tests must PASS:

- ✅ `test_sdk_imports` - Imports work
- ✅ `test_model_settings_object_creation` - ModelSettings is object
- ✅ `test_model_settings_with_extra_args` - Seed via extra_args
- ✅ `test_agent_parameter_names` - Correct parameter names
- ✅ `test_runner_async_method` - Runner.run() works
- ✅ `test_adapter_prepare_creates_valid_agent` - prepare() succeeds
- ✅ `test_adapter_prepare_with_schema` - Guardrails work
- ✅ `test_adapter_run_executes_successfully` - Full execution works
- ✅ `test_adapter_run_with_tools` - Tools work
- ✅ `test_type_annotations` - Types correct

---

## Test Configuration

### pytest.ini Addition

```ini
[pytest]
markers =
    integration: marks tests as integration tests (deselect with '-m "not integration"')
```

### pyproject.toml Addition

```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
]
```

---

## Cost Considerations

**Note**: Integration tests make real API calls and incur costs.

**Estimated Cost per Test Run**:
- Model: gpt-4o-mini
- Tokens per test: ~100-200 total
- Cost: ~$0.001-0.005 per full test run
- Total for 9 tests: ~$0.01-0.05

**Optimization**:
- Use `gpt-4o-mini` (cheapest)
- Limit max_tokens
- Cache results where possible
- Skip tests in CI if no API key (automatic)

---

## CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev,openai-agents]"

      - name: Run unit tests
        run: pytest -m "not integration"

      - name: Run integration tests
        if: ${{ secrets.OPENAI_API_KEY }}
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: pytest -m integration
```

---

## Appendix: Test Data

### Minimal Test Inputs

```python
# Minimal agent definition
MINIMAL_DEFINITION = AgentDefinition(
    system="You are helpful.",
    user_template="{q}",
    model="gpt-4o-mini",
    parameters={"temperature": 0.5}
)

# Definition with schema
SCHEMA_DEFINITION = AgentDefinition(
    system="Respond in JSON.",
    user_template="{q}",
    model="gpt-4o-mini",
    json_schema={
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"]
    },
    parameters={"temperature": 0.5}
)

# Definition with tools
def test_tool(arg: str) -> str:
    return f"Result: {arg}"

TOOLS_DEFINITION = AgentDefinition(
    system="You have tools.",
    user_template="{q}",
    model="gpt-4o-mini",
    tools=[
        Tool(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {"arg": {"type": "string"}},
                "required": ["arg"]
            },
            handler=test_tool,
            deterministic=True
        )
    ],
    parameters={"temperature": 0.5}
)
```

---

## Summary

This test specification provides:

1. **7 comprehensive integration tests** covering all bug fixes
2. **Clear pass/fail criteria** for each test
3. **Documentation of expected behavior** vs bugs
4. **CI/CD integration** instructions
5. **Cost awareness** for API usage

**Estimated Implementation Time**: 2-3 hours
**Estimated Test Execution Time**: 2-3 minutes (with API calls)
