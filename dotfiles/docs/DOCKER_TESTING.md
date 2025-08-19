# Docker Testing Architecture

## Overview
All tests in this project can run safely in Docker using the unified `Dockerfile.test`. This ensures complete isolation and prevents any accidental modifications to the host system.

## Single Dockerfile Strategy

We use **one Dockerfile** (`Dockerfile.test`) for all testing needs:
- ✅ Unit tests
- ✅ Integration tests  
- ✅ Phase 1 MVP validation
- ✅ New verb testing
- ✅ Safety feature validation

## Test Commands

### Primary Testing Commands

```bash
# Complete validation (includes Docker tests) - USE THIS FOR CI/CD
make check

# Fast validation (unit tests only) - USE THIS FOR DEVELOPMENT
make check-fast

# Quick lint checks (2 seconds) - USE THIS WHILE CODING
make quick-check
```

### Docker-Specific Commands

```bash
# Run ALL tests in Docker (unit + integration)
make docker-integration-tests

# Run specific test suites
make docker-test              # Phase 1 default variant
make docker-test-all          # All Phase 1 variants
make docker-test-new-verbs    # New verb implementations

# Verify Docker safety guards
make verify-docker-guard
```

## How It Works

### 1. Build Stage
```dockerfile
# Dockerfile.test uses multi-stage build
FROM ubuntu:24.04 as base
# Install Python, uv, dependencies
# Create non-root testuser
# Copy and install project
```

### 2. Test Execution
```bash
# Unit tests run in Docker
docker run --rm -v $(PWD):/app dotfiles-test \
  sh -c "cd /app && uv run pytest tests/unit"

# Integration tests run with safety checks
docker run --rm -v $(PWD):/app -e RUNNING_IN_DOCKER=1 \
  dotfiles-test python /app/tests/integration/run_integration_tests.py
```

### 3. Safety Mechanisms
- Docker environment detection via multiple indicators
- Non-root user execution
- Volume mounts for code, not system files
- Environment variable `DOTFILES_TEST_MODE=true`

## Integration Test Safety

### Multiple Protection Layers

1. **File Naming Convention**
   - Integration tests use `docker_test_*.py` prefix
   - Won't match pytest's default `test_*.py` pattern

2. **Docker Environment Guard**
   ```python
   from docker_only_guard import require_docker
   require_docker()  # Exits if not in Docker
   ```

3. **Pytest Configuration**
   ```toml
   # pyproject.toml
   testpaths = ["tests/unit"]  # Only unit tests by default
   ```

4. **Module Skip**
   ```python
   # tests/integration/__init__.py
   if "pytest" in sys.modules:
       pytest.skip("Integration tests must run in Docker only")
   ```

## Development Workflow

### Fast Development Cycle
```bash
# While coding - instant feedback
make quick-check          # 2 seconds

# Before commits - thorough check
make check-fast           # 10 seconds

# Before PRs - complete validation
make check                # 2-5 minutes (includes Docker)
```

### CI/CD Pipeline
```yaml
# GitHub Actions example
- name: Complete Validation
  run: make check  # Includes Docker tests automatically
```

## Docker Environment Variables

The following environment variables are set in Docker:

| Variable | Value | Purpose |
|----------|-------|---------|
| `DOTFILES_TEST_MODE` | `true` | Indicates test environment |
| `RUNNING_IN_DOCKER` | `1` | Docker detection |
| `DOTFILES_VARIANT` | varies | Test variant (default/personal/work) |
| `PATH` | includes `.venv/bin` | Python virtual environment |

## File Structure

```
Dockerfile.test           # Unified test image
docker-test-runner.sh     # Test execution script
docker-compose.test.yml   # Multi-variant testing

tests/
├── unit/                 # Safe to run anywhere
│   └── test_*.py        # Standard pytest files
│
└── integration/          # Docker-only tests
    ├── docker_only_guard.py      # Safety enforcement
    ├── docker_test_*.py          # Integration tests
    ├── run_integration_tests.py  # Main runner
    └── conftest.py               # Pytest config
```

## Adding New Tests

### Unit Tests
```python
# tests/unit/test_feature.py
def test_feature(tmp_path):
    """Standard unit test - safe to run anywhere."""
    # Uses tmp_path fixture for file operations
```

### Integration Tests
```python
# tests/integration/docker_test_feature.py
#!/usr/bin/env python3

# MANDATORY: Docker safety check
from docker_only_guard import require_docker
require_docker()

# Now safe to import and test
def test_feature_integration():
    """Integration test - only runs in Docker."""
    # Can modify /tmp, /home/testuser, etc.
```

## Troubleshooting

### Tests Not Running in Docker
```bash
# Check Docker is installed and running
docker --version
docker info

# Build test image manually
docker build -t dotfiles-test -f Dockerfile.test .

# Run with debug output
docker run --rm -it dotfiles-test bash
```

### Integration Tests Running on Host
This should NEVER happen, but if it does:
1. Check `make verify-docker-guard` passes
2. Ensure `RUNNING_IN_DOCKER` is not set on host
3. Verify integration test files have guards

### Slow Docker Builds
```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker build -t dotfiles-test -f Dockerfile.test .

# Or use docker-compose which caches layers
docker-compose -f docker-compose.test.yml build
```

## Best Practices

1. **Always use `make check` for final validation** - It includes Docker tests
2. **Use `make check-fast` during development** - Faster feedback loop
3. **Never bypass Docker guards** - They protect your system
4. **Keep tests isolated** - Each test should be independent
5. **Use appropriate fixtures** - `tmp_path` for unit tests, Docker paths for integration

## Summary

- ✅ **One Dockerfile** (`Dockerfile.test`) for all testing
- ✅ **Safe by default** - Integration tests can't run on host
- ✅ **Fast development** - Multiple check speeds available
- ✅ **CI/CD ready** - `make check` runs everything
- ✅ **Well documented** - Clear commands and workflows