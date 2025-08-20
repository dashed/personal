"""Unit tests for the apt verb."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from dotfiles_sync.models import StepConfig, OperationType, ExecutionContext, SystemInfo
from dotfiles_sync.context import OperationContext
from verbs.apt import AptVerb


@pytest.fixture
def apt_verb():
    """Create an AptVerb instance."""
    return AptVerb()


@pytest.fixture
def mock_context():
    """Create a mock operation context."""
    exec_ctx = Mock(spec=ExecutionContext)
    exec_ctx.config_path = Path("dotfiles.toml")
    exec_ctx.variant = "test"
    exec_ctx.dry_run = False
    exec_ctx.system_info = Mock(spec=SystemInfo)
    exec_ctx.system_info.platform = "linux"
    exec_ctx.system_info.username = "testuser"
    exec_ctx.system_info.hostname = "testhost"

    op_ctx = Mock(spec=OperationContext)
    op_ctx.execution_context = exec_ctx
    op_ctx.operation_type = "apt_install"
    op_ctx.sequence_num = 1

    return op_ctx


def test_apt_validate_missing_packages(apt_verb, mock_context):
    """Test validation with missing packages."""
    step = StepConfig(op=OperationType.APT_INSTALL, packages=[])
    errors = apt_verb.validate(step, mock_context)
    assert any("Packages list is required" in error for error in errors)


def test_apt_validate_wrong_platform(apt_verb, mock_context):
    """Test validation on non-Linux platform."""
    mock_context.execution_context.system_info.platform = "darwin"
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git"])
    errors = apt_verb.validate(step, mock_context)
    assert any("APT not supported on platform" in error for error in errors)


@patch('verbs.apt.AptVerb._find_apt')
def test_apt_validate_apt_missing(mock_find_apt, apt_verb, mock_context):
    """Test validation when apt is not found."""
    mock_find_apt.return_value = None
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git"])
    errors = apt_verb.validate(step, mock_context)
    assert any("APT not found" in error for error in errors)


@patch('verbs.apt.AptVerb._find_apt')
@patch('verbs.apt.AptVerb._can_use_sudo')
def test_apt_validate_sudo_required_but_unavailable(mock_can_sudo, mock_find_apt, apt_verb, mock_context):
    """Test validation when sudo is required but not available."""
    mock_find_apt.return_value = "/usr/bin/apt-get"
    mock_can_sudo.return_value = False
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git"], sudo=True)
    errors = apt_verb.validate(step, mock_context)
    assert any("Sudo access required but not available" in error for error in errors)


@patch('verbs.apt.AptVerb._find_apt')
def test_apt_validate_success(mock_find_apt, apt_verb, mock_context):
    """Test successful validation."""
    mock_find_apt.return_value = "/usr/bin/apt-get"
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git"])
    errors = apt_verb.validate(step, mock_context)
    assert len(errors) == 0


def test_parse_package_spec_simple(apt_verb):
    """Test parsing simple package specification."""
    spec = apt_verb._parse_package_spec("git")
    assert spec["name"] == "git"
    assert spec["version"] is None
    assert spec["original_spec"] == "git"


def test_parse_package_spec_with_version(apt_verb):
    """Test parsing package specification with version."""
    spec = apt_verb._parse_package_spec("git=2.34.1")
    assert spec["name"] == "git"
    assert spec["version"] == "2.34.1"
    assert spec["original_spec"] == "git=2.34.1"


@patch('verbs.apt.AptVerb._find_apt')
@patch('verbs.apt.AptVerb._is_package_installed')
def test_apt_dry_run_new_packages(mock_installed, mock_find_apt, apt_verb, mock_context):
    """Test dry run with new packages to install."""
    mock_find_apt.return_value = "/usr/bin/apt-get"
    mock_installed.return_value = False
    
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git", "curl"])
    
    result = apt_verb.dry_run(step, mock_context)
    
    assert result.success
    assert "Would install: git, curl" in result.message
    assert result.dry_run


@patch('verbs.apt.AptVerb._find_apt')
@patch('verbs.apt.AptVerb._is_package_installed')
def test_apt_dry_run_already_installed(mock_installed, mock_find_apt, apt_verb, mock_context):
    """Test dry run with already installed packages."""
    mock_find_apt.return_value = "/usr/bin/apt-get"
    mock_installed.return_value = True
    
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git"])
    
    result = apt_verb.dry_run(step, mock_context)
    
    assert result.success
    assert "Already installed: git" in result.message


@patch('verbs.apt.AptVerb._find_apt')
@patch('verbs.apt.AptVerb._update_cache_if_needed')
@patch('verbs.apt.AptVerb._is_package_installed')
@patch('verbs.apt.AptVerb._install_package')
def test_apt_apply_success(mock_install, mock_installed, mock_update, mock_find_apt, apt_verb, mock_context):
    """Test successful apt apply operation."""
    mock_find_apt.return_value = "/usr/bin/apt-get"
    mock_update.return_value = True
    mock_installed.return_value = False
    mock_install.return_value = True
    
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git"])
    
    result = apt_verb.apply(step, mock_context)
    
    assert result.success
    assert "Installed: git" in result.message
    assert result.rollback_data["original_state"]["installed_packages"] == ["git"]


@patch('verbs.apt.AptVerb._find_apt')
@patch('verbs.apt.AptVerb._update_cache_if_needed')
@patch('verbs.apt.AptVerb._is_package_installed')
def test_apt_apply_already_installed(mock_installed, mock_update, mock_find_apt, apt_verb, mock_context):
    """Test apt apply with already installed packages."""
    mock_find_apt.return_value = "/usr/bin/apt-get"
    mock_update.return_value = True
    mock_installed.return_value = True
    
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git"])
    
    result = apt_verb.apply(step, mock_context)
    
    assert result.success
    assert "Already installed: git" in result.message


@patch('verbs.apt.AptVerb._find_apt')
@patch('verbs.apt.AptVerb._update_cache_if_needed')
@patch('verbs.apt.AptVerb._is_package_installed')
@patch('verbs.apt.AptVerb._install_package')
def test_apt_apply_install_failure(mock_install, mock_installed, mock_update, mock_find_apt, apt_verb, mock_context):
    """Test apt apply with installation failure."""
    mock_find_apt.return_value = "/usr/bin/apt-get"
    mock_update.return_value = True
    mock_installed.return_value = False
    mock_install.return_value = False
    
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["nonexistent"])
    
    result = apt_verb.apply(step, mock_context)
    
    assert not result.success
    assert "Failed: nonexistent" in result.message


@patch('verbs.apt.AptVerb._find_apt')
@patch('verbs.apt.AptVerb._uninstall_package')
def test_apt_rollback_success(mock_uninstall, mock_find_apt, apt_verb, mock_context):
    """Test successful apt rollback."""
    mock_find_apt.return_value = "/usr/bin/apt-get"
    mock_uninstall.return_value = True
    
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git"])
    rollback_data = {
        "original_state": {"installed_packages": ["git"]}
    }
    
    success = apt_verb.rollback(step, mock_context, rollback_data)
    
    assert success
    mock_uninstall.assert_called_once()


@patch('verbs.apt.AptVerb._find_apt')
def test_apt_rollback_no_packages(mock_find_apt, apt_verb, mock_context):
    """Test rollback with no packages to uninstall."""
    mock_find_apt.return_value = "/usr/bin/apt-get"
    
    step = StepConfig(op=OperationType.APT_INSTALL, packages=["git"])
    rollback_data = {
        "original_state": {"installed_packages": []}
    }
    
    success = apt_verb.rollback(step, mock_context, rollback_data)
    
    assert success  # Should succeed with no work to do


@patch('shutil.which')
def test_find_apt_success_apt_get(mock_which, apt_verb):
    """Test finding apt-get executable."""
    mock_which.side_effect = ["/usr/bin/apt-get", None]  # apt-get found, apt not checked
    
    path = apt_verb._find_apt()
    
    assert path == "/usr/bin/apt-get"


@patch('shutil.which')
def test_find_apt_success_apt(mock_which, apt_verb):
    """Test finding apt executable when apt-get not found."""
    mock_which.side_effect = [None, "/usr/bin/apt"]  # apt-get not found, apt found
    
    path = apt_verb._find_apt()
    
    assert path == "/usr/bin/apt"


@patch('shutil.which')
def test_find_apt_failure(mock_which, apt_verb):
    """Test when neither apt-get nor apt is found."""
    mock_which.side_effect = [None, None]  # Neither found
    
    path = apt_verb._find_apt()
    
    assert path is None


@patch('shutil.which')
@patch('subprocess.run')
def test_can_use_sudo_success(mock_run, mock_which, apt_verb):
    """Test successful sudo availability check."""
    mock_which.return_value = "/usr/bin/sudo"
    mock_run.return_value.returncode = 0
    
    can_sudo = apt_verb._can_use_sudo()
    
    assert can_sudo


@patch('shutil.which')
def test_can_use_sudo_not_found(mock_which, apt_verb):
    """Test sudo not found."""
    mock_which.return_value = None
    
    can_sudo = apt_verb._can_use_sudo()
    
    assert not can_sudo


@patch('shutil.which')
@patch('subprocess.run')
def test_can_use_sudo_permission_denied(mock_run, mock_which, apt_verb):
    """Test sudo available but permission denied."""
    mock_which.return_value = "/usr/bin/sudo"
    mock_run.return_value.returncode = 1  # Permission denied
    
    can_sudo = apt_verb._can_use_sudo()
    
    assert not can_sudo


@patch('subprocess.run')
def test_is_package_installed_true(mock_run, apt_verb):
    """Test checking if package is installed - returns True."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "ii  git  1:2.34.1  all  fast, scalable version control"
    
    package_info = {"name": "git", "version": None}
    is_installed = apt_verb._is_package_installed(package_info)
    
    assert is_installed


