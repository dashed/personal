"""
Secret management verb implementation.

This module provides secure secret retrieval and file creation functionality
with support for multiple secret providers and no secret logging.
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotfiles_sync.models import StepConfig, OperationResult, SecretProvider
from dotfiles_sync.context import OperationContext

from .base import Verb


class SecretVerb(Verb):
    """
    Retrieve secrets from various providers and write to files.

    Features:
    - Multiple secret provider support (environment, keychain, etc.)
    - Secure file creation with proper permissions
    - No secret logging or database storage
    - Provider abstraction for extensibility
    - Automatic permission setting (600 by default)
    """

    def __init__(self) -> None:
        """Initialize the secret verb."""
        super().__init__("secret_ref")

    def validate(self, step: StepConfig, context: OperationContext) -> List[str]:
        """
        Validate secret_ref operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            List of validation error messages
        """
        errors = []

        # Check required fields
        if not step.key:
            errors.append("Secret key is required for secret_ref operation")
        if not step.dst:
            errors.append("Destination path is required for secret_ref operation")

        # Validate paths using base class (but don't log the key)
        path_errors = self._validate_paths(step, context)
        # Filter out any error messages that might contain the secret key
        for error in path_errors:
            if step.key and step.key in error:
                errors.append("Secret key validation failed (details hidden for security)")
            else:
                errors.append(error)

        # Get secret provider from security config
        security_config = (
            context.execution_context.config.security if context.execution_context.config else None
        )
        provider = (
            security_config.secret_provider if security_config else SecretProvider.ENVIRONMENT
        )

        # Validate provider availability
        if not self._is_provider_available(provider):
            errors.append(f"Secret provider '{provider.value}' is not available on this system")

        return errors

    def apply(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Apply secret_ref operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            Operation result (no secret data in logs)
        """
        try:
            dst_path = context.get_dst_path()
            if not dst_path or not step.key:
                return OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="secret_ref",
                    message="Destination path or secret key not available",
                )

            # Get secret provider
            security_config = (
                context.execution_context.config.security
                if context.execution_context.config
                else None
            )
            provider = (
                security_config.secret_provider if security_config else SecretProvider.ENVIRONMENT
            )

            # Create backup if destination exists
            backup_path = None
            original_exists = dst_path.exists()

            if original_exists:
                backup_path = self._backup_file(dst_path, context)

            # Retrieve secret
            secret_value = self._retrieve_secret(step.key, provider)
            if secret_value is None:
                return OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="secret_ref",
                    message=f"Failed to retrieve secret from {provider.value} provider",
                )

            # Create parent directories if needed
            if step.create_parent_dirs and dst_path.parent:
                dst_path.parent.mkdir(parents=True, exist_ok=True)

                # Set parent directory permissions if specified
                if step.parent_dir_mode:
                    try:
                        mode = int(step.parent_dir_mode, 8)
                        dst_path.parent.chmod(mode)
                    except (ValueError, OSError) as e:
                        self.logger.warning(f"Failed to set parent directory permissions: {e}")

            # Write secret to file
            dst_path.write_text(secret_value, encoding="utf-8")

            # Set secure file permissions (600 by default, or as specified)
            file_mode = step.mode or "0600"  # Default to owner read/write only
            try:
                mode = int(file_mode, 8)
                dst_path.chmod(mode)
            except (ValueError, OSError) as e:
                self.logger.warning(f"Failed to set file permissions: {e}")

            # Prepare rollback data (no secrets included)
            rollback_data = self._prepare_rollback_data(
                step, context, backup_path=backup_path, original_state={"existed": original_exists}
            )

            # Success message (no secret data)
            message = f"Secret written to {dst_path} from {provider.value} provider"
            if backup_path:
                message += " (backup created)"

            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="secret_ref",
                message=message,
                rollback_data=rollback_data,
            )

        except Exception as e:
            # Log error but don't include potentially sensitive details
            self.logger.error(f"Secret operation failed: {type(e).__name__}")
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="secret_ref",
                message=f"Operation failed: {type(e).__name__}",
            )

    def rollback(
        self, step: StepConfig, context: OperationContext, rollback_data: Dict[str, Any]
    ) -> bool:
        """
        Rollback secret_ref operation.

        Args:
            step: Step configuration
            context: Operation context
            rollback_data: Data from the original operation

        Returns:
            True if rollback succeeded, False otherwise
        """
        try:
            dst_path = context.get_dst_path()
            if not dst_path:
                return False

            original_state = rollback_data.get("original_state", {})
            backup_path_str = rollback_data.get("backup_path")

            if original_state.get("existed", False):
                # File existed before, restore from backup
                if backup_path_str and Path(backup_path_str).exists():
                    import shutil

                    shutil.copy2(backup_path_str, dst_path)
                    self.logger.info(f"Restored {dst_path} from backup")
                else:
                    self.logger.warning(f"Could not restore original file for {dst_path}")
                    return False
            else:
                # File didn't exist before, remove it
                if dst_path.exists():
                    # Securely remove the file
                    dst_path.unlink()
                    self.logger.info(f"Removed {dst_path} (didn't exist before)")

            return True

        except Exception as e:
            self.logger.error(f"Secret rollback failed: {type(e).__name__}")
            return False

    def dry_run(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Perform a dry run of secret_ref operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            Operation result for dry run (no secret data)
        """
        validation_errors = self.validate(step, context)
        if validation_errors:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="secret_ref",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=True,
            )

        dst_path = context.get_dst_path()
        if not dst_path:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="secret_ref",
                message="Destination path not available",
                dry_run=True,
            )

        # Get secret provider
        security_config = (
            context.execution_context.config.security if context.execution_context.config else None
        )
        provider = (
            security_config.secret_provider if security_config else SecretProvider.ENVIRONMENT
        )

        message = f"Would retrieve secret and write to {dst_path} using {provider.value} provider"
        if dst_path.exists():
            message += " (would overwrite existing file)"

        return OperationResult(
            success=True,
            operation_id=0,
            operation_type="secret_ref",
            message=message,
            dry_run=True,
        )

    # Private helper methods

    def _is_provider_available(self, provider: SecretProvider) -> bool:
        """Check if a secret provider is available on this system."""
        try:
            if provider == SecretProvider.ENVIRONMENT:
                return True  # Environment variables are always available

            elif provider == SecretProvider.KEYCHAIN:
                # Check for macOS Security framework or Linux keyring
                import platform

                system = platform.system()
                if system == "Darwin":
                    # macOS - check for security command
                    return (
                        subprocess.run(
                            ["which", "security"], capture_output=True, timeout=5
                        ).returncode
                        == 0
                    )
                elif system == "Linux":
                    # Linux - check for keyring libraries
                    try:
                        import keyring  # type: ignore # noqa: F401

                        return True
                    except ImportError:
                        return False
                return False

            elif provider == SecretProvider.ONEPASSWORD:
                # Check for 1Password CLI
                return (
                    subprocess.run(["which", "op"], capture_output=True, timeout=5).returncode == 0
                )

            elif provider == SecretProvider.LASTPASS:
                # Check for LastPass CLI
                return (
                    subprocess.run(["which", "lpass"], capture_output=True, timeout=5).returncode
                    == 0
                )

            return False

        except Exception:
            return False

    def _retrieve_secret(self, key: str, provider: SecretProvider) -> Optional[str]:
        """
        Retrieve secret from the specified provider.

        Args:
            key: Secret key/name
            provider: Secret provider to use

        Returns:
            Secret value or None if not found
        """
        try:
            if provider == SecretProvider.ENVIRONMENT:
                return self._get_env_secret(key)
            elif provider == SecretProvider.KEYCHAIN:
                return self._get_keychain_secret(key)
            elif provider == SecretProvider.ONEPASSWORD:
                return self._get_onepassword_secret(key)
            elif provider == SecretProvider.LASTPASS:
                return self._get_lastpass_secret(key)

            return None

        except Exception as e:
            self.logger.error(f"Error retrieving secret: {type(e).__name__}")
            return None

    def _get_env_secret(self, key: str) -> Optional[str]:
        """Get secret from environment variable."""
        return os.environ.get(key)

    def _get_keychain_secret(self, key: str) -> Optional[str]:
        """Get secret from system keychain."""
        import platform

        system = platform.system()

        try:
            if system == "Darwin":
                # macOS keychain
                result = subprocess.run(
                    [
                        "security",
                        "find-generic-password",
                        "-s",
                        key,  # Service name
                        "-w",  # Output password only
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    return result.stdout.strip()

            elif system == "Linux":
                # Linux keyring
                try:
                    import keyring  # type: ignore

                    return keyring.get_password("dotfiles", key)
                except ImportError:
                    pass

        except Exception:
            pass

        return None

    def _get_onepassword_secret(self, key: str) -> Optional[str]:
        """Get secret from 1Password."""
        try:
            # 1Password CLI command to get item
            result = subprocess.run(
                ["op", "item", "get", key, "--field", "password"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return result.stdout.strip()

        except Exception:
            pass

        return None

    def _get_lastpass_secret(self, key: str) -> Optional[str]:
        """Get secret from LastPass."""
        try:
            # LastPass CLI command to get password
            result = subprocess.run(
                ["lpass", "show", key, "--password"], capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                return result.stdout.strip()

        except Exception:
            pass

        return None
