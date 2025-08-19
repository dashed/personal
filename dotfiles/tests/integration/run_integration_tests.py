#!/usr/bin/env python3
"""
Main runner for all integration tests.

This script ensures all integration tests run only in Docker
and provides a central entry point for Docker-based testing.
Supports pattern-based test filtering similar to pytest.
"""

import sys
import argparse
import fnmatch
import importlib
import importlib.util
from pathlib import Path
from typing import List, Dict, Tuple

# Add integration directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import and run Docker safety check
from docker_only_guard import require_docker

require_docker()


def discover_test_modules() -> Dict[str, str]:
    """
    Discover all available integration test modules.

    Returns:
        Dict mapping test names to their descriptions
    """
    test_dir = Path(__file__).parent
    test_modules = {}

    for test_file in test_dir.glob("docker_test_*.py"):
        module_name = test_file.stem

        # Try to get description from module docstring
        try:
            spec = importlib.util.spec_from_file_location(module_name, test_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get description from docstring
            description = "Integration test"
            if module.__doc__:
                first_line = module.__doc__.strip().split("\n")[0]
                if first_line and not first_line.startswith('"""'):
                    description = first_line

            test_modules[module_name] = description
        except Exception:
            test_modules[module_name] = "Integration test (description unavailable)"

    return test_modules


def filter_tests_by_patterns(all_tests: Dict[str, str], patterns: List[str]) -> List[str]:
    """
    Filter test modules by glob patterns.

    Args:
        all_tests: Dict of all available tests {name: description}
        patterns: List of glob patterns to match against

    Returns:
        List of test module names that match the patterns
    """
    if not patterns:
        return list(all_tests.keys())

    matched_tests = set()
    exclude_patterns = []
    include_patterns = []

    # Separate include and exclude patterns
    for pattern in patterns:
        if pattern.startswith("-") or pattern.startswith("!"):
            exclude_patterns.append(pattern[1:])
        else:
            include_patterns.append(pattern)

    # If no include patterns, start with all tests
    if not include_patterns:
        matched_tests = set(all_tests.keys())
    else:
        # Match include patterns
        for pattern in include_patterns:
            for test_name in all_tests.keys():
                if fnmatch.fnmatch(test_name, pattern):
                    matched_tests.add(test_name)

    # Remove tests matching exclude patterns
    for pattern in exclude_patterns:
        matched_tests = {test for test in matched_tests if not fnmatch.fnmatch(test, pattern)}

    return list(matched_tests)


def import_and_run_test(module_name: str) -> Tuple[bool, Exception]:
    """
    Import a test module and run its main function.

    Args:
        module_name: Name of the test module to import

    Returns:
        Tuple of (success: bool, exception: Exception or None)
    """
    try:
        # Dynamic import
        module = importlib.import_module(module_name)

        # Run the main function
        if hasattr(module, "main"):
            exit_code = module.main()
            return exit_code == 0, None
        else:
            print(f"Warning: {module_name} has no main() function")
            return False, Exception(f"No main() function in {module_name}")

    except Exception as e:
        return False, e


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run integration tests with pattern matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run all tests
  %(prog)s '*safety*'                # Run safety-related tests
  %(prog)s '*core*' '*cli*'          # Run core and CLI tests  
  %(prog)s '*' -'*backup*'           # Run all tests except backup tests
  %(prog)s --list                    # List available tests
  %(prog)s --dry-run '*safety*'      # Show what tests would run

Pattern syntax:
  *          - Match any characters
  ?          - Match single character  
  [abc]      - Match any character in brackets
  -pattern   - Exclude pattern (prefix with - or !)
  
Test naming:
  docker_test_safety_features    -> matches '*safety*', '*features*'
  docker_test_core_operations    -> matches '*core*', '*operations*' 
  docker_test_cli_commands       -> matches '*cli*', '*commands*'
        """,
    )

    parser.add_argument(
        "patterns", nargs="*", help="Glob patterns to match test names (default: run all tests)"
    )

    parser.add_argument("--list", "-l", action="store_true", help="List available tests and exit")

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show which tests would run without executing them",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    return parser.parse_args()


def main():
    """Run integration tests with optional pattern matching."""
    args = parse_arguments()

    # Discover all available test modules
    all_tests = discover_test_modules()

    if args.list:
        print("=" * 60)
        print("AVAILABLE INTEGRATION TESTS")
        print("=" * 60)
        for name, description in sorted(all_tests.items()):
            print(f"  {name:<30} - {description}")
        print(f"\nTotal: {len(all_tests)} test modules")
        return 0

    # Filter tests by patterns
    selected_tests = filter_tests_by_patterns(all_tests, args.patterns)

    if not selected_tests:
        print("❌ No tests match the specified patterns")
        if args.patterns:
            print(f"Patterns: {args.patterns}")
        print("Use --list to see available tests")
        return 1

    # Sort tests for consistent execution order
    selected_tests.sort()

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN - TESTS THAT WOULD BE EXECUTED")
        print("=" * 60)
        for test_name in selected_tests:
            description = all_tests.get(test_name, "Unknown test")
            print(f"  {test_name:<30} - {description}")
        print(f"\nTotal: {len(selected_tests)} test(s) would run")
        return 0

    # Run selected tests
    print("=" * 60)
    print("RUNNING INTEGRATION TESTS IN DOCKER")
    if args.patterns:
        print(f"Patterns: {' '.join(args.patterns)}")
    print("=" * 60)
    print(f"Selected tests: {len(selected_tests)}/{len(all_tests)}")
    print()

    # Track results
    all_passed = True
    results = []

    for i, test_name in enumerate(selected_tests, 1):
        description = all_tests.get(test_name, "Unknown test")
        print(f"[{i}/{len(selected_tests)}] Running {test_name}...")
        if args.verbose:
            print(f"  Description: {description}")

        success, error = import_and_run_test(test_name)

        if success:
            results.append((test_name, True, None))
            print(f"✅ {test_name} PASSED")
        else:
            all_passed = False
            results.append((test_name, False, error))
            print(f"❌ {test_name} FAILED")
            if args.verbose and error:
                print(f"  Error: {error}")

        print()  # Empty line between tests

    # Print summary
    print("=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for _, passed, _ in results if passed)
    failed_count = len(results) - passed_count

    for test_name, passed, error in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:<35} {status}")
        if not passed and error and args.verbose:
            print(f"    Error: {str(error)[:80]}...")

    print(f"\nResults: {passed_count} passed, {failed_count} failed")

    if all_passed:
        print("🎉 All selected tests passed!")
        return 0
    else:
        print("❌ Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
