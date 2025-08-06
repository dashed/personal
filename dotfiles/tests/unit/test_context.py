"""Unit tests for the context module with Pydantic models."""

import pytest
from pathlib import Path
from dotfiles_sync.models import SystemInfo, ExecutionContext, OperationType, Platform, StepConfig
from dotfiles_sync.context import OperationContext


def test_system_info_initialization():
    """Test SystemInfo initialization from current system."""
    info = SystemInfo.from_current_system()
    
    # Check that fields are populated
    assert info.hostname
    assert info.username
    assert info.platform in [Platform.MACOS, Platform.LINUX, Platform.WINDOWS]
    assert info.arch in ["x86_64", "arm64", "i386", "unknown"]
    assert info.python_version


def test_system_info_platform_matching():
    """Test platform matching logic."""
    info = SystemInfo.from_current_system()
    
    # Test with current platform
    assert info.matches_platform([info.platform])
    assert info.matches_platform([Platform.ALL])
    assert not info.matches_platform([])
    
    # Test with multiple platforms
    assert info.matches_platform([Platform.WINDOWS, Platform.LINUX, Platform.MACOS])


def test_execution_context_initialization():
    """Test ExecutionContext initialization with Pydantic."""
    ctx = ExecutionContext(
        config_path=Path("test.toml"),
        variant="test",
        dry_run=False,
        force=True
    )
    
    assert ctx.config_path == Path("test.toml").resolve()
    assert ctx.variant == "test"
    assert ctx.dry_run is False
    assert ctx.force is True
    assert ctx.system_info is not None


def test_execution_context_path_expansion(tmp_path):
    """Test path expansion in ExecutionContext."""
    config_file = tmp_path / "config.toml"
    config_file.touch()
    
    ctx = ExecutionContext(config_path=config_file)
    
    # Test home directory expansion
    home_path = ctx.expand_path("~/.config/test")
    assert str(home_path).startswith(str(Path.home()))
    assert not str(home_path).startswith("~")
    
    # Test relative path (relative to config directory)
    rel_path = ctx.expand_path("relative/path")
    assert rel_path == (tmp_path / "relative" / "path").resolve()
    
    # Test absolute path
    abs_path = ctx.expand_path("/absolute/path")
    assert abs_path == Path("/absolute/path").resolve()


def test_operation_context_initialization():
    """Test OperationContext initialization with Pydantic models."""
    exec_ctx = ExecutionContext(config_path=Path("test.toml"))
    step_config = StepConfig(
        op=OperationType.LINK,
        src="source",
        dst="destination"
    )
    
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="link",
        step_config=step_config,
        sequence_num=1
    )
    
    assert op_ctx.operation_type == "link"
    assert op_ctx.step_config == step_config
    assert op_ctx.sequence_num == 1


def test_operation_context_paths(tmp_path):
    """Test getting source and destination paths."""
    config_file = tmp_path / "config.toml"
    config_file.touch()
    
    exec_ctx = ExecutionContext(config_path=config_file)
    step_config = StepConfig(
        op=OperationType.LINK,
        src="source/file",
        dst="~/.config/target"
    )
    
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="link",
        step_config=step_config,
        sequence_num=1
    )
    
    # Get paths
    src_path = op_ctx.get_src_path()
    dst_path = op_ctx.get_dst_path()
    
    assert src_path == (tmp_path / "source" / "file").resolve()
    assert str(dst_path).startswith(str(Path.home()))
    assert ".config/target" in str(dst_path)


def test_operation_context_no_paths():
    """Test operations without src/dst paths."""
    exec_ctx = ExecutionContext(config_path=Path("test.toml"))
    step_config = StepConfig(
        op=OperationType.BREW_INSTALL,
        packages=["git"]
    )
    
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="brew_install",
        step_config=step_config,
        sequence_num=1
    )
    
    assert op_ctx.get_src_path() is None
    assert op_ctx.get_dst_path() is None


