# 🚀 Nexus Agent Framework Integration & OpenAI Responses API Support

## Overview

This PR introduces the **Nexus Agent Framework** to the Steer LLM SDK, implementing a comprehensive agent-based architecture with support for OpenAI's Responses API. This represents a major evolution of the SDK, adding structured output capabilities, deterministic execution, and a powerful agent abstraction layer.

## ✨ Key Features

### 1. **Agent Framework (Complete Phase 1)**
- **Core Primitives**: `AgentDefinition`, `AgentOptions`, `AgentResult`
- **Agent Runner**: Orchestrates agent execution with streaming callbacks
- **Event Management**: Normalized streaming interface across all providers
- **Deterministic Execution**: Centralized parameter control for reproducible results
- **Idempotency**: Request deduplication with TTL-based caching

### 2. **OpenAI Responses API Integration**
- Full support for **GPT-4.1-mini** and **GPT-5-mini** models
- Automatic routing between Chat Completions and Responses API
- Native JSON schema validation
- Special handling for model-specific requirements (e.g., GPT-5-mini temperature omission)
- Streaming support with graceful fallback

### 3. **Provider Capabilities System**
- Replaced hardcoded model checks with capability-driven routing
- Comprehensive feature detection per model
- Support for:
  - JSON schema validation
  - Streaming with usage data
  - Deterministic seeds
  - Tool calling
  - Prompt caching
  - Fixed temperature requirements

### 4. **Structured Output & Validation**
- Native JSON schema support for compatible models
- Post-hoc validation for other providers
- Built-in tools: `format_validator`, `extract_json`, `json_repair`
- Strict schema enforcement with detailed error messages

## 📊 Changes Summary

- **73 files changed**: 3,120 insertions(+), 905 deletions(-)
- **New modules**: `steer_llm_sdk/agents/` with complete agent implementation
- **Updated providers**: Enhanced OpenAI, Anthropic, and xAI providers
- **Documentation**: Comprehensive guides and architecture docs
- **Testing**: Unit tests for all new components

## 💰 Model Updates

### GPT-5-mini Configuration
- Input: $0.250/1M tokens
- Output: $2.000/1M tokens  
- Cached: $0.025/1M tokens
- 256K context window
- Full Responses API support

## 🔄 Migration Guide

### For Existing Users
- ✅ **No breaking changes** - All existing APIs remain backward compatible
- ✅ Direct `generate()` and `stream()` methods work as before
- ✅ Automatic capability-based routing happens transparently

### New Agent Framework (Opt-in)
```python
from steer_llm_sdk.agents import AgentDefinition, AgentRunner

agent = AgentDefinition(
    system="You extract structured data.",
    user_template="Extract key facts from: {text}",
    json_schema={"type": "object", "properties": {"facts": {"type": "array"}}},
    model="gpt-5-mini"
)

result = await AgentRunner().run(agent, variables={"text": source_text})
```

## 📝 Documentation

- **Architecture**: `docs/sdk-architecture.md`
- **Responses API Guide**: `docs/openai-responses-api.md`
- **Progress Tracker**: `docs/SDK_PROGRESS.md`
- **User Guides**: Complete examples in `docs/user-guides/`

## ✅ Testing

- All existing tests pass
- New unit tests for agent components
- Integration tests for Responses API
- Backward compatibility verified

## 🚦 Pre-merge Checklist

- [x] Code follows project style guidelines
- [x] Tests pass locally
- [x] Documentation updated
- [x] Version bumped to 0.2.0
- [x] CHANGELOG.md created
- [x] No breaking changes to existing APIs
- [x] File size limits enforced (<400 LOC per file)

## 🔮 Future Phases

This PR completes Phase 1 of the Nexus integration. Future phases will include:
- Phase 2-8: A2A protocol, orchestrator integration, evaluation framework, etc.
- Enhanced retry mechanisms and circuit breakers
- Expanded tool library
- Production monitoring and metrics

## 📦 Release Plan

After merging:
1. Create GitHub release v0.2.0
2. Build and upload wheel file
3. Update dependent projects to use new version

---

This is a significant milestone that establishes the foundation for advanced agent-based architectures while maintaining full backward compatibility. The implementation follows the architectural plans in `docs/projects/nexus/` and sets up the SDK for future Nexus phases.