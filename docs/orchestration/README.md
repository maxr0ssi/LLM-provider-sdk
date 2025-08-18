# Orchestration Documentation

This directory contains documentation for the Steer LLM SDK orchestration module.

## Current State (2025-08-18)

The orchestration module has undergone a comprehensive cleanup and is now **production-ready**. All legacy code has been removed, naming conventions have been standardized, and all tests are passing.

See [CURRENT_STATE.md](./CURRENT_STATE.md) for detailed information about the current implementation.

## Documentation Structure

### Core Documentation
- [Overview](./overview.md) - Introduction and architecture overview
- [CURRENT_STATE.md](./CURRENT_STATE.md) - Detailed current state after cleanup
- [Planning & Reliability Guide](./planning-reliability-guide.md) - Advanced features guide

### Development Documentation
- [CLEANUP_SUMMARY.md](./CLEANUP_SUMMARY.md) - Summary of cleanup changes
- [orchestration-dev-phases.md](./orchestration-dev-phases.md) - Development history

### Tool Development
- [Tool Development Guide](./tool-development-guide.md) - How to create custom tools
- [Evidence Bundle Guide](./evidence-bundle-guide.md) - Working with evidence bundles

## Quick Links

### For Users
- Start with the [Overview](./overview.md)
- Learn about [Planning & Reliability](./planning-reliability-guide.md) features
- See [CURRENT_STATE.md](./CURRENT_STATE.md) for the latest implementation details

### For Developers
- [Tool Development Guide](./tool-development-guide.md) for creating custom tools
- [CLEANUP_SUMMARY.md](./CLEANUP_SUMMARY.md) for migration from old versions

## Key Highlights

✅ **Production Ready**: All 32 orchestration tests passing  
✅ **Clean Architecture**: No legacy code or technical debt  
✅ **Advanced Features**: Retry logic, circuit breakers, idempotency  
✅ **Professional Naming**: No more "Enhanced" or version suffixes  
✅ **Well Documented**: Comprehensive guides and examples  

## Support

For questions or issues related to the orchestration module, please refer to the [main SDK documentation](../../README.md) or file an issue in the repository.