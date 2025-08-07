#!/usr/bin/env python3
"""
Integration tests for new verb implementations.

These tests are designed to run in Docker containers to ensure
safe testing without affecting the host system.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports first
sys.path.insert(0, '/app/src')

# Import modules we need
from dotfiles_sync.cli import cli  # noqa: E402
from click.testing import CliRunner  # noqa: E402

# SAFETY: Ensure we're running in Docker
from docker_only_guard import require_docker  # noqa: E402
require_docker()


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


def create_test_config_with_new_verbs(config_path: Path):
    """Create a test configuration with new verb operations."""
    config_content = """
[package]
name = "test-dotfiles"
version = "1.0.0"
author = "Test Author <test@example.com>"
description = "Integration test configuration for new verbs"

[safety]
dry_run_default = false
backup_before_modify = true
backup_retention_days = 7
verify_checksums = false
fail_on_error = false
max_operations = 100
require_confirmation = false

[security]
whitelist_paths = ["/tmp/**", "/tmp/test_home/**", "~/", "~/**"]
blacklist_paths = ["/etc", "/usr", "/System"]
secret_provider = "environment"
enable_command_whitelist = false
allowed_commands = []

# Test syncdir verb
[[step]]
op = "syncdir"
src = "test_source"
dst = "~/synced_dir"
description = "Test directory synchronization"
exclude = ["*.log", "*.tmp"]

# Test append verb
[[step]]
op = "append"
text = '''
# Added by dotfiles-sync
export TEST_VAR="appended"
'''
dst = "~/.bashrc"
marker = "DOTFILES_APPEND_TEST"
description = "Test appending to file"

# Test prepend verb
[[step]]
op = "prepend"
text = '''
# Prepended by dotfiles-sync
# This should appear at the top
'''
dst = "~/.profile"
marker = "DOTFILES_PREPEND_TEST"
description = "Test prepending to file"

# Test run verb
[[step]]
op = "run"
command = "echo 'Test command executed' > /tmp/run_test.txt"
description = "Test run command"

# Test run_once verb
[[step]]
op = "run_once"
command = "echo 'Run once test' > /tmp/run_once_test.txt"
checksum = "test_checksum_123"
description = "Test run_once command"

# Test append without marker (non-idempotent)
[[step]]
op = "append"
text = "alias ll='ls -la'\\n"
dst = "~/.aliases"
description = "Test simple append"

