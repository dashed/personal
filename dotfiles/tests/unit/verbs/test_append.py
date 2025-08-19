"""Unit tests for the append verb."""

import pytest
from unittest.mock import Mock

from dotfiles_sync.models import StepConfig, OperationType, ExecutionContext, SystemInfo
from dotfiles_sync.context import OperationContext
from verbs.append import AppendVerb


@pytest.fixture
def append_verb():
    """Create an AppendVerb instance."""
    return AppendVerb()


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
    op_ctx.operation_type = "append"
    op_ctx.sequence_num = 1

    return op_ctx


def test_append_validate_missing_text(append_verb, mock_context):
    """Test validation with missing text."""
    # StepConfig validates required fields, so we need to provide dummy values
    # and then clear them to test our validation
    step = StepConfig(op=OperationType.APPEND, text="dummy", dst="file.txt")
    step.text = None  # Clear to test validation
    errors = append_verb.validate(step, mock_context)
    assert "Text is required" in errors[0]


def test_append_validate_missing_dst(append_verb, mock_context):
    """Test validation with missing destination."""
    # StepConfig validates required fields, so we need to provide dummy values
    # and then clear them to test our validation
    step = StepConfig(op=OperationType.APPEND, text="some text", dst="dummy")
    step.dst = None  # Clear to test validation
    errors = append_verb.validate(step, mock_context)
    assert "Destination file is required" in errors[0]


def test_append_dry_run_new_file(append_verb, mock_context, tmp_path):
    """Test dry run with new file."""
    dst_file = tmp_path / "newfile.txt"

    step = StepConfig(op=OperationType.APPEND, text="appended text", dst=str(dst_file))
    mock_context.get_dst_path = Mock(return_value=dst_file)

    result = append_verb.dry_run(step, mock_context)

    assert result.success
    assert "Would create" in result.message
    assert "and append 13 characters" in result.message
    assert result.dry_run


def test_append_dry_run_existing_file(append_verb, mock_context, tmp_path):
    """Test dry run with existing file."""
    dst_file = tmp_path / "existing.txt"
    dst_file.write_text("original content\n")

    step = StepConfig(op=OperationType.APPEND, text="appended text", dst=str(dst_file))
    mock_context.get_dst_path = Mock(return_value=dst_file)

    result = append_verb.dry_run(step, mock_context)

    assert result.success
    assert "Would append 13 characters" in result.message
    assert result.dry_run


def test_append_dry_run_marker_exists(append_verb, mock_context, tmp_path):
    """Test dry run with marker already present."""
    dst_file = tmp_path / "marked.txt"
    dst_file.write_text("# BEGIN_CUSTOM\nsome content\n")

    step = StepConfig(
        op=OperationType.APPEND, text="new text", dst=str(dst_file), marker="BEGIN_CUSTOM"
    )
    mock_context.get_dst_path = Mock(return_value=dst_file)

    result = append_verb.dry_run(step, mock_context)

    assert result.success
    assert result.skipped
    assert "already exists" in result.message


def test_append_apply_new_file(append_verb, mock_context, tmp_path):
    """Test apply with new file."""
    dst_file = tmp_path / "newfile.txt"

    step = StepConfig(op=OperationType.APPEND, text="appended text", dst=str(dst_file))
    mock_context.get_dst_path = Mock(return_value=dst_file)

    result = append_verb.apply(step, mock_context)

    assert result.success
    assert "Appended text" in result.message
    assert not result.dry_run
    assert dst_file.exists()
    assert dst_file.read_text() == "appended text"

    # Check rollback data
    assert result.rollback_data["file_existed"] is False
    assert result.rollback_data["dst_path"] == str(dst_file)


def test_append_apply_existing_file(append_verb, mock_context, tmp_path):
    """Test apply with existing file."""
    dst_file = tmp_path / "existing.txt"
    original = "original content"
    dst_file.write_text(original)

    step = StepConfig(op=OperationType.APPEND, text="appended text", dst=str(dst_file))
    mock_context.get_dst_path = Mock(return_value=dst_file)

    result = append_verb.apply(step, mock_context)

    assert result.success
    assert dst_file.read_text() == "original content\nappended text"

    # Check rollback data
    assert result.rollback_data["file_existed"] is True
    assert result.rollback_data["original_content"] == original


def test_append_apply_with_marker(append_verb, mock_context, tmp_path):
    """Test apply with marker."""
    dst_file = tmp_path / "marked.txt"
    dst_file.write_text("original\n")

    step = StepConfig(
        op=OperationType.APPEND, text="custom text", dst=str(dst_file), marker="BEGIN_CUSTOM"
    )
    mock_context.get_dst_path = Mock(return_value=dst_file)

    result = append_verb.apply(step, mock_context)

    assert result.success
    content = dst_file.read_text()
    assert "# BEGIN_CUSTOM" in content
    assert "custom text" in content


def test_append_apply_with_mode(append_verb, mock_context, tmp_path):
    """Test apply with file mode setting."""
    dst_file = tmp_path / "moded.txt"

    step = StepConfig(op=OperationType.APPEND, text="text", dst=str(dst_file), mode="0600")
    mock_context.get_dst_path = Mock(return_value=dst_file)

    result = append_verb.apply(step, mock_context)

    assert result.success
    assert dst_file.exists()

    # Check file mode (owner read/write only)
    import stat

    mode = dst_file.stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_append_apply_idempotent_with_marker(append_verb, mock_context, tmp_path):
    """Test idempotency with marker."""
    dst_file = tmp_path / "marked.txt"
    dst_file.write_text("# BEGIN_CUSTOM\nalready added\n")

    step = StepConfig(
        op=OperationType.APPEND, text="new text", dst=str(dst_file), marker="BEGIN_CUSTOM"
    )
    mock_context.get_dst_path = Mock(return_value=dst_file)

    result = append_verb.apply(step, mock_context)

    assert result.success
    assert result.skipped
    assert "already exists" in result.message


def test_append_rollback_new_file(append_verb, mock_context, tmp_path):
    """Test rollback when file was created."""
    dst_file = tmp_path / "newfile.txt"
    dst_file.write_text("appended content")

    step = StepConfig(op=OperationType.APPEND, text="text", dst=str(dst_file))

    rollback_data = {
        "file_existed": False,
        "dst_path": str(dst_file),
        "appended_text": "appended content",
    }

    success = append_verb.rollback(step, mock_context, rollback_data)

    assert success
    assert not dst_file.exists()


def test_append_rollback_existing_file(append_verb, mock_context, tmp_path):
    """Test rollback when file existed."""
    dst_file = tmp_path / "existing.txt"
    dst_file.write_text("original\nappended")

    step = StepConfig(op=OperationType.APPEND, text="text", dst=str(dst_file))

    rollback_data = {
        "file_existed": True,
        "original_content": "original",
        "dst_path": str(dst_file),
        "appended_text": "\nappended",
    }

    success = append_verb.rollback(step, mock_context, rollback_data)

    assert success
    assert dst_file.exists()
    assert dst_file.read_text() == "original"
