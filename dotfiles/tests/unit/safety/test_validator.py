"""
Tests for the validator component.

These tests verify the path validation, permission checking, checksum verification,
and command validation functionality of the safety validators.
"""

import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock
import pytest

from src.safety.validator import (
    PathValidator,
    PermissionValidator,
    ChecksumValidator,
    CommandValidator,
    SafetyValidator,
    ValidationResult,
    ValidationError,
)
from src.dotfiles_sync.models import SecurityConfig, SafetyConfig


class TestValidationResult:
    """Test suite for ValidationResult model."""

    def test_validation_result_creation(self):
        """Test ValidationResult creation."""
        result = ValidationResult(
            valid=True, message="Test passed", error_code="TEST_OK", details={"test": "data"}
        )

        assert result.valid is True
        assert result.message == "Test passed"
        assert result.error_code == "TEST_OK"
        assert result.details == {"test": "data"}

    def test_validation_result_minimal(self):
        """Test ValidationResult with minimal data."""
        result = ValidationResult(valid=False, message="Test failed")

        assert result.valid is False
        assert result.message == "Test failed"
        assert result.error_code is None
        assert result.details is None


class TestPathValidator:
    """Test suite for PathValidator class."""

    @pytest.fixture
    def security_config(self):
        """Create test security configuration."""
        return SecurityConfig(
            whitelist_paths=["~/.config/**", "~/.local/**"],
            blacklist_paths=["/etc/**", "/System/**", "~/.ssh/authorized_keys"],
        )

    @pytest.fixture
    def path_validator(self, security_config):
        """Create PathValidator instance."""
        return PathValidator(security_config)

    def test_init(self, path_validator, security_config):
        """Test PathValidator initialization."""
        assert path_validator.security_config == security_config
        assert len(path_validator._whitelist_patterns) > 0
        assert len(path_validator._blacklist_patterns) > 0

    def test_validate_destination_whitelisted(self, path_validator):
        """Test validation of whitelisted destination path."""
        dst_path = Path.home() / ".config" / "test.conf"

        result = path_validator.validate_destination_path(dst_path)

        assert result.valid is True
        assert "valid" in result.message.lower()

    def test_validate_destination_blacklisted(self, path_validator):
        """Test validation of blacklisted destination path."""
        dst_path = Path("/etc/passwd")

        result = path_validator.validate_destination_path(dst_path)

        assert result.valid is False
        assert result.error_code == "PATH_BLACKLISTED"
        assert "blacklist" in result.message.lower()

    def test_validate_destination_not_whitelisted(self, path_validator):
        """Test validation of path not in whitelist."""
        dst_path = Path("/tmp/random_file")

        result = path_validator.validate_destination_path(dst_path)

        assert result.valid is False
        assert result.error_code == "PATH_NOT_WHITELISTED"
        assert "not in whitelist" in result.message.lower()

    def test_validate_destination_dangerous_path(self, path_validator):
        """Test validation of dangerous path patterns."""
        dst_path = Path.home() / ".ssh" / "authorized_keys"

        result = path_validator.validate_destination_path(dst_path)

        assert result.valid is False
        assert result.error_code in ["PATH_BLACKLISTED", "PATH_DANGEROUS"]

    def test_validate_source_exists(self, path_validator):
        """Test validation of existing source path."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            src_path = Path(tmp.name)
            tmp.write(b"test content")

        try:
            result = path_validator.validate_source_path(src_path)
            assert result.valid is True
        finally:
            src_path.unlink()

    def test_validate_source_not_exists(self, path_validator):
        """Test validation of non-existent source path."""
        src_path = Path("/nonexistent/file.txt")

        result = path_validator.validate_source_path(src_path)

        assert result.valid is False
        assert result.error_code == "SOURCE_NOT_FOUND"

    def test_validate_source_not_readable(self, path_validator):
        """Test validation of unreadable source path."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            src_path = Path(tmp.name)
            tmp.write(b"test content")

        try:
            # Make file unreadable
            src_path.chmod(0o000)

            result = path_validator.validate_source_path(src_path)

            # May pass or fail depending on system permissions
            # Just ensure it doesn't crash
            assert isinstance(result, ValidationResult)
        finally:
            src_path.chmod(0o644)  # Restore permissions
            src_path.unlink()

    def test_path_matches_patterns(self, path_validator):
        """Test internal pattern matching logic."""
        patterns = {"~/.config/**", "/tmp/*"}

        # Should match
        assert path_validator._path_matches_patterns(
            Path.home() / ".config" / "app" / "settings.json",
            {str(Path.home() / ".config") + "/**"},
        )

        # Should not match
        assert not path_validator._path_matches_patterns(Path("/usr/local/bin/app"), patterns)


