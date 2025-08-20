"""Unit tests for the template verb."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from dotfiles_sync.models import StepConfig, OperationType, ExecutionContext, SystemInfo
from dotfiles_sync.context import OperationContext
from verbs.template import TemplateVerb


@pytest.fixture
def template_verb():
    """Create a TemplateVerb instance."""
    return TemplateVerb()


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
    op_ctx.operation_type = "template"
    op_ctx.sequence_num = 1

    return op_ctx


@patch('verbs.template.JINJA2_AVAILABLE', False)
def test_template_validate_jinja2_missing(template_verb, mock_context):
    """Test validation when Jinja2 is not available."""
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src="template.j2",
        dst="output.txt",
        vars={"key": "value"}
    )
    errors = template_verb.validate(step, mock_context)
    assert any("Jinja2 is not installed" in error for error in errors)


def test_template_validate_missing_src(template_verb, mock_context):
    """Test validation with missing source template."""
    step = StepConfig(op=OperationType.TEMPLATE, dst="output.txt", vars={"key": "value"})
    step.src = None
    errors = template_verb.validate(step, mock_context)
    assert any("Source template path is required" in error for error in errors)


def test_template_validate_missing_dst(template_verb, mock_context):
    """Test validation with missing destination."""
    step = StepConfig(op=OperationType.TEMPLATE, src="template.j2", vars={"key": "value"})
    step.dst = None
    errors = template_verb.validate(step, mock_context)
    assert any("Destination path is required" in error for error in errors)


def test_template_validate_missing_vars(template_verb, mock_context):
    """Test validation with missing template variables."""
    step = StepConfig(op=OperationType.TEMPLATE, src="template.j2", dst="output.txt")
    step.vars = None
    errors = template_verb.validate(step, mock_context)
    assert any("Template variables (vars) are required" in error for error in errors)


def test_template_validate_invalid_vars_type(template_verb, mock_context, tmp_path):
    """Test validation with invalid vars type."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("Hello {{ name }}")
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst="output.txt",
        vars="not_a_dict"
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    
    errors = template_verb.validate(step, mock_context)
    assert any("Template variables must be a dictionary" in error for error in errors)


def test_template_validate_template_not_exists(template_verb, mock_context, tmp_path):
    """Test validation when template file doesn't exist."""
    nonexistent_file = tmp_path / "nonexistent.j2"
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(nonexistent_file),
        dst="output.txt",
        vars={"key": "value"}
    )
    mock_context.get_src_path = Mock(return_value=nonexistent_file)
    
    errors = template_verb.validate(step, mock_context)
    assert any("Template file does not exist" in error for error in errors)


def test_template_validate_template_syntax_error(template_verb, mock_context, tmp_path):
    """Test validation with template syntax error."""
    template_file = tmp_path / "bad_template.j2"
    template_file.write_text("Hello {{ name }")  # Missing closing brace
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst="output.txt",
        vars={"name": "World"}
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    
    errors = template_verb.validate(step, mock_context)
    assert any("Template syntax error" in error for error in errors)


def test_template_validate_success(template_verb, mock_context, tmp_path):
    """Test successful validation."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("Hello {{ name }}!")
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst="output.txt",
        vars={"name": "World"}
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    
    errors = template_verb.validate(step, mock_context)
    assert len(errors) == 0


def test_template_dry_run_success(template_verb, mock_context, tmp_path):
    """Test successful dry run."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("Hello {{ name }}!")
    
    output_file = tmp_path / "output.txt"
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst=str(output_file),
        vars={"name": "World"}
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = template_verb.dry_run(step, mock_context)
    
    assert result.success
    assert "Would render template" in result.message
    assert "13 characters" in result.message  # Length of "Hello World!"
    assert result.dry_run


