#!/usr/bin/env python3
"""
Unit tests for CLI drift detection commands (Phase 2).

This module tests the new CLI commands and enhancements for configuration drift.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from dotfiles_sync.cli import cli
from dotfiles_sync.config_drift import (
    ConfigDriftResult,
    ConfigDriftSummary,
    ConfigDriftType,
    ConfigDriftSeverity,
)


class TestDriftCheckCommand:
    """Test the drift-check command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    @pytest.fixture
    def sample_drift_summary(self):
        """Create a sample drift summary for testing."""
        return ConfigDriftSummary(
            total_drift=3,
            new_operations=[
                ConfigDriftResult(
                    drift_type=ConfigDriftType.NEW,
                    dst_path="~/.zshrc",
                    operation_type="link",
                    current_step_hash="hash1",
                    applied_step_hash=None,
                    current_config={"op": "link", "src": "zsh/zshrc", "dst": "~/.zshrc"},
                    applied_config=None,
                    impact="New link operation will be applied on next sync",
                    severity=ConfigDriftSeverity.INFO,
                )
            ],
            modified_operations=[
                ConfigDriftResult(
                    drift_type=ConfigDriftType.MODIFIED,
                    dst_path="~/.gitconfig",
                    operation_type="copy",
                    current_step_hash="hash2",
                    applied_step_hash="hash2_old",
                    current_config={"op": "copy", "src": "git/gitconfig", "dst": "~/.gitconfig"},
                    applied_config={"op": "copy", "src": "git/gitconfig-old", "dst": "~/.gitconfig"},
                    impact="Configuration changed for copy operation",
                    severity=ConfigDriftSeverity.WARNING,
                )
            ],
            orphaned_operations=[
                ConfigDriftResult(
                    drift_type=ConfigDriftType.ORPHANED,
                    dst_path="~/.old_file",
                    operation_type="link",
                    current_step_hash=None,
                    applied_step_hash="hash3",
                    current_config=None,
                    applied_config={"op": "link", "src": "old", "dst": "~/.old_file"},
                    impact="Operation no longer in configuration, file remains managed",
                    severity=ConfigDriftSeverity.WARNING,
                )
            ],
            recommended_action="Run 'dotfiles-sync reconcile' to clean 1 orphaned operations, update 1 modified operations, apply 1 new operations",
            checked_variant="default",
        )

    @pytest.fixture
    def no_drift_summary(self):
        """Create a summary with no drift."""
        return ConfigDriftSummary(
            total_drift=0,
            new_operations=[],
            modified_operations=[],
            orphaned_operations=[],
            recommended_action="No action needed - configuration is in sync",
            checked_variant="default",
        )

    def test_drift_check_with_drift(self, runner, sample_drift_summary):
        """Test drift-check command when drift exists."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[package]
name = "test"
version = "1.0.0"

[[step]]
op = "link"
src = "test"
dst = "~/.test"
""")
            config_path = f.name

        try:
            with patch("dotfiles_sync.cli.StateDatabase"), \
                 patch("dotfiles_sync.cli.ConfigLoader") as mock_loader, \
                 patch("dotfiles_sync.cli.ConfigDriftDetector") as mock_detector:
                
                # Mock the detector to return our sample drift
                mock_detector_instance = MagicMock()
                mock_detector.return_value = mock_detector_instance
                mock_detector_instance.detect_drift.return_value = sample_drift_summary
                
                # Mock the config loader
                mock_loader_instance = MagicMock()
                mock_loader.return_value = mock_loader_instance
                mock_loader_instance.load.return_value = MagicMock()
                
                result = runner.invoke(cli, ["--config", config_path, "drift-check"])
                
                # Should exit with code 1 when drift exists
                assert result.exit_code == 1
                assert "Configuration Drift Report" in result.output
                assert "ORPHANED OPERATIONS" in result.output
                assert "MODIFIED OPERATIONS" in result.output
                assert "NEW OPERATIONS" in result.output
                
        finally:
            Path(config_path).unlink()

    def test_drift_check_no_drift(self, runner, no_drift_summary):
        """Test drift-check command when no drift exists."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[package]
name = "test"
version = "1.0.0"
""")
            config_path = f.name

        try:
            with patch("dotfiles_sync.cli.StateDatabase"), \
                 patch("dotfiles_sync.cli.ConfigLoader") as mock_loader, \
                 patch("dotfiles_sync.cli.ConfigDriftDetector") as mock_detector:
                
                # Mock the detector to return no drift
                mock_detector_instance = MagicMock()
                mock_detector.return_value = mock_detector_instance
                mock_detector_instance.detect_drift.return_value = no_drift_summary
                
                # Mock the config loader
                mock_loader_instance = MagicMock()
                mock_loader.return_value = mock_loader_instance
                mock_loader_instance.load.return_value = MagicMock()
                
                result = runner.invoke(cli, ["--config", config_path, "drift-check"])
                
                # Should exit with code 0 when no drift
                assert result.exit_code == 0
                assert "No action needed" in result.output
                
        finally:
            Path(config_path).unlink()

    def test_drift_check_json_format(self, runner, sample_drift_summary):
        """Test drift-check command with JSON output format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[package]
name = "test"
version = "1.0.0"
""")
            config_path = f.name

        try:
            with patch("dotfiles_sync.cli.StateDatabase"), \
                 patch("dotfiles_sync.cli.ConfigLoader") as mock_loader, \
                 patch("dotfiles_sync.cli.ConfigDriftDetector") as mock_detector:
                
                # Mock the detector
                mock_detector_instance = MagicMock()
                mock_detector.return_value = mock_detector_instance
                mock_detector_instance.detect_drift.return_value = sample_drift_summary
                
                # Mock the config loader
                mock_loader_instance = MagicMock()
                mock_loader.return_value = mock_loader_instance
                mock_loader_instance.load.return_value = MagicMock()
                
                result = runner.invoke(
                    cli, ["--config", config_path, "drift-check", "--format", "json"]
                )
                
                # Verify JSON output
                assert result.exit_code == 1
                # The output should contain valid JSON
                assert "{" in result.output and "}" in result.output
                # The JSON should contain the expected structure
                assert '"total_drift"' in result.output
                assert '"new_operations"' in result.output
                assert '"modified_operations"' in result.output
                assert '"orphaned_operations"' in result.output
                # Verify count
                assert '"total_drift": 3' in result.output or '"total_drift":3' in result.output
                
        finally:
            Path(config_path).unlink()

    def test_drift_check_detailed_flag(self, runner, sample_drift_summary):
        """Test drift-check command with --detailed flag."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[package]
name = "test"
version = "1.0.0"
""")
            config_path = f.name

        try:
            with patch("dotfiles_sync.cli.StateDatabase"), \
                 patch("dotfiles_sync.cli.ConfigLoader") as mock_loader, \
                 patch("dotfiles_sync.cli.ConfigDriftDetector") as mock_detector:
                
                # Mock the detector
                mock_detector_instance = MagicMock()
                mock_detector.return_value = mock_detector_instance
                mock_detector_instance.detect_drift.return_value = sample_drift_summary
                
                # Mock the config loader
                mock_loader_instance = MagicMock()
                mock_loader.return_value = mock_loader_instance
                mock_loader_instance.load.return_value = MagicMock()
                
                result = runner.invoke(
                    cli, ["--config", config_path, "drift-check", "--detailed"]
                )
                
                assert result.exit_code == 1
                # Detailed output should include config details
                assert "Details for" in result.output
                assert "Applied config:" in result.output or "Config:" in result.output
                
        finally:
            Path(config_path).unlink()


