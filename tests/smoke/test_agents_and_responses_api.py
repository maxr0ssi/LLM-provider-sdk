import asyncio
import os
import pytest

pytestmark = pytest.mark.asyncio


async def _run_agent_once(text: str, model: str):
    from steer_llm_sdk.agents.models import AgentDefinition
    from steer_llm_sdk.agents.runner.agent_runner import AgentRunner

    agent = AgentDefinition(
        system="You extract a JSON array of facts.",
        user_template="Extract facts from: {text}",
        json_schema={
            "type": "object",
            "properties": {
                "facts": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["facts"],
        },
        model=model,
        parameters={"temperature": 0.0, "max_tokens": 128},
    )

    runner = AgentRunner()
    result = await runner.run(agent, {"text": text}, {"deterministic": True})
    assert result.model
    assert isinstance(result.usage, dict)
    assert result.elapsed_ms >= 0
    # content may be dict (validated) or string if provider failed validation
    assert result.content is not None
    return result


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY")
async def test_responses_api_gpt41_mini_smoke():
    res = await _run_agent_once("Hello world", "gpt-4.1-mini")
    assert res.model


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY")
async def test_responses_api_gpt5_mini_smoke():
    res = await _run_agent_once("Hello world", "gpt-5-mini")
    assert res.model


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Requires OPENAI_API_KEY")
async def test_responses_api_strict_and_instructions():
    from steer_llm_sdk.agents.models import AgentDefinition
    from steer_llm_sdk.agents.runner.agent_runner import AgentRunner

    agent = AgentDefinition(
        system="You return JSON with key 'ok'.",
        user_template="Say hi.",
        json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False},
        model="gpt-4.1-mini",
        parameters={"max_tokens": 64},
    )
    runner = AgentRunner()
    result = await runner.run(
        agent,
        variables={},
        options={"deterministic": True, "metadata": {"strict": True, "responses_use_instructions": True}},
    )
    assert result.content is not None


