## Checklist – Layered Modular SDK

### Contracts
- [ ] Provider Adapter interface documented and adopted
- [ ] GenerationParams fields formalized (responses flags, seed)
- [ ] Usage dict normalized across providers

### Capabilities
- [ ] Capability registry complete for OpenAI (4.1 mini, 5 mini, 4o‑mini)
- [ ] Capability registry complete for Anthropic/xAI

### Routing & Decisions
- [ ] Decision policy implemented (Call | Agent) with tests
- [ ] Param mapping driven only by capabilities

### Streaming & Usage
- [ ] StreamAdapter normalizes text/JSON deltas
- [ ] on_usage emitted once if not in‑stream

### Reliability
- [ ] Typed errors in providers
- [ ] RetryManager covers transient ProviderError
- [ ] Idempotency checked for agent runs

### Metrics
- [ ] Metrics emitted with normalized usage and latency
- [ ] Optional sink documented

### Docs & Examples
- [ ] User guides updated
- [ ] Examples for new provider/model/local adapter


