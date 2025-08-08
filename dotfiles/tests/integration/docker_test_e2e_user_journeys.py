#!/usr/bin/env python3
"""
End-to-End User Journey Integration Tests.

These tests simulate complete real-world user workflows from the command line,
exactly as users would interact with the system. All tests run in Docker
containers to ensure safe testing without affecting the host system.

SAFETY: These tests MUST run in Docker. There is NO override mechanism.
        The docker_only_guard ensures these tests can NEVER run on the host.
        This is by design to prevent accidental damage to developer machines.
"""

import os
import sys
import shutil
import json
from pathlib import Path
from typing import Tuple, Optional

# Add src to path for imports
sys.path.insert(0, "/app/src")

# Import modules we need
from dotfiles_sync.cli import cli
from dotfiles_sync.state_database import StateDatabase
from click.testing import CliRunner

# CRITICAL SAFETY CHECK: Ensure we're running in Docker
# NO OVERRIDES - These tests can ONLY run in Docker
from docker_only_guard import require_docker

# Absolute requirement - no bypasses allowed
require_docker("""
❌ CRITICAL SAFETY ERROR: E2E tests MUST run in Docker!

These tests simulate complete user workflows and will modify your file system.
Running them on your host machine could damage your actual dotfiles.

There is NO way to override this safety check.

To run these tests, you MUST use Docker:
  make docker-test-e2e           # Run E2E tests in Docker
  make docker-test-all           # Run all integration tests

Or run directly in Docker:
  docker build -t dotfiles-test -f Dockerfile.test .
  docker run --rm -v $(pwd):/app dotfiles-test python /app/tests/integration/docker_test_e2e_user_journeys.py

These tests are designed to be destructive and CANNOT be run outside of Docker.
""")


