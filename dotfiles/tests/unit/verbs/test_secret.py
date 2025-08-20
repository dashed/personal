"""Unit tests for the secret verb."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from dotfiles_sync.models import StepConfig, OperationType, ExecutionContext, SystemInfo, SecretProvider, SecurityConfig
from dotfiles_sync.context import OperationContext
from verbs.secret import SecretVerb


@pytest.fixture
def secret_verb():
    """Create a SecretVerb instance."""
    return SecretVerb()


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
    
    # Mock config with security settings
    exec_ctx.config = Mock()
    exec_ctx.config.security = Mock(spec=SecurityConfig)
    exec_ctx.config.security.secret_provider = SecretProvider.ENVIRONMENT

    op_ctx = Mock(spec=OperationContext)
    op_ctx.execution_context = exec_ctx
    op_ctx.operation_type = "secret_ref"
    op_ctx.sequence_num = 1

    return op_ctx


def test_secret_validate_missing_key(secret_verb, mock_context):
    """Test validation with missing secret key."""
    step = StepConfig(op=OperationType.SECRET_REF, dst="secret.txt")
    step.key = None
    errors = secret_verb.validate(step, mock_context)
    assert any("Secret key is required" in error for error in errors)


def test_secret_validate_missing_dst(secret_verb, mock_context):
    """Test validation with missing destination."""
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY")
    step.dst = None
    errors = secret_verb.validate(step, mock_context)
    assert any("Destination path is required" in error for error in errors)


@patch('verbs.secret.SecretVerb._is_provider_available')
def test_secret_validate_provider_unavailable(mock_available, secret_verb, mock_context):
    """Test validation when secret provider is not available."""
    mock_available.return_value = False
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst="secret.txt")
    errors = secret_verb.validate(step, mock_context)
    assert any("Secret provider 'ENVIRONMENT' is not available" in error for error in errors)


@patch('verbs.secret.SecretVerb._is_provider_available')
def test_secret_validate_success(mock_available, secret_verb, mock_context):
    """Test successful validation."""
    mock_available.return_value = True
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst="secret.txt")
    errors = secret_verb.validate(step, mock_context)
    assert len(errors) == 0


def test_secret_validate_filters_key_from_errors(secret_verb, mock_context, tmp_path):
    """Test that validation filters out secret keys from error messages."""
    step = StepConfig(op=OperationType.SECRET_REF, key="SUPER_SECRET", dst="secret.txt")
    mock_context.get_dst_path = Mock(return_value=tmp_path / "secret.txt")
    
    # Mock path validation to return an error containing the key
    with patch.object(secret_verb, '_validate_paths') as mock_validate:
        mock_validate.return_value = ["Error with SUPER_SECRET in message"]
        
        errors = secret_verb.validate(step, mock_context)
        
        # Should filter out the key from error messages
        assert any("Secret key validation failed (details hidden for security)" in error for error in errors)


def test_secret_dry_run_success(secret_verb, mock_context, tmp_path):
    """Test successful dry run."""
    output_file = tmp_path / "secret.txt"
    
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst=str(output_file))
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = secret_verb.dry_run(step, mock_context)
    
    assert result.success
    assert "Would retrieve secret and write to" in result.message
    assert "ENVIRONMENT provider" in result.message
    assert result.dry_run


def test_secret_dry_run_would_overwrite(secret_verb, mock_context, tmp_path):
    """Test dry run with existing file."""
    output_file = tmp_path / "secret.txt"
    output_file.write_text("existing content")
    
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst=str(output_file))
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = secret_verb.dry_run(step, mock_context)
    
    assert result.success
    assert "would overwrite existing file" in result.message


@patch('verbs.secret.SecretVerb._retrieve_secret')
def test_secret_apply_new_file(mock_retrieve, secret_verb, mock_context, tmp_path):
    """Test applying secret to new file."""
    mock_retrieve.return_value = "secret_value"
    
    output_file = tmp_path / "secret.txt"
    
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst=str(output_file))
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = secret_verb.apply(step, mock_context)
    
    assert result.success
    assert "Secret written to" in result.message
    assert "ENVIRONMENT provider" in result.message
    assert output_file.exists()
    assert output_file.read_text() == "secret_value"
    
    # Check file permissions (should be 600 by default)
    import stat
    mode = output_file.stat().st_mode
    assert stat.S_IMODE(mode) == 0o600
    
    # Check rollback data (no secrets should be stored)
    assert not result.rollback_data["original_state"]["existed"]


@patch('verbs.secret.SecretVerb._retrieve_secret')
def test_secret_apply_existing_file_with_backup(mock_retrieve, secret_verb, mock_context, tmp_path):
    """Test applying secret to existing file with backup."""
    mock_retrieve.return_value = "new_secret_value"
    
    output_file = tmp_path / "secret.txt"
    output_file.write_text("old secret")
    
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst=str(output_file))
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    # Mock backup creation
    with patch.object(secret_verb, '_backup_file') as mock_backup:
        mock_backup.return_value = tmp_path / "backup.txt"
        
        result = secret_verb.apply(step, mock_context)
    
    assert result.success
    assert "backup created" in result.message
    assert output_file.read_text() == "new_secret_value"
    
    # Check rollback data
    assert result.rollback_data["original_state"]["existed"]


@patch('verbs.secret.SecretVerb._retrieve_secret')
def test_secret_apply_with_custom_mode(mock_retrieve, secret_verb, mock_context, tmp_path):
    """Test applying secret with custom file mode."""
    mock_retrieve.return_value = "secret_value"
    
    output_file = tmp_path / "secret.txt"
    
    step = StepConfig(
        op=OperationType.SECRET_REF, 
        key="SECRET_KEY", 
        dst=str(output_file),
        mode="0640"
    )
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = secret_verb.apply(step, mock_context)
    
    assert result.success
    assert output_file.exists()
    
    # Check custom file permissions
    import stat
    mode = output_file.stat().st_mode
    assert stat.S_IMODE(mode) == 0o640


@patch('verbs.secret.SecretVerb._retrieve_secret')
def test_secret_apply_with_parent_dirs(mock_retrieve, secret_verb, mock_context, tmp_path):
    """Test applying secret with parent directory creation."""
    mock_retrieve.return_value = "secret_value"
    
    output_file = tmp_path / "nested" / "dirs" / "secret.txt"
    
    step = StepConfig(
        op=OperationType.SECRET_REF, 
        key="SECRET_KEY", 
        dst=str(output_file),
        create_parent_dirs=True,
        parent_dir_mode="0750"
    )
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = secret_verb.apply(step, mock_context)
    
    assert result.success
    assert output_file.exists()
    assert output_file.parent.exists()
    
    # Check parent directory permissions
    import stat
    parent_mode = output_file.parent.stat().st_mode
    assert stat.S_IMODE(parent_mode) == 0o750


@patch('verbs.secret.SecretVerb._retrieve_secret')
def test_secret_apply_retrieval_failure(mock_retrieve, secret_verb, mock_context, tmp_path):
    """Test secret application when retrieval fails."""
    mock_retrieve.return_value = None  # Secret not found
    
    output_file = tmp_path / "secret.txt"
    
    step = StepConfig(op=OperationType.SECRET_REF, key="NONEXISTENT_KEY", dst=str(output_file))
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    result = secret_verb.apply(step, mock_context)
    
    assert not result.success
    assert "Failed to retrieve secret" in result.message
    assert not output_file.exists()


def test_secret_apply_error_handling(secret_verb, mock_context, tmp_path):
    """Test error handling during secret application."""
    output_file = tmp_path / "secret.txt"
    
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst=str(output_file))
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    # Mock retrieve_secret to raise an exception
    with patch.object(secret_verb, '_retrieve_secret', side_effect=Exception("Mock error")):
        result = secret_verb.apply(step, mock_context)
    
    assert not result.success
    assert "Operation failed" in result.message
    # Should not leak error details that might contain secrets
    assert "Mock error" not in result.message


def test_secret_rollback_new_file(secret_verb, mock_context, tmp_path):
    """Test rolling back when file was newly created."""
    output_file = tmp_path / "secret.txt"
    output_file.write_text("secret content")
    
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst=str(output_file))
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    rollback_data = {
        "original_state": {"existed": False}
    }
    
    success = secret_verb.rollback(step, mock_context, rollback_data)
    
    assert success
    assert not output_file.exists()


def test_secret_rollback_existing_file_with_backup(secret_verb, mock_context, tmp_path):
    """Test rolling back existing file with backup."""
    output_file = tmp_path / "secret.txt"
    output_file.write_text("new secret")
    
    backup_file = tmp_path / "backup.txt"
    backup_file.write_text("original secret")
    
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst=str(output_file))
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    rollback_data = {
        "original_state": {"existed": True},
        "backup_path": str(backup_file)
    }
    
    success = secret_verb.rollback(step, mock_context, rollback_data)
    
    assert success
    assert output_file.exists()
    assert output_file.read_text() == "original secret"


def test_is_provider_available_environment(secret_verb):
    """Test environment provider availability check."""
    available = secret_verb._is_provider_available(SecretProvider.ENVIRONMENT)
    assert available  # Environment variables are always available


@patch('platform.system')
@patch('subprocess.run')
def test_is_provider_available_keychain_macos(mock_run, mock_system, secret_verb):
    """Test keychain provider availability on macOS."""
    mock_system.return_value = "Darwin"
    mock_run.return_value.returncode = 0  # security command found
    
    available = secret_verb._is_provider_available(SecretProvider.KEYCHAIN)
    assert available


@patch('platform.system')
def test_is_provider_available_keychain_linux_with_keyring(mock_system, secret_verb):
    """Test keychain provider availability on Linux with keyring."""
    mock_system.return_value = "Linux"
    
    with patch.dict('sys.modules', {'keyring': Mock()}):
        available = secret_verb._is_provider_available(SecretProvider.KEYCHAIN)
        assert available


@patch('platform.system')
def test_is_provider_available_keychain_linux_without_keyring(mock_system, secret_verb):
    """Test keychain provider availability on Linux without keyring."""
    mock_system.return_value = "Linux"
    
    available = secret_verb._is_provider_available(SecretProvider.KEYCHAIN)
    assert not available  # keyring module not available


@patch('subprocess.run')
def test_is_provider_available_onepassword(mock_run, secret_verb):
    """Test 1Password provider availability."""
    mock_run.return_value.returncode = 0  # op command found
    
    available = secret_verb._is_provider_available(SecretProvider.ONEPASSWORD)
    assert available


@patch('subprocess.run')
def test_is_provider_available_lastpass(mock_run, secret_verb):
    """Test LastPass provider availability."""
    mock_run.return_value.returncode = 0  # lpass command found
    
    available = secret_verb._is_provider_available(SecretProvider.LASTPASS)
    assert available


@patch.dict('os.environ', {'TEST_SECRET': 'secret_value'})
def test_get_env_secret_found(secret_verb):
    """Test retrieving secret from environment variables."""
    secret = secret_verb._get_env_secret("TEST_SECRET")
    assert secret == "secret_value"


def test_get_env_secret_not_found(secret_verb):
    """Test retrieving non-existent secret from environment."""
    secret = secret_verb._get_env_secret("NONEXISTENT_SECRET")
    assert secret is None


@patch('platform.system')
@patch('subprocess.run')
def test_get_keychain_secret_macos_success(mock_run, mock_system, secret_verb):
    """Test successful keychain secret retrieval on macOS."""
    mock_system.return_value = "Darwin"
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "secret_password\n"
    
    secret = secret_verb._get_keychain_secret("test_service")
    assert secret == "secret_password"


@patch('platform.system')
@patch('subprocess.run')
def test_get_keychain_secret_macos_not_found(mock_run, mock_system, secret_verb):
    """Test keychain secret retrieval failure on macOS."""
    mock_system.return_value = "Darwin"
    mock_run.return_value.returncode = 1  # Not found
    
    secret = secret_verb._get_keychain_secret("nonexistent_service")
    assert secret is None


@patch('platform.system')
def test_get_keychain_secret_linux_with_keyring(mock_system, secret_verb):
    """Test keychain secret retrieval on Linux with keyring."""
    mock_system.return_value = "Linux"
    
    mock_keyring = Mock()
    mock_keyring.get_password.return_value = "linux_secret"
    
    with patch.dict('sys.modules', {'keyring': mock_keyring}):
        secret = secret_verb._get_keychain_secret("test_key")
        assert secret == "linux_secret"
        mock_keyring.get_password.assert_called_once_with("dotfiles", "test_key")


@patch('subprocess.run')
def test_get_onepassword_secret_success(mock_run, secret_verb):
    """Test successful 1Password secret retrieval."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "onepassword_secret\n"
    
    secret = secret_verb._get_onepassword_secret("item_name")
    assert secret == "onepassword_secret"