def test_operation_context_should_create_backup(tmp_path):
    """Test backup creation logic."""
    config_file = tmp_path / "config.toml"
    config_file.touch()
    
    # Create a destination file that exists
    existing_file = tmp_path / "existing.txt"
    existing_file.touch()
    
    # Test with dry run (should not backup)
    exec_ctx_dry = ExecutionContext(config_path=config_file, dry_run=True)
    step_config = StepConfig(
        op=OperationType.LINK,
        src="source",
        dst=str(existing_file)
    )
    op_ctx = OperationContext(
        execution_context=exec_ctx_dry,
        operation_type="link",
        step_config=step_config,
        sequence_num=1
    )
    assert not op_ctx.should_create_backup()
    
    # Test with apply mode and existing file (should backup)
    exec_ctx_apply = ExecutionContext(config_path=config_file, dry_run=False)
    op_ctx = OperationContext(
        execution_context=exec_ctx_apply,
        operation_type="link",
        step_config=step_config,
        sequence_num=1
    )
    assert op_ctx.should_create_backup()
    
    # Test with non-modifying operation (should not backup)
    step_config_brew = StepConfig(
        op=OperationType.BREW_INSTALL,
        packages=["git"]
    )
    op_ctx_brew = OperationContext(
        execution_context=exec_ctx_apply,
        operation_type="brew_install",
        step_config=step_config_brew,
        sequence_num=2
    )
    assert not op_ctx_brew.should_create_backup()


def test_operation_context_should_skip_platform():
    """Test platform skip logic."""
    exec_ctx = ExecutionContext(config_path=Path("test.toml"))
    current_platform = exec_ctx.system_info.platform
    
    # Operation with no platform restriction
    step_no_platform = StepConfig(
        op=OperationType.LINK,
        src="test",
        dst="test"
    )
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="link",
        step_config=step_no_platform,
        sequence_num=1
    )
    assert not op_ctx.should_skip_platform()
    
    # Operation for current platform
    step_current = StepConfig(
        op=OperationType.LINK,
        src="test",
        dst="test",
        platforms=[current_platform]
    )
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="link",
        step_config=step_current,
        sequence_num=2
    )
    assert not op_ctx.should_skip_platform()
    
    # Operation for different platform
    other_platform = Platform.WINDOWS if current_platform != Platform.WINDOWS else Platform.LINUX
    step_other = StepConfig(
        op=OperationType.LINK,
        src="test",
        dst="test",
        platforms=[other_platform]
    )
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="link",
        step_config=step_other,
        sequence_num=3
    )
    assert op_ctx.should_skip_platform()


def test_operation_context_should_skip_variant():
    """Test variant skip logic."""
    exec_ctx = ExecutionContext(config_path=Path("test.toml"), variant="personal")
    
    # Operation for current variant
    step_personal = StepConfig(
        op=OperationType.LINK,
        src="test",
        dst="test",
        variants=["personal", "work"]
    )
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="link",
        step_config=step_personal,
        sequence_num=1
    )
    assert not op_ctx.should_skip_variant()
    
    # Operation for all variants
    step_all = StepConfig(
        op=OperationType.LINK,
        src="test",
        dst="test",
        variants=["all"]
    )
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="link",
        step_config=step_all,
        sequence_num=2
    )
    assert not op_ctx.should_skip_variant()
    
    # Operation for different variant
    step_work = StepConfig(
        op=OperationType.LINK,
        src="test",
        dst="test",
        variants=["work"]
    )
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="link",
        step_config=step_work,
        sequence_num=3
    )
    assert op_ctx.should_skip_variant()


def test_operation_context_get_rollback_data():
    """Test rollback data generation."""
    exec_ctx = ExecutionContext(config_path=Path("test.toml"))
    step_config = StepConfig(
        op=OperationType.LINK,
        src="source/file",
        dst="dest/file"
    )
    
    op_ctx = OperationContext(
        execution_context=exec_ctx,
        operation_type="link",
        step_config=step_config,
        sequence_num=5
    )
    
    rollback_data = op_ctx.get_rollback_data()
    
    assert rollback_data["operation_type"] == "link"
    assert rollback_data["sequence_num"] == 5
    assert "src_path" in rollback_data
    assert "dst_path" in rollback_data


def test_execution_context_frozen():
    """Test that certain Pydantic models are frozen (immutable)."""
    info = SystemInfo.from_current_system()
    
    # SystemInfo should be frozen
    with pytest.raises(Exception):  # Pydantic raises ValidationError for frozen models
        info.hostname = "new_hostname"