def test_template_dry_run_overwrite_existing(template_verb, mock_context, tmp_path):
    """Test dry run with existing destination file."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("Hello {{ name }}!")
    
    output_file = tmp_path / "output.txt"
    output_file.write_text("existing content")
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst=str(output_file),
        vars={"name": "World"}
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = template_verb.dry_run(step, mock_context)
    
    assert result.success
    assert "would overwrite existing file" in result.message


def test_template_apply_new_file(template_verb, mock_context, tmp_path):
    """Test applying template to new file."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("Hello {{ name }}! Platform: {{ platform }}")
    
    output_file = tmp_path / "output.txt"
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst=str(output_file),
        vars={"name": "World"}
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = template_verb.apply(step, mock_context)
    
    assert result.success
    assert "Template rendered" in result.message
    assert output_file.exists()
    content = output_file.read_text()
    assert "Hello World!" in content
    assert "Platform: linux" in content  # System info should be injected
    
    # Check rollback data
    assert not result.rollback_data["original_state"]["existed"]


def test_template_apply_existing_file_with_backup(template_verb, mock_context, tmp_path):
    """Test applying template to existing file with backup."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("New content: {{ message }}")
    
    output_file = tmp_path / "output.txt"
    original_content = "original content"
    output_file.write_text(original_content)
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst=str(output_file),
        vars={"message": "updated"}
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    # Mock backup creation
    with patch.object(template_verb, '_backup_file') as mock_backup:
        mock_backup.return_value = tmp_path / "backup.txt"
        
        result = template_verb.apply(step, mock_context)
    
    assert result.success
    assert "Template rendered" in result.message
    assert "backup:" in result.message
    assert output_file.read_text() == "New content: updated"
    
    # Check rollback data
    assert result.rollback_data["original_state"]["existed"]
    assert result.rollback_data["original_state"]["content"] == original_content


def test_template_apply_with_parent_dirs(template_verb, mock_context, tmp_path):
    """Test applying template with parent directory creation."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("Content: {{ content }}")
    
    output_file = tmp_path / "subdir" / "nested" / "output.txt"
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst=str(output_file),
        vars={"content": "test"},
        create_parent_dirs=True,
        parent_dir_mode="0755"
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = template_verb.apply(step, mock_context)
    
    assert result.success
    assert output_file.exists()
    assert output_file.parent.exists()
    assert output_file.read_text() == "Content: test"