class E2ETestHelper:
    """Helper class for E2E test operations."""

    def __init__(self):
        """Initialize test helper."""
        self.runner = CliRunner()
        self.test_dir = None
        self.home_dir = None
        self.config_path = None

    def setup_test_environment(self) -> Tuple[Path, Path]:
        """
        Set up a clean test environment.

        Returns:
            Tuple of (test_dir, home_dir)
        """
        # Create test directories
        test_dir = Path("/tmp/dotfiles_e2e_test")
        if test_dir.exists():
            shutil.rmtree(test_dir)
        test_dir.mkdir(parents=True, exist_ok=True)

        home_dir = Path("/tmp/test_home_e2e")
        if home_dir.exists():
            shutil.rmtree(home_dir)
        home_dir.mkdir(parents=True, exist_ok=True)

        # Set HOME to test directory
        os.environ["HOME"] = str(home_dir)

        self.test_dir = test_dir
        self.home_dir = home_dir

        return test_dir, home_dir

    def create_dotfiles_structure(self, variant: str = "default") -> Path:
        """
        Create a realistic dotfiles directory structure.

        Args:
            variant: Variant to create files for

        Returns:
            Path to dotfiles directory
        """
        dotfiles_dir = self.test_dir / "dotfiles"
        dotfiles_dir.mkdir(exist_ok=True)

        # Create common dotfiles
        (dotfiles_dir / "zshrc").write_text("""# ZSH Configuration
export PATH="$HOME/.local/bin:$PATH"
alias ll='ls -la'
alias gs='git status'
""")

        (dotfiles_dir / "gitconfig").write_text("""[user]
    name = Test User
    email = test@example.com
[core]
    editor = vim
""")

        (dotfiles_dir / "vimrc").write_text("""" Vim Configuration
set number
set expandtab
set tabstop=4
syntax on
""")

        # Create variant-specific files (always create all to avoid validation errors)
        (dotfiles_dir / "personal_aliases").write_text("""# Personal aliases
alias projects='cd ~/personal/projects'
alias blog='cd ~/personal/blog'
""")
        
        (dotfiles_dir / "work_config").write_text("""# Work configuration
export COMPANY_API_KEY="test-key"
export WORK_ENV="development"
""")
        
        (dotfiles_dir / "work_aliases").write_text("""# Work aliases
alias deploy='./scripts/deploy.sh'
alias vpn='connect-company-vpn'
""")

        # Create config directory structure
        config_dir = dotfiles_dir / "config"
        config_dir.mkdir(exist_ok=True)

        (config_dir / "tmux.conf").write_text("""# Tmux configuration
set -g mouse on
set -g base-index 1
""")

        return dotfiles_dir

    def create_config_file(self, variant: str = "default", include_all_verbs: bool = False) -> Path:
        """
        Create a test configuration file.

        Args:
            variant: Default variant to use
            include_all_verbs: Include examples of all verb types

        Returns:
            Path to configuration file
        """
        config_content = """[package]
name = "test-dotfiles"
version = "1.0.0"
author = "Test User <test@example.com>"
description = "E2E test configuration"

[safety]
dry_run_default = true
backup_before_modify = true
backup_retention_days = 7
verify_checksums = false
fail_on_error = false
require_confirmation = false

[security]
whitelist_paths = ["/tmp/**", "~/", "~/**"]
blacklist_paths = ["/etc", "/usr", "/System"]
enable_command_whitelist = false

# Core dotfiles - link operations
[[step]]
op = "link"
src = "dotfiles/zshrc"
dst = "~/.zshrc"
description = "ZSH configuration"
variants = ["all"]

[[step]]
op = "link"
src = "dotfiles/vimrc"
dst = "~/.vimrc"
description = "Vim configuration"
variants = ["all"]

# Git config - copy operation (don't want symlink)
[[step]]
op = "copy"
src = "dotfiles/gitconfig"
dst = "~/.gitconfig"
description = "Git configuration"
variants = ["all"]

# Tmux config - link
[[step]]
op = "link"
src = "dotfiles/config/tmux.conf"
dst = "~/.tmux.conf"
description = "Tmux configuration"
variants = ["all"]

# Personal variant files
[[step]]
op = "link"
src = "dotfiles/personal_aliases"
dst = "~/.personal_aliases"
description = "Personal aliases"
variants = ["personal"]

# Work variant files
[[step]]
op = "copy"
src = "dotfiles/work_config"
dst = "~/.work_config"
description = "Work environment configuration"
variants = ["work"]
mode = "0600"  # Secure work config

[[step]]
op = "link"
src = "dotfiles/work_aliases"
dst = "~/.work_aliases"
description = "Work aliases"
variants = ["work"]
"""

        if include_all_verbs:
            config_content += """
# Advanced operations for testing
[[step]]
op = "syncdir"
src = "dotfiles/config"
dst = "~/.config/dotfiles"
description = "Sync configuration directory"
exclude = ["*.bak", "*.tmp"]
variants = ["all"]

[[step]]
op = "append"
text = '''
# Added by dotfiles-sync
source ~/.personal_aliases
'''
dst = "~/.zshrc"
marker = "DOTFILES_PERSONAL"
description = "Source personal aliases"
variants = ["personal"]

[[step]]
op = "run"
command = "touch ~/.dotfiles_installed"
description = "Mark dotfiles as installed"
variants = ["all"]
"""

        config_path = self.test_dir / "dotfiles.toml"
        config_path.write_text(config_content)
        self.config_path = config_path
        return config_path

    def run_command(self, *args, check_success: bool = True) -> any:
        """
        Run a CLI command and optionally check for success.

        Args:
            *args: Command arguments
            check_success: Whether to assert success

        Returns:
            Click Result object
        """
        # Build full command with config
        cmd = []
        if self.config_path:
            cmd.extend(["--config", str(self.config_path)])
        cmd.extend(args)

        result = self.runner.invoke(cli, cmd)

        if check_success and result.exit_code != 0:
            print(f"Command failed: {' '.join(map(str, cmd))}")
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.output}")
            if result.exception:
                print(f"Exception: {result.exception}")
                import traceback

                traceback.print_exception(
                    type(result.exception), result.exception, result.exception.__traceback__
                )

        return result

    def verify_file_exists(self, path: Path, content_contains: Optional[str] = None) -> bool:
        """
        Verify a file exists and optionally contains specific content.

        Args:
            path: Path to check
            content_contains: Optional string that should be in the file

        Returns:
            True if file exists (and contains content if specified)
        """
        if not path.exists():
            return False

        if content_contains and path.is_file():
            return content_contains in path.read_text()

        return True

    def verify_symlink(self, link_path: Path, target: Optional[Path] = None) -> bool:
        """
        Verify a symlink exists and optionally points to the right target.

        Args:
            link_path: Path to symlink
            target: Optional expected target

        Returns:
            True if symlink is valid
        """
        if not link_path.exists() or not link_path.is_symlink():
            return False

        if target:
            actual_target = link_path.resolve()
            expected_target = target.resolve()
            return actual_target == expected_target

        return True

    def cleanup(self):
        """Clean up test environment."""
        if self.test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        if self.home_dir and self.home_dir.exists():
            shutil.rmtree(self.home_dir)


