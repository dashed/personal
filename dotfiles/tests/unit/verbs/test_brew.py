"""Unit tests for the brew verb."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from dotfiles_sync.models import StepConfig, OperationType, ExecutionContext, SystemInfo
from dotfiles_sync.context import OperationContext
from verbs.brew import BrewVerb


@pytest.fixture
def brew_verb():
    """Create a BrewVerb instance."""
    return BrewVerb()


@pytest.fixture
def mock_context():
    """Create a mock operation context."""
    exec_ctx = Mock(spec=ExecutionContext)
    exec_ctx.config_path = Path("dotfiles.toml")
    exec_ctx.variant = "test"
    exec_ctx.dry_run = False
    exec_ctx.system_info = Mock(spec=SystemInfo)
    exec_ctx.system_info.platform = "darwin"
    exec_ctx.system_info.username = "testuser"
    exec_ctx.system_info.hostname = "testhost"

    op_ctx = Mock(spec=OperationContext)
    op_ctx.execution_context = exec_ctx
    op_ctx.operation_type = "brew_install"
    op_ctx.sequence_num = 1

    return op_ctx


def test_brew_validate_missing_packages(brew_verb, mock_context):
    """Test validation with missing packages."""
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=[])
    errors = brew_verb.validate(step, mock_context)
    assert any("Packages list is required" in error for error in errors)


def test_brew_validate_wrong_platform(brew_verb, mock_context):
    """Test validation on non-macOS platform."""
    mock_context.execution_context.system_info.platform = "linux"
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=["git"])
    errors = brew_verb.validate(step, mock_context)
    assert any("Homebrew not supported" in error for error in errors)


@patch('verbs.brew.BrewVerb._find_brew')
def test_brew_validate_brew_missing(mock_find_brew, brew_verb, mock_context):
    """Test validation when brew is not installed."""
    mock_find_brew.return_value = None
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=["git"])
    errors = brew_verb.validate(step, mock_context)
    assert any("Homebrew not found" in error for error in errors)


@patch('verbs.brew.BrewVerb._find_brew')
def test_brew_validate_success(mock_find_brew, brew_verb, mock_context):
    """Test successful validation."""
    mock_find_brew.return_value = "/opt/homebrew/bin/brew"
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=["git"])
    errors = brew_verb.validate(step, mock_context)
    assert len(errors) == 0


def test_parse_package_spec_simple(brew_verb):
    """Test parsing simple package specification."""
    spec = brew_verb._parse_package_spec("git")
    assert spec["name"] == "git"
    assert spec["version"] is None
    assert spec["is_cask"] is False
    assert spec["tap"] is None


def test_parse_package_spec_with_version(brew_verb):
    """Test parsing package specification with version."""
    spec = brew_verb._parse_package_spec("node@18")
    assert spec["name"] == "node"
    assert spec["version"] == "18"
    assert spec["is_cask"] is False


def test_parse_package_spec_cask(brew_verb):
    """Test parsing cask specification."""
    spec = brew_verb._parse_package_spec("cask:visual-studio-code")
    assert spec["name"] == "visual-studio-code"
    assert spec["is_cask"] is True


def test_parse_package_spec_with_tap(brew_verb):
    """Test parsing package with custom tap."""
    spec = brew_verb._parse_package_spec("homebrew/cask-fonts/font-fira-code")
    assert spec["name"] == "font-fira-code"
    assert spec["tap"] == "homebrew/cask-fonts"


@patch('verbs.brew.BrewVerb._find_brew')
@patch('verbs.brew.BrewVerb._is_package_installed')
def test_brew_dry_run_new_packages(mock_installed, mock_find_brew, brew_verb, mock_context):
    """Test dry run with new packages to install."""
    mock_find_brew.return_value = "/opt/homebrew/bin/brew"
    mock_installed.return_value = False
    
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=["git", "node"])
    
    result = brew_verb.dry_run(step, mock_context)
    
    assert result.success
    assert "Would install: git, node" in result.message
    assert result.dry_run


@patch('verbs.brew.BrewVerb._find_brew')
@patch('verbs.brew.BrewVerb._is_package_installed')
def test_brew_dry_run_already_installed(mock_installed, mock_find_brew, brew_verb, mock_context):
    """Test dry run with already installed packages."""
    mock_find_brew.return_value = "/opt/homebrew/bin/brew"
    mock_installed.return_value = True
    
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=["git"])
    
    result = brew_verb.dry_run(step, mock_context)
    
    assert result.success
    assert "Already installed: git" in result.message


@patch('verbs.brew.BrewVerb._find_brew')
@patch('verbs.brew.BrewVerb._ensure_brew_installed')
@patch('verbs.brew.BrewVerb._is_package_installed')
@patch('verbs.brew.BrewVerb._install_package')
def test_brew_apply_success(mock_install, mock_installed, mock_ensure_brew, mock_find_brew, brew_verb, mock_context):
    """Test successful brew apply operation."""
    mock_find_brew.return_value = "/opt/homebrew/bin/brew"
    mock_ensure_brew.return_value = True
    mock_installed.return_value = False
    mock_install.return_value = True
    
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=["git"])
    
    result = brew_verb.apply(step, mock_context)
    
    assert result.success
    assert "Installed: git" in result.message
    assert result.rollback_data["original_state"]["installed_packages"] == ["git"]


@patch('verbs.brew.BrewVerb._find_brew')
@patch('verbs.brew.BrewVerb._ensure_brew_installed')
@patch('verbs.brew.BrewVerb._is_package_installed')
def test_brew_apply_already_installed(mock_installed, mock_ensure_brew, mock_find_brew, brew_verb, mock_context):
    """Test brew apply with already installed packages."""
    mock_find_brew.return_value = "/opt/homebrew/bin/brew"
    mock_ensure_brew.return_value = True
    mock_installed.return_value = True
    
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=["git"])
    
    result = brew_verb.apply(step, mock_context)
    
    assert result.success
    assert "Already installed: git" in result.message


@patch('verbs.brew.BrewVerb._find_brew')
@patch('verbs.brew.BrewVerb._ensure_brew_installed')
@patch('verbs.brew.BrewVerb._is_package_installed')
@patch('verbs.brew.BrewVerb._install_package')
def test_brew_apply_install_failure(mock_install, mock_installed, mock_ensure_brew, mock_find_brew, brew_verb, mock_context):
    """Test brew apply with installation failure."""
    mock_find_brew.return_value = "/opt/homebrew/bin/brew"
    mock_ensure_brew.return_value = True
    mock_installed.return_value = False
    mock_install.return_value = False
    
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=["nonexistent"])
    
    result = brew_verb.apply(step, mock_context)
    
    assert not result.success
    assert "Failed: nonexistent" in result.message


@patch('verbs.brew.BrewVerb._find_brew')
@patch('verbs.brew.BrewVerb._uninstall_package')
def test_brew_rollback_success(mock_uninstall, mock_find_brew, brew_verb, mock_context):
    """Test successful brew rollback."""
    mock_find_brew.return_value = "/opt/homebrew/bin/brew"
    mock_uninstall.return_value = True
    
    step = StepConfig(op=OperationType.BREW_INSTALL, packages=["git"])
    rollback_data = {
        "original_state": {"installed_packages": ["git"]}
    }
    
    success = brew_verb.rollback(step, mock_context, rollback_data)
    
    assert success
    mock_uninstall.assert_called_once()


@patch('shutil.which')
def test_find_brew_success(mock_which, brew_verb):
    """Test finding brew executable."""
    mock_which.return_value = "/opt/homebrew/bin/brew"
    
    path = brew_verb._find_brew()
    
    assert path == "/opt/homebrew/bin/brew"


@patch('shutil.which')
def test_find_brew_failure(mock_which, brew_verb):
    """Test when brew is not found."""
    mock_which.side_effect = [None, None]  # Not found in either location
    
    path = brew_verb._find_brew()
    
    assert path is None


@patch('subprocess.run')
def test_is_package_installed_true(mock_run, brew_verb):
    """Test checking if package is installed - returns True."""
    brew_verb.brew_path = "/opt/homebrew/bin/brew"
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "git\n"
    
    package_info = {"name": "git", "version": None, "type": "formula"}
    is_installed = brew_verb._is_package_installed(package_info)
    
    assert is_installed


@patch('subprocess.run')
def test_is_package_installed_false(mock_run, brew_verb):
    """Test checking if package is installed - returns False."""
    brew_verb.brew_path = "/opt/homebrew/bin/brew"
    mock_run.return_value.returncode = 1
    
    package_info = {"name": "nonexistent", "version": None, "type": "formula"}
    is_installed = brew_verb._is_package_installed(package_info)
    
    assert not is_installed


@patch('subprocess.run')
def test_install_package_success(mock_run, brew_verb):
    """Test successful package installation."""
    brew_verb.brew_path = "/opt/homebrew/bin/brew"
    mock_run.return_value.returncode = 0
    
    package_info = {
        "name": "git", 
        "version": None, 
        "is_cask": False, 
        "tap": None,
        "original_spec": "git"
    }
    success = brew_verb._install_package(package_info)
    
    assert success


@patch('subprocess.run')
def test_install_cask_package(mock_run, brew_verb):
    """Test cask package installation."""
    brew_verb.brew_path = "/opt/homebrew/bin/brew"
    mock_run.return_value.returncode = 0
    
    package_info = {
        "name": "visual-studio-code", 
        "is_cask": True, 
        "tap": None,
        "original_spec": "cask:visual-studio-code"
    }
    success = brew_verb._install_package(package_info)
    
    assert success
    # Verify correct command is called for cask
    args, kwargs = mock_run.call_args
    assert "install" in args[0]
    assert "--cask" in args[0]


@patch('subprocess.run')
def test_ensure_brew_installed_already_exists(mock_run, brew_verb):
    """Test ensuring brew is installed when it already exists."""
    brew_verb.brew_path = "/opt/homebrew/bin/brew"
    
    result = brew_verb._ensure_brew_installed()
    
    assert result  # Should return True since brew_path is set
    mock_run.assert_not_called()  # Should not try to install


@patch('subprocess.run')
@patch('verbs.brew.BrewVerb._find_brew')
def test_auto_install_brew(mock_find_brew, mock_run, brew_verb):
    """Test automatic brew installation."""
    # First call returns None (not found), second returns path (found after install)
    mock_find_brew.side_effect = [None, "/opt/homebrew/bin/brew"]
    mock_run.return_value.returncode = 0
    
    result = brew_verb._ensure_brew_installed()
    
    assert result
    mock_run.assert_called_once()  # Should call install script