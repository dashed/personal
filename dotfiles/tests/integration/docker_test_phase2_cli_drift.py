#!/usr/bin/env python3
"""
Docker integration tests for Phase 2: CLI Visibility & Reporting.

This module tests the new CLI drift detection commands in a Docker environment.
DO NOT RUN THIS OUTSIDE OF DOCKER.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the Docker-only guard first
from tests.integration.docker_only_guard import require_docker

# This will exit if not running in Docker
require_docker()

# Now safe to import the actual modules
from dotfiles_sync.cli import cli  # noqa: E402
from dotfiles_sync.state_database import StateDatabase  # noqa: E402
from dotfiles_sync.models import TransactionContext  # noqa: E402

import pytest  # noqa: E402
from click.testing import CliRunner  # noqa: E402


class TestPhase2CLIDriftIntegration:
    """Integration tests for Phase 2 CLI drift detection features."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def test_dir(self, tmp_path):
        """Create a test directory structure."""
        test_dir = tmp_path / "dotfiles_test"
        test_dir.mkdir()
        
        # Create source files
        files_dir = test_dir / "files"
        files_dir.mkdir()
        
        (files_dir / "bashrc").write_text("# Test bashrc\nalias ll='ls -la'\n")
        (files_dir / "vimrc").write_text('" Test vimrc\nset number\n')
        (files_dir / "gitconfig").write_text("[user]\n  name = Test User\n")
        
        return test_dir

    def test_drift_check_command_no_drift(self, runner, test_dir):
        """Test drift-check command when no drift exists."""
        # Create config file
        config_path = test_dir / "dotfiles.toml"
        config_path.write_text("""
[package]
name = "test-dotfiles"
version = "1.0.0"

[[step]]
op = "link"
src = "files/bashrc"
dst = "/tmp/test_bashrc"
""")
        
        # Initialize database with applied operation
        db_path = test_dir / "test.db"
        with StateDatabase(db_path=str(db_path)) as db:
            with db.transaction("default", "test", "docker") as tx:
                db.record_applied_step(
                    tx,
                    "link",
                    {"op": "link", "src": "files/bashrc", "dst": "/tmp/test_bashrc"},
                    src_path="files/bashrc",
                    dst_path="/tmp/test_bashrc",
                )
        
        # Run drift-check command
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "drift-check"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        
        assert result.exit_code == 0
        assert "No action needed" in result.output or "Total Drift: 0" in result.output

    def test_drift_check_command_with_new_operations(self, runner, test_dir):
        """Test drift-check command when new operations exist."""
        # Create config file with two operations
        config_path = test_dir / "dotfiles.toml"
        config_path.write_text("""
[package]
name = "test-dotfiles"
version = "1.0.0"

[[step]]
op = "link"
src = "files/bashrc"
dst = "/tmp/test_bashrc"

[[step]]
op = "copy"
src = "files/vimrc"
dst = "/tmp/test_vimrc"
""")
        
        # Initialize database with only one applied operation
        db_path = test_dir / "test.db"
        with StateDatabase(db_path=str(db_path)) as db:
            with db.transaction("default", "test", "docker") as tx:
                db.record_applied_step(
                    tx,
                    "link",
                    {"op": "link", "src": "files/bashrc", "dst": "/tmp/test_bashrc"},
                    src_path="files/bashrc",
                    dst_path="/tmp/test_bashrc",
                )
        
        # Run drift-check command
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "drift-check"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        
        assert result.exit_code == 1  # Exit code 1 indicates drift exists
        assert "NEW OPERATIONS" in result.output
        assert "/tmp/test_vimrc" in result.output

    def test_drift_check_command_with_orphaned_operations(self, runner, test_dir):
        """Test drift-check command when orphaned operations exist."""
        # Create config file with one operation
        config_path = test_dir / "dotfiles.toml"
        config_path.write_text("""
[package]
name = "test-dotfiles"
version = "1.0.0"

[[step]]
op = "link"
src = "files/bashrc"
dst = "/tmp/test_bashrc"
""")
        
        # Initialize database with two applied operations
        db_path = test_dir / "test.db"
        with StateDatabase(db_path=str(db_path)) as db:
            with db.transaction("default", "test", "docker") as tx:
                db.record_applied_step(
                    tx,
                    "link",
                    {"op": "link", "src": "files/bashrc", "dst": "/tmp/test_bashrc"},
                    src_path="files/bashrc",
                    dst_path="/tmp/test_bashrc",
                )
                db.record_applied_step(
                    tx,
                    "copy",
                    {"op": "copy", "src": "files/vimrc", "dst": "/tmp/test_vimrc"},
                    src_path="files/vimrc",
                    dst_path="/tmp/test_vimrc",
                )
        
        # Run drift-check command
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "drift-check"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        
        assert result.exit_code == 1
        assert "ORPHANED OPERATIONS" in result.output
        assert "/tmp/test_vimrc" in result.output

    def test_drift_check_json_output(self, runner, test_dir):
        """Test drift-check command with JSON output format."""
        # Create config file
        config_path = test_dir / "dotfiles.toml"
        config_path.write_text("""
[package]
name = "test-dotfiles"
version = "1.0.0"

[[step]]
op = "link"
src = "files/bashrc"
dst = "/tmp/test_bashrc"
""")
        
        # Initialize empty database
        db_path = test_dir / "test.db"
        StateDatabase(db_path=str(db_path)).close()
        
        # Run drift-check command with JSON format
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "drift-check", "--format", "json"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        
        assert result.exit_code == 1
        # Verify JSON structure in output
        assert '"total_drift"' in result.output
        assert '"new_operations"' in result.output
        assert '"modified_operations"' in result.output
        assert '"orphaned_operations"' in result.output

    def test_status_command_with_config_drift(self, runner, test_dir):
        """Test status command with --config-drift flag."""
        # Create config file
        config_path = test_dir / "dotfiles.toml"
        config_path.write_text("""
[package]
name = "test-dotfiles"
version = "1.0.0"

[[step]]
op = "link"
src = "files/bashrc"
dst = "/tmp/test_bashrc"

[[step]]
op = "copy"
src = "files/vimrc"
dst = "/tmp/test_vimrc"
""")
        
        # Initialize database with one applied operation
        db_path = test_dir / "test.db"
        with StateDatabase(db_path=str(db_path)) as db:
            with db.transaction("default", "test", "docker") as tx:
                db.record_applied_step(
                    tx,
                    "link",
                    {"op": "link", "src": "files/bashrc", "dst": "/tmp/test_bashrc"},
                    src_path="files/bashrc",
                    dst_path="/tmp/test_bashrc",
                )
        
        # Run status command with --config-drift
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "status", "--config-drift"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        
        assert result.exit_code == 0
        assert "System Status" in result.output
        assert "Configuration Drift" in result.output
        assert "New: 1" in result.output or "1" in result.output

    def test_validate_command_with_check_database(self, runner, test_dir):
        """Test validate command with --check-database flag."""
        # Create config file
        config_path = test_dir / "dotfiles.toml"
        config_path.write_text("""
[package]
name = "test-dotfiles"
version = "1.0.0"

[[step]]
op = "link"
src = "files/bashrc"
dst = "/tmp/test_bashrc"
""")
        
        # Initialize database with different operation
        db_path = test_dir / "test.db"
        with StateDatabase(db_path=str(db_path)) as db:
            with db.transaction("default", "test", "docker") as tx:
                db.record_applied_step(
                    tx,
                    "copy",
                    {"op": "copy", "src": "files/old", "dst": "/tmp/test_old"},
                    src_path="files/old",
                    dst_path="/tmp/test_old",
                )
        
        # Run validate command with --check-database
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "validate", "--check-database"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        
        assert result.exit_code == 0
        assert "Configuration is valid!" in result.output
        assert "Database Validation" in result.output
        assert "orphaned operations found" in result.output or "new operations ready" in result.output

    def test_sync_command_with_show_drift(self, runner, test_dir):
        """Test sync command with --show-drift flag."""
        # Create config file
        config_path = test_dir / "dotfiles.toml"
        config_path.write_text("""
[package]
name = "test-dotfiles"
version = "1.0.0"

[[step]]
op = "copy"
src = "files/bashrc"
dst = "/tmp/test_bashrc_sync"
""")
        
        # Create the source file
        (test_dir / "files" / "bashrc").write_text("# Bashrc content\n")
        
        # Initialize empty database
        db_path = test_dir / "test.db"
        StateDatabase(db_path=str(db_path)).close()
        
        # Run sync command with --show-drift
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "sync", "--show-drift", "--force"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        
        assert result.exit_code == 0
        assert "Pre-sync Drift Analysis" in result.output
        assert "Configuration drift detected" in result.output or "No configuration drift" in result.output
        assert "Results Summary" in result.output

    def test_drift_check_detailed_output(self, runner, test_dir):
        """Test drift-check command with --detailed flag."""
        # Create config file with modified operation
        config_path = test_dir / "dotfiles.toml"
        config_path.write_text("""
[package]
name = "test-dotfiles"
version = "1.0.0"

[[step]]
op = "link"
src = "files/bashrc"
dst = "/tmp/test_bashrc"
mode = "0644"
""")
        
        # Initialize database with same destination but different config
        db_path = test_dir / "test.db"
        with StateDatabase(db_path=str(db_path)) as db:
            with db.transaction("default", "test", "docker") as tx:
                db.record_applied_step(
                    tx,
                    "link",
                    {"op": "link", "src": "files/bashrc_old", "dst": "/tmp/test_bashrc"},
                    src_path="files/bashrc_old",
                    dst_path="/tmp/test_bashrc",
                )
        
        # Run drift-check command with --detailed
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "drift-check", "--detailed"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        
        assert result.exit_code == 1
        assert "Details for" in result.output or "Config:" in result.output

    def test_multiple_variants_drift_check(self, runner, test_dir):
        """Test drift-check with different variants."""
        # Create config file with variant-specific steps
        config_path = test_dir / "dotfiles.toml"
        config_path.write_text("""
[package]
name = "test-dotfiles"
version = "1.0.0"

[[step]]
op = "link"
src = "files/bashrc"
dst = "/tmp/test_bashrc"
variants = ["default"]

[[step]]
op = "copy"
src = "files/vimrc"
dst = "/tmp/test_vimrc"
variants = ["personal"]

[[step]]
op = "copy"
src = "files/gitconfig"
dst = "/tmp/test_gitconfig"
variants = ["work"]
""")
        
        # Initialize empty database
        db_path = test_dir / "test.db"
        StateDatabase(db_path=str(db_path)).close()
        
        # Test default variant
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "--variant", "default", "drift-check"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        assert result.exit_code == 1
        assert "/tmp/test_bashrc" in result.output
        assert "/tmp/test_vimrc" not in result.output
        
        # Test personal variant
        result = runner.invoke(
            cli,
            ["--config", str(config_path), "--variant", "personal", "drift-check"],
            env={"DOTFILES_DB_PATH": str(db_path)}
        )
        assert result.exit_code == 1
        assert "/tmp/test_vimrc" in result.output
        assert "/tmp/test_bashrc" not in result.output


if __name__ == "__main__":
    # Ensure we're in Docker
    require_docker()
    
    # Run tests
    pytest.main([__file__, "-v"])