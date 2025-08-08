"""
Docker environment guard for integration tests.

This module ensures integration tests only run in Docker containers.
"""

import os
import sys
from pathlib import Path


def check_docker_environment():
    """
    Check if we're running in a Docker container.

    Returns:
        bool: True if in Docker, False otherwise
    """
    # Check for Docker-specific files
    docker_indicators = [
        Path("/.dockerenv"),  # Docker creates this file
        Path("/proc/1/cgroup"),  # Contains docker references in containers
    ]

    for indicator in docker_indicators:
        if indicator.exists():
            if indicator.name == "cgroup":
                # Check if file contains "docker"
                try:
                    with open(indicator, "r") as f:
                        if "docker" in f.read().lower():
                            return True
                except Exception:
                    pass
            else:
                return True

    # Check for Docker environment variables
    docker_env_vars = [
        "DOCKER_CONTAINER",
        "RUNNING_IN_DOCKER",
        "IS_DOCKER",
        "DOTFILES_TEST_MODE",  # Set in Dockerfile.test
    ]

    for var in docker_env_vars:
        if os.environ.get(var):
            return True

    # Check if /app directory exists (our Docker convention)
    if Path("/app").exists() and Path("/app/src").exists():
        return True

    return False


def require_docker(exit_message: str = None):
    """
    Require Docker environment or exit.

    Args:
        exit_message: Custom message to display when not in Docker
    """
    if not check_docker_environment():
        if not exit_message:
            exit_message = """
❌ SAFETY ERROR: Integration tests must run in Docker!

These tests modify the file system and must not run on your host machine.
Please use one of these commands:

  make docker-test              # Run standard Docker tests
  make docker-test-all          # Run all Docker tests
  make docker-test-new-verbs    # Run new verb integration tests

Or run directly in Docker:
  docker run --rm -v $(pwd):/app dotfiles-test python /app/tests/integration/<test_file>.py

Refusing to run to protect your system.
"""
        print(exit_message, file=sys.stderr)
        sys.exit(1)


def is_docker():
    """Simple check if running in Docker."""
    return check_docker_environment()