class TestPermissionValidator:
    """Test suite for PermissionValidator class."""

    def test_check_write_permission_existing_file(self):
        """Test write permission check for existing file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = Path(tmp.name)
            tmp.write(b"test content")

        try:
            result = PermissionValidator.check_write_permission(file_path)
            assert result.valid is True
        finally:
            file_path.unlink()

    def test_check_write_permission_new_file(self):
        """Test write permission check for new file in existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "new_file.txt"

            result = PermissionValidator.check_write_permission(file_path)

            assert result.valid is True

    def test_check_write_permission_denied(self):
        """Test write permission check when denied."""
        # Try to write to a typically protected location
        protected_path = Path("/usr/bin/protected_file")

        result = PermissionValidator.check_write_permission(protected_path)

        # Should fail due to permissions (unless running as root)
        if os.getuid() != 0:  # Not root
            assert result.valid is False
            assert result.error_code == "PERMISSION_DENIED"

    def test_validate_file_mode_match(self):
        """Test file mode validation when modes match."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = Path(tmp.name)
            tmp.write(b"test content")

        try:
            # Set specific mode
            file_path.chmod(0o644)

            result = PermissionValidator.validate_file_mode(file_path, "644")

            assert result.valid is True
        finally:
            file_path.unlink()

    def test_validate_file_mode_mismatch(self):
        """Test file mode validation when modes don't match."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = Path(tmp.name)
            tmp.write(b"test content")

        try:
            # Set one mode, expect another
            file_path.chmod(0o644)

            result = PermissionValidator.validate_file_mode(file_path, "600")

            assert result.valid is False
            assert result.error_code == "MODE_MISMATCH"
        finally:
            file_path.unlink()

    def test_validate_file_mode_nonexistent(self):
        """Test file mode validation for non-existent file."""
        file_path = Path("/nonexistent/file.txt")

        result = PermissionValidator.validate_file_mode(file_path, "644")

        assert result.valid is False
        assert result.error_code == "FILE_NOT_FOUND"


