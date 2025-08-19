"""Unit tests for the CLI module."""

import pytest
from click.testing import CliRunner
from pathlib import Path
from dotfiles_sync.cli import cli
from dotfiles_sync import __version__


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def test_config_path():
    """Get path to test configuration fixture."""
    return Path(__file__).parent.parent / "fixtures" / "test_config.toml"


def test_cli_version(runner):
    """Test --version flag."""
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_help(runner):
    """Test --help flag."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Dotfiles Management System" in result.output
    assert "--dry-run" in result.output
    assert "--apply" in result.output


def test_cli_no_command_shows_help(runner):
    """Test that invoking with no command shows help."""
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "Dotfiles Management System" in result.output


def test_validate_command_valid_config(runner, test_config_path):
    """Test validate command with valid configuration."""
    result = runner.invoke(cli, ["--config", str(test_config_path), "validate"])
    assert result.exit_code == 0
    assert "Configuration is valid" in result.output
    assert "test-dotfiles" in result.output


def test_validate_command_invalid_config(runner, tmp_path):
    """Test validate command with invalid configuration."""
    # Create an invalid config (missing required sections)
    invalid_config = tmp_path / "invalid.toml"
    invalid_config.write_text("[invalid]\ntest = true")

    result = runner.invoke(cli, ["--config", str(invalid_config), "validate"])
    assert result.exit_code == 1
    assert "validation failed" in result.output.lower()


def test_validate_command_missing_config(runner):
    """Test validate command with non-existent configuration."""
    result = runner.invoke(cli, ["--config", "nonexistent.toml", "validate"])
    assert result.exit_code == 2  # Click exits with 2 for missing file paths
    assert "does not exist" in result.output.lower()


def test_status_command(runner, tmp_path):
    """Test status command."""
    # Create a minimal config
    config = tmp_path / "config.toml"
    config.write_text("""
[package]
name = "test"
version = "1.0.0"

[safety]
dry_run_default = true
""")

    result = runner.invoke(cli, ["--config", str(config), "status"])
    assert result.exit_code == 0
    assert "System Status" in result.output


def test_rollback_command_no_id(runner):
    """Test rollback command without transaction ID."""
    result = runner.invoke(cli, ["rollback"])
    assert result.exit_code == 1
    assert "No transaction ID or file specified" in result.output


def test_sync_command_implemented(runner, test_config_path):
    """Test sync command is now implemented."""
    result = runner.invoke(cli, ["--config", str(test_config_path), "sync"])
    assert result.exit_code == 0
    assert "Syncing dotfiles" in result.output
    assert "DRY RUN" in result.output  # Should be dry run by default


def test_cli_dry_run_default(runner, test_config_path):
    """Test that dry-run is default behavior."""
    result = runner.invoke(cli, ["--config", str(test_config_path), "sync"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output or "dry run" in result.output.lower()


def test_cli_apply_flag(runner, test_config_path):
    """Test --apply flag overrides dry-run."""
    result = runner.invoke(cli, ["--config", str(test_config_path), "--apply", "sync"])
    assert result.exit_code == 0
    # When applying, it should not show DRY RUN
    assert "DRY RUN" not in result.output


def test_cli_log_level(runner, test_config_path):
    """Test different log levels."""
    # Test with DEBUG level
    result = runner.invoke(
        cli, ["--log-level", "DEBUG", "--config", str(test_config_path), "validate"]
    )
    assert result.exit_code == 0

    # Test with ERROR level
    result = runner.invoke(
        cli, ["--log-level", "ERROR", "--config", str(test_config_path), "validate"]
    )
    assert result.exit_code == 0
