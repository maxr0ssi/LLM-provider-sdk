# Release Checklist for v0.3.0

## Pre-Release Steps

### Code Quality
- [x] All tests passing (unit and smoke tests)
- [x] No linting errors
- [x] Documentation updated
- [x] Version bumped in pyproject.toml
- [x] Changelog updated

### Cleanup Completed
- [x] Removed all backup files (.bak)
- [x] Deleted archive directories
- [x] Removed legacy pricing code
- [x] Consolidated streaming documentation
- [x] Implemented lazy circuit breakers
- [x] Refactored model configurations

### Package Preparation
- [x] Updated pyproject.toml metadata
- [x] Created MANIFEST.in
- [x] Added GitHub workflows
- [x] Updated installation instructions

## Release Process

1. **Final Testing**
   ```bash
   # Run all tests
   pytest tests/ -v
   
   # Build package locally
   python -m build
   
   # Check package contents
   tar -tzf dist/*.tar.gz | head -20
   ```

2. **Commit All Changes**
   ```bash
   git add -A
   git commit -m "chore: prepare v0.3.0 release

   - Agent infrastructure with OpenAI Agents SDK
   - Unified streaming architecture
   - Enhanced observability and metrics
   - Circuit breakers and retry mechanisms
   - Nexus-ready agent framework
   - Pre-release cleanup completed"
   ```

3. **Create Release Candidate Tag**
   ```bash
   git tag -a v0.3.0-rc1 -m "Release candidate 1 for v0.3.0"
   git push origin agent-architecture
   git push origin v0.3.0-rc1
   ```

4. **Test Installation**
   ```bash
   # Test from tag
   pip install git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.0-rc1
   ```

5. **Create Final Release**
   ```bash
   # If RC is good, tag final release
   git tag -a v0.3.0 -m "Release v0.3.0 - Agent Infrastructure"
   git push origin v0.3.0
   ```

## Post-Release

1. **Monitor GitHub Actions**
   - Check workflow runs
   - Verify package published

2. **Update Nexus/SteerQA**
   - Update dependency to v0.3.0
   - Test integration

3. **Announce Release**
   - Update internal docs
   - Notify team

## Package Usage

For private GitHub package:
```bash
export GITHUB_TOKEN=your_token
pip install git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.0
```

With extras:
```bash
pip install "git+https://github.com/maxr0ssi/LLM-provider-sdk.git@v0.3.0#egg=steer-llm-sdk[openai-agents,tiktoken,http]"
```