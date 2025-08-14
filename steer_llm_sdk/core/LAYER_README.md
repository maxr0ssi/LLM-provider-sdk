# Core Business Logic Layers

This directory contains the provider-agnostic core business logic of the Steer LLM SDK, organized into distinct layers that work together to provide a clean, extensible architecture.

## Layer Structure

### decision/
**Purpose**: Initial request analysis and routing decisions
- Analyzes incoming requests to determine processing path
- Decides between agent-based and direct LLM routes
- Handles message shaping and preparation

### normalization/
**Purpose**: Standardizes data across different providers
- Parameter normalization (converts frontend params to provider-specific formats)
- Usage data normalization (standardizes token counts, costs, etc.)
- Streaming event normalization (unifies streaming interfaces)

### capabilities/
**Purpose**: Model capability registry and policy enforcement
- Maintains registry of model capabilities
- Enforces capability-driven behavior (no hardcoded conditionals)
- Applies determinism and budget policies
- Provides feature detection for routing decisions

### routing/
**Purpose**: Provider selection and request routing
- Selects appropriate provider based on model and capabilities
- Routes requests to provider adapters
- Handles load balancing and failover
- Manages provider availability checks

## Design Principles

1. **Provider Agnostic**: No provider-specific code in core layers
2. **Capability Driven**: Behavior determined by capabilities, not hardcoded logic
3. **Clean Interfaces**: Each layer has well-defined inputs and outputs
4. **Testable**: Each layer can be tested independently
5. **Extensible**: New features can be added without modifying existing code

## Data Flow

```
Request → decision → normalization → capabilities → routing → Provider Adapter
```

Each layer transforms and enriches the request before passing it to the next layer.