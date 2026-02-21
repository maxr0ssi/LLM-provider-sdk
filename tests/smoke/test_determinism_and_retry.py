import os
import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY")
async def test_determinism_two_runs_equal():
    from steer_llm_sdk.agents.models import AgentDefinition
    from steer_llm_sdk.agents.runner.agent_runner import AgentRunner

    agent = AgentDefinition(
        system="Return JSON { 'ok': true } strictly.",
        user_template="Say hi.",
        json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False},
        model="gpt-4.1-mini",
        parameters={"max_tokens": 32},
    )
    runner = AgentRunner()
    r1 = await runner.run(agent, {}, {"deterministic": True, "metadata": {"strict": True}})
    r2 = await runner.run(agent, {}, {"deterministic": True, "metadata": {"strict": True}})
    assert r1.content == r2.content


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY")
async def test_instructions_mapping_off():
    from steer_llm_sdk.agents.models import AgentDefinition
    from steer_llm_sdk.agents.runner.agent_runner import AgentRunner

    agent = AgentDefinition(
        system="You are helpful.",
        user_template="Just respond with JSON {{\"ok\": true}}.",
        json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False},
        model="gpt-4.1-mini",
        parameters={"max_tokens": 32},
    )
    runner = AgentRunner()
    res = await runner.run(agent, {}, {"deterministic": True, "metadata": {"strict": True}})
    assert isinstance(res.content, dict)
    assert "ok" in res.content


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY")
async def test_retry_on_transient_provider_error(monkeypatch):
    from steer_llm_sdk.agents.models import AgentDefinition
    from steer_llm_sdk.agents.runner.agent_runner import AgentRunner
    from steer_llm_sdk.providers.base import ProviderError

    agent = AgentDefinition(
        system="You are helpful.",
        user_template="Reply JSON {{\"ok\": true}}.",
        json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False},
        model="gpt-4.1-mini",
        parameters={"max_tokens": 32},
    )
    runner = AgentRunner()

    orig_generate = runner.router.generate
    state = {"calls": 0}

    async def flaky(*args, **kwargs):
        state["calls"] += 1
        if state["calls"] == 1:
            error = ProviderError("transient", provider="openai")
            error.is_retryable = True  # Mark as retryable
            raise error
        return await orig_generate(*args, **kwargs)

    monkeypatch.setattr(runner.router, "generate", flaky)

    res = await runner.run(agent, {}, {"deterministic": True, "metadata": {"strict": True}})
    assert isinstance(res.content, (dict, str))
    assert state["calls"] >= 2