class TestEnhancedStatusCommand:
    """Test the enhanced status command with --config-drift flag."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_status_with_config_drift_flag(self, runner):
        """Test status command with --config-drift flag."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[package]
name = "test"
version = "1.0.0"
""")
            config_path = f.name

        try:
            with patch("dotfiles_sync.cli.StateDatabase") as mock_db, \
                 patch("dotfiles_sync.cli.ConfigLoader") as mock_loader, \
                 patch("dotfiles_sync.cli.ConfigDriftDetector") as mock_detector:
                
                # Mock database
                mock_db_instance = MagicMock()
                mock_db.return_value.__enter__.return_value = mock_db_instance
                mock_db_instance.get_statistics.return_value = {
                    "applied_steps": 5,
                    "transactions": {"total": 10, "completed": 8, "failed": 1, "rolled_back": 1}
                }
                mock_db_instance.get_current_state.return_value = []
                
                # Mock drift detector
                mock_detector_instance = MagicMock()
                mock_detector.return_value = mock_detector_instance
                drift_summary = ConfigDriftSummary(
                    total_drift=2,
                    new_operations=[
                        ConfigDriftResult(
                            drift_type=ConfigDriftType.NEW,
                            dst_path="~/.test1",
                            operation_type="link",
                            impact="New operation",
                            severity=ConfigDriftSeverity.INFO,
                        )
                    ],
                    modified_operations=[
                        ConfigDriftResult(
                            drift_type=ConfigDriftType.MODIFIED,
                            dst_path="~/.test2",
                            operation_type="copy",
                            impact="Modified operation",
                            severity=ConfigDriftSeverity.WARNING,
                        )
                    ],
                    orphaned_operations=[],
                    recommended_action="Run 'dotfiles-sync sync' to apply changes",
                    checked_variant="default",
                )
                mock_detector_instance.detect_drift.return_value = drift_summary
                
                # Mock config loader
                mock_loader_instance = MagicMock()
                mock_loader.return_value = mock_loader_instance
                mock_loader_instance.load.return_value = MagicMock()
                
                result = runner.invoke(
                    cli, ["--config", config_path, "status", "--config-drift"]
                )
                
                assert result.exit_code == 0
                assert "System Status" in result.output
                assert "Configuration Drift" in result.output
                assert "Configuration drift detected: 2 operations" in result.output
                
        finally:
            Path(config_path).unlink()


class TestEnhancedValidateCommand:
    """Test the enhanced validate command with --check-database flag."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_validate_with_check_database_flag(self, runner):
        """Test validate command with --check-database flag."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[package]
name = "test"
version = "1.0.0"

[[step]]
op = "link"
src = "test"
dst = "~/.test"
""")
            config_path = f.name

        try:
            with patch("dotfiles_sync.cli.StateDatabase") as mock_db, \
                 patch("dotfiles_sync.cli.ConfigLoader") as mock_loader, \
                 patch("dotfiles_sync.cli.ConfigDriftDetector") as mock_detector:
                
                # Mock config loader
                mock_loader_instance = MagicMock()
                mock_loader.return_value = mock_loader_instance
                mock_config = MagicMock()
                mock_config.package.name = "test"
                mock_config.package.version = "1.0.0"
                mock_config.safety.dry_run_default = True
                mock_config.step = [MagicMock()]
                mock_loader_instance.load.return_value = mock_config
                mock_loader_instance.validate.return_value = None
                
                # Mock database
                mock_db_instance = MagicMock()
                mock_db.return_value.__enter__.return_value = mock_db_instance
                
                # Mock drift detector
                mock_detector_instance = MagicMock()
                mock_detector.return_value = mock_detector_instance
                drift_summary = ConfigDriftSummary(
                    total_drift=2,
                    new_operations=[],
                    modified_operations=[
                        ConfigDriftResult(
                            drift_type=ConfigDriftType.MODIFIED,
                            dst_path="~/.gitconfig",
                            operation_type="copy",
                            impact="Configuration changed",
                            severity=ConfigDriftSeverity.WARNING,
                        )
                    ],
                    orphaned_operations=[
                        ConfigDriftResult(
                            drift_type=ConfigDriftType.ORPHANED,
                            dst_path="~/.old_file",
                            operation_type="link",
                            impact="Operation no longer in configuration",
                            severity=ConfigDriftSeverity.WARNING,
                        )
                    ],
                    recommended_action="",
                    checked_variant="default",
                )
                mock_detector_instance.detect_drift.return_value = drift_summary
                
                result = runner.invoke(
                    cli, ["--config", config_path, "validate", "--check-database"]
                )
                
                assert result.exit_code == 0
                assert "Configuration is valid!" in result.output
                assert "Database Validation" in result.output
                assert "1 orphaned operations found" in result.output
                assert "1 modified operations found" in result.output
                
        finally:
            Path(config_path).unlink()


