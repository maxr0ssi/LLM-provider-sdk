# Steer LLM SDK Documentation

Welcome to the Steer LLM SDK documentation. This directory contains comprehensive guides, architectural documentation, and integration examples.

## Quick Navigation

- **[Documentation Index](INDEX.md)** - Complete list of all documentation
- **[Main README](../README.md)** - SDK overview, installation, and quick start

## Key Documentation

### Getting Started
- [Chat Completions Guide](guides/chat-completions.md) - Basic usage patterns
- [Streaming Guide](guides/streaming.md) - Complete streaming implementation
- [Structured Outputs](guides/structured-outputs.md) - Deterministic generation and schemas
- [Configuration Guide](configuration/) - Provider and system setup

### Architecture
- [Orchestration Architecture](architecture/orchestration.md) - Tool-based orchestration design
- [Streaming Architecture](architecture/streaming.md) - Unified streaming design
- [Layered Architecture](architecture/projects/layered-modular/) - System design and phases
- [Metrics & Observability](architecture/metrics.md) - Monitoring and tracing

### Advanced Features
- [Orchestration Guide](orchestration/) - Tool-based execution with reliability
- [Agent Runtime](guides/agent-runtime-integration.md) - Building AI agents
- [OpenAI Agents SDK](integrations/openai-agents/) - Native agent integration
- [Observability](guides/observability.md) - Metrics and monitoring

### Integration
- [HTTP Endpoints](guides/http-endpoints.md) - REST API reference

## Recent Updates

- **v0.3.2** - Production-ready orchestration module with tool-based architecture
- **v0.3.1** - API key security improvements
- **v0.3.0** - Agent infrastructure, streaming consolidation, pre-release cleanup
- **Streaming API Split** - New `stream_with_usage()` method ([migration guide](guides/streaming-api-migration.md))
- **OpenAI Agents SDK** - Full integration with tools and structured outputs

## Contributing

When adding new documentation:
1. Place guides in `guides/`
2. Place architecture docs in `architecture/`
3. Update the [INDEX.md](INDEX.md) file
4. Follow the existing markdown style
