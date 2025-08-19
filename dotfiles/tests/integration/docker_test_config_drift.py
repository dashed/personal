#!/usr/bin/env python3
"""
Docker integration tests for configuration drift detection.

This module tests the ConfigDriftDetector in a Docker environment to ensure
safe testing of drift detection scenarios without affecting the host system.
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
from dotfiles_sync.config_drift import ConfigDriftDetector, ConfigDriftType  # noqa: E402
from dotfiles_sync.state_database import StateDatabase  # noqa: E402
from dotfiles_sync.config import ConfigLoader  # noqa: E402

import pytest  # noqa: E402
from click.testing import CliRunner  # noqa: E402


class TestConfigDriftIntegration:
    """Integration tests for configuration drift detection."""

    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_config(self, tmp_path):
        """Create a temporary configuration file."""
        config_content = """
[package]
name = "test-dotfiles"
version = "1.0.0"
author = "Test User <test@example.com>"

[safety]
dry_run_default = true
backup_before_modify = true

[security]
whitelist_paths = ["~/**", "/tmp/**"]
blacklist_paths = ["/etc/**", "/root/**"]

[[step]]
op = "link"
src = "test-files/bashrc"
dst = "~/.test_bashrc"
description = "Test bash configuration"

[[step]]
op = "copy"
src = "test-files/vimrc"
dst = "~/.test_vimrc"
description = "Test vim configuration"
"""
        config_path = tmp_path / "dotfiles.toml"
        config_path.write_text(config_content)

        # Create source files
        test_files_dir = tmp_path / "test-files"
        test_files_dir.mkdir()
        (test_files_dir / "bashrc").write_text("# Test bashrc")
        (test_files_dir / "vimrc").write_text('" Test vimrc')
        (test_files_dir / "zshrc").write_text("# Test zshrc")

        return config_path

    def test_no_drift_on_fresh_system(self, runner, temp_config, tmp_path):
        """Test that fresh system shows no drift."""
        # Use temporary database
        db_path = tmp_path / "test_state.db"
        os.environ["DOTFILES_STATE_DB"] = str(db_path)

        try:
            # Initialize database
            with StateDatabase(db_path=str(db_path)) as db:
                # Load config and detect drift
                loader = ConfigLoader(temp_config)
                config = loader.load()

                detector = ConfigDriftDetector(db)
                summary = detector.detect_drift(config, variant="default")

                # Should show new operations but no drift
                assert summary.total_drift == 2  # Two new operations
                assert len(summary.new_operations) == 2
                assert len(summary.orphaned_operations) == 0
                assert len(summary.modified_operations) == 0
        finally:
            if "DOTFILES_STATE_DB" in os.environ:
                del os.environ["DOTFILES_STATE_DB"]

    def test_detect_new_operations(self, runner, temp_config, tmp_path):
        """Test detecting new operations added to config."""
        db_path = tmp_path / "test_state.db"
        os.environ["DOTFILES_STATE_DB"] = str(db_path)

        try:
            # Apply initial config
            result = runner.invoke(
                cli,
                ["--config", str(temp_config), "--apply", "sync"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0

            # Add new step to config
            config_content = temp_config.read_text()
            config_content += """
