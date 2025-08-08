"""
Base Verb class for dotfiles operations.

This module provides the abstract base class for all verb operations
(link, copy, append, etc.) with a consistent interface for validation,
application, and rollback.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging
import hashlib
import shutil
from datetime import datetime

from dotfiles_sync.context import OperationContext
from dotfiles_sync.models import StepConfig, OperationResult

logger = logging.getLogger(__name__)


class Verb(ABC):
    """
    Abstract base class for all verb operations.

    Each verb represents a type of operation that can be performed
    (e.g., link, copy, append) with consistent validation, execution,
    and rollback capabilities.
    """

    def __init__(self, name: str):
        """Initialize verb with a name."""
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    def validate(self, spec: StepConfig, ctx: OperationContext) -> List[str]:
        """
        Validate the operation specification.

        Args:
            spec: Step configuration from dotfiles.toml
            ctx: Operation context with paths and settings

        Returns:
            List of validation error messages (empty if valid)
        """
        pass

    @abstractmethod
    def apply(self, spec: StepConfig, ctx: OperationContext) -> OperationResult:
        """
        Apply the operation.

        Args:
            spec: Step configuration from dotfiles.toml
            ctx: Operation context with paths and settings

        Returns:
            OperationResult with success status and any error message
        """
        pass

    @abstractmethod
    def rollback(
        self, spec: StepConfig, ctx: OperationContext, rollback_data: Dict[str, Any]
    ) -> bool:
        """
        Rollback the operation.

        Args:
            spec: Step configuration from dotfiles.toml
            ctx: Operation context with paths and settings
            rollback_data: Data saved during apply for rollback

        Returns:
            True if rollback succeeded, False otherwise
        """
        pass

    def dry_run(self, spec: StepConfig, ctx: OperationContext) -> OperationResult:
        """
        Simulate the operation without making changes.

        Args:
            spec: Step configuration from dotfiles.toml
            ctx: Operation context with paths and settings

        Returns:
            OperationResult indicating what would happen
        """
        # Validate first
        errors = self.validate(spec, ctx)
        if errors:
            return OperationResult(
                success=False,
                operation_id=0,  # Will be updated by executor
                operation_type=self.name,
                message=f"Validation failed: {'; '.join(errors)}",
                dry_run=True,
            )

        # Default dry run just reports what would be done
        src_path = ctx.get_src_path()
        dst_path = ctx.get_dst_path()

        message = f"Would {self.name}"
        if src_path:
            message += f" {src_path}"
        if dst_path:
            message += f" to {dst_path}"

        return OperationResult(
            success=True,
            operation_id=0,  # Will be updated by executor
            operation_type=self.name,
            message=message,
            dry_run=True,
        )

    # Utility methods for subclasses

    def _calculate_checksum(self, file_path: Path) -> Optional[str]:
        """Calculate SHA256 checksum of a file."""
        if not file_path.exists() or not file_path.is_file():
            return None

        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _backup_file(self, file_path: Path, ctx: OperationContext) -> Optional[Path]:
        """
        Create a backup of a file.

        Args:
            file_path: Path to file to backup
            ctx: Operation context

        Returns:
            Path to backup file, or None if no backup needed
        """
        if not file_path.exists():
            return None

        if not ctx.should_create_backup():
            return None

        # Create backup directory
        backup_base = Path.home() / ".local" / "state" / "dotfiles" / "backups"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = backup_base / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create backup path preserving directory structure
        relative_path = (
            file_path.relative_to(Path.home())
            if file_path.is_relative_to(Path.home())
            else file_path
        )
        backup_path = backup_dir / str(relative_path).replace("/", "_")

        # Copy file or directory
        if file_path.is_dir():
            shutil.copytree(file_path, backup_path, dirs_exist_ok=True)
        else:
            shutil.copy2(file_path, backup_path)

        self.logger.info(f"Created backup: {backup_path}")
        return backup_path

    def _validate_paths(self, spec: StepConfig, ctx: OperationContext) -> List[str]:
        """
        Common path validation for operations.

        Args:
            spec: Step configuration
            ctx: Operation context

        Returns:
            List of validation errors
        """
        errors = []

        # Check if we should skip this operation
        if ctx.should_skip_platform():
            errors.append(
                f"Operation not applicable for platform {ctx.execution_context.system_info.platform}"
            )

        if ctx.should_skip_variant():
            errors.append(f"Operation not applicable for variant {ctx.execution_context.variant}")

        # Validate source path if needed
        src_path = ctx.get_src_path()
        if src_path and spec.src:
            if not src_path.exists():
                errors.append(f"Source path does not exist: {src_path}")

        # Validate destination path security
        dst_path = ctx.get_dst_path()
        if dst_path and spec.dst:
            # Check against security whitelist/blacklist
            # Note: Security validation will be implemented in Phase 2
            # For Phase 1, we allow all paths within home directory
            if not str(dst_path.resolve()).startswith(str(Path.home())):
                errors.append(f"Destination path outside home directory not allowed: {dst_path}")

        return errors

    def _is_path_allowed(self, path: Path, security_config: Any) -> bool:
        """Check if a path is allowed by security configuration."""
        path_str = str(path.resolve())

        # Check blacklist first (takes precedence)
        if hasattr(security_config, "blacklist_paths"):
            for pattern in security_config.blacklist_paths or []:
                pattern = pattern.replace("$HOME", str(Path.home()))
                if self._path_matches_pattern(path_str, pattern):
                    return False

        # Check whitelist
        if hasattr(security_config, "whitelist_paths"):
            whitelist = security_config.whitelist_paths or []
            if not whitelist:
                return True  # No whitelist means all paths allowed

            for pattern in whitelist:
                pattern = pattern.replace("$HOME", str(Path.home()))
                if self._path_matches_pattern(path_str, pattern):
                    return True
            return False  # Not in whitelist

        return True  # No security config means allowed

    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a glob pattern."""
        from fnmatch import fnmatch

        # Handle glob patterns
        if "*" in pattern or "?" in pattern:
            return fnmatch(path, pattern)

        # Handle prefix matching for directories
        if pattern.endswith("/"):
            return path.startswith(pattern) or path.startswith(pattern.rstrip("/"))

        # Exact match
        return path == pattern

    def _prepare_rollback_data(
        self,
        spec: StepConfig,
        ctx: OperationContext,
        backup_path: Optional[Path] = None,
        original_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Prepare rollback data for an operation.

        Args:
            spec: Step configuration
            ctx: Operation context
            backup_path: Path to backup if created
            original_state: Original state before operation

        Returns:
            Dictionary with rollback information
        """
        rollback_data = {
            "operation_type": self.name,
            "timestamp": datetime.now().isoformat(),
            "spec": spec.model_dump(),
        }

        if backup_path:
            rollback_data["backup_path"] = str(backup_path)

        if original_state:
            rollback_data["original_state"] = original_state

        src_path = ctx.get_src_path()
        dst_path = ctx.get_dst_path()

        if src_path:
            rollback_data["src_path"] = str(src_path)
        if dst_path:
            rollback_data["dst_path"] = str(dst_path)

        return rollback_data