# Test syncdir with nested directories
[[step]]
op = "syncdir"
src = "nested_source"
dst = "~/nested_dest"
description = "Test nested directory sync"
"""
    
    config_path.write_text(config_content)
    
    # Create source directories and files for syncdir tests
    source_dir = config_path.parent / "test_source"
    source_dir.mkdir(exist_ok=True)
    (source_dir / "file1.txt").write_text("Content of file 1")
    (source_dir / "file2.conf").write_text("Config file content")
    (source_dir / "debug.log").write_text("Should be excluded")
    (source_dir / "temp.tmp").write_text("Should also be excluded")
    
    # Create nested source directory
    nested_dir = config_path.parent / "nested_source"
    nested_dir.mkdir(exist_ok=True)
    (nested_dir / "level1").mkdir(exist_ok=True)
    (nested_dir / "level1" / "file.txt").write_text("Nested file")
    (nested_dir / "level1" / "level2").mkdir(exist_ok=True)
    (nested_dir / "level1" / "level2" / "deep.txt").write_text("Deep nested file")


def test_syncdir_verb():
    """Test syncdir verb functionality."""
    print("\n=== Testing syncdir verb ===")
    
    test_dir, home_dir = setup_test_environment()
    config_path = test_dir / "config.toml"
    create_test_config_with_new_verbs(config_path)
    
    runner = CliRunner()
    
    # Run sync with new config
    result = runner.invoke(cli, [
        '--config', str(config_path),
        '--apply',
        'sync'
    ])
    
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output}")
    
    # Verify syncdir worked
    synced_dir = home_dir / "synced_dir"
    assert synced_dir.exists(), "Synced directory should exist"
    assert (synced_dir / "file1.txt").exists(), "file1.txt should be synced"
    assert (synced_dir / "file2.conf").exists(), "file2.conf should be synced"
    assert not (synced_dir / "debug.log").exists(), "*.log files should be excluded"
    assert not (synced_dir / "temp.tmp").exists(), "*.tmp files should be excluded"
    
    # Verify nested sync
    nested_dest = home_dir / "nested_dest"
    assert nested_dest.exists(), "Nested destination should exist"
    assert (nested_dest / "level1" / "file.txt").exists(), "Nested file should exist"
    assert (nested_dest / "level1" / "level2" / "deep.txt").exists(), "Deep nested file should exist"
    
    print("✓ Syncdir verb test passed")
    return True


def test_append_prepend_verbs():
    """Test append and prepend verb functionality."""
    print("\n=== Testing append and prepend verbs ===")
    
    test_dir, home_dir = setup_test_environment()
    config_path = test_dir / "config.toml"
    create_test_config_with_new_verbs(config_path)
    
    # Create existing files to append/prepend to
    bashrc = home_dir / ".bashrc"
    bashrc.write_text("# Original bashrc content\nexport PATH=/usr/local/bin:$PATH\n")
    
    runner = CliRunner()
    
    # Run sync
    result = runner.invoke(cli, [
        '--config', str(config_path),
        '--apply',
        'sync'
    ])
    
    print(f"Exit code: {result.exit_code}")
    
    # Verify append worked
    bashrc_content = bashrc.read_text()
    assert "DOTFILES_APPEND_TEST" in bashrc_content, "Marker should be in appended file"
    assert 'export TEST_VAR="appended"' in bashrc_content, "Appended content should be present"
    assert bashrc_content.index("Original bashrc") < bashrc_content.index("TEST_VAR"), "Append should be after original"
    
    # Verify prepend worked
    profile = home_dir / ".profile"
    assert profile.exists(), "Profile should be created"
    profile_content = profile.read_text()
    assert "DOTFILES_PREPEND_TEST" in profile_content, "Marker should be in prepended file"
    assert "Prepended by dotfiles-sync" in profile_content, "Prepended content should be present"
    assert profile_content.startswith("# DOTFILES_PREPEND_TEST"), "Prepend should be at the beginning"
    
    # Verify simple append
    aliases = home_dir / ".aliases"
    assert aliases.exists(), "Aliases file should be created"
    assert "alias ll='ls -la'" in aliases.read_text(), "Simple append should work"
    
    # Test idempotency - run again
    runner.invoke(cli, [
        '--config', str(config_path),
        '--apply',
        'sync'
    ])
    
    # Files with markers shouldn't be modified again
    bashrc_content2 = bashrc.read_text()
    assert bashrc_content2.count("DOTFILES_APPEND_TEST") == 1, "Marker should appear only once (idempotent)"
    
    print("✓ Append and prepend verbs test passed")
    return True


def test_run_verbs():
    """Test run and run_once verb functionality."""
    print("\n=== Testing run and run_once verbs ===")
    
    test_dir, home_dir = setup_test_environment()
    config_path = test_dir / "config.toml"
    create_test_config_with_new_verbs(config_path)
    
    runner = CliRunner()
    
    # First run
    result = runner.invoke(cli, [
        '--config', str(config_path),
        '--apply',
        'sync'
    ])
    
    print(f"Exit code: {result.exit_code}")
    
    # Verify run command executed
    run_test_file = Path("/tmp/run_test.txt")
    assert run_test_file.exists(), "Run command should create test file"
    assert "Test command executed" in run_test_file.read_text(), "Run command output should be correct"
    
    # Verify run_once command executed
    run_once_file = Path("/tmp/run_once_test.txt")
    assert run_once_file.exists(), "Run_once command should create test file"
    assert "Run once test" in run_once_file.read_text(), "Run_once command output should be correct"
    
    # Delete files created by run command
    run_test_file.unlink()
    run_once_file.unlink()
    
    # Second run - test idempotency
    result2 = runner.invoke(cli, [
        '--config', str(config_path),
        '--apply',
        'sync'
    ])
    
    # Run command should execute again
    assert run_test_file.exists(), "Run command should execute again"
    
    # Run_once command should NOT execute again (should be skipped)
    assert not run_once_file.exists(), "Run_once command should not execute again"
    
    # Check that run_once was skipped in the output
    assert "skipping" in result2.output.lower() or "already executed" in result2.output.lower(), \
        "Run_once should indicate it was skipped"
    
    print("✓ Run and run_once verbs test passed")
    return True


def test_dry_run_mode():
    """Test that dry run mode doesn't actually execute new verbs."""
    print("\n=== Testing dry run mode with new verbs ===")
    
    # Clean up any existing test directories to ensure clean test
    import shutil
    if Path("/tmp/test_home").exists():
        shutil.rmtree("/tmp/test_home")
    if Path("/tmp/dotfiles_test").exists():
        shutil.rmtree("/tmp/dotfiles_test")
    # Clean up test files from previous runs
    if Path("/tmp/run_test.txt").exists():
        Path("/tmp/run_test.txt").unlink()
    if Path("/tmp/run_once_test.txt").exists():
        Path("/tmp/run_once_test.txt").unlink()
    
    test_dir, home_dir = setup_test_environment()
    config_path = test_dir / "config.toml"
    create_test_config_with_new_verbs(config_path)
    
    runner = CliRunner()
    
    # Run in dry-run mode (default)
    result = runner.invoke(cli, [
        '--config', str(config_path),
        'sync'
    ])
    
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output}")
    
    # Verify nothing was actually created/modified
    assert not (home_dir / "synced_dir").exists(), "Syncdir should not create in dry run"
    assert not (home_dir / ".bashrc").exists(), "Append should not create files in dry run"
    assert not (home_dir / ".profile").exists(), "Prepend should not create files in dry run"
    assert not Path("/tmp/run_test.txt").exists(), "Run command should not execute in dry run"
    assert not Path("/tmp/run_once_test.txt").exists(), "Run_once command should not execute in dry run"
    
    # Output should indicate dry run
    assert "dry" in result.output.lower() or "would" in result.output.lower(), \
        "Output should indicate dry run mode"
    
    print("✓ Dry run mode test passed")
    return True