class TestEnhancedSyncCommand:
    """Test the enhanced sync command with --show-drift flag."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_sync_with_show_drift_flag(self, runner):
        """Test sync command with --show-drift flag."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[package]
name = "test"
version = "1.0.0"

[[step]]
op = "link"
src = "test"
dst = "~/.test"
""")
            config_path = f.name

        try:
            with patch("dotfiles_sync.cli.StateDatabase") as mock_db, \
                 patch("dotfiles_sync.cli.ConfigLoader") as mock_loader, \
                 patch("dotfiles_sync.cli.ConfigDriftDetector") as mock_detector, \
                 patch("dotfiles_sync.cli.OperationExecutor") as mock_executor, \
                 patch("dotfiles_sync.cli.click.confirm") as mock_confirm:
                
                # Mock config loader
                mock_loader_instance = MagicMock()
                mock_loader.return_value = mock_loader_instance
                mock_config = MagicMock()
                mock_loader_instance.load.return_value = mock_config
                mock_loader_instance.validate.return_value = None
                
                # Mock database
                mock_db_instance = MagicMock()
                mock_db.return_value.__enter__.return_value = mock_db_instance
                
                # Mock drift detector
                mock_detector_instance = MagicMock()
                mock_detector.return_value = mock_detector_instance
                drift_summary = ConfigDriftSummary(
                    total_drift=1,
                    new_operations=[
                        ConfigDriftResult(
                            drift_type=ConfigDriftType.NEW,
                            dst_path="~/.test",
                            operation_type="link",
                            impact="New link operation will be applied",
                            severity=ConfigDriftSeverity.INFO,
                        )
                    ],
                    modified_operations=[],
                    orphaned_operations=[],
                    recommended_action="Run 'dotfiles-sync sync' to apply 1 new operations",
                    checked_variant="default",
                )
                mock_detector_instance.detect_drift.return_value = drift_summary
                
                # Mock executor
                mock_executor_instance = MagicMock()
                mock_executor.return_value = mock_executor_instance
                mock_executor_instance.execute_all.return_value = [
                    MagicMock(success=True, message="Test operation", dry_run=True)
                ]
                
                # Mock confirmation
                mock_confirm.return_value = True
                
                result = runner.invoke(
                    cli, ["--config", config_path, "sync", "--show-drift"]
                )
                
                assert result.exit_code == 0
                assert "Pre-sync Drift Analysis" in result.output
                assert "Configuration drift detected: 1 operations" in result.output
                assert "Continue with sync?" in result.output or "Results Summary" in result.output
                
        finally:
            Path(config_path).unlink()

    def test_sync_with_show_drift_cancelled(self, runner):
        """Test sync command with --show-drift when user cancels."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[package]
