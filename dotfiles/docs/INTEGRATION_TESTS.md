# Integration Tests - Docker Only Safety Guide

## Overview
All integration tests in this project are **strictly Docker-only** to ensure they never modify the host system. Multiple safety layers prevent accidental execution on host machines.

## Safety Mechanisms

### 1. **Docker Environment Guard**
- File: `tests/integration/docker_only_guard.py`
- Checks for Docker indicators:
  - `/.dockerenv` file existence
  - `/proc/1/cgroup` contains "docker"
  - Docker environment variables
  - `/app` directory structure
- Exits with safety error if not in Docker

### 2. **Pytest Configuration**
- `pyproject.toml`: Only includes `tests/unit` in test paths
- `tests/integration/__init__.py`: Skips module if pytest tries to import
- `tests/integration/conftest.py`: Additional Docker check for pytest

### 3. **File Naming Convention**
- Integration tests use `docker_test_*.py` prefix
- Does not match pytest's default `test_*.py` pattern
- Prevents accidental discovery

## Running Integration Tests

### Safe Commands (Docker-isolated)
```bash
# Run all integration tests in Docker
make docker-integration

# Run specific integration test suite
make docker-test-new-verbs

# Run standard Docker tests
make docker-test
make docker-test-all
```

### Verification Commands
```bash
# Verify Docker guards are working
make verify-docker-guard

# Run normal tests (excludes integration)
make test
```

## Integration Test Files

### Current Integration Tests
- `docker_test_new_verbs.py` - Tests for syncdir, append, prepend, run, run_once verbs

### Supporting Files
- `docker_only_guard.py` - Docker environment detection and enforcement
- `run_integration_tests.py` - Main runner for all integration tests
- `conftest.py` - Pytest configuration for integration tests
- `Dockerfile.integration` - Docker image for integration testing

## Writing New Integration Tests

1. **Always import the Docker guard first:**
```python
from docker_only_guard import require_docker
require_docker()
```

2. **Use docker_test_ prefix for test files:**
```
docker_test_feature.py  ✅ Good
test_feature.py         ❌ Bad (will be auto-discovered)
```

3. **Test in isolated directories:**
```python
# Use /tmp or other Docker-specific paths
test_dir = Path("/tmp/dotfiles_test")
```

## Safety Verification

The system has multiple layers of protection:

1. **File naming** - Integration tests don't match pytest patterns
2. **Module skip** - `__init__.py` skips if pytest imports
3. **Docker guard** - Files check for Docker environment
4. **Pytest config** - Only searches `tests/unit` by default
5. **Conftest** - Additional safety check for pytest

## What Happens If Run on Host?

If someone tries to run integration tests on the host system:

```bash
$ python tests/integration/docker_test_new_verbs.py

❌ SAFETY ERROR: Integration tests must run in Docker!

These tests modify the file system and must not run on your host machine.
Please use one of these commands:

  make docker-test              # Run standard Docker tests
  make docker-test-all          # Run all Docker tests
  make docker-test-new-verbs    # Run new verb integration tests
```

The test will immediately exit without running any potentially destructive operations.

## Docker Image

### Unified Test Image (`Dockerfile.test`)
- Base Ubuntu 24.04 or Debian image
- Python 3.12 with uv package manager
- Used for both unit and integration testing
- Multi-stage build for efficiency
- Runs as non-root `testuser` for safety
- Sets `DOTFILES_TEST_MODE=true` environment variable
- Includes comprehensive test runner script
- Supports multiple variants (default, personal, work)

## Continuous Integration

For CI/CD pipelines, always use Docker:

```yaml
# Example GitHub Actions
- name: Run Integration Tests
  run: make docker-integration
```

Never run integration tests directly in CI runners without Docker isolation.

## Troubleshooting

### Tests Not Found
If integration tests aren't found in Docker:
1. Check file paths are correct
2. Ensure `/app/src` is in Python path
3. Verify Docker volume mounts

### Docker Guard Failing in Docker
If the guard incorrectly blocks in Docker:
1. Set `RUNNING_IN_DOCKER=1` environment variable
2. Ensure `/.dockerenv` exists
3. Check Docker image has proper markers

### Normal Tests Including Integration
If `make test` tries to run integration tests:
1. Check `pyproject.toml` has `testpaths = ["tests/unit"]`
2. Verify `tests/integration/__init__.py` exists
3. Ensure integration tests use `docker_test_` prefix

## Summary

✅ **Integration tests are completely isolated from host system**
✅ **Multiple safety layers prevent accidental execution**
✅ **Clear separation between unit and integration tests**
✅ **Docker-only execution is enforced at multiple levels**
✅ **Safe for development and CI/CD pipelines**