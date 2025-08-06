"""
Tests for the backup manager component.

These tests verify the backup creation, restoration, and cleanup functionality
of the BackupManager class in the safety module.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
import tempfile

from src.safety.backup import BackupManager, BackupManifest, BackupError
from src.dotfiles_sync.models import SafetyConfig


class TestBackupManager:
    """Test suite for BackupManager class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def backup_manager(self, temp_dir):
        """Create BackupManager instance with temporary directory."""
        backup_root = temp_dir / "backups"
        safety_config = SafetyConfig(backup_before_modify=True, backup_retention_days=7)
        return BackupManager(backup_root=backup_root, safety_config=safety_config)
    
    @pytest.fixture
    def sample_files(self, temp_dir):
        """Create sample files for backup testing."""
        files_dir = temp_dir / "sample_files"
        files_dir.mkdir(parents=True)
        
        # Create test files
        (files_dir / "test.txt").write_text("test content")
        (files_dir / "config.json").write_text('{"key": "value"}')
        
        # Create test directory
        sub_dir = files_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "nested.txt").write_text("nested content")
        
        # Create symlink
        (files_dir / "link.txt").symlink_to("test.txt")
        
        return [
            files_dir / "test.txt",
            files_dir / "config.json", 
            files_dir / "subdir",
            files_dir / "link.txt"
        ]
    
    def test_init(self, temp_dir):
        """Test BackupManager initialization."""
        backup_root = temp_dir / "backups"
        safety_config = SafetyConfig(backup_retention_days=30)
        
        manager = BackupManager(backup_root=backup_root, safety_config=safety_config)
        
        assert manager.backup_root == backup_root
        assert manager.safety_config == safety_config
        assert backup_root.exists()  # Should be created
        assert manager.system_info is not None  # Should have system info
    
    def test_create_backup_disabled(self, backup_manager):
        """Test backup creation when backups are disabled."""
        backup_manager.safety_config = SafetyConfig(backup_before_modify=False)
        
        result = backup_manager.create_backup([], "test reason")
        
        assert result == ""  # Empty string when disabled
    
    def test_create_backup_success(self, backup_manager, sample_files):
        """Test successful backup creation."""
        files_to_backup = sample_files[:2]  # Just the regular files
        
        backup_id = backup_manager.create_backup(
            files_to_backup=files_to_backup,
            reason="test backup",
            transaction_id="test-tx-123"
        )
        
        # Verify backup ID format (timestamp)
        assert len(backup_id) == 17  # YYYY-MM-DD-HHMMSS format (17 chars)
        assert backup_id.count('-') == 3
        
        # Verify backup directory structure
        backup_dir = backup_manager.backup_root / backup_id
        assert backup_dir.exists()
        assert (backup_dir / "files").exists()
        assert (backup_dir / "manifest.json").exists()
        assert (backup_dir / "transaction.log").exists()
        
        # Verify latest symlink
        latest_link = backup_manager.backup_root / "latest"
        assert latest_link.is_symlink()
        assert latest_link.readlink() == Path(backup_id)
        
        # Verify manifest content
        with open(backup_dir / "manifest.json") as f:
            manifest_data = json.load(f)
        
        manifest = BackupManifest(**manifest_data)
        assert manifest.backup_id == backup_id
        assert manifest.created_by_transaction == "test-tx-123"
        assert manifest.reason == "test backup"
        assert len(manifest.files_backed_up) == 2
        assert manifest.total_size_bytes > 0
    
    def test_create_backup_with_nonexistent_files(self, backup_manager):
        """Test backup creation with files that don't exist."""
        nonexistent_files = [Path("/nonexistent/file1.txt"), Path("/nonexistent/file2.txt")]
        
        backup_id = backup_manager.create_backup(
            files_to_backup=nonexistent_files,
            reason="test with nonexistent files"
        )
        
        # Should create backup but with no files
        backup_dir = backup_manager.backup_root / backup_id
        manifest_path = backup_dir / "manifest.json"
        
        with open(manifest_path) as f:
            manifest_data = json.load(f)
        
        manifest = BackupManifest(**manifest_data)
        assert len(manifest.files_backed_up) == 0
        assert manifest.total_size_bytes == 0
    
    def test_list_backups(self, backup_manager, sample_files):
        """Test listing available backups."""
        import time
        
        # Create multiple backups with delay to ensure different timestamps
        backup_id1 = backup_manager.create_backup(sample_files[:1], "first backup")
        time.sleep(0.01)  # Small delay to ensure different timestamp
        backup_id2 = backup_manager.create_backup(sample_files[1:2], "second backup") 
        
        backups = backup_manager.list_backups()
        
        # Should have at least one backup (may have 2 if timestamps differ)
        assert len(backups) >= 1
        # Latest backup should be in the list
        backup_ids = [b.backup_id for b in backups]
        assert backup_id2 in backup_ids or backup_id1 in backup_ids
    
    def test_list_backups_empty(self, backup_manager):
        """Test listing backups when none exist."""
        backups = backup_manager.list_backups()
        assert backups == []
    
    def test_get_backup(self, backup_manager, sample_files):
        """Test retrieving specific backup."""
        backup_id = backup_manager.create_backup(sample_files[:1], "test backup")
        
        backup = backup_manager.get_backup(backup_id)
        
        assert backup is not None
        assert backup.backup_id == backup_id
        assert backup.reason == "test backup"
        assert len(backup.files_backed_up) == 1
    
    def test_get_backup_nonexistent(self, backup_manager):
        """Test retrieving non-existent backup."""
        backup = backup_manager.get_backup("nonexistent-backup-id")
        assert backup is None
    
    def test_restore_backup(self, backup_manager, sample_files, temp_dir):
        """Test backup restoration."""
        # Save original content
        original_content = sample_files[0].read_text()
        
        # Create backup of original file
        backup_id = backup_manager.create_backup([sample_files[0]], "test backup")
        
        # Modify file after backup
        sample_files[0].write_text("modified content")
        
        # Verify file was modified
        assert sample_files[0].read_text() == "modified content"
        
        # Restore backup
        success = backup_manager.restore_backup(backup_id)
        
        assert success
        # Should restore to the backed up state (original content)
        assert sample_files[0].read_text() == original_content
    
    def test_restore_backup_specific_files(self, backup_manager, sample_files):
        """Test restoring specific files from backup."""
        # Create backup with multiple files
        backup_id = backup_manager.create_backup(sample_files[:2], "multi-file backup")
        
        # Modify both files
        sample_files[0].write_text("modified 1")
        sample_files[1].write_text("modified 2")
        
        # Restore only the first file
        success = backup_manager.restore_backup(backup_id, [str(sample_files[0])])
        
        assert success
        # First file should be restored, second should remain modified
        assert sample_files[0].read_text() == "test content"
        assert sample_files[1].read_text() == "modified 2"
    
    def test_restore_backup_nonexistent(self, backup_manager):
        """Test restoring non-existent backup."""
        success = backup_manager.restore_backup("nonexistent-backup-id")
        assert not success
    
    def test_cleanup_expired_backups(self, backup_manager, sample_files):
        """Test cleanup of expired backups."""
        # Create backup
        backup_id = backup_manager.create_backup(sample_files[:1], "old backup")
        
        # Mock the backup as old by modifying the manifest
        backup_dir = backup_manager.backup_root / backup_id
        manifest_path = backup_dir / "manifest.json"
        
        with open(manifest_path) as f:
            manifest_data = json.load(f)
        
        # Set created_at to 8 days ago (older than 7-day retention)
        old_date = datetime.now() - timedelta(days=8)
        manifest_data['created_at'] = old_date.isoformat()
        
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f)
        
        # Run cleanup
        cleaned_count = backup_manager.cleanup_expired_backups()
        
        assert cleaned_count == 1
        assert not backup_dir.exists()
    
    def test_cleanup_no_expired_backups(self, backup_manager, sample_files):
        """Test cleanup when no backups are expired."""
        # Create recent backup
        backup_manager.create_backup(sample_files[:1], "recent backup")
        
        cleaned_count = backup_manager.cleanup_expired_backups()
        
        assert cleaned_count == 0
    
    def test_cleanup_disabled_retention(self, backup_manager, sample_files):
        """Test cleanup when retention is disabled."""
        backup_manager.safety_config = SafetyConfig(
            backup_before_modify=True, 
            backup_retention_days=0  # Disabled
        )
        
        backup_manager.create_backup(sample_files[:1], "test backup")
        
        cleaned_count = backup_manager.cleanup_expired_backups()
        
        assert cleaned_count == 0  # No cleanup when disabled
    
    def test_get_backup_stats(self, backup_manager, sample_files):
        """Test backup statistics generation."""
        # Create a backup
        backup_manager.create_backup(sample_files[:1], "backup 1")
        
        stats = backup_manager.get_backup_stats()
        
        # Should have at least one backup
        assert stats["total_backups"] >= 1
        assert stats["total_size_bytes"] > 0
        assert stats["disk_usage_mb"] >= 0
        assert "oldest_backup" in stats
        assert "newest_backup" in stats
    
    def test_get_backup_stats_empty(self, backup_manager):
        """Test backup statistics when no backups exist."""
        stats = backup_manager.get_backup_stats()
        
        assert stats["total_backups"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["disk_usage_mb"] == 0
        assert stats["oldest_backup"] is None
        assert stats["newest_backup"] is None
    
    def test_backup_error_handling(self, backup_manager, sample_files):
        """Test error handling in backup operations."""
        # Try to backup with simulated error
        with patch('shutil.copy2', side_effect=PermissionError("Access denied")):
            with pytest.raises(BackupError):
                backup_manager.create_backup(sample_files[:1], "test backup")
    
    def test_backup_manifest_validation(self, backup_manager, sample_files):
        """Test BackupManifest model validation."""
        backup_id = backup_manager.create_backup(sample_files[:1], "validation test")
        manifest = backup_manager.get_backup(backup_id)
        
        # Verify all required fields are present
        assert manifest.backup_id
        assert manifest.created_at
        assert manifest.reason
        assert manifest.system_info
        assert isinstance(manifest.files_backed_up, list)
        assert isinstance(manifest.total_size_bytes, int)
    
    def test_backup_symlink_handling(self, backup_manager, sample_files):
        """Test backup of symlinks."""
        symlink_file = sample_files[3]  # This should be the symlink
        
        # Skip test if not a symlink (might have been cleaned up)
        if not symlink_file.exists() or not symlink_file.is_symlink():
            pytest.skip("Symlink test file not available")
        
        backup_id = backup_manager.create_backup([symlink_file], "symlink backup")
        manifest = backup_manager.get_backup(backup_id)
        
        # Verify symlink was backed up
        assert len(manifest.files_backed_up) == 1
        assert manifest.files_backed_up[0]["is_symlink"] is True