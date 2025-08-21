"""
Cleanup functionality for the Dotfiles Management System.

This module provides functionality to clean up orphaned operations and reconcile
configuration drift by removing operations that are no longer in the configuration.
"""

import getpass
import logging
import shutil
import socket
import uuid
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

from dotfiles_sync.config_drift import ConfigDriftResult, ConfigDriftType
from dotfiles_sync.state_database import StateDatabase


logger = logging.getLogger(__name__)


class CleanupResult(BaseModel):
    """Result of cleanup operation."""

    cleaned_count: int = Field(0, description="Number of operations cleaned")
    failed_count: int = Field(0, description="Number of operations that failed to clean")
    backed_up_files: List[str] = Field(default_factory=list, description="Files backed up")
    removed_files: List[str] = Field(default_factory=list, description="Files removed")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    transaction_id: Optional[str] = Field(None, description="Transaction ID used")

    @property
    def success(self) -> bool:
        """Check if cleanup was successful."""
        return self.failed_count == 0


class OrphanedOperationCleaner:
    """
    Handles cleanup of orphaned operations.

    This class provides functionality to clean up operations that are no longer
    in the configuration file but remain in the database, including options
    to backup and remove files.
    """

    def __init__(self, database: StateDatabase):
        """
        Initialize the cleaner.

        Args:
            database: State database instance for cleanup operations
        """
        self.database = database
        self.logger = logging.getLogger(__name__)

    def clean_operations(
        self,
        operations: List[ConfigDriftResult],
        remove_files: bool = False,
        backup: bool = True,
        transaction_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> CleanupResult:
        """
        Clean up orphaned or modified operations.

        Args:
            operations: List of drift results to clean
            remove_files: Whether to remove files from filesystem
            backup: Whether to backup files before removal
            transaction_id: Optional transaction ID to use
            dry_run: Preview mode without making changes

        Returns:
            CleanupResult with details of what was cleaned
        """
        result = CleanupResult(transaction_id=transaction_id)

        if not operations:
            self.logger.info("No operations to clean")
            return result

        # Generate transaction ID if not provided
        if not transaction_id:
            transaction_id = str(uuid.uuid4())
            result.transaction_id = transaction_id

        # Start transaction for cleanup
        with self.database.transaction(
            variant="cleanup", user=getpass.getuser(), hostname=socket.gethostname()
        ) as tx:
            try:
                for op in operations:
                    try:
                        if dry_run:
                            result.cleaned_count += 1
                            self.logger.info(f"DRY RUN: Would clean {op.dst_path}")
                            continue

                        self._clean_single_operation(op, remove_files, backup, result, tx.id)

                    except Exception as e:
                        result.failed_count += 1
                        error_msg = f"{op.dst_path}: {str(e)}"
                        result.errors.append(error_msg)
                        self.logger.error(f"Failed to clean operation {op.dst_path}: {e}")

                self.logger.info(
                    f"Cleanup complete: {result.cleaned_count} cleaned, {result.failed_count} failed"
                )

            except Exception as e:
                self.logger.error(f"Cleanup transaction failed: {e}")
                raise

        return result

    def _clean_single_operation(
        self,
        op: ConfigDriftResult,
        remove_files: bool,
        backup: bool,
        result: CleanupResult,
        transaction_id: str,
    ) -> None:
        """
        Clean a single operation.

        Args:
            op: Configuration drift result to clean
            remove_files: Whether to remove files
            backup: Whether to backup before removal
            result: Result object to update
            transaction_id: Transaction ID for database operations
        """
        # Backup file if requested and file exists
        if backup and remove_files and op.dst_path:
            backup_path = self._backup_file(op.dst_path, op.drift_type.value)
            if backup_path:
                result.backed_up_files.append(backup_path)

        # Mark operation as orphaned in database
        if op.applied_step_hash:
            affected = self.database.mark_operations_as_orphaned(
                [op.applied_step_hash], transaction_id
            )
            if affected > 0:
                self.logger.debug(f"Marked {affected} operations as orphaned for {op.dst_path}")
        else:
            self.logger.warning(
                f"No applied step hash for {op.dst_path}, skipping database cleanup"
            )

        # Remove file if requested
        if remove_files and op.dst_path:
            removed_path = self._remove_file(op.dst_path)
            if removed_path:
                result.removed_files.append(removed_path)

        result.cleaned_count += 1
        self.logger.info(f"Cleaned operation: {op.dst_path} ({op.operation_type})")

    def _backup_file(self, dst_path: str, reason: str) -> Optional[str]:
        """
        Create a backup of a file before cleanup.

        Args:
            dst_path: Destination path to backup
            reason: Reason for backup

        Returns:
            Path to backup file if successful, None otherwise
        """
        try:
            file_path = Path(dst_path).expanduser()
            if not file_path.exists():
                self.logger.debug(f"File {dst_path} does not exist, skipping backup")
                return None

            # Create backup directory
            backup_dir = Path.home() / ".local" / "state" / "dotfiles" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Generate backup filename with timestamp
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.name}.{timestamp}.cleanup-backup"

            # Include relative path structure in backup
            try:
                rel_path = file_path.relative_to(Path.home())
                backup_path = backup_dir / rel_path.parent / backup_name
                backup_path.parent.mkdir(parents=True, exist_ok=True)
            except ValueError:
                # Path is not relative to home, use flat structure
                backup_path = backup_dir / backup_name

            # Create backup
            if file_path.is_file() or file_path.is_symlink():
                shutil.copy2(file_path, backup_path)
            elif file_path.is_dir():
                shutil.copytree(file_path, backup_path)
            else:
                self.logger.warning(f"Unknown file type for {dst_path}, skipping backup")
                return None

            self.logger.info(f"Backed up {dst_path} to {backup_path}")
            return str(backup_path)

        except Exception as e:
            self.logger.error(f"Failed to backup {dst_path}: {e}")
            return None

    def _remove_file(self, dst_path: str) -> Optional[str]:
        """
        Remove a file from the filesystem.

        Args:
            dst_path: Path to file to remove

        Returns:
            Path that was removed if successful, None otherwise
        """
        try:
            file_path = Path(dst_path).expanduser()
            if not file_path.exists():
                self.logger.debug(f"File {dst_path} does not exist, skipping removal")
                return None

            if file_path.is_symlink() or file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                self.logger.warning(f"Unknown file type for {dst_path}, skipping removal")
                return None

            self.logger.info(f"Removed {dst_path}")
            return str(file_path)

        except Exception as e:
            self.logger.error(f"Failed to remove {dst_path}: {e}")
            return None

    def preview_cleanup(
        self, operations: List[ConfigDriftResult], remove_files: bool = False
    ) -> str:
        """
        Generate a preview of what cleanup would do.

        Args:
            operations: Operations to clean
            remove_files: Whether files would be removed

        Returns:
            String description of cleanup plan
        """
        if not operations:
            return "No operations to clean"

        lines = [f"Cleanup Plan for {len(operations)} operations:\n"]

        for op in operations:
            action = f"  • {op.dst_path} ({op.operation_type})"

            if op.drift_type == ConfigDriftType.ORPHANED:
                action += " - Remove from database (orphaned)"
            elif op.drift_type == ConfigDriftType.MODIFIED:
                action += " - Reset database state (modified)"

            if remove_files and op.dst_path:
                file_path = Path(op.dst_path).expanduser()
                if file_path.exists():
                    action += " + DELETE FILE"

            lines.append(action)

        return "\n".join(lines)

    def get_cleanup_statistics(self, operations: List[ConfigDriftResult]) -> dict:
        """
        Get statistics about what would be cleaned.

        Args:
            operations: Operations to analyze

        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            "total_operations": len(operations),
            "orphaned": sum(1 for op in operations if op.drift_type == ConfigDriftType.ORPHANED),
            "modified": sum(1 for op in operations if op.drift_type == ConfigDriftType.MODIFIED),
            "files_exist": 0,
            "symlinks": 0,
            "directories": 0,
        }

        for op in operations:
            if op.dst_path:
                file_path = Path(op.dst_path).expanduser()
                if file_path.exists():
                    stats["files_exist"] += 1
                    if file_path.is_symlink():
                        stats["symlinks"] += 1
                    elif file_path.is_dir():
                        stats["directories"] += 1

        return stats
