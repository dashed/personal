"""Unit tests for the run verb."""

import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock

from dotfiles_sync.models import StepConfig, OperationType, ExecutionContext, SystemInfo
from dotfiles_sync.context import OperationContext
from verbs.run import RunVerb


@pytest.fixture
def run_verb():
    """Create a RunVerb instance."""
    return RunVerb()


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
    op_ctx.operation_type = "run"
    op_ctx.sequence_num = 1

    return op_ctx


def test_run_validate_missing_command(run_verb, mock_context):
    """Test validation with missing command."""
    # StepConfig validates required fields, so we need to provide dummy values
    # and then clear them to test our validation
    step = StepConfig(op=OperationType.RUN, command="dummy")
    step.command = None  # Clear to test validation
    errors = run_verb.validate(step, mock_context)
    assert "Command is required" in errors[0]


def test_run_validate_success(run_verb, mock_context):
    """Test successful validation."""
    step = StepConfig(op=OperationType.RUN, command="echo hello")
    errors = run_verb.validate(step, mock_context)
    assert len(errors) == 0


def test_run_dry_run_simple(run_verb, mock_context):
    """Test dry run with simple command."""
    step = StepConfig(op=OperationType.RUN, command="echo hello")
    result = run_verb.dry_run(step, mock_context)

    assert result.success
    assert "Would run command: echo hello" in result.message
    assert result.dry_run


def test_run_dry_run_with_sudo(run_verb, mock_context):
    """Test dry run with sudo."""
    step = StepConfig(op=OperationType.RUN, command="apt update", sudo=True)
    result = run_verb.dry_run(step, mock_context)

    assert result.success
    assert "Would run command: sudo apt update" in result.message
    assert result.dry_run


@patch("subprocess.run")
def test_run_apply_success(mock_subprocess, run_verb, mock_context):
    """Test successful command execution."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Hello, World!"
    mock_result.stderr = ""
    mock_subprocess.return_value = mock_result

    step = StepConfig(op=OperationType.RUN, command="echo 'Hello, World!'")
    result = run_verb.apply(step, mock_context)

    assert result.success
    assert "Successfully executed" in result.message
    assert not result.dry_run

    # Verify subprocess was called correctly
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args
    assert call_args[0][0] == "echo 'Hello, World!'"
    assert call_args[1]["shell"] is True
    assert call_args[1]["capture_output"] is True


@patch("subprocess.run")
def test_run_apply_failure(mock_subprocess, run_verb, mock_context):
    """Test failed command execution."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Command not found"
    mock_subprocess.return_value = mock_result

    step = StepConfig(op=OperationType.RUN, command="nonexistent_command")
    result = run_verb.apply(step, mock_context)

    assert not result.success
    assert "exit code 1" in result.message
    assert result.error == "Command not found"


@patch("subprocess.run")
def test_run_apply_with_sudo(mock_subprocess, run_verb, mock_context):
    """Test command execution with sudo."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_subprocess.return_value = mock_result

    step = StepConfig(op=OperationType.RUN, command="apt update", sudo=True)
    result = run_verb.apply(step, mock_context)

    assert result.success

    # Verify sudo was added
    call_args = mock_subprocess.call_args
    assert call_args[0][0] == "sudo apt update"


@patch("subprocess.run")
def test_run_apply_with_env_vars(mock_subprocess, run_verb, mock_context):
    """Test command execution with environment variables."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_subprocess.return_value = mock_result

    step = StepConfig(op=OperationType.RUN, command="echo $MY_VAR", vars={"MY_VAR": "test_value"})
    result = run_verb.apply(step, mock_context)

    assert result.success

    # Verify environment was passed
    call_args = mock_subprocess.call_args
    env = call_args[1]["env"]
    assert env is not None
    assert "MY_VAR" in env
    assert env["MY_VAR"] == "test_value"


@patch("subprocess.run")
def test_run_apply_with_working_dir(mock_subprocess, run_verb, mock_context, tmp_path):
    """Test command execution with working directory."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_subprocess.return_value = mock_result

    work_dir = tmp_path / "workdir"
    work_dir.mkdir()

    step = StepConfig(op=OperationType.RUN, command="pwd", dst=str(work_dir))
    mock_context.get_dst_path = Mock(return_value=work_dir)

    result = run_verb.apply(step, mock_context)

    assert result.success

    # Verify working directory was set
    call_args = mock_subprocess.call_args
    assert call_args[1]["cwd"] == str(work_dir)


@patch("subprocess.run")
def test_run_apply_timeout(mock_subprocess, run_verb, mock_context):
    """Test command timeout."""
    mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 300)

    step = StepConfig(op=OperationType.RUN, command="sleep 600")
    result = run_verb.apply(step, mock_context)

    assert not result.success
    assert "timed out" in result.message
    assert result.error == "Timeout"


def test_run_rollback(run_verb, mock_context):
    """Test rollback (which is a no-op for run commands)."""
    step = StepConfig(op=OperationType.RUN, command="echo hello")
    rollback_data = {}

    success = run_verb.rollback(step, mock_context, rollback_data)

    # Rollback always returns True as run operations can't be rolled back
    assert success
