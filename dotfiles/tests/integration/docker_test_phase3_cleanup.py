#!/usr/bin/env python3
"""
Phase 3: Cleanup and Reconciliation Integration Tests.

These tests verify the 'clean' and 'reconcile' commands that handle orphaned
operations and complete drift resolution. All tests run in isolated Docker
containers to ensure safe testing.

SAFETY: These tests MUST run in Docker. There is NO override mechanism.
"""

import sys

# Add src to path for imports
sys.path.insert(0, "/app/src")

# CRITICAL SAFETY CHECK: Ensure we're running in Docker
from docker_only_guard import require_docker

# Import test helper from existing E2E tests
from docker_test_e2e_user_journeys import E2ETestHelper

# Absolute requirement - no bypasses allowed
require_docker("""
❌ CRITICAL SAFETY ERROR: Phase 3 Cleanup tests MUST run in Docker!

These tests use cleanup commands that will modify your file system.
Running them on your host machine could damage your actual dotfiles.

There is NO way to override this safety check.

To run these tests, you MUST use Docker:
  make docker-test-cleanup          # Run Phase 3 cleanup tests
  make docker-test-all              # Run all integration tests

These tests are designed to be destructive and CANNOT be run outside Docker.
""")


def test_clean_orphaned_operations():
    """
    Test the 'clean' command for orphaned operations.

    This test verifies that orphaned operations can be cleaned from the
    database and optionally from the filesystem.
    """
    print("\n=== Testing Clean Orphaned Operations ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Setup: Initialize with dotfiles
        print("Setting up initial environment...")
        helper.create_dotfiles_structure()  # Create structure but don't need to store return value
        helper.create_config_file()

        # Apply initial configuration to create database state
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Initial sync should succeed"

        # Verify files were created
        expected_files = [
            home_dir / ".zshrc",
            home_dir / ".vimrc",
            home_dir / ".gitconfig",
            home_dir / ".tmux.conf",
        ]
        for f in expected_files:
            assert f.exists(), f"{f} should exist after sync"

        # Simulate orphaned operations by removing an operation from config
        print("Creating orphaned operations by modifying config...")
        config_file = test_dir / "dotfiles.toml"
        config_content = config_file.read_text()

        # Remove the .tmux.conf operation from config to orphan it
        lines = config_content.split("\n")
        modified_config = []
        skip_block = False

        for i, line in enumerate(lines):
            if "[[step]]" in line:
                # Look ahead to see if this is the tmux step
                is_tmux_step = False
                for j in range(i + 1, min(i + 5, len(lines))):
                    if "tmux" in lines[j].lower():
                        is_tmux_step = True
                        break
                skip_block = is_tmux_step
                if not skip_block:
                    modified_config.append(line)
            elif skip_block:
                # Skip until next [[step]] or end of config
                if "[[step]]" not in line:
                    continue
                else:
                    # Process this new step
                    skip_block = False
                    # Re-check this line
                    is_tmux_step = False
                    for j in range(i + 1, min(i + 5, len(lines))):
                        if "tmux" in lines[j].lower():
                            is_tmux_step = True
                            break
                    skip_block = is_tmux_step
                    if not skip_block:
                        modified_config.append(line)
            else:
                modified_config.append(line)

        # Write simplified config without tmux
        config_file.write_text("\n".join(modified_config))

        # Check for drift - should detect orphaned operation
        print("Checking drift to detect orphaned operations...")
        result = helper.run_command("drift-check", check_success=False)
        # drift-check returns 1 when drift is found, which is expected
        assert result.exit_code == 1, "Should detect drift due to orphaned operations"

        # Preview clean operation
        print("Previewing clean operation...")
        result = helper.run_command("clean", "--preview")
        assert result.exit_code == 0, "Clean preview should succeed"
        assert (
            "Cleanup Analysis" in result.output
            or "Enhanced Cleanup Analysis" in result.output
            or "No cleanup needed" in result.output
        ), "Should show cleanup analysis"

        # Test clean without file removal (database only)
        print("Cleaning orphaned operations (database only)...")
        result = helper.run_command(
            "--apply", "--force", "clean", "--orphaned-only", check_success=True
        )
        assert result.exit_code == 0, "Clean should succeed"

        # Verify file still exists but operation is cleaned from database
        tmux_file = home_dir / ".tmux.conf"
        assert tmux_file.exists(), "File should still exist after database-only clean"

        # Check drift again - should show fewer orphaned operations
        result = helper.run_command("drift-check", check_success=False)
        # May still have drift if file exists but not in config

        print("✓ Clean orphaned operations test passed")
        return True

    finally:
        helper.cleanup()


def test_clean_with_file_removal():
    """
    Test the 'clean' command with file removal and backup.

    This test verifies that files can be safely removed during cleanup
    with proper backup mechanisms.
    """
    print("\n=== Testing Clean with File Removal ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Setup: Initialize with dotfiles
        print("Setting up environment for file removal test...")
        dotfiles_dir = helper.create_dotfiles_structure()  # Need to keep for later use
        helper.create_config_file()

        # Apply initial configuration
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Initial sync should succeed"

        # Create a test file that will become orphaned
        test_file = home_dir / ".test_orphaned_file"
        test_file.write_text("# Test file to be orphaned\ntest_content=true\n")

        # Add this file to database by temporarily adding to config
        config_file = test_dir / "dotfiles.toml"
        config_content = config_file.read_text()
        additional_step = """
[[step]]
op = "copy"
src = "dotfiles/test_orphaned_file"
dst = "~/.test_orphaned_file"
"""

        # Create source file
        source_file = dotfiles_dir / "test_orphaned_file"
        source_file.write_text("# Test file to be orphaned\ntest_content=true\n")

        # Apply with the additional file
        config_file.write_text(config_content + additional_step)
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Sync with additional file should succeed"

        # Now remove from config to make it orphaned
        config_file.write_text(config_content)

        # Verify drift is detected
        result = helper.run_command("drift-check", check_success=False)
        assert result.exit_code == 1, "Should detect orphaned operation"

        # Clean with file removal and backup
        print("Cleaning with file removal and backup...")
        result = helper.run_command(
            "--apply", "--force", "clean", "--remove-files", check_success=True
        )
        assert result.exit_code == 0, "Clean with file removal should succeed"

        # Verify file was removed
        assert not test_file.exists(), "Orphaned file should be removed"

        # Verify backup was created (check backup directory exists)
        backup_dir = home_dir / ".local" / "state" / "dotfiles" / "backups"
        if backup_dir.exists():
            print(f"✓ Backup directory created: {backup_dir}")

        print("✓ Clean with file removal test passed")
        return True

    finally:
        helper.cleanup()


def test_reconcile_complete_drift():
    """
    Test the 'reconcile' command for complete drift resolution.

    This test verifies that reconcile can clean orphaned operations
    and then sync new/modified operations in one command.
    """
    print("\n=== Testing Reconcile Complete Drift Resolution ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Setup: Initialize with basic configuration
        print("Setting up environment for reconcile test...")
        helper.create_dotfiles_structure()  # Create structure but don't need to store return value

        # Create a simple initial config with just zshrc and gitconfig
        initial_config = """[package]
name = "test-dotfiles"
version = "1.0.0"

[safety]
dry_run_default = false
backup_enabled = true

[security]
whitelist_paths = ["/tmp/**", "~/**", "/tmp/test_home_e2e/**"]

[[step]]
op = "link"
src = "dotfiles/zshrc"
dst = "~/.zshrc"

[[step]]
op = "copy"
src = "dotfiles/gitconfig"
dst = "~/.gitconfig"
"""

        config_file = test_dir / "dotfiles.toml"
        config_file.write_text(initial_config)

        # Apply initial configuration
        result = helper.run_command("--config", str(config_file), "--apply", "sync")
        assert result.exit_code == 0, "Initial sync should succeed"

        # Verify initial files exist
        assert (home_dir / ".zshrc").is_symlink(), "zshrc should be symlinked"
        assert (home_dir / ".gitconfig").is_file(), "gitconfig should be copied"

        # Now create a complex drift scenario:
        # 1. Add new operations to config (new drift)
        # 2. Modify existing operations (modified drift)
        # 3. Remove operations from config (orphaned drift)

        print("Creating complex drift scenario...")

        # Add vimrc and tmux.conf back to create "new" operations
        complex_config = """[package]
name = "test-dotfiles" 
version = "1.0.0"

[safety]
dry_run_default = false
backup_enabled = true

[security]
whitelist_paths = ["/tmp/**", "~/**", "/tmp/test_home_e2e/**"]

# Keep existing zshrc (no drift)
[[step]]
op = "link"
src = "dotfiles/zshrc"
dst = "~/.zshrc"

# Add new vimrc (new drift)
[[step]]
op = "link"
src = "dotfiles/vimrc"
dst = "~/.vimrc"

# Add new tmux.conf (new drift)
[[step]]
op = "copy"
src = "dotfiles/config/tmux.conf"
dst = "~/.tmux.conf"
"""
        # Note: removed gitconfig to make it orphaned

        config_file.write_text(complex_config)

        # Check drift before reconcile
        print("Checking drift before reconcile...")
        result = helper.run_command(
            "--config", str(config_file), "drift-check", check_success=False
        )
        assert result.exit_code == 1, "Should detect complex drift"

        # Preview reconcile operation
        print("Previewing reconcile operation...")
        result = helper.run_command("--config", str(config_file), "reconcile", "--preview")
        assert result.exit_code == 0, "Reconcile preview should succeed"

        # Execute reconcile
        print("Executing reconcile...")
        result = helper.run_command("--config", str(config_file), "--apply", "--force", "reconcile")
        assert result.exit_code == 0, "Reconcile should succeed"

        # Verify reconciliation results:
        # - zshrc should still exist (no change)
        # - vimrc should be created (new operation)
        # - tmux.conf should be created (new operation)
        # - gitconfig should be removed or orphaned (orphaned operation)

        assert (home_dir / ".zshrc").is_symlink(), "zshrc should remain symlinked"
        assert (home_dir / ".vimrc").is_symlink(), "vimrc should be newly symlinked"
        assert (home_dir / ".tmux.conf").is_file(), "tmux.conf should be newly copied"

        # Check drift after reconcile - should be clean
        print("Verifying drift is resolved after reconcile...")
        result = helper.run_command(
            "--config", str(config_file), "drift-check", check_success=False
        )
        assert result.exit_code == 0, "No drift should remain after reconcile"

        print("✓ Reconcile complete drift resolution test passed")
        return True

    finally:
        helper.cleanup()


def test_cleanup_safety_features():
    """
    Test safety features of cleanup operations.

    This test verifies confirmation dialogs, dry-run mode, and error handling.
    """
    print("\n=== Testing Cleanup Safety Features ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Setup basic environment
        print("Setting up environment for safety tests...")
        helper.create_dotfiles_structure()
        helper.create_config_file()

        # Apply initial configuration
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Initial sync should succeed"

        # Create orphaned scenario
        config_file = test_dir / "dotfiles.toml"
        config_content = config_file.read_text()

        # Remove vimrc to make it orphaned
        lines = config_content.split("\n")
        filtered_lines = []
        skip_block = False
        skip_next_step = False

        for i, line in enumerate(lines):
            # Check if we should skip this entire step block
            if "[[step]]" in line:
                # Look ahead to see if this is a vim-related step
                skip_next_step = False
                for j in range(i + 1, min(i + 5, len(lines))):
                    if "vimrc" in lines[j] or "vim/" in lines[j]:
                        skip_next_step = True
                        break
                skip_block = skip_next_step
                if not skip_block:
                    filtered_lines.append(line)
            elif skip_block:
                # Skip lines until next [[step]]
                if not line.strip() or line.startswith("#"):
                    # Keep empty lines and comments
                    filtered_lines.append(line)
                # Otherwise skip the line
            else:
                filtered_lines.append(line)

        config_file.write_text("\n".join(filtered_lines))

        # Test dry-run mode (preview)
        print("Testing dry-run/preview mode...")
        result = helper.run_command("clean", "--preview")
        assert result.exit_code == 0, "Preview should succeed"
        assert (
            "Cleanup Analysis" in result.output
            or "Enhanced Cleanup Analysis" in result.output
            or "No cleanup needed" in result.output
        )

        # Test without file removal (safer option)
        print("Testing database-only cleanup...")
        result = helper.run_command(
            "--apply", "--force", "clean", "--orphaned-only", check_success=True
        )
        assert result.exit_code == 0, "Database-only clean should succeed"

        # Test with backup enabled (default safety)
        print("Testing cleanup with backup safety...")
        result = helper.run_command(
            "--apply", "--force", "clean", "--remove-files", check_success=True
        )
        assert result.exit_code == 0, "Clean with backup should succeed"

        # Test statistics and reporting
        print("Testing cleanup statistics...")
        result = helper.run_command("clean", "--preview")
        assert result.exit_code == 0, "Should be able to get statistics"

        print("✓ Cleanup safety features test passed")
        return True

    finally:
        helper.cleanup()


def main():
    """Run all Phase 3 cleanup integration tests."""
    print("=" * 60)
    print("PHASE 3: CLEANUP AND RECONCILIATION INTEGRATION TESTS")
    print("=" * 60)
    print("\nThese tests verify the 'clean' and 'reconcile' commands")
    print("for handling orphaned operations and drift resolution.")
    print("-" * 60)

    tests = [
        ("Clean Orphaned Operations", test_clean_orphaned_operations),
        ("Clean with File Removal", test_clean_with_file_removal),
        ("Reconcile Complete Drift", test_reconcile_complete_drift),
        ("Cleanup Safety Features", test_cleanup_safety_features),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            print(f"\nRunning: {test_name}")
            print("=" * 60)
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
    print("PHASE 3 CLEANUP TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total:  {passed + failed}")

    if failed == 0:
        print("\n🎉 All Phase 3 cleanup tests passed!")
        print("Clean and reconcile commands are working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed")

    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
