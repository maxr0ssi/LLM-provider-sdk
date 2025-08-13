# Release v0.2.0 - Nexus Agent Framework & OpenAI Responses API

## 🎉 Major Release: Agent Framework Integration

This release introduces the **Nexus Agent Framework** to the Steer LLM SDK, marking a significant evolution in our AI capabilities. The SDK now provides a comprehensive agent-based architecture with support for OpenAI's Responses API.

## 🚀 What's New

### Agent Framework
- Complete agent abstraction layer with `AgentDefinition`, `AgentOptions`, and `AgentResult`
- Streaming callbacks for real-time responses
- Deterministic execution for reproducible results
- Idempotency support with request deduplication

### OpenAI Responses API
- Full support for GPT-4.1-mini and GPT-5-mini models
- Native JSON schema validation
- Automatic API routing based on model capabilities
- Special handling for model-specific requirements

### Provider Capabilities
- New capability-driven architecture
- Feature detection per model
- Support for prompt caching, tool calling, and fixed temperatures
- Normalized interface across all providers

## 📦 Installation

Install directly from this release:

```bash
# Using the wheel file
pip install https://github.com/maxr0ssi/LLM-provider-sdk/releases/download/v0.2.0/steer_llm_sdk-0.2.0-py3-none-any.whl

# Or from source
pip install git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.2.0
```

## 💰 Updated Pricing

### GPT-5-mini
- Input: $0.250/1M tokens
- Output: $2.000/1M tokens
- Cached: $0.025/1M tokens

## 🔧 Usage Example

```python
from steer_llm_sdk.agents import AgentDefinition, AgentRunner

# Define an agent with structured output
agent = AgentDefinition(
    system="You extract structured data.",
    user_template="Extract key facts from: {text}",
    json_schema={
        "type": "object",
        "properties": {"facts": {"type": "array", "items": {"type": "string"}}},
        "required": ["facts"]
    },
    model="gpt-5-mini"
)

# Run the agent
result = await AgentRunner().run(
    agent, 
    variables={"text": "Your input text here"},
    options={"deterministic": True}
)
```

## ✅ Compatibility

- **No breaking changes** - All existing APIs remain backward compatible
- Python 3.10+ required
- New jsonschema dependency added

## 📚 Documentation

- [Architecture Overview](docs/sdk-architecture.md)
- [OpenAI Responses API Guide](docs/openai-responses-api.md)
- [Agent Framework Guide](docs/user-guides/agents-openai-responses.md)

## 🙏 Acknowledgments

This release represents Phase 1 of the Nexus integration, establishing the foundation for advanced agent-based architectures in the Steer ecosystem.

---

**Full Changelog**: https://github.com/maxr0ssi/LLM-provider-sdk/compare/v0.1.2...v0.2.0