@patch('subprocess.run')
def test_get_onepassword_secret_not_found(mock_run, secret_verb):
    """Test 1Password secret retrieval failure."""
    mock_run.return_value.returncode = 1  # Not found
    
    secret = secret_verb._get_onepassword_secret("nonexistent_item")
    assert secret is None


@patch('subprocess.run')
def test_get_lastpass_secret_success(mock_run, secret_verb):
    """Test successful LastPass secret retrieval."""
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "lastpass_secret\n"
    
    secret = secret_verb._get_lastpass_secret("site_name")
    assert secret == "lastpass_secret"


@patch('subprocess.run')
def test_get_lastpass_secret_not_found(mock_run, secret_verb):
    """Test LastPass secret retrieval failure."""
    mock_run.return_value.returncode = 1  # Not found
    
    secret = secret_verb._get_lastpass_secret("nonexistent_site")
    assert secret is None


def test_retrieve_secret_environment_success(secret_verb):
    """Test secret retrieval via environment provider."""
    with patch.object(secret_verb, '_get_env_secret', return_value="env_secret"):
        secret = secret_verb._retrieve_secret("TEST_KEY", SecretProvider.ENVIRONMENT)
        assert secret == "env_secret"


def test_retrieve_secret_keychain_success(secret_verb):
    """Test secret retrieval via keychain provider."""
    with patch.object(secret_verb, '_get_keychain_secret', return_value="keychain_secret"):
        secret = secret_verb._retrieve_secret("TEST_KEY", SecretProvider.KEYCHAIN)
        assert secret == "keychain_secret"