def test_template_apply_with_file_mode(template_verb, mock_context, tmp_path):
    """Test applying template with file mode setting."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("Content: {{ content }}")
    
    output_file = tmp_path / "output.txt"
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst=str(output_file),
        vars={"content": "test"},
        mode="0600"
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = template_verb.apply(step, mock_context)
    
    assert result.success
    assert output_file.exists()
    
    # Check file permissions
    import stat
    mode = output_file.stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_template_rollback_new_file(template_verb, mock_context, tmp_path):
    """Test rolling back when file was newly created."""
    output_file = tmp_path / "output.txt"
    output_file.write_text("rendered content")
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src="template.j2",
        dst=str(output_file),
        vars={"key": "value"}
    )
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    rollback_data = {
        "original_state": {"existed": False}
    }
    
    success = template_verb.rollback(step, mock_context, rollback_data)
    
    assert success
    assert not output_file.exists()


def test_template_rollback_existing_file_with_backup(template_verb, mock_context, tmp_path):
    """Test rolling back existing file with backup."""
    output_file = tmp_path / "output.txt"
    output_file.write_text("new content")
    
    backup_file = tmp_path / "backup.txt"
    backup_file.write_text("original content")
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src="template.j2",
        dst=str(output_file),
        vars={"key": "value"}
    )
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    rollback_data = {
        "original_state": {"existed": True},
        "backup_path": str(backup_file)
    }
    
    success = template_verb.rollback(step, mock_context, rollback_data)
    
    assert success
    assert output_file.exists()
    assert output_file.read_text() == "original content"


def test_template_rollback_existing_file_with_saved_content(template_verb, mock_context, tmp_path):
    """Test rolling back existing file using saved content."""
    output_file = tmp_path / "output.txt"
    output_file.write_text("new content")
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src="template.j2",
        dst=str(output_file),
        vars={"key": "value"}
    )
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    rollback_data = {
        "original_state": {
            "existed": True,
            "content": "original content"
        }
    }
    
    success = template_verb.rollback(step, mock_context, rollback_data)
    
    assert success
    assert output_file.exists()
    assert output_file.read_text() == "original content"


def test_prepare_template_vars(template_verb, mock_context):
    """Test preparing template variables with system info injection."""
    config_vars = {"custom_var": "custom_value", "name": "test"}
    
    template_vars = template_verb._prepare_template_vars(config_vars, mock_context)
    
    # Check system variables are injected
    assert template_vars["platform"] == "linux"
    assert template_vars["username"] == "testuser"
    assert template_vars["hostname"] == "testhost"
    assert template_vars["variant"] == "test"
    assert "home" in template_vars
    assert "env" in template_vars
    
    # Check custom variables are included
    assert template_vars["custom_var"] == "custom_value"
    assert template_vars["name"] == "test"


def test_sanitize_template_vars(template_verb):
    """Test template variable sanitization."""
    dangerous_vars = {
        "__builtins__": "dangerous",
        "eval": "dangerous",
        "safe_var": "safe_value",
        "number": 42,
        "boolean": True,
        "list": [1, 2, 3],
        "dict": {"key": "value"}
    }
    
    sanitized = template_verb._sanitize_template_vars(dangerous_vars)
    
    # Dangerous variables should be removed
    assert "__builtins__" not in sanitized
    assert "eval" not in sanitized
    
    # Safe variables should be preserved
    assert sanitized["safe_var"] == "safe_value"
    assert sanitized["number"] == 42
    assert sanitized["boolean"] is True
    assert sanitized["list"] == [1, 2, 3]
    assert sanitized["dict"] == {"key": "value"}


def test_template_custom_filters(template_verb, tmp_path):
    """Test custom Jinja2 filters."""
    template_dir = tmp_path
    env = template_verb._get_template_environment(template_dir)
    
    # Test basename filter
    assert env.filters["basename"]("/path/to/file.txt") == "file.txt"
    
    # Test dirname filter
    assert "path/to" in env.filters["dirname"]("/path/to/file.txt")
    
    # Test expanduser filter (should work with ~ paths)
    expanded = env.filters["expanduser"]("~/test")
    assert "~" not in expanded  # Should be expanded
    
    # Test abspath filter
    abs_path = env.filters["abspath"]("relative/path")
    assert abs_path.startswith("/")  # Should be absolute


@patch.dict('os.environ', {'TEST_VAR': 'test_value'})
def test_template_environment_variables(template_verb, mock_context, tmp_path):
    """Test that environment variables are available in templates."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("Test: {{ env.TEST_VAR }}")
    
    output_file = tmp_path / "output.txt"
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst=str(output_file),
        vars={"dummy": "value"}
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = template_verb.apply(step, mock_context)
    
    assert result.success
    assert output_file.read_text() == "Test: test_value"


def test_template_apply_error_handling(template_verb, mock_context, tmp_path):
    """Test error handling during template application."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("{{ undefined_variable }}")  # Will cause error
    
    output_file = tmp_path / "output.txt"
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst=str(output_file),
        vars={}  # No variables defined
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = template_verb.apply(step, mock_context)
    
    assert not result.success
    assert "Operation failed" in result.message


def test_template_dry_run_error_handling(template_verb, mock_context, tmp_path):
    """Test error handling during dry run."""
    template_file = tmp_path / "template.j2"
    template_file.write_text("{{ undefined_variable }}")  # Will cause error
    
    output_file = tmp_path / "output.txt"
    
    step = StepConfig(
        op=OperationType.TEMPLATE,
        src=str(template_file),
        dst=str(output_file),
        vars={}  # No variables defined
    )
    mock_context.get_src_path = Mock(return_value=template_file)
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = template_verb.dry_run(step, mock_context)
    
    assert not result.success
    assert "Dry run failed" in result.message
    assert result.dry_run