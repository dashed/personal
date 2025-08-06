"""Unit tests for the configuration module with Pydantic models."""

import pytest
from pathlib import Path
from pydantic import ValidationError
from dotfiles_sync.config import ConfigLoader, ConfigValidationError
from dotfiles_sync.models import DotfilesConfig, Platform, OperationType


@pytest.fixture
def test_config_path():
    """Get path to test configuration fixture."""
    return Path(__file__).parent.parent / "fixtures" / "test_config.toml"


@pytest.fixture
def config_loader(test_config_path):
    """Create a ConfigLoader instance with test config."""
    return ConfigLoader(test_config_path)


def test_load_valid_config(config_loader):
    """Test loading a valid configuration file."""
    config = config_loader.load()
    
    assert config is not None
    assert isinstance(config, DotfilesConfig)
    assert config.package.name == "test-dotfiles"
    assert config.package.version == "0.1.0"
    assert config.package.author == "Test User <test@example.com>"


def test_validate_valid_config(config_loader):
    """Test validation of a valid configuration."""
    config = config_loader.load()
    # Should not raise any exception
    config_loader.validate(config)


def test_missing_config_file():
    """Test handling of missing configuration file."""
    loader = ConfigLoader(Path("nonexistent.toml"))
    
    with pytest.raises(ConfigValidationError) as exc_info:
        loader.load()
    
    assert "not found" in str(exc_info.value)


def test_invalid_toml_syntax(tmp_path):
    """Test handling of invalid TOML syntax."""
    invalid_toml = tmp_path / "invalid.toml"
    invalid_toml.write_text("invalid syntax {")
    
    loader = ConfigLoader(invalid_toml)
    with pytest.raises(ConfigValidationError) as exc_info:
        loader.load()
    
    assert "Invalid TOML syntax" in str(exc_info.value)


def test_missing_required_package_fields(tmp_path):
    """Test validation with missing package fields."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text("""
[package]
# Missing name and version

[safety]
dry_run_default = true
""")
    
    loader = ConfigLoader(config_toml)
    with pytest.raises(ConfigValidationError) as exc_info:
        loader.load()
    
    assert "validation failed" in str(exc_info.value).lower()


def test_invalid_version_format(tmp_path):
    """Test validation with invalid version format."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text("""
[package]
name = "test"
version = "invalid"

[safety]
dry_run_default = true
""")
    
    loader = ConfigLoader(config_toml)
    with pytest.raises(ConfigValidationError) as exc_info:
        loader.load()
    
    assert "validation failed" in str(exc_info.value).lower()


def test_invalid_safety_field_type(tmp_path):
    """Test validation with invalid safety field type."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text("""
[package]
name = "test"
version = "1.0.0"

[safety]
backup_retention_days = "thirty"  # Should be integer
""")
    
    loader = ConfigLoader(config_toml)
    with pytest.raises(ConfigValidationError) as exc_info:
        loader.load()
    
    assert "validation failed" in str(exc_info.value).lower()


def test_invalid_operation_type(tmp_path):
    """Test validation with invalid operation type."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text("""
[package]
name = "test"
version = "1.0.0"

[safety]
dry_run_default = true

[[step]]
op = "invalid_op"
src = "test"
dst = "test"
""")
    
    loader = ConfigLoader(config_toml)
    with pytest.raises(ConfigValidationError) as exc_info:
        loader.load()
    
    assert "validation failed" in str(exc_info.value).lower()


def test_filter_steps_by_variant(config_loader):
    """Test filtering steps by variant."""
    config = config_loader.load()
    
    # Filter for "default" variant
    default_steps = config_loader.filter_steps_by_variant("default")
    assert len(default_steps) == 1
    assert default_steps[0].op == OperationType.LINK
    
    # Filter for "test" variant
    test_steps = config_loader.filter_steps_by_variant("test")
    assert len(test_steps) == 3  # link, copy, and brew_install
    
    # Filter for non-existent variant
    other_steps = config_loader.filter_steps_by_variant("other")
    assert len(other_steps) == 0


def test_filter_steps_by_platform(config_loader):
    """Test filtering steps by platform."""
    config = config_loader.load()
    
    # Filter for macOS platform
    macos_steps = config_loader.filter_steps_by_platform(Platform.MACOS)
    assert len(macos_steps) == 3  # Only brew_install has platform restriction
    
    # Filter for Linux platform
    linux_steps = config_loader.filter_steps_by_platform(Platform.LINUX)
    assert len(linux_steps) == 2  # link and copy have no platform restriction


def test_get_safety_settings(config_loader):
    """Test getting safety settings with defaults."""
    config = config_loader.load()
    safety = config_loader.get_safety_settings()
    
    # Check loaded values
    assert safety["dry_run_default"] is True
    assert safety["backup_before_modify"] is True
    assert safety["backup_retention_days"] == 7
    
    # Check defaults from Pydantic model
    assert safety["max_operations"] == 1000
    assert safety["require_confirmation"] is True


def test_step_missing_required_field(tmp_path):
    """Test validation with step missing required field."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text("""
[package]
name = "test"
version = "1.0.0"

[safety]
dry_run_default = true

[[step]]
op = "link"
src = "test"
# Missing dst
""")
    
    loader = ConfigLoader(config_toml)
    with pytest.raises(ConfigValidationError) as exc_info:
        loader.load()
    
    assert "validation failed" in str(exc_info.value).lower()


def test_conflicting_whitelist_blacklist(tmp_path):
    """Test validation with overlapping whitelist and blacklist."""
    config_toml = tmp_path / "config.toml"
    config_toml.write_text("""
[package]
name = "test"
version = "1.0.0"

[safety]
dry_run_default = true

[security]
whitelist_paths = ["/etc", "/usr"]
blacklist_paths = ["/etc", "/home"]
""")
    
    loader = ConfigLoader(config_toml)
    with pytest.raises(ConfigValidationError) as exc_info:
        loader.load()
    
    error_msg = str(exc_info.value).lower()
    assert "validation failed" in error_msg or "overlap" in error_msg


def test_reload_configuration(config_loader):
    """Test reloading configuration from disk."""
    # Load initial config
    config1 = config_loader.load()
    assert config1.package.name == "test-dotfiles"
    
    # Reload should work
    config2 = config_loader.reload()
    assert config2.package.name == "test-dotfiles"
    assert config2 is not config1  # Should be a new instance


def test_get_raw_data(config_loader):
    """Test getting raw TOML data."""
    config = config_loader.load()
    raw_data = config_loader.get_raw_data()
    
    assert raw_data is not None
    assert isinstance(raw_data, dict)
    assert "package" in raw_data
    assert raw_data["package"]["name"] == "test-dotfiles"