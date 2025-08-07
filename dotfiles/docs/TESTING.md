# Testing Guide

## Test Commands Overview

### Quick Development Testing
```bash
# Fastest - just linting with ty and ruff (< 2 seconds)
make quick-check

# Fast - linting, type checking, unit tests (< 10 seconds)
make check-fast

# Complete - all checks including Docker integration tests (2-5 minutes)
make check
```

### Specific Test Types

#### Unit Tests
```bash
# Run unit tests only
make test

# Run with coverage report
uv run pytest tests/unit --cov=dotfiles_sync --cov-report=html
```

#### Integration Tests (Docker Only)
```bash
# Run ALL integration tests in Docker (recommended)
make docker-integration-tests

# Run specific integration test suites
make docker-test-new-verbs    # Test new verb implementations
make docker-test              # Standard Phase 1 tests
make docker-test-all          # All Phase 1 variants
```

#### Linting and Type Checking
```bash
# Linting with ruff
make lint

# Type checking with ty
make typecheck

# Fast type checking with ty (Rust-based)
make ty
```

## Command Reference

### Primary Commands

| Command | Description | Time | Use Case |
|---------|------------|------|----------|
| `make quick-check` | ty + ruff only | ~2s | While coding |
| `make check-fast` | All checks except Docker | ~10s | Before commits |
| `make check` | Complete validation | 2-5min | Before PRs |
| `make check-all` | Alias for `make check` | 2-5min | CI/CD |

### Docker Integration Test Commands

| Command | Description | Safe? |
|---------|------------|-------|
| `make docker-integration-tests` | Run all integration tests | ✅ Yes |
| `make docker-test-new-verbs` | Test new verbs | ✅ Yes |
| `make docker-test` | Phase 1 default variant | ✅ Yes |
| `make docker-test-all` | All Phase 1 variants | ✅ Yes |
| `make verify-docker-guard` | Check safety mechanisms | ✅ Yes |

## Test Organization

### Directory Structure
```
tests/
├── unit/                 # Unit tests (safe, run on host)
│   ├── safety/          # Safety component tests
│   ├── verbs/           # Verb implementation tests
│   └── test_*.py        # Core module tests
│
└── integration/         # Integration tests (Docker only!)
    ├── docker_only_guard.py    # Safety enforcement
    ├── docker_test_*.py        # Test files (won't auto-discover)
    └── conftest.py             # Pytest configuration
```

### Safety Features

1. **Unit Tests** - Always safe to run on host
   - Use `tmp_path` fixtures
   - Mock all file operations
   - No real system modifications

2. **Integration Tests** - Docker only
   - Docker environment guard
   - Special file naming (`docker_test_*.py`)
   - Excluded from default pytest paths
   - Multiple safety checks

## Writing Tests

### Unit Tests
```python
def test_something(tmp_path):
    """Test with temporary directory."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    # Test your code
```

### Integration Tests
```python
#!/usr/bin/env python3
# MUST have Docker guard!
from docker_only_guard import require_docker
require_docker()

# Now safe to import and test
from dotfiles_sync.cli import cli
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      # Fast checks first
      - name: Fast checks
        run: make check-fast
      
      # Full validation with Docker
      - name: Complete validation
        run: make check
```

### Local Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Run fast checks before commit
make check-fast || exit 1
```

## Performance Tips

1. **During Development**
   - Use `make quick-check` frequently (2 seconds)
   - Run `make check-fast` before commits (10 seconds)

2. **Before Pull Requests**
   - Always run `make check` (includes integration tests)
   - Fix any issues before pushing

3. **Continuous Integration**
   - Use `make check-all` for complete validation
   - Fail fast with `make check-fast` first

## Troubleshooting

### Tests Not Found
```bash
# Ensure you're in project root
pwd  # Should show .../dotfiles

# Check Python path
uv run python -c "import sys; print(sys.path)"
```

### Docker Tests Failing
```bash
# Check Docker is running
docker info

# Build image manually
docker build -t dotfiles-integration -f Dockerfile.integration .

# Run with debug output
docker run --rm dotfiles-integration
```

### Integration Tests Running on Host
This should NEVER happen due to safety guards, but if it does:
1. Check `tests/integration/docker_only_guard.py` exists
2. Verify `pyproject.toml` has `testpaths = ["tests/unit"]`
3. Ensure files use `docker_test_*.py` naming

## Coverage Reports

```bash
# Generate HTML coverage report
uv run pytest tests/unit --cov=dotfiles_sync --cov-report=html

# Open in browser
open htmlcov/index.html

# Current coverage: ~73%
```

## Test Philosophy

1. **Safety First** - Integration tests NEVER run on host
2. **Fast Feedback** - Quick checks during development
3. **Comprehensive** - Full validation before merges
4. **Isolated** - Each test is independent
5. **Realistic** - Integration tests use real operations in Docker