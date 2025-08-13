## Layered Modular Redesign – Project Brief

### Objective
Make the layered, provider‑agnostic architecture real across the SDK, enabling easy addition of providers, models, and optional provider‑native agent adapters without breaking backward compatibility.

### Goals
- Clear separation of layers per `docs/architecture/layered-modular-design.md`.
- Normalized params, usage, streaming events across providers.
- Capability‑driven behavior; no hard‑coded model branches.
- Optional adapters for provider‑native agent systems (outside core).
- Maintain current public API and pass all existing smoke tests.

### Deliverables
- Architecture alignment edits (minimal, focused) with stable interfaces.
- Completed capability registry for supported models.
- Usage normalization and standardized on‑stream vs end‑stream usage emission.
- Typed errors across providers; unified retry strategy.
- Documentation and examples for users.

### Success criteria
- All smoke tests pass; new tests added for normalization and capabilities.
- Adding a new provider requires only: adapter + capability entries + tests.
- Adding a new model requires only: capability entry + tests.

### Read next
- `architecture-plan.md` – target structure and contracts
- `refactoring-plan.md` – phased work plan
- `examples.md` – usage examples
- `diagrams.md` – updated ASCII diagrams
- `test-plan.md` – validation strategy
- `migration.md` – compatibility and changes
- `backlog.md` & `checklist.md` – task tracking


