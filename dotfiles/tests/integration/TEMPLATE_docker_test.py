#!/usr/bin/env python3
"""
TEMPLATE FOR NEW INTEGRATION TESTS

Copy this file when creating new integration tests to ensure proper Docker safety.
Replace TEMPLATE with your test name and update the docstring.

IMPORTANT: Integration tests MUST run in Docker. There is NO override mechanism.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports first
sys.path.insert(0, '/app/src')

# Import modules you need (after path setup)
from dotfiles_sync.cli import cli
from click.testing import CliRunner

# CRITICAL SAFETY CHECK: Ensure we're running in Docker
# NO OVERRIDES - These tests can ONLY run in Docker
from docker_only_guard import require_docker

# Absolute requirement - no bypasses allowed
require_docker("""
❌ CRITICAL SAFETY ERROR: Integration tests MUST run in Docker!

These tests modify the file system and could damage your actual dotfiles.
Running them on your host machine is dangerous.

There is NO way to override this safety check.

To run these tests, you MUST use Docker:
  make docker-integration-tests    # Run all integration tests
  make docker-test                  # Run standard tests

Or run directly in Docker:
  docker build -t dotfiles-test -f Dockerfile.test .
  docker run --rm -v $(pwd):/app dotfiles-test python /app/tests/integration/<this_test>.py

These tests are designed to be destructive and CANNOT be run outside of Docker.
""")


def setup_test_environment():
    """Set up the test environment."""
    # Create test directories
    test_dir = Path("/tmp/dotfiles_test")
    test_dir.mkdir(exist_ok=True)
    
    home_dir = Path("/tmp/test_home")
    home_dir.mkdir(exist_ok=True)
    
    # Set HOME to test directory
    os.environ["HOME"] = str(home_dir)
    
    return test_dir, home_dir


def test_example_functionality():
    """
    Test description here.
    
    This test verifies that [functionality] works correctly.
    """
    print("\n=== Testing [Functionality] ===")
    
    test_dir, home_dir = setup_test_environment()
    
    # TODO: Implement your test logic here
    # Example:
    # 1. Create test configuration
    # 2. Run CLI commands
    # 3. Verify results
    # 4. Clean up
    
    print("✓ [Functionality] test passed")
    return True


def main():
    """Run all tests in this module."""
    print("=" * 60)
    print("INTEGRATION TEST: [TEST NAME]")
    print("=" * 60)
    
    tests = [
        ("Example Test", test_example_functionality),
        # Add more test functions here
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} FAILED")
        except AssertionError as e:
            failed += 1
            print(f"❌ {test_name} FAILED: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())