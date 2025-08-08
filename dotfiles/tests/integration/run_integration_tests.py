#!/usr/bin/env python3
"""
Main runner for all integration tests.

This script ensures all integration tests run only in Docker
and provides a central entry point for Docker-based testing.
"""

import sys
from pathlib import Path

# Add integration directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import and run Docker safety check
from docker_only_guard import require_docker

require_docker()


# Now safe to run integration tests
def main():
    """Run all integration tests."""
    print("=" * 60)
    print("RUNNING INTEGRATION TESTS IN DOCKER")
    print("=" * 60)
    print()

    # Import integration test modules
    # They will check Docker environment again for extra safety
    from docker_test_new_verbs import main as test_new_verbs
    from docker_test_database_methods import main as test_database_methods
    from docker_test_e2e_user_journeys import main as test_e2e_journeys
    from docker_test_core_operations import main as test_core_operations
    from docker_test_cli_commands import main as test_cli_commands

    # Track results
    all_passed = True
    results = []

    # Run new verbs integration tests
    print("Running new verbs integration tests...")
    try:
        exit_code = test_new_verbs()
        if exit_code != 0:
            all_passed = False
        results.append(("New Verbs Tests", exit_code == 0))
    except Exception as e:
        print(f"Error running new verbs tests: {e}")
        all_passed = False
        results.append(("New Verbs Tests", False))

    # Run database methods integration tests
    print("\nRunning database methods integration tests...")
    try:
        exit_code = test_database_methods()
        if exit_code != 0:
            all_passed = False
        results.append(("Database Methods Tests", exit_code == 0))
    except Exception as e:
        print(f"Error running database methods tests: {e}")
        all_passed = False
        results.append(("Database Methods Tests", False))

    # Run E2E user journey tests
    print("\nRunning E2E user journey tests...")
    try:
        exit_code = test_e2e_journeys()
        if exit_code != 0:
            all_passed = False
        results.append(("E2E User Journey Tests", exit_code == 0))
    except Exception as e:
        print(f"Error running E2E tests: {e}")
        all_passed = False
        results.append(("E2E User Journey Tests", False))

    # Run core operations tests
    print("\nRunning core operations tests...")
    try:
        exit_code = test_core_operations()
        if exit_code != 0:
            all_passed = False
        results.append(("Core Operations Tests", exit_code == 0))
    except Exception as e:
        print(f"Error running core operations tests: {e}")
        all_passed = False
        results.append(("Core Operations Tests", False))

    # Run CLI commands tests
    print("\nRunning CLI commands tests...")
    try:
        exit_code = test_cli_commands()
        if exit_code != 0:
            all_passed = False
        results.append(("CLI Commands Tests", exit_code == 0))
    except Exception as e:
        print(f"Error running CLI commands tests: {e}")
        all_passed = False
        results.append(("CLI Commands Tests", False))

    # Add more integration test suites here as needed
    # from docker_test_phase3 import main as test_phase3
    # etc.

    # Print summary
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    if all_passed:
        print("\n🎉 All integration tests passed!")
        return 0
    else:
        print("\n❌ Some integration tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