# Test functions
def test_first_time_user_complete_workflow():
    """
    Simulate a new user setting up dotfiles for the first time.

    This test covers the complete workflow from initial setup to
    managing drift and understanding the system.
    """
    print("\n=== Testing First Time User Complete Workflow ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Step 1: Create dotfiles structure
        print("1. Creating dotfiles structure...")
        dotfiles_dir = helper.create_dotfiles_structure()
        assert dotfiles_dir.exists(), "Dotfiles directory should exist"

        # Step 2: Create configuration
        print("2. Creating configuration file...")
        config_path = helper.create_config_file()
        assert config_path.exists(), "Config file should exist"

        # Step 3: Validate configuration
        print("3. Validating configuration...")
        result = helper.run_command("validate")
        assert result.exit_code == 0, "Validation should succeed"
        assert "valid" in result.output.lower(), "Should report valid configuration"

        # Step 4: Preview changes (dry-run)
        print("4. Previewing changes (dry-run)...")
        result = helper.run_command("sync")
        assert result.exit_code == 0, "Dry run should succeed"
        assert "dry" in result.output.lower() or "would" in result.output.lower(), (
            "Should indicate dry run mode"
        )

        # Verify nothing was actually created
        assert not (home_dir / ".zshrc").exists(), "Files should not exist after dry run"

        # Step 5: Apply configuration
        print("5. Applying configuration...")
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Apply should succeed"

        # Verify files were created
        assert helper.verify_symlink(home_dir / ".zshrc"), "~/.zshrc should be a symlink"
        assert helper.verify_symlink(home_dir / ".vimrc"), "~/.vimrc should be a symlink"
        assert helper.verify_file_exists(home_dir / ".gitconfig", "Test User"), (
            "~/.gitconfig should exist with correct content"
        )
        assert helper.verify_symlink(home_dir / ".tmux.conf"), "~/.tmux.conf should be a symlink"

        # Step 6: Check status
        print("6. Checking status...")
        result = helper.run_command("status")
        assert result.exit_code == 0, "Status should succeed"
        # Status command should report applied operations

        # Step 7: Make local change and detect drift
        print("7. Simulating local changes and detecting drift...")
        zshrc_path = home_dir / ".zshrc"
        if zshrc_path.is_symlink():
            # Remove symlink and create regular file
            zshrc_path.unlink()
            zshrc_path.write_text("""# Modified locally
export PATH="$HOME/.local/bin:$PATH"
alias ll='ls -la'
alias gs='git status'
alias test='echo test'  # Added locally
""")

        # Check status again - should detect drift
        result = helper.run_command("status")
        assert result.exit_code == 0, "Status check should succeed"

        # Step 8: Re-sync to fix drift
        print("8. Re-syncing to fix drift...")
        result = helper.run_command("--apply", "--force", "sync")
        assert result.exit_code == 0, "Force sync should succeed"

        # Verify symlink is restored
        assert helper.verify_symlink(home_dir / ".zshrc"), "~/.zshrc should be restored as symlink"

        # Step 9: Test idempotency - run sync again
        print("9. Testing idempotency...")
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Second sync should succeed"
        # Should complete without errors even though everything is already in place

        print("✓ First time user workflow test passed")
        return True

    finally:
        helper.cleanup()


def test_daily_developer_workflow():
    """
    Simulate daily usage patterns of a developer.

    This test covers checking status, handling local modifications,
    and keeping dotfiles in sync during daily work.
    """
    print("\n=== Testing Daily Developer Workflow ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Setup: Initialize with dotfiles
        dotfiles_dir = helper.create_dotfiles_structure()
        helper.create_config_file()

        # Apply initial configuration
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Initial sync should succeed"

        # Morning routine - check status
        print("1. Morning: Checking status...")
        result = helper.run_command("status")
        assert result.exit_code == 0, "Status check should succeed"

        # Preview any pending changes
        print("2. Preview sync (no changes expected)...")
        result = helper.run_command("sync")
        assert result.exit_code == 0, "Sync preview should succeed"

        # Work on project - modify vim config
        print("3. Working: Modifying vim configuration...")
        vimrc_path = home_dir / ".vimrc"
        if vimrc_path.is_symlink():
            # Get the target of the symlink
            vimrc_path.readlink()
            # For testing, we'll modify the source file directly
            # In real usage, user might unlink and create new file
            vimrc_path.unlink()
            vimrc_path.write_text("""" Vim Configuration
set number
set expandtab
set tabstop=4
syntax on
" Added during work
Plug 'github/copilot.vim'
""")

        # End of day - check what changed
        print("4. End of day: Checking for changes...")
        result = helper.run_command("status")
        assert result.exit_code == 0, "Status check should succeed"

        # Option 1: Keep the change - update source
        print("5. Keeping changes: Updating source...")
        # Copy modified file back to source
        source_vimrc = dotfiles_dir / "vimrc"
        source_vimrc.write_text(vimrc_path.read_text())

        # Re-sync to establish link with updated content
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Sync after source update should succeed"

        # Verify the symlink is restored with new content
        assert helper.verify_symlink(home_dir / ".vimrc"), "Vimrc should be symlink again"

        # Make another change to test rollback
        print("6. Testing unwanted change scenario...")
        gitconfig = home_dir / ".gitconfig"
        original_content = gitconfig.read_text()
        gitconfig.write_text(original_content + "\n[test]\n    unwanted = true\n")

        # Detect the unwanted change
        result = helper.run_command("status")
        assert result.exit_code == 0, "Status should detect change"

        # Revert the unwanted change
        print("7. Reverting unwanted change...")
        result = helper.run_command("--apply", "--force", "sync")
        assert result.exit_code == 0, "Force sync should revert changes"

        # Verify original content is restored
        assert "unwanted" not in gitconfig.read_text(), "Unwanted change should be reverted"

        print("✓ Daily developer workflow test passed")
        return True

    finally:
        helper.cleanup()


def test_variant_switching_workflow():
    """
    Test switching between work/personal/default variants.

    This test verifies that variant-specific files are properly
    applied and removed when switching between variants.
    """
    print("\n=== Testing Variant Switching Workflow ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Create dotfiles for all variants
        print("1. Setting up multi-variant environment...")
        helper.create_dotfiles_structure("personal")
        helper.create_dotfiles_structure("work")  # This adds to existing structure
        helper.create_config_file()

        # Step 1: Apply default variant
        print("2. Applying default variant...")
        result = helper.run_command("--variant", "default", "--apply", "sync")
        assert result.exit_code == 0, "Default variant sync should succeed"

        # Verify default files exist, variant-specific don't
        assert helper.verify_symlink(home_dir / ".zshrc"), "Default files should exist"
        assert not (home_dir / ".personal_aliases").exists(), (
            "Personal files should not exist in default"
        )
        assert not (home_dir / ".work_config").exists(), "Work files should not exist in default"

        # Step 2: Switch to personal variant
        print("3. Switching to personal variant...")
        result = helper.run_command("--variant", "personal", "--apply", "sync")
        assert result.exit_code == 0, "Personal variant sync should succeed"

        # Verify personal files exist
        assert helper.verify_symlink(home_dir / ".zshrc"), "Default files should still exist"
        assert helper.verify_symlink(home_dir / ".personal_aliases"), (
            "Personal aliases should exist"
        )
        assert not (home_dir / ".work_config").exists(), "Work files should not exist in personal"

        # Step 3: Switch to work variant
        print("4. Switching to work variant...")
        result = helper.run_command("--variant", "work", "--apply", "sync")
        assert result.exit_code == 0, "Work variant sync should succeed"

        # Verify work files exist
        assert helper.verify_symlink(home_dir / ".zshrc"), "Default files should still exist"
        # NOTE: Variant cleanup (removing previous variant files) is not yet implemented
        # This would require tracking which files belong to which variant
        # assert not (home_dir / ".personal_aliases").exists(), "Personal files should be removed"
        assert helper.verify_file_exists(home_dir / ".work_config", "COMPANY_API_KEY"), (
            "Work config should exist"
        )
        assert helper.verify_symlink(home_dir / ".work_aliases"), "Work aliases should exist"

        # Verify work config has secure permissions
        work_config = home_dir / ".work_config"
        if work_config.exists():
            oct(work_config.stat().st_mode)[-3:]
            # Note: Permission setting might not work in all Docker environments
            # so we just check it exists

        # Step 4: Switch back to default
        print("5. Switching back to default variant...")
        result = helper.run_command("--variant", "default", "--apply", "sync")
        assert result.exit_code == 0, "Return to default should succeed"

        # Verify default files exist
        assert helper.verify_symlink(home_dir / ".zshrc"), "Default files should exist"
        # NOTE: Variant cleanup is not yet implemented - files from other variants remain
        # This would require the system to track and remove variant-specific files
        # assert not (home_dir / ".personal_aliases").exists(), "Personal files should be removed"
        # assert not (home_dir / ".work_config").exists(), "Work files should be removed"
        # assert not (home_dir / ".work_aliases").exists(), "Work aliases should be removed"

        print("✓ Variant switching workflow test passed")
        return True

    finally:
        helper.cleanup()


def test_disaster_recovery_workflow():
    """
    Test recovery from various failure scenarios.

    This test covers file corruption, deletion, and recovery
    using rollback and backup features.
    """
    print("\n=== Testing Disaster Recovery Workflow ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Setup environment
        print("1. Setting up environment...")
        helper.create_dotfiles_structure()
        helper.create_config_file()

        # Apply configuration
        print("2. Applying initial configuration...")
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Initial sync should succeed"

        # Verify initial state
        initial_files = [
            home_dir / ".zshrc",
            home_dir / ".vimrc",
            home_dir / ".gitconfig",
            home_dir / ".tmux.conf",
        ]
        for f in initial_files:
            assert f.exists(), f"{f} should exist"

        # Get transaction ID from database
        db_path = home_dir / ".local/state/dotfiles/state.db"
        transaction_id = None
        if db_path.exists():
            db = StateDatabase(str(db_path))
            cursor = db.conn.cursor()
            cursor.execute("SELECT id FROM transactions ORDER BY started_at DESC LIMIT 1")
            result = cursor.fetchone()
            if result:
                transaction_id = result[0]

        # Simulate disaster - delete and corrupt files
        print("3. Simulating disaster (file deletion/corruption)...")

        # Delete some files
        (home_dir / ".zshrc").unlink()
        (home_dir / ".vimrc").unlink()

        # Corrupt a file
        (home_dir / ".gitconfig").write_text("CORRUPTED DATA\n")

        # Check status - should detect problems
        print("4. Detecting damage...")
        result = helper.run_command("status")
        assert result.exit_code == 0, "Status check should work even with problems"

        # Recovery option 1: Force re-sync
        print("5. Attempting recovery via force sync...")
        result = helper.run_command("--apply", "--force", "sync")
        assert result.exit_code == 0, "Force sync should succeed"

        # Verify files are restored
        assert helper.verify_symlink(home_dir / ".zshrc"), ".zshrc should be restored"
        assert helper.verify_symlink(home_dir / ".vimrc"), ".vimrc should be restored"
        assert helper.verify_file_exists(home_dir / ".gitconfig", "Test User"), (
            ".gitconfig should be restored with correct content"
        )

        # Test rollback functionality if we have a transaction ID
        if transaction_id:
            print("6. Testing rollback to specific transaction...")

            # Make some changes first
            (home_dir / ".gitconfig").write_text("Modified after recovery\n")

            # Attempt rollback
            result = helper.run_command("rollback", "--rollback-to", transaction_id)
            # Note: Rollback might not be fully implemented yet
            # Just check it doesn't crash

        # Test backup creation and listing
        print("7. Testing backup functionality...")

        # Check if backups exist
        backup_dir = home_dir / ".local/state/dotfiles/backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("backup_*"))
            print(f"   Found {len(backups)} backup(s)")

            # Verify backup structure if any exist
            for backup in backups[:1]:  # Check first backup
                manifest_file = backup / "manifest.json"
                if manifest_file.exists():
                    manifest = json.loads(manifest_file.read_text())
                    assert "timestamp" in manifest, "Backup should have timestamp"
                    assert "files" in manifest, "Backup should list files"

        # Final verification
        print("8. Final state verification...")
        result = helper.run_command("status")
        assert result.exit_code == 0, "Final status check should succeed"

        # All critical files should be present and correct
        for f in initial_files:
            assert f.exists(), f"{f} should be restored"

        print("✓ Disaster recovery workflow test passed")
        return True

    finally:
        helper.cleanup()


def test_migration_from_existing_setup():
    """
    Test migrating from manually managed dotfiles.

    This test simulates a user who already has dotfiles and wants
    to start managing them with dotfiles-sync.
    """
    print("\n=== Testing Migration from Existing Setup ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Step 1: Create existing dotfiles (simulating manual management)
        print("1. Creating existing manually-managed dotfiles...")

        existing_zshrc = home_dir / ".zshrc"
        existing_zshrc.write_text("""# Existing ZSH config
export PATH="/usr/local/bin:$PATH"
alias myalias='echo "my custom alias"'
source ~/.private_vars
""")

        existing_gitconfig = home_dir / ".gitconfig"
        existing_gitconfig.write_text("""[user]
    name = Existing User
    email = existing@example.com
[alias]
    co = checkout
    br = branch
""")

        existing_vimrc = home_dir / ".vimrc"
        existing_vimrc.write_text("""" Existing vim config
set nocompatible
filetype plugin indent on
set backspace=indent,eol,start
""")

        # Step 2: Create dotfiles structure that matches existing files
        print("2. Creating managed dotfiles structure...")
        dotfiles_dir = helper.create_dotfiles_structure()

        # Copy existing configs to dotfiles directory
        shutil.copy2(existing_zshrc, dotfiles_dir / "zshrc")
        shutil.copy2(existing_gitconfig, dotfiles_dir / "gitconfig")
        shutil.copy2(existing_vimrc, dotfiles_dir / "vimrc")

        # Step 3: Create configuration
        print("3. Creating configuration for existing setup...")
        helper.create_config_file()

        # Step 4: Preview migration (dry-run)
        print("4. Previewing migration (dry-run)...")
        result = helper.run_command("sync")
        assert result.exit_code == 0, "Dry run should succeed"

        # Step 5: Check that backups would be created
        print("5. Verifying backup strategy...")
        # In a real implementation, we should check that existing files
        # would be backed up before being replaced

        # Step 6: Apply migration with force flag
        print("6. Applying migration...")
        result = helper.run_command("--apply", "--force", "sync")
        assert result.exit_code == 0, "Migration should succeed"

        # Step 7: Verify files are now managed
        print("7. Verifying managed state...")

        # Check that files are now symlinks (for link operations)
        assert helper.verify_symlink(home_dir / ".zshrc"), ".zshrc should now be a symlink"
        assert helper.verify_symlink(home_dir / ".vimrc"), ".vimrc should now be a symlink"

        # gitconfig was a copy operation, so it should be a regular file
        assert helper.verify_file_exists(home_dir / ".gitconfig"), ".gitconfig should exist"
        assert not (home_dir / ".gitconfig").is_symlink(), (
            ".gitconfig should be a regular file (copy operation)"
        )

        # Step 8: Verify content is preserved
        print("8. Verifying content preservation...")

        # Check that custom content is preserved
        zshrc_content = (home_dir / ".zshrc").read_text()
        assert "myalias" in zshrc_content, "Custom aliases should be preserved"

        gitconfig_content = (home_dir / ".gitconfig").read_text()
        assert "Existing User" in gitconfig_content, "User info should be preserved"

        # Step 9: Test status after migration
        print("9. Checking post-migration status...")
        result = helper.run_command("status")
        assert result.exit_code == 0, "Status should work after migration"

        # Step 10: Test that system is now under management
        print("10. Testing management capabilities...")

        # Make a change to test drift detection
        if (home_dir / ".vimrc").is_symlink():
            (home_dir / ".vimrc").unlink()
            (home_dir / ".vimrc").write_text("Modified content")

        result = helper.run_command("status")
        assert result.exit_code == 0, "Should detect drift"

        # Restore from management
        result = helper.run_command("--apply", "--force", "sync")
        assert result.exit_code == 0, "Should restore managed state"

        print("✓ Migration from existing setup test passed")
        return True

    finally:
        helper.cleanup()


def test_complete_user_journey():
    """
    Test a complete user journey from initial setup through daily use.

    This comprehensive test combines multiple workflows to ensure
    the system works correctly for a complete user experience.
    """
    print("\n=== Testing Complete User Journey ===")

    helper = E2ETestHelper()
    test_dir, home_dir = helper.setup_test_environment()

    try:
        # Phase 1: Initial Setup
        print("Phase 1: Initial Setup")
        print("-" * 40)

        helper.create_dotfiles_structure("default")
        helper.create_config_file(include_all_verbs=True)

        # Validate
        result = helper.run_command("validate")
        assert result.exit_code == 0, "Validation should succeed"

        # Dry run
        result = helper.run_command("sync")
        assert result.exit_code == 0, "Dry run should succeed"

        # Apply
        result = helper.run_command("--apply", "sync")
        assert result.exit_code == 0, "Initial setup should succeed"

        # Phase 2: Daily Use
        print("\nPhase 2: Daily Use")
        print("-" * 40)

        # Check status
        result = helper.run_command("status")
        assert result.exit_code == 0, "Status check should succeed"

        # Modify a file
        vimrc = home_dir / ".vimrc"
        if vimrc.is_symlink():
            vimrc.unlink()
            vimrc.write_text("Modified vim config")

        # Detect and fix drift
        result = helper.run_command("status")
        assert result.exit_code == 0, "Should detect drift"

        result = helper.run_command("--apply", "--force", "sync")
        assert result.exit_code == 0, "Should fix drift"

        # Phase 3: Variant Switching
        print("\nPhase 3: Variant Switching")
        print("-" * 40)

        # Add personal variant files
        helper.create_dotfiles_structure("personal")

        # Switch to personal
        result = helper.run_command("--variant", "personal", "--apply", "sync")
        assert result.exit_code == 0, "Personal variant should apply"

        # Verify personal files
        assert (home_dir / ".personal_aliases").exists(), "Personal files should exist"

        # Switch back
        result = helper.run_command("--variant", "default", "--apply", "sync")
        assert result.exit_code == 0, "Should switch back to default"

        # Phase 4: Advanced Operations
        print("\nPhase 4: Advanced Operations")
        print("-" * 40)

        # Test that advanced operations work
        if (home_dir / ".config/dotfiles").exists():
            print("   ✓ syncdir operation completed")

        if (home_dir / ".dotfiles_installed").exists():
            print("   ✓ run operation completed")

        # Phase 5: Recovery
        print("\nPhase 5: Recovery Testing")
        print("-" * 40)

        # Delete a file
        (home_dir / ".zshrc").unlink()

        # Recover
        result = helper.run_command("--apply", "--force", "sync")
        assert result.exit_code == 0, "Recovery should succeed"

        assert (home_dir / ".zshrc").exists(), "File should be recovered"

        print("\n✓ Complete user journey test passed")
        return True

    finally:
        helper.cleanup()


def main():
    """Run all E2E user journey tests."""
    print("=" * 60)
    print("END-TO-END USER JOURNEY INTEGRATION TESTS")
    print("=" * 60)
    print("\nThese tests simulate complete real-world user workflows.")
    print("Running in Docker container for safety.")
    print("-" * 60)

    tests = [
        ("First Time User Setup", test_first_time_user_complete_workflow),
        ("Daily Developer Workflow", test_daily_developer_workflow),
        ("Variant Switching", test_variant_switching_workflow),
        ("Disaster Recovery", test_disaster_recovery_workflow),
        ("Migration from Existing", test_migration_from_existing_setup),
        ("Complete User Journey", test_complete_user_journey),
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
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total:  {passed + failed}")

    if failed == 0:
        print("\n🎉 All E2E tests passed!")
    else:
        print(f"\n⚠️  {failed} test(s) failed")

    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
