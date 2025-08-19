"""Unit tests for the syncdir verb."""

import pytest
from unittest.mock import Mock

from dotfiles_sync.models import StepConfig, OperationType, ExecutionContext, SystemInfo
from dotfiles_sync.context import OperationContext
from verbs.syncdir import SyncDirVerb


@pytest.fixture
def syncdir_verb():
    """Create a SyncDirVerb instance."""
    return SyncDirVerb()


@pytest.fixture
def mock_context(tmp_path):
    """Create a mock operation context."""
    exec_ctx = Mock(spec=ExecutionContext)
    exec_ctx.config_path = tmp_path / "dotfiles.toml"
    exec_ctx.variant = "test"
    exec_ctx.dry_run = False
    exec_ctx.system_info = Mock(spec=SystemInfo)
    exec_ctx.system_info.username = "testuser"
    exec_ctx.system_info.hostname = "testhost"

    op_ctx = Mock(spec=OperationContext)
    op_ctx.execution_context = exec_ctx
    op_ctx.operation_type = "syncdir"
    op_ctx.sequence_num = 1

    return op_ctx


def test_syncdir_validate_missing_src(syncdir_verb, mock_context):
    """Test validation with missing source."""
    # StepConfig validates required fields, so we need to provide dummy values
    # and then clear them to test our validation
    step = StepConfig(op=OperationType.SYNCDIR, src="dummy", dst="dest")
    step.src = None  # Clear to test validation
    errors = syncdir_verb.validate(step, mock_context)
    assert "Source directory is required" in errors[0]


def test_syncdir_validate_missing_dst(syncdir_verb, mock_context):
    """Test validation with missing destination."""
    # StepConfig validates required fields, so we need to provide dummy values
    # and then clear them to test our validation
    step = StepConfig(op=OperationType.SYNCDIR, src="source", dst="dummy")
    step.dst = None  # Clear to test validation
    errors = syncdir_verb.validate(step, mock_context)
    assert "Destination directory is required" in errors[0]


def test_syncdir_validate_src_not_exists(syncdir_verb, mock_context, tmp_path):
    """Test validation when source doesn't exist."""
    step = StepConfig(op=OperationType.SYNCDIR, src="nonexistent", dst="dest")
    mock_context.get_src_path = Mock(return_value=tmp_path / "nonexistent")

    errors = syncdir_verb.validate(step, mock_context)
    assert "Source directory does not exist" in errors[0]


def test_syncdir_dry_run_success(syncdir_verb, mock_context, tmp_path):
    """Test successful dry run."""
    # Create source directory with files
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    (src_dir / "file1.txt").write_text("content1")
    (src_dir / "file2.txt").write_text("content2")

    dst_dir = tmp_path / "dest"

    step = StepConfig(op=OperationType.SYNCDIR, src=str(src_dir), dst=str(dst_dir))
    mock_context.get_src_path = Mock(return_value=src_dir)
    mock_context.get_dst_path = Mock(return_value=dst_dir)

    result = syncdir_verb.dry_run(step, mock_context)

    assert result.success
    assert "Would sync 2 files" in result.message
    assert result.dry_run


def test_syncdir_dry_run_size_limit(syncdir_verb, mock_context, tmp_path):
    """Test dry run with size limit exceeded."""
    # Create source directory with large file
    src_dir = tmp_path / "source"
    src_dir.mkdir()

    # Create a mock large file
    large_file = src_dir / "large.bin"
    large_file.write_bytes(b"x" * (101 * 1024 * 1024))  # 101MB

    dst_dir = tmp_path / "dest"

    step = StepConfig(op=OperationType.SYNCDIR, src=str(src_dir), dst=str(dst_dir))
    mock_context.get_src_path = Mock(return_value=src_dir)
    mock_context.get_dst_path = Mock(return_value=dst_dir)

    result = syncdir_verb.dry_run(step, mock_context)

    assert not result.success
    assert "exceeds limit" in result.message


def test_syncdir_apply_success(syncdir_verb, mock_context, tmp_path):
    """Test successful apply operation."""
    # Create source directory with files
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    (src_dir / "file1.txt").write_text("content1")
    (src_dir / "subdir").mkdir()
    (src_dir / "subdir" / "file2.txt").write_text("content2")

    dst_dir = tmp_path / "dest"

    step = StepConfig(op=OperationType.SYNCDIR, src=str(src_dir), dst=str(dst_dir))
    mock_context.get_src_path = Mock(return_value=src_dir)
    mock_context.get_dst_path = Mock(return_value=dst_dir)

    result = syncdir_verb.apply(step, mock_context)

    assert result.success
    assert "Synced 2 files" in result.message
    assert not result.dry_run
    assert result.rollback_data is not None

    # Verify files were copied
    assert (dst_dir / "file1.txt").exists()
    assert (dst_dir / "file1.txt").read_text() == "content1"
    assert (dst_dir / "subdir" / "file2.txt").exists()
    assert (dst_dir / "subdir" / "file2.txt").read_text() == "content2"


def test_syncdir_apply_with_exclude(syncdir_verb, mock_context, tmp_path):
    """Test apply with exclude patterns."""
    # Create source directory with files
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    (src_dir / "file1.txt").write_text("content1")
    (src_dir / "file2.log").write_text("log content")
    (src_dir / "file3.txt").write_text("content3")

    dst_dir = tmp_path / "dest"

    step = StepConfig(
        op=OperationType.SYNCDIR, src=str(src_dir), dst=str(dst_dir), exclude=["*.log"]
    )
    mock_context.get_src_path = Mock(return_value=src_dir)
    mock_context.get_dst_path = Mock(return_value=dst_dir)

    result = syncdir_verb.apply(step, mock_context)

    assert result.success
    assert "Synced 2 files" in result.message

    # Verify .log file was excluded
    assert (dst_dir / "file1.txt").exists()
    assert (dst_dir / "file3.txt").exists()
    assert not (dst_dir / "file2.log").exists()


def test_syncdir_rollback(syncdir_verb, mock_context, tmp_path):
    """Test rollback operation."""
    # Create files that were "created"
    dst_dir = tmp_path / "dest"
    dst_dir.mkdir()
    file1 = dst_dir / "file1.txt"
    file1.write_text("content")
    file2 = dst_dir / "file2.txt"
    file2.write_text("content")

    step = StepConfig(op=OperationType.SYNCDIR, src="source", dst=str(dst_dir))

    rollback_data = {"created_files": [str(file1), str(file2)], "dst_path": str(dst_dir)}

    success = syncdir_verb.rollback(step, mock_context, rollback_data)

    assert success
    assert not file1.exists()
    assert not file2.exists()
    assert dst_dir.exists()  # Directory should remain
