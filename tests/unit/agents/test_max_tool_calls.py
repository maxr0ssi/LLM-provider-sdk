"""Tests for max_tool_calls field on AgentOptions and its propagation."""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from steer_llm_sdk.agents.models.agent_options import AgentOptions
from steer_llm_sdk.integrations.agents.base import AgentRunOptions


# ---------------------------------------------------------------------------
# AgentOptions field tests
# ---------------------------------------------------------------------------


class TestAgentOptionsMaxToolCalls:
    def test_default_is_none(self):
        opts = AgentOptions()
        assert opts.max_tool_calls is None

    def test_explicit_value(self):
        opts = AgentOptions(max_tool_calls=5)
        assert opts.max_tool_calls == 5

    def test_serialises_to_dict(self):
        opts = AgentOptions(max_tool_calls=3)
        d = opts.model_dump()
        assert d["max_tool_calls"] == 3

    def test_none_serialises(self):
        opts = AgentOptions()
        d = opts.model_dump()
        assert d["max_tool_calls"] is None


# ---------------------------------------------------------------------------
# AgentRunOptions field tests
# ---------------------------------------------------------------------------


class TestAgentRunOptionsMaxToolCalls:
    def test_default_is_none(self):
        opts = AgentRunOptions()
        assert opts.max_tool_calls is None

    def test_explicit_value(self):
        opts = AgentRunOptions(max_tool_calls=7)
        assert opts.max_tool_calls == 7


# ---------------------------------------------------------------------------
# Precedence resolution (unit-level, no I/O)
# ---------------------------------------------------------------------------


def _resolve_max_tool_calls(opts: AgentOptions) -> int | None:
    """Mirror the resolution logic from AgentRunner._run_with_runtime."""
    budget = opts.budget or {}
    max_tool_calls = opts.max_tool_calls
    if max_tool_calls is None and budget:
        max_tool_calls = budget.get("turns")
    return max_tool_calls


class TestMaxToolCallsPrecedence:
    def test_explicit_wins_over_budget(self):
        opts = AgentOptions(max_tool_calls=5, budget={"turns": 10})
        assert _resolve_max_tool_calls(opts) == 5

    def test_falls_back_to_budget_turns(self):
        opts = AgentOptions(budget={"turns": 3})
        assert _resolve_max_tool_calls(opts) == 3

    def test_both_none_gives_none(self):
        opts = AgentOptions()
        assert _resolve_max_tool_calls(opts) is None

    def test_budget_without_turns_gives_none(self):
        opts = AgentOptions(budget={"tokens": 3000, "ms": 30000})
        assert _resolve_max_tool_calls(opts) is None


# ---------------------------------------------------------------------------
# OpenAI adapter run() — max_turns passthrough
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_openai_sdk():
    """Minimal mock of the OpenAI Agents SDK for adapter tests."""
    with patch("steer_llm_sdk.integrations.agents.openai.adapter.AGENTS_SDK_AVAILABLE", True):
        with patch("steer_llm_sdk.integrations.agents.openai.tools.AGENTS_SDK_AVAILABLE", True):
            mock_agent = Mock()
            mock_agent.name = "Assistant"

            mock_runner = Mock()
            mock_result = Mock()
            mock_result.final_output = "ok"
            mock_result.usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
            mock_result.tool_calls = []
            mock_runner.run = AsyncMock(return_value=mock_result)

            def mock_agent_ctor(name, instructions, model=None, tools=None,
                                model_settings=None, output_guardrails=None, **kw):
                mock_agent.name = name
                mock_agent.instructions = instructions
                mock_agent.model = model
                mock_agent.tools = tools or []
                mock_agent.model_settings = model_settings or {}
                mock_agent.output_guardrails = output_guardrails or []
                mock_agent.guardrails = output_guardrails or []
                return mock_agent

            mock_ft = lambda fn: fn  # noqa: E731

            with patch("steer_llm_sdk.integrations.agents.openai.adapter.Agent", side_effect=mock_agent_ctor):
                with patch("steer_llm_sdk.integrations.agents.openai.adapter.Runner", mock_runner):
                    with patch("steer_llm_sdk.integrations.agents.openai.adapter.function_tool", mock_ft):
                        with patch("steer_llm_sdk.integrations.agents.openai.tools.function_tool", mock_ft):
                            yield {"runner": mock_runner, "agent": mock_agent}


@pytest.fixture
def _adapter_env():
    """Common mocks needed to instantiate the adapter."""
    caps = Mock(
        supports_seed=True, supports_json_schema=True,
        supports_temperature=True, temperature_range=[0, 2],
        uses_max_completion_tokens=False,
        uses_max_output_tokens_in_responses_api=False,
    )

    def norm(params, model, provider, capabilities):
        return {"temperature": 0.7, "max_tokens": 100}

    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        with patch("steer_llm_sdk.integrations.agents.openai.adapter.get_capabilities_for_model", return_value=caps):
            with patch("steer_llm_sdk.integrations.agents.openai.adapter.normalize_params", side_effect=norm):
                with patch("steer_llm_sdk.integrations.agents.openai.adapter.calculate_exact_cost", return_value=0.0):
                    yield


@pytest.fixture
def simple_definition():
    from steer_llm_sdk.agents.models.agent_definition import AgentDefinition
    return AgentDefinition(
        system="sys",
        user_template="{q}",
        model="gpt-4",
        parameters={"temperature": 0.7, "max_tokens": 100},
    )


class TestAdapterRunMaxTurns:
    @pytest.mark.asyncio
    async def test_run_passes_max_turns_when_set(
        self, mock_openai_sdk, _adapter_env, simple_definition
    ):
        from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter

        adapter = OpenAIAgentAdapter()
        options = AgentRunOptions(runtime="openai_agents", max_tool_calls=5)
        prepared = await adapter.prepare(simple_definition, options)

        await adapter.run(prepared, {"q": "hi"})

        mock_openai_sdk["runner"].run.assert_called_once()
        call_kwargs = mock_openai_sdk["runner"].run.call_args
        assert call_kwargs.kwargs.get("max_turns") == 5 or call_kwargs[1].get("max_turns") == 5

    @pytest.mark.asyncio
    async def test_run_omits_max_turns_when_none(
        self, mock_openai_sdk, _adapter_env, simple_definition
    ):
        from steer_llm_sdk.integrations.agents.openai.adapter import OpenAIAgentAdapter

        adapter = OpenAIAgentAdapter()
        options = AgentRunOptions(runtime="openai_agents")
        prepared = await adapter.prepare(simple_definition, options)

        await adapter.run(prepared, {"q": "hi"})

        call_kwargs = mock_openai_sdk["runner"].run.call_args
        # max_turns should NOT be in kwargs
        assert "max_turns" not in (call_kwargs.kwargs or {})