def test_error_handling():
    """Test error handling for new verbs."""
    print("\n=== Testing error handling ===")
    
    test_dir, home_dir = setup_test_environment()
    
    # Create config with invalid operations
    config_content = """
[package]
name = "test-error"
version = "1.0.0"

[safety]
dry_run_default = false
require_confirmation = false

# Invalid syncdir - source doesn't exist
[[step]]
op = "syncdir"
src = "/nonexistent/source"
dst = "~/test"

# Invalid append - no text provided
[[step]]
op = "append"
dst = "~/test.txt"

# Invalid run - command will fail
[[step]]
op = "run"
command = "false"  # This command always returns non-zero
"""
    
    config_path = test_dir / "error_config.toml"
    config_path.write_text(config_content)
    
    runner = CliRunner()
    
    # This should handle errors gracefully
    result = runner.invoke(cli, [
        '--config', str(config_path),
        '--apply',
        'sync'
    ])
    
    # Should complete but report errors
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.output}")
    
    # Check that errors were reported
    assert "error" in result.output.lower() or "fail" in result.output.lower(), \
        "Errors should be reported in output"
    
    print("✓ Error handling test passed")
    return True


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("INTEGRATION TESTS FOR NEW VERBS")
    print("=" * 60)
    
    tests = [
        ("Syncdir Verb", test_syncdir_verb),
        ("Append/Prepend Verbs", test_append_prepend_verbs),
        ("Run/RunOnce Verbs", test_run_verbs),
        ("Dry Run Mode", test_dry_run_mode),
        ("Error Handling", test_error_handling),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_name} passed")
            else:
                failed += 1
                print(f"✗ {test_name} failed")
        except Exception as e:
            failed += 1
            print(f"✗ {test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())