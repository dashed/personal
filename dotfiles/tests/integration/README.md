# Integration Tests

## 🔒 CRITICAL SAFETY REQUIREMENT

**ALL integration tests MUST run ONLY in Docker containers. There are NO exceptions or overrides.**

This is enforced by `docker_only_guard.py` which checks for Docker-specific indicators. If the check fails, tests will exit immediately.

## Why Docker-Only?

Integration tests are designed to be **destructive**:
- They create and delete files
- They modify system directories
- They create symlinks
- They could damage your actual dotfiles if run on the host

## Creating New Integration Tests

### 1. Use the Template

**ALWAYS start from the template:**

```bash
cp tests/integration/TEMPLATE_docker_test.py tests/integration/docker_test_your_feature.py
```

The template includes:
- ✅ Proper Docker safety check (`require_docker()`)
- ✅ No override mechanisms
- ✅ Standard test structure
- ✅ Error handling
- ✅ Result reporting

### 2. Template Structure

```python
#!/usr/bin/env python3
"""Your test description"""

# ... imports ...

# CRITICAL: This MUST be in every integration test
from docker_only_guard import require_docker
require_docker()  # NO CONDITIONS, NO OVERRIDES

# ... your test code ...
```

### 3. Add to Test Runner

Edit `run_integration_tests.py` to include your new test:

```python
from docker_test_your_feature import main as test_your_feature

# In main():
# Run your feature tests
print("\nRunning your feature tests...")
try:
    exit_code = test_your_feature()
    # ... handle results ...
```

## Running Integration Tests

### Run ALL Integration Tests
```bash
make docker-integration-tests
```

### Run Specific Test Suite
```bash
make docker-test-e2e        # End-to-end user journeys
make docker-test-new-verbs  # New verb implementations
make docker-test            # Standard test suite
```

### Run Individual Test File (Docker Required)
```bash
docker build -t dotfiles-test -f Dockerfile.test .
docker run --rm -v $(pwd):/app dotfiles-test python /app/tests/integration/docker_test_your_feature.py
```

## Safety Checklist for New Tests

Before submitting a new integration test, verify:

- [ ] Used `TEMPLATE_docker_test.py` as starting point
- [ ] Includes `from docker_only_guard import require_docker`
- [ ] Calls `require_docker()` unconditionally (no if statements)
- [ ] NO environment variables for overrides
- [ ] NO command-line flags for bypassing
- [ ] Test creates files only in `/tmp/` directories
- [ ] Test sets `HOME` to a test directory
- [ ] Test cleans up after itself

## Docker Safety Mechanism

The `docker_only_guard.py` checks for:
1. Docker-specific files (`/.dockerenv`)
2. Docker process indicators (`/proc/1/cgroup`)
3. Docker environment variables
4. Docker directory structure (`/app`)

If ANY check fails → Test exits immediately

## NO OVERRIDES Policy

**There is intentionally NO way to bypass the Docker requirement:**
- ❌ No `--force` flags
- ❌ No `FORCE_HOST_EXECUTION` environment variables
- ❌ No `--skip-docker-check` options
- ❌ No conditional logic around `require_docker()`

This is by design to prevent accidental damage to developer machines.

## Examples of Good Integration Tests

### ✅ GOOD - Proper Safety
```python
from docker_only_guard import require_docker
require_docker()  # Unconditional, at module level
```

### ❌ BAD - Conditional Check
```python
if not os.environ.get("SKIP_DOCKER_CHECK"):
    require_docker()  # NEVER DO THIS!
```

### ❌ BAD - Override Mechanism
```python
if os.environ.get("FORCE_HOST"):
    print("Warning: Running on host")
else:
    require_docker()  # NEVER DO THIS!
```

## Test File Naming Convention

Integration test files MUST follow this pattern:
- `docker_test_*.py` - Integration test files
- `test_*.py` - Reserved for unit tests (in `tests/unit/`)

## Questions?

If you need to test something that seems to require host access:
1. It probably belongs in unit tests (`tests/unit/`) with mocking
2. If it truly needs integration testing, it MUST run in Docker
3. Consider if the test design needs rethinking

Remember: **Safety first, no exceptions!**