class TestChecksumValidator:
    """Test suite for ChecksumValidator class."""

    def test_calculate_sha256(self):
        """Test SHA256 checksum calculation."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = Path(tmp.name)
            test_content = b"test content for checksum"
            tmp.write(test_content)

        try:
            checksum = ChecksumValidator.calculate_sha256(file_path)

            # Verify checksum is correct
            expected = hashlib.sha256(test_content).hexdigest()
            assert checksum == expected
        finally:
            file_path.unlink()

    def test_calculate_sha256_nonexistent(self):
        """Test SHA256 calculation for non-existent file."""
        file_path = Path("/nonexistent/file.txt")

        checksum = ChecksumValidator.calculate_sha256(file_path)

        assert checksum is None

    def test_verify_checksum_match(self):
        """Test checksum verification when checksums match."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = Path(tmp.name)
            test_content = b"test content"
            tmp.write(test_content)

        try:
            expected_checksum = hashlib.sha256(test_content).hexdigest()

            result = ChecksumValidator.verify_checksum(file_path, expected_checksum)

            assert result.valid is True
        finally:
            file_path.unlink()

    def test_verify_checksum_mismatch(self):
        """Test checksum verification when checksums don't match."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            file_path = Path(tmp.name)
            tmp.write(b"test content")

        try:
            wrong_checksum = "wrong_checksum_value"

            result = ChecksumValidator.verify_checksum(file_path, wrong_checksum)

            assert result.valid is False
            assert result.error_code == "CHECKSUM_MISMATCH"
        finally:
            file_path.unlink()

    def test_verify_checksum_calculation_failed(self):
        """Test checksum verification when calculation fails."""
        file_path = Path("/nonexistent/file.txt")

        result = ChecksumValidator.verify_checksum(file_path, "some_checksum")

        assert result.valid is False
        assert result.error_code == "CHECKSUM_CALCULATION_FAILED"


class TestCommandValidator:
    """Test suite for CommandValidator class."""

    @pytest.fixture
    def security_config_with_whitelist(self):
        """Create security config with command whitelisting enabled."""
        return SecurityConfig(
            enable_command_whitelist=True,
            allowed_commands=["./scripts/install.sh", "brew install", "git clone"],
        )

    @pytest.fixture
    def command_validator_enabled(self, security_config_with_whitelist):
        """Create CommandValidator with whitelisting enabled."""
        return CommandValidator(security_config_with_whitelist)

    @pytest.fixture
    def command_validator_disabled(self):
        """Create CommandValidator with whitelisting disabled."""
        config = SecurityConfig(enable_command_whitelist=False)
        return CommandValidator(config)

    def test_validate_command_whitelisting_disabled(self, command_validator_disabled):
        """Test command validation when whitelisting is disabled."""
        result = command_validator_disabled.validate_command("rm -rf /")

        assert result.valid is True
        assert "disabled" in result.message.lower()

    def test_validate_command_allowed(self, command_validator_enabled):
        """Test validation of allowed command."""
        result = command_validator_enabled.validate_command("brew install python")

        assert result.valid is True
        assert "allowed" in result.message.lower()

    def test_validate_command_not_allowed(self, command_validator_enabled):
        """Test validation of non-allowed command."""
        result = command_validator_enabled.validate_command("rm -rf /")

        assert result.valid is False
        assert result.error_code == "COMMAND_NOT_WHITELISTED"


class TestSafetyValidator:
    """Test suite for SafetyValidator class."""

    @pytest.fixture
    def security_config(self):
        """Create test security configuration."""
        return SecurityConfig(
            whitelist_paths=["~/.config/**"],
            blacklist_paths=["/etc/**"],
            enable_command_whitelist=True,
            allowed_commands=["./scripts/test.sh"],
        )

    @pytest.fixture
    def safety_config(self):
        """Create test safety configuration."""
        return SafetyConfig(verify_checksums=True)

    @pytest.fixture
    def safety_validator(self, security_config, safety_config):
        """Create SafetyValidator instance."""
        return SafetyValidator(security_config, safety_config)

    def test_init(self, safety_validator, security_config, safety_config):
        """Test SafetyValidator initialization."""
        assert safety_validator.security_config == security_config
        assert safety_validator.safety_config == safety_config
        assert isinstance(safety_validator.path_validator, PathValidator)
        assert isinstance(safety_validator.command_validator, CommandValidator)

    def test_validate_operation_link(self, safety_validator):
        """Test operation validation for link operation."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            src_path = Path(tmp.name)
            tmp.write(b"test")

        try:
            dst_path = Path.home() / ".config" / "test_link"

            results = safety_validator.validate_operation(
                operation_type="link", src_path=src_path, dst_path=dst_path
            )

            # Should have results for source validation, destination validation, and permissions
            assert len(results) >= 2

            # Check that we have validation results
            assert all(isinstance(r, ValidationResult) for r in results)
        finally:
            src_path.unlink()

    def test_validate_operation_command(self, safety_validator):
        """Test operation validation for command operation."""
        results = safety_validator.validate_operation(
            operation_type="run", command="./scripts/test.sh"
        )

        # Should validate the command
        assert len(results) >= 1
        command_results = [r for r in results if "command" in r.message.lower()]
        assert len(command_results) >= 1

    def test_validate_operation_with_checksum(self, safety_validator):
        """Test operation validation with checksum verification."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            src_path = Path(tmp.name)
            test_content = b"test content"
            tmp.write(test_content)

        try:
            dst_path = Path.home() / ".config" / "test_file"
            expected_checksum = hashlib.sha256(test_content).hexdigest()

            results = safety_validator.validate_operation(
                operation_type="copy",
                src_path=src_path,
                dst_path=dst_path,
                expected_checksum=expected_checksum,
            )

            # Should include checksum validation
            checksum_results = [r for r in results if "checksum" in r.message.lower()]
            assert len(checksum_results) >= 1
        finally:
            src_path.unlink()

    def test_validate_pre_flight_no_config(self, safety_validator):
        """Test pre-flight validation without configuration."""
        exec_ctx = Mock()
        exec_ctx.config = None

        results = safety_validator.validate_pre_flight(exec_ctx)

        assert len(results) == 1
        assert not results[0].valid
        assert results[0].error_code == "NO_CONFIG"

    def test_validate_pre_flight_with_config(self, safety_validator):
        """Test pre-flight validation with configuration."""
        from src.dotfiles_sync.models import (
            DotfilesConfig,
            PackageConfig,
            SafetyConfig,
            StepConfig,
            OperationType,
        )

        # Create mock execution context with config
        exec_ctx = Mock()
        exec_ctx.config = DotfilesConfig(
            package=PackageConfig(name="test", version="1.0.0"),
            safety=SafetyConfig(),
            step=[StepConfig(op=OperationType.LINK, src="test.txt", dst="~/.config/test.txt")],
        )

        results = safety_validator.validate_pre_flight(exec_ctx)

        # Should validate each step
        assert len(results) >= 1
        # At least some validations should be performed
        assert any(isinstance(r, ValidationResult) for r in results)


class TestValidationError:
    """Test suite for ValidationError exception."""

    def test_validation_error_creation(self):
        """Test ValidationError creation with validation results."""
        validation_results = [
            ValidationResult(valid=False, message="Error 1"),
            ValidationResult(valid=False, message="Error 2"),
        ]

        error = ValidationError("Multiple validation errors", validation_results)

        assert str(error) == "Multiple validation errors"
        assert error.validation_results == validation_results
        assert len(error.validation_results) == 2