name = "test"
version = "1.0.0"
""")
            config_path = f.name

        try:
            with patch("dotfiles_sync.cli.StateDatabase") as mock_db, \
                 patch("dotfiles_sync.cli.ConfigLoader") as mock_loader, \
                 patch("dotfiles_sync.cli.ConfigDriftDetector") as mock_detector, \
                 patch("dotfiles_sync.cli.click.confirm") as mock_confirm:
                
                # Mock config loader
                mock_loader_instance = MagicMock()
                mock_loader.return_value = mock_loader_instance
                mock_loader_instance.load.return_value = MagicMock()
                mock_loader_instance.validate.return_value = None
                
                # Mock database
                mock_db_instance = MagicMock()
                mock_db.return_value.__enter__.return_value = mock_db_instance
                
                # Mock drift detector with drift
                mock_detector_instance = MagicMock()
                mock_detector.return_value = mock_detector_instance
                drift_summary = ConfigDriftSummary(
                    total_drift=1,
                    new_operations=[
                        ConfigDriftResult(
                            drift_type=ConfigDriftType.NEW,
                            dst_path="~/.test",
                            operation_type="link",
                            impact="New link operation",
                            severity=ConfigDriftSeverity.INFO,
                        )
                    ],
                    modified_operations=[],
                    orphaned_operations=[],
                    recommended_action="",
                    checked_variant="default",
                )
                mock_detector_instance.detect_drift.return_value = drift_summary
                
                # User cancels sync
                mock_confirm.return_value = False
                
                result = runner.invoke(
                    cli, ["--config", config_path, "sync", "--show-drift"]
                )
                
                assert result.exit_code == 0
                assert "Sync cancelled" in result.output
                assert "Results Summary" not in result.output
                
        finally:
            Path(config_path).unlink()