def test_retrieve_secret_onepassword_success(secret_verb):
    """Test secret retrieval via 1Password provider."""
    with patch.object(secret_verb, '_get_onepassword_secret', return_value="op_secret"):
        secret = secret_verb._retrieve_secret("TEST_KEY", SecretProvider.ONEPASSWORD)
        assert secret == "op_secret"


def test_retrieve_secret_lastpass_success(secret_verb):
    """Test secret retrieval via LastPass provider."""
    with patch.object(secret_verb, '_get_lastpass_secret', return_value="lp_secret"):
        secret = secret_verb._retrieve_secret("TEST_KEY", SecretProvider.LASTPASS)
        assert secret == "lp_secret"


def test_retrieve_secret_error_handling(secret_verb):
    """Test error handling during secret retrieval."""
    with patch.object(secret_verb, '_get_env_secret', side_effect=Exception("Mock error")):
        secret = secret_verb._retrieve_secret("TEST_KEY", SecretProvider.ENVIRONMENT)
        assert secret is None


def test_secret_no_logging_of_sensitive_data(secret_verb, mock_context, tmp_path, caplog):
    """Test that secrets are never logged."""
    output_file = tmp_path / "secret.txt"
    
    step = StepConfig(op=OperationType.SECRET_REF, key="SECRET_KEY", dst=str(output_file))
    mock_context.get_dst_path = Mock(return_value=output_file)
    
    with patch.object(secret_verb, '_retrieve_secret', return_value="SUPER_SECRET_VALUE"):
        result = secret_verb.apply(step, mock_context)
    
    assert result.success
    
    # Check that secret value is not in any log messages
    for record in caplog.records:
        assert "SUPER_SECRET_VALUE" not in record.message
        assert "SUPER_SECRET_VALUE" not in str(record.args)
    
    # Check that secret value is not in result message
    assert "SUPER_SECRET_VALUE" not in result.message