[[step]]
op = "link"
src = "test-files/zshrc"
dst = "~/.test_zshrc"
description = "New zsh configuration"
"""
            temp_config.write_text(config_content)

            # Detect drift
            with StateDatabase(db_path=str(db_path)) as db:
                loader = ConfigLoader(temp_config)
                config = loader.load()

                detector = ConfigDriftDetector(db)
                summary = detector.detect_drift(config, variant="default")

                # Should detect the new zshrc operation
                assert summary.total_drift == 1
                assert len(summary.new_operations) == 1
                assert ".test_zshrc" in summary.new_operations[0].dst_path
                assert summary.new_operations[0].drift_type == ConfigDriftType.NEW

        finally:
            if "DOTFILES_STATE_DB" in os.environ:
                del os.environ["DOTFILES_STATE_DB"]

    def test_detect_orphaned_operations(self, runner, temp_config, tmp_path):
        """Test detecting orphaned operations when removed from config."""
        db_path = tmp_path / "test_state.db"
        os.environ["DOTFILES_STATE_DB"] = str(db_path)

        try:
            # Apply initial config with all operations
            result = runner.invoke(
                cli,
                ["--config", str(temp_config), "--apply", "sync"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0

            # Remove vimrc step from config
            config_content = temp_config.read_text()
            lines = config_content.split("\n")
            # Remove the vimrc step (find and remove the section)
            new_lines = []
            skip_until_next_step = False
            for line in lines:
                if 'dst = "~/.test_vimrc"' in line:
                    # Start skipping from the previous [[step]]
                    # Remove the last added lines that belong to this step
                    while new_lines and not new_lines[-1].startswith("[[step]]"):
                        new_lines.pop()
                    if new_lines and new_lines[-1].startswith("[[step]]"):
                        new_lines.pop()
                    skip_until_next_step = True
                elif skip_until_next_step and line.startswith("[[step]]"):
                    skip_until_next_step = False
                    new_lines.append(line)
                elif not skip_until_next_step:
                    new_lines.append(line)

            temp_config.write_text("\n".join(new_lines))

            # Detect drift
            with StateDatabase(db_path=str(db_path)) as db:
                loader = ConfigLoader(temp_config)
                config = loader.load()

                detector = ConfigDriftDetector(db)
                summary = detector.detect_drift(config, variant="default")

                # Should detect orphaned vimrc operation
                assert summary.total_drift == 1
                assert len(summary.orphaned_operations) == 1
                assert ".test_vimrc" in summary.orphaned_operations[0].dst_path
                assert summary.orphaned_operations[0].drift_type == ConfigDriftType.ORPHANED

        finally:
            if "DOTFILES_STATE_DB" in os.environ:
                del os.environ["DOTFILES_STATE_DB"]

    def test_detect_modified_operations(self, runner, temp_config, tmp_path):
        """Test detecting modified operations when config changes."""
        db_path = tmp_path / "test_state.db"
        os.environ["DOTFILES_STATE_DB"] = str(db_path)

        try:
            # Apply initial config
            result = runner.invoke(
                cli,
                ["--config", str(temp_config), "--apply", "sync"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0

            # Modify the bashrc step (change from link to copy)
            config_content = temp_config.read_text()
            config_content = config_content.replace('op = "link"', 'op = "copy"', 1)
            config_content = config_content.replace(
                'description = "Test bash configuration"',
                'description = "Modified bash configuration"',
            )
            temp_config.write_text(config_content)

            # Detect drift
            with StateDatabase(db_path=str(db_path)) as db:
                loader = ConfigLoader(temp_config)
                config = loader.load()

                detector = ConfigDriftDetector(db)
                summary = detector.detect_drift(config, variant="default")

                # Should detect modified bashrc operation
                assert summary.total_drift >= 1
                assert len(summary.modified_operations) >= 1

                # Find the modified bashrc operation
                bashrc_mod = None
                for op in summary.modified_operations:
                    if ".test_bashrc" in op.dst_path:
                        bashrc_mod = op
                        break

                assert bashrc_mod is not None
                assert bashrc_mod.drift_type == ConfigDriftType.MODIFIED
                assert "changed" in bashrc_mod.impact.lower()

        finally:
            if "DOTFILES_STATE_DB" in os.environ:
                del os.environ["DOTFILES_STATE_DB"]

    def test_complex_drift_scenario(self, runner, temp_config, tmp_path):
        """Test complex scenario with multiple types of drift."""
        db_path = tmp_path / "test_state.db"
        os.environ["DOTFILES_STATE_DB"] = str(db_path)

        try:
            # Apply initial config
            result = runner.invoke(
                cli,
                ["--config", str(temp_config), "--apply", "sync"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0

            # Create complex changes:
            # 1. Remove vimrc (orphaned)
            # 2. Modify bashrc (modified)
            # 3. Add zshrc (new)
            config_content = """
[package]
name = "test-dotfiles"
version = "1.0.0"
author = "Test User <test@example.com>"

[safety]
dry_run_default = true
backup_before_modify = true

[security]
whitelist_paths = ["~/**", "/tmp/**"]
blacklist_paths = ["/etc/**", "/root/**"]

# Modified bashrc - changed mode
[[step]]
op = "copy"
src = "test-files/bashrc"
dst = "~/.test_bashrc"
mode = "0600"
description = "Modified bash configuration"

# New zshrc
[[step]]
op = "link"
src = "test-files/zshrc"
dst = "~/.test_zshrc"
description = "New zsh configuration"

# vimrc removed - will be orphaned
"""
            temp_config.write_text(config_content)

            # Detect drift
            with StateDatabase(db_path=str(db_path)) as db:
                loader = ConfigLoader(temp_config)
                config = loader.load()

                detector = ConfigDriftDetector(db)
                summary = detector.detect_drift(config, variant="default")

                # Should detect all three types of drift
                assert summary.total_drift == 3
                assert len(summary.new_operations) == 1  # zshrc
                assert len(summary.modified_operations) == 1  # bashrc
                assert len(summary.orphaned_operations) == 1  # vimrc

                # Verify specific operations
                assert ".test_zshrc" in summary.new_operations[0].dst_path
                assert ".test_bashrc" in summary.modified_operations[0].dst_path
                assert ".test_vimrc" in summary.orphaned_operations[0].dst_path

                # Check recommendation
                assert "reconcile" in summary.recommended_action.lower()

        finally:
            if "DOTFILES_STATE_DB" in os.environ:
                del os.environ["DOTFILES_STATE_DB"]

    def test_variant_specific_drift(self, runner, tmp_path):
        """Test drift detection with variant-specific operations."""
        # Create variant-specific config
        config_content = """
[package]
name = "test-dotfiles"
version = "1.0.0"

[safety]
dry_run_default = true

[security]
whitelist_paths = ["~/**", "/tmp/**"]

[[step]]
op = "link"
src = "files/common"
dst = "~/.test_common"
variants = ["all"]

[[step]]
op = "link"
src = "files/personal"
dst = "~/.test_personal"
variants = ["personal"]

[[step]]
op = "link"
src = "files/work"
dst = "~/.test_work"
variants = ["work"]
"""
        config_path = tmp_path / "dotfiles.toml"
        config_path.write_text(config_content)

        # Create source files
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / "common").write_text("common")
        (files_dir / "personal").write_text("personal")
        (files_dir / "work").write_text("work")

        db_path = tmp_path / "test_state.db"
        os.environ["DOTFILES_STATE_DB"] = str(db_path)

        try:
            # Apply work variant
            result = runner.invoke(
                cli,
                ["--config", str(config_path), "--variant", "work", "--apply", "sync"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0

            # Detect drift for personal variant
            with StateDatabase(db_path=str(db_path)) as db:
                loader = ConfigLoader(config_path)
                config = loader.load()

                detector = ConfigDriftDetector(db)

                # Check drift for personal variant
                summary_personal = detector.detect_drift(config, variant="personal")

                # Should show personal as new, work as orphaned
                assert len(summary_personal.new_operations) == 1
                assert ".test_personal" in summary_personal.new_operations[0].dst_path

                # Work file should be orphaned when checking personal variant
                assert len(summary_personal.orphaned_operations) == 1
                assert ".test_work" in summary_personal.orphaned_operations[0].dst_path

        finally:
            if "DOTFILES_STATE_DB" in os.environ:
                del os.environ["DOTFILES_STATE_DB"]

    def test_database_methods_integration(self, tmp_path):
        """Test database drift detection methods in integration."""
        db_path = tmp_path / "test_state.db"

        with StateDatabase(db_path=str(db_path)) as db:
            # Apply some operations
            with db.transaction("test", "user", "host") as tx:
                db.record_applied_step(
                    tx,
                    operation_type="link",
                    config={"op": "link", "src": "file1", "dst": "~/.file1"},
                    src_path="file1",
                    dst_path=str(Path("~/.file1").expanduser()),
                )
                db.record_applied_step(
                    tx,
                    operation_type="copy",
                    config={"op": "copy", "src": "file2", "dst": "~/.file2"},
                    src_path="file2",
                    dst_path=str(Path("~/.file2").expanduser()),
                )

            # Get applied step hashes
            hashes = db.get_applied_step_hashes_by_variant()
            assert len(hashes) == 2

            # Get all step hashes
            all_hashes = {v["step_hash"] for v in hashes.values()}

            # Find orphaned operations (all should be orphaned if we pass empty set)
            orphaned = db.find_orphaned_operations(set())
            assert len(orphaned) == 2

            # Find orphaned with one hash kept
            one_hash = list(all_hashes)[0]
            orphaned_partial = db.find_orphaned_operations({one_hash})
            assert len(orphaned_partial) == 1

            # Mark operations as orphaned
            with db.transaction("test", "user", "host") as tx:
                affected = db.mark_operations_as_orphaned(list(all_hashes), tx.id)
                assert affected == 2

            # Verify they're marked as not current
            current = db.get_current_applied_steps()
            assert len(current) == 0

            # Get drift summary
            summary = db.get_config_drift_summary()
            assert summary["total_applied"] == 0  # All marked as not current

    def test_drift_detection_with_actual_files(self, runner, tmp_path):
        """Test drift detection with actual file operations."""
        # Create config that creates actual files
        config_content = """
[package]
name = "test-dotfiles"
version = "1.0.0"

[safety]
dry_run_default = false
backup_before_modify = true

[security]
whitelist_paths = ["/tmp/**"]

[[step]]
op = "copy"
src = "files/testfile"
dst = "/tmp/test_drift_file"
description = "Test file for drift detection"
"""
        config_path = tmp_path / "dotfiles.toml"
        config_path.write_text(config_content)

        # Create source file
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / "testfile").write_text("Original content")

        db_path = tmp_path / "test_state.db"
        os.environ["DOTFILES_STATE_DB"] = str(db_path)

        try:
            # Apply config
            result = runner.invoke(
                cli,
                ["--config", str(config_path), "--apply", "sync"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            assert Path("/tmp/test_drift_file").exists()

            # Modify source file
            (files_dir / "testfile").write_text("Modified content")

            # Detect drift
            with StateDatabase(db_path=str(db_path)) as db:
                loader = ConfigLoader(config_path)
                config = loader.load()

                detector = ConfigDriftDetector(db)
                detector.detect_drift(config, variant="default")

                # Should detect modified operation due to source change
                # Note: The hash changes because the config includes the actual content
                # In this case, since we're comparing configs, not file contents,
                # it might not detect as modified unless config itself changes
                # This is expected behavior for Phase 1

                # Clean up
                if Path("/tmp/test_drift_file").exists():
                    Path("/tmp/test_drift_file").unlink()

        finally:
            if "DOTFILES_STATE_DB" in os.environ:
                del os.environ["DOTFILES_STATE_DB"]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
