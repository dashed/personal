"""
Backup manager for the Dotfiles Management System.

This module implements comprehensive backup functionality including:
- Automatic backups before destructive operations
- Backup retention and cleanup policies
- Recovery and rollback capabilities
- Integration with the state database

Follows the backup structure specified in spec.md:
~/.local/state/dotfiles/backups/TIMESTAMP/
├── manifest.json    # Backup metadata
├── files/           # Actual file backups
└── transaction.log  # Operation log
"""

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from dotfiles_sync.models import SafetyConfig, SystemInfo


class BackupManifest(BaseModel):
    """Metadata for a backup operation."""

    backup_id: str = Field(..., description="Unique backup identifier (timestamp)")
    created_at: datetime = Field(default_factory=datetime.now)
    created_by_transaction: Optional[str] = Field(
        None, description="Transaction ID that created this backup"
    )
    reason: str = Field(..., description="Why this backup was created")
    system_info: Optional[SystemInfo] = Field(None, description="System information at backup time")
    files_backed_up: List[Dict[str, Any]] = Field(default_factory=list)
    total_size_bytes: int = Field(0, description="Total backup size in bytes")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), Path: str}


class BackupManager:
    """
    Manages backup operations for the dotfiles system.

    Features:
    - Automatic backups before destructive operations
    - Timestamped backup directories
    - Backup retention and cleanup
    - Manifest tracking
    - Integration with state database
    """

    def __init__(
        self, backup_root: Optional[Path] = None, safety_config: Optional[SafetyConfig] = None
    ):
        """
        Initialize backup manager.

        Args:
            backup_root: Root directory for backups. Defaults to ~/.local/state/dotfiles/backups
            safety_config: Safety configuration for retention policies
        """
        self.backup_root = backup_root or Path.home() / ".local/state/dotfiles/backups"
        self.safety_config = safety_config or SafetyConfig.model_construct()
        self.system_info = SystemInfo.from_current_system()

        # Ensure backup directory exists
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self, files_to_backup: List[Path], reason: str, transaction_id: Optional[str] = None
    ) -> str:
        """
        Create a backup of specified files.

        Args:
            files_to_backup: List of file paths to backup
            reason: Reason for creating backup (e.g., "before link operation")
            transaction_id: Associated transaction ID

        Returns:
            Backup ID (timestamp string)

        Raises:
            BackupError: If backup creation fails
        """
        if not self.safety_config.backup_before_modify:
            return ""  # Backups disabled

        # Generate backup ID from timestamp
        timestamp = datetime.now()
        backup_id = timestamp.strftime("%Y-%m-%d-%H%M%S")
        backup_dir = self.backup_root / backup_id

        try:
            # Create backup directory structure
            backup_dir.mkdir(parents=True, exist_ok=True)
            files_dir = backup_dir / "files"
            files_dir.mkdir(exist_ok=True)

            manifest = BackupManifest(
                backup_id=backup_id,
                created_at=timestamp,
                created_by_transaction=transaction_id,
                reason=reason,
                system_info=self.system_info,
                total_size_bytes=0,
            )

            total_size = 0

            # Backup each file
            for src_path in files_to_backup:
                if not src_path.exists():
                    continue

                # Create safe backup filename (replace path separators)
                safe_name = str(src_path).replace("/", "-").replace("\\", "-")
                if safe_name.startswith("-"):
                    safe_name = safe_name[1:]
                backup_file_path = files_dir / safe_name

                # Backup the file/directory
                if src_path.is_file():
                    shutil.copy2(src_path, backup_file_path)
                    file_size = src_path.stat().st_size
                elif src_path.is_dir():
                    shutil.copytree(src_path, backup_file_path, dirs_exist_ok=True)
                    file_size = sum(f.stat().st_size for f in src_path.rglob("*") if f.is_file())
                elif src_path.is_symlink():
                    # Preserve symlink
                    backup_file_path.symlink_to(src_path.readlink())
                    file_size = 0
                else:
                    continue

                total_size += file_size

                # Add to manifest
                manifest.files_backed_up.append(
                    {
                        "original_path": str(src_path),
                        "backup_path": str(backup_file_path),
                        "size_bytes": file_size,
                        "is_file": src_path.is_file(),
                        "is_dir": src_path.is_dir(),
                        "is_symlink": src_path.is_symlink(),
                        "permissions": oct(src_path.stat().st_mode)[-3:]
                        if src_path.exists()
                        else None,
                    }
                )

            manifest.total_size_bytes = total_size

            # Write manifest
            manifest_path = backup_dir / "manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest.model_dump(), f, indent=2, default=str)

            # Create transaction log placeholder
            transaction_log_path = backup_dir / "transaction.log"
            with open(transaction_log_path, "w") as f:
                f.write(f"Backup created at {timestamp.isoformat()}\n")
                f.write(f"Reason: {reason}\n")
                if transaction_id:
                    f.write(f"Transaction ID: {transaction_id}\n")
                f.write(f"Files backed up: {len(manifest.files_backed_up)}\n")

            # Update latest symlink
            latest_link = self.backup_root / "latest"
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()
            latest_link.symlink_to(backup_id)

            return backup_id

        except Exception as e:
            # Clean up partial backup on failure
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)
            raise BackupError(f"Failed to create backup: {e}") from e

    def list_backups(self) -> List[BackupManifest]:
        """
        List all available backups, sorted by creation time (newest first).

        Returns:
            List of backup manifests
        """
        backups: List[BackupManifest] = []

        if not self.backup_root.exists():
            return backups

        for backup_dir in self.backup_root.iterdir():
            if backup_dir.is_dir() and backup_dir.name != "latest":
                manifest_path = backup_dir / "manifest.json"
                if manifest_path.exists():
                    try:
                        with open(manifest_path) as f:
                            data = json.load(f)
                        # Parse datetime strings back to datetime objects
                        if "created_at" in data and isinstance(data["created_at"], str):
                            from datetime import datetime

                            data["created_at"] = datetime.fromisoformat(
                                data["created_at"].replace("Z", "+00:00")
                            )
                        backups.append(BackupManifest(**data))
                    except (json.JSONDecodeError, Exception) as e:
                        # Skip invalid manifests
                        import logging

                        logging.debug(f"Failed to load manifest from {manifest_path}: {e}")
                        continue

        # Sort by creation time (newest first)
        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    def get_backup(self, backup_id: str) -> Optional[BackupManifest]:
        """
        Get backup manifest by ID.

        Args:
            backup_id: Backup identifier

        Returns:
            Backup manifest or None if not found
        """
        manifest_path = self.backup_root / backup_id / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path) as f:
                data = json.load(f)
            # Parse datetime strings back to datetime objects
            if "created_at" in data and isinstance(data["created_at"], str):
                from datetime import datetime

                data["created_at"] = datetime.fromisoformat(
                    data["created_at"].replace("Z", "+00:00")
                )
            return BackupManifest(**data)
        except (json.JSONDecodeError, Exception):
            return None

    def restore_backup(self, backup_id: str, files_to_restore: Optional[List[str]] = None) -> bool:
        """
        Restore files from a backup.

        Args:
            backup_id: Backup identifier
            files_to_restore: Specific files to restore (None = all files)

        Returns:
            True if successful, False otherwise
        """
        manifest = self.get_backup(backup_id)
        if not manifest:
            return False

        backup_dir = self.backup_root / backup_id
        files_dir = backup_dir / "files"

        if not files_dir.exists():
            return False

        try:
            for file_info in manifest.files_backed_up:
                original_path = Path(file_info["original_path"])
                backup_path = Path(file_info["backup_path"])

                # Skip if specific files requested and this isn't one of them
                if files_to_restore and str(original_path) not in files_to_restore:
                    continue

                if not backup_path.exists():
                    continue

                # Create parent directories if needed
                original_path.parent.mkdir(parents=True, exist_ok=True)

                # Remove existing file/dir/symlink
                if original_path.exists() or original_path.is_symlink():
                    if original_path.is_dir() and not original_path.is_symlink():
                        shutil.rmtree(original_path)
                    else:
                        original_path.unlink()

                # Restore the backup
                if file_info["is_dir"]:
                    shutil.copytree(backup_path, original_path)
                elif file_info["is_symlink"]:
                    # Restore symlink
                    target = backup_path.readlink()
                    original_path.symlink_to(target)
                else:
                    shutil.copy2(backup_path, original_path)

                # Restore permissions if available
                if file_info.get("permissions"):
                    try:
                        original_path.chmod(int(file_info["permissions"], 8))
                    except (ValueError, OSError):
                        pass

            return True

        except Exception:
            return False

    def cleanup_expired_backups(self) -> int:
        """
        Clean up expired backups based on retention policy.

        Returns:
            Number of backups cleaned up
        """
        if self.safety_config.backup_retention_days <= 0:
            return 0  # Retention disabled

        cutoff_date = datetime.now() - timedelta(days=self.safety_config.backup_retention_days)
        backups = self.list_backups()
        cleaned_count = 0

        for backup in backups:
            if backup.created_at < cutoff_date:
                backup_dir = self.backup_root / backup.backup_id
                if backup_dir.exists():
                    try:
                        shutil.rmtree(backup_dir)
                        cleaned_count += 1
                    except OSError:
                        # Skip if can't delete
                        continue

        return cleaned_count

    def get_backup_stats(self) -> Dict[str, Any]:
        """
        Get backup statistics.

        Returns:
            Dictionary with backup statistics
        """
        backups = self.list_backups()

        if not backups:
            return {
                "total_backups": 0,
                "total_size_bytes": 0,
                "oldest_backup": None,
                "newest_backup": None,
                "disk_usage_mb": 0,
            }

        total_size = sum(b.total_size_bytes for b in backups)
        oldest = min(backups, key=lambda b: b.created_at)
        newest = max(backups, key=lambda b: b.created_at)

        return {
            "total_backups": len(backups),
            "total_size_bytes": total_size,
            "disk_usage_mb": round(total_size / (1024 * 1024), 2),
            "oldest_backup": oldest.backup_id,
            "newest_backup": newest.backup_id,
            "oldest_date": oldest.created_at.isoformat(),
            "newest_date": newest.created_at.isoformat(),
        }


class BackupError(Exception):
    """Exception raised for backup-related errors."""

    pass
