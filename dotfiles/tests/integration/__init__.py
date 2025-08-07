"""
Integration tests module.

These tests MUST only run in Docker containers.
Do not import or run these tests directly on host systems.
"""

# Prevent pytest from discovering integration tests
# when running normal test suite
import os
import sys

# Check if we're being imported by pytest during collection
if "pytest" in sys.modules and not os.environ.get("ALLOW_INTEGRATION_TESTS"):
    # Skip this entire module during pytest collection
    import pytest
    pytest.skip("Integration tests must run in Docker only", allow_module_level=True)