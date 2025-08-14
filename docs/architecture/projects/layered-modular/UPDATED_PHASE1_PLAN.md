# Updated Phase 1 Plan with Directory Restructuring

## Overview
Based on your feedback, we need to restructure the directory tree FIRST to properly reflect the layered-modular architecture before implementing the contracts and normalization. This ensures our code organization matches our architectural vision from the start.

## Revised Phase Timeline

### Phase 0.5: Directory Restructuring (COMPLETED - 2025-08-14)
**Priority**: CRITICAL - Completed; Phase 1 unblocked

#### Week 1: Restructure Directory Tree
1. **Day 1-2: Create New Structure**
   - Create all layer directories as specified in RESTRUCTURING_PLAN.md
   - Add __init__.py files with layer documentation
    - Create a migration script to automate file moves
    - Scaffold new modules required by the structure: `streaming/types.py` and `reliability/budget.py`

2. **Day 3-4: Move Core Components** (Completed)
   - Normalization modules in `core/normalization/`
   - Capability system in `core/capabilities/`  
   - Routing logic in `core/routing/`
   - All internal imports updated

3. **Day 5: Move Providers & Support Systems** (Completed)
   - Providers restructured into top-level `providers/` directory
   - Streaming components moved:
     - `streaming/manager.py` and `streaming/adapter.py`
     - `streaming/types.py` created
   - Reliability components moved:
     - `reliability/errors.py`, `reliability/retry.py`, `reliability/idempotency.py`
     - `reliability/budget.py` created
   - Observability components placed under `observability/`
   - Agent framework remains cohesive

4. **Day 6-7: Compatibility & Testing** (Completed)
   - Backward compatibility shims created
   - `main.py` is a shim re-exporting from `api/client.py`
   - All imports fixed
   - Tests passing
   - Migration notes drafted

### Phase 1: Contracts & Normalization (Updated - 1 week)
**Dependencies**: Phase 0.5 complete

#### Week 2: Complete Implementation in New Structure
1. **Complete Provider Adapter Interface**
   - Finalize base.py in new location
   - Update all providers to inherit from base
   - Add interface documentation

2. **Enhance Normalization Modules**
   - Add streaming normalization module
   - Complete parameter normalization tests
   - Add provider-specific edge cases

3. **Implement Streaming Standards**
   - Create streaming/events.py with event definitions
   - Standardize on_usage emission timing
   - Document streaming contract

4. **Integration Testing**
   - Test all providers with new structure
   - Verify normalization consistency
   - Benchmark performance

## Key Benefits of Restructuring First

1. **Clear Mental Model**: Directory structure matches architecture diagrams
2. **Easier Development**: Know exactly where each component belongs
3. **Better Collaboration**: Team members can find code intuitively
4. **Prevent Refactoring**: Avoid moving code multiple times
5. **Clean Git History**: File moves tracked properly from the start

## Migration Script Example

```python
#!/usr/bin/env python3
"""
Automated migration script for restructuring the SDK.
"""
import os
import shutil
from pathlib import Path

migrations = [
    # (source, destination)
    ("steer_llm_sdk/main.py", "steer_llm_sdk/api/client.py"),
    ("steer_llm_sdk/cli.py", "steer_llm_sdk/api/cli.py"),
    ("steer_llm_sdk/llm/normalizers", "steer_llm_sdk/core/normalization"),
    ("steer_llm_sdk/llm/capabilities.py", "steer_llm_sdk/core/capabilities/loader.py"),
    ("steer_llm_sdk/llm/router.py", "steer_llm_sdk/core/routing/router.py"),
    ("steer_llm_sdk/llm/registry.py", "steer_llm_sdk/core/routing/selector.py"),
    ("steer_llm_sdk/agents/runner/event_manager.py", "steer_llm_sdk/streaming/manager.py"),
    ("steer_llm_sdk/agents/runner/stream_adapter.py", "steer_llm_sdk/streaming/adapter.py"),
    ("steer_llm_sdk/agents/errors.py", "steer_llm_sdk/reliability/errors.py"),
    ("steer_llm_sdk/agents/retry.py", "steer_llm_sdk/reliability/retry.py"),
    ("steer_llm_sdk/agents/runner/idempotency.py", "steer_llm_sdk/reliability/idempotency.py"),
    ("steer_llm_sdk/llm/providers", "steer_llm_sdk/providers"),
    # ... more migrations
]

def migrate_files():
    for source, dest in migrations:
        # Create destination directory
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        # Move with git
        os.system(f"git mv {source} {dest}")

if __name__ == "__main__":
    migrate_files()
```

## Updated Success Criteria

### For Phase 0.5
- ✅ All files in correct layer directories
- ✅ No broken imports
- ✅ All tests passing
- ✅ Clear layer boundaries established
- ✅ Backward compatibility maintained
- ✅ New modules created: `streaming/types.py`, `reliability/budget.py`
- ✅ `main.py` acts as compatibility shim for `api/client.py`

### For Phase 1 (in new structure)
- ✅ Provider adapter interface in `providers/base.py`
- ✅ All normalizers in `core/normalization/`
- ✅ Streaming standards in `streaming/`
- ✅ No hardcoded logic in providers
- ✅ Capability-driven behavior throughout

## Risk Mitigation

1. **Import Errors**: Use automated tools to update imports
2. **Test Failures**: Run tests after each major move
3. **Git History**: Use `git mv` to preserve history
4. **Team Disruption**: Communicate changes clearly
5. **Merge Conflicts**: Complete quickly in dedicated branch

## Next Steps

1. Review and approve RESTRUCTURING_PLAN.md
2. Create migration script
3. Execute Phase 0.5 restructuring
4. Update all documentation to reflect new structure
5. Continue with enhanced Phase 1 implementation
6. Consult `PARALLEL_PLANNER.md` to split workstreams and reduce cycle time

This approach ensures our codebase structure reflects our architectural vision from the beginning, making all subsequent phases cleaner and more intuitive.