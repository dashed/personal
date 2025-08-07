"""
Pytest configuration for integration tests.

This file prevents pytest from auto-discovering integration tests
and provides shared fixtures for integration testing.
"""

import pytest
import sys
from pathlib import Path

# Add integration directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import Docker guard
from docker_only_guard import check_docker_environment


def pytest_collection_modifyitems(config, items):
    """Skip integration tests if not in Docker."""
    if not check_docker_environment():
        skip_integration = pytest.mark.skip(reason="Integration tests only run in Docker")
        for item in items:
            if "integration" in str(item.fspath):
                item.add_marker(skip_integration)


# Shared fixtures for integration tests
@pytest.fixture
def docker_test_dir(tmp_path):
    """Create a test directory for Docker tests."""
    test_dir = tmp_path / "docker_test"
    test_dir.mkdir()
    return test_dir


@pytest.fixture
def docker_home_dir(tmp_path, monkeypatch):
    """Create and set a test HOME directory."""
    home_dir = tmp_path / "test_home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    return home_dir