@patch('subprocess.run')
def test_is_package_installed_false(mock_run, apt_verb):
    """Test checking if package is installed - returns False."""
    mock_run.return_value.returncode = 1  # Package not found
    
    package_info = {"name": "nonexistent", "version": None}
    is_installed = apt_verb._is_package_installed(package_info)
    
    assert not is_installed


@patch('subprocess.run')
def test_is_package_installed_with_version(mock_run, apt_verb):
    """Test checking if specific version is installed."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "ii  git  1:2.34.1  all  fast, scalable version control"
    
    package_info = {"name": "git", "version": "2.34.1"}
    is_installed = apt_verb._is_package_installed(package_info)
    
    assert is_installed


@patch('subprocess.run')
def test_install_package_success(mock_run, apt_verb):
    """Test successful package installation."""
    apt_verb.apt_path = "/usr/bin/apt-get"
    mock_run.return_value.returncode = 0
    
    package_info = {"name": "git", "original_spec": "git"}
    success = apt_verb._install_package(package_info, use_sudo=False)
    
    assert success


@patch('subprocess.run')
def test_install_package_with_sudo(mock_run, apt_verb):
    """Test package installation with sudo."""
    apt_verb.apt_path = "/usr/bin/apt-get"
    mock_run.return_value.returncode = 0
    
    package_info = {"name": "git", "original_spec": "git"}
    success = apt_verb._install_package(package_info, use_sudo=True)
    
    assert success
    # Verify sudo is used in command
    args, kwargs = mock_run.call_args
    assert "sudo" in args[0]


@patch('subprocess.run')
def test_install_package_failure(mock_run, apt_verb):
    """Test package installation failure."""
    apt_verb.apt_path = "/usr/bin/apt-get"
    mock_run.return_value.returncode = 1
    mock_run.return_value.stderr = "Package not found"
    
    package_info = {"name": "nonexistent", "original_spec": "nonexistent"}
    success = apt_verb._install_package(package_info, use_sudo=False)
    
    assert not success


@patch('subprocess.run')
def test_uninstall_package_success(mock_run, apt_verb):
    """Test successful package uninstallation."""
    apt_verb.apt_path = "/usr/bin/apt-get"
    mock_run.return_value.returncode = 0
    
    package_info = {"name": "git"}
    success = apt_verb._uninstall_package(package_info, use_sudo=False)
    
    assert success


@patch('subprocess.run')
def test_uninstall_package_failure(mock_run, apt_verb):
    """Test package uninstallation failure."""
    apt_verb.apt_path = "/usr/bin/apt-get"
    mock_run.return_value.returncode = 1
    
    package_info = {"name": "git"}
    success = apt_verb._uninstall_package(package_info, use_sudo=False)
    
    assert not success


@patch('pathlib.Path.exists')
@patch('pathlib.Path.stat')
@patch('time.time')
@patch('subprocess.run')
def test_update_cache_if_needed_fresh_cache(mock_run, mock_time, mock_stat, mock_exists, apt_verb):
    """Test cache update when cache is fresh."""
    apt_verb.apt_path = "/usr/bin/apt-get"
    mock_exists.return_value = True
    mock_time.return_value = 1000000
    mock_stat.return_value.st_mtime = 999500  # Cache is 8.33 minutes old (less than 1 hour)
    
    result = apt_verb._update_cache_if_needed(use_sudo=False)
    
    assert result
    mock_run.assert_not_called()  # Should not update cache


@patch('pathlib.Path.exists')
@patch('pathlib.Path.stat')
@patch('time.time')
@patch('subprocess.run')
def test_update_cache_if_needed_stale_cache(mock_run, mock_time, mock_stat, mock_exists, apt_verb):
    """Test cache update when cache is stale."""
    apt_verb.apt_path = "/usr/bin/apt-get"
    mock_exists.return_value = True
    mock_time.return_value = 1000000
    mock_stat.return_value.st_mtime = 996000  # Cache is more than 1 hour old
    mock_run.return_value.returncode = 0
    
    result = apt_verb._update_cache_if_needed(use_sudo=False)
    
    assert result
    mock_run.assert_called_once()  # Should update cache


@patch('pathlib.Path.exists')
@patch('subprocess.run')
def test_update_cache_if_needed_no_cache_file(mock_run, mock_exists, apt_verb):
    """Test cache update when cache file doesn't exist."""
    apt_verb.apt_path = "/usr/bin/apt-get"
    mock_exists.return_value = False
    mock_run.return_value.returncode = 0
    
    result = apt_verb._update_cache_if_needed(use_sudo=False)
    
    assert result
    mock_run.assert_called_once()  # Should update cache