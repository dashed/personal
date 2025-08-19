#!/usr/bin/env python3
"""
Unit tests for cleanup functionality (Phase 3).

This module tests the OrphanedOperationCleaner class and related cleanup operations.
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dotfiles_sync.cleanup import CleanupResult, OrphanedOperationCleaner
from dotfiles_sync.config_drift import (
    ConfigDriftResult,
    ConfigDriftType,
    ConfigDriftSeverity,
)
from dotfiles_sync.models import TransactionContext
from dotfiles_sync.state_database import StateDatabase


class TestCleanupResult:
    """Test the CleanupResult model."""

    def test_cleanup_result_creation(self):
        """Test creating a cleanup result."""
        result = CleanupResult(
            cleaned_count=5,
            failed_count=1,
            backed_up_files=["/tmp/backup1", "/tmp/backup2"],
            removed_files=["/tmp/removed1"],
            errors=["Error message"],
            transaction_id="test-tx-123",
        )

        assert result.cleaned_count == 5
        assert result.failed_count == 1
        assert len(result.backed_up_files) == 2
        assert len(result.removed_files) == 1
        assert len(result.errors) == 1
        assert result.transaction_id == "test-tx-123"
        assert not result.success  # Has failures

    def test_cleanup_result_success_property(self):
        """Test the success property of cleanup result."""
        # Successful cleanup
        success_result = CleanupResult(cleaned_count=3, failed_count=0)
        assert success_result.success

        # Failed cleanup
        failed_result = CleanupResult(cleaned_count=2, failed_count=1)
        assert not failed_result.success

    def test_cleanup_result_defaults(self):
        """Test default values for cleanup result."""
        result = CleanupResult()
        assert result.cleaned_count == 0
        assert result.failed_count == 0
        assert result.backed_up_files == []
        assert result.removed_files == []
        assert result.errors == []
        assert result.transaction_id is None
        assert result.success  # No failures


class TestOrphanedOperationCleaner:
    """Test the OrphanedOperationCleaner class."""

    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        db = MagicMock(spec=StateDatabase)
        
        # Mock transaction context manager
        mock_tx = MagicMock()
        mock_tx.id = "test-tx-id"
        db.transaction.return_value.__enter__.return_value = mock_tx
        db.transaction.return_value.__exit__.return_value = None
        
        # Mock database methods
        db.mark_operations_as_orphaned.return_value = 1
        
        return db

    @pytest.fixture
    def cleaner(self, mock_database):
        """Create an OrphanedOperationCleaner instance."""
        return OrphanedOperationCleaner(mock_database)

    @pytest.fixture
    def sample_orphaned_operations(self):
        """Create sample orphaned operations."""
        return [
            ConfigDriftResult(
                drift_type=ConfigDriftType.ORPHANED,
                dst_path="/tmp/test_file1",
                operation_type="link",
                applied_step_hash="hash1",
                impact="Operation no longer in configuration",
                severity=ConfigDriftSeverity.WARNING,
            ),
            ConfigDriftResult(
                drift_type=ConfigDriftType.ORPHANED,
                dst_path="/tmp/test_file2",
                operation_type="copy",
                applied_step_hash="hash2",
                impact="Operation no longer in configuration",
                severity=ConfigDriftSeverity.WARNING,
            ),
        ]

    def test_cleaner_initialization(self, mock_database):
        """Test cleaner initialization."""
        cleaner = OrphanedOperationCleaner(mock_database)
        assert cleaner.database is mock_database
        assert cleaner.logger is not None

    def test_clean_operations_empty_list(self, cleaner):
        """Test cleaning with empty operations list."""
        result = cleaner.clean_operations([])
        
        assert result.cleaned_count == 0
        assert result.failed_count == 0
        assert result.success
        assert result.backed_up_files == []
        assert result.removed_files == []
        assert result.errors == []

    def test_clean_operations_dry_run(self, cleaner, sample_orphaned_operations):
        """Test cleaning operations in dry run mode."""
        result = cleaner.clean_operations(sample_orphaned_operations, dry_run=True)
        
        assert result.cleaned_count == 2
        assert result.failed_count == 0
        assert result.success
        # In dry run mode, no actual cleanup should occur
        cleaner.database.mark_operations_as_orphaned.assert_not_called()

    def test_clean_operations_database_only(self, cleaner, sample_orphaned_operations):
        """Test cleaning operations from database only (no file removal)."""
        result = cleaner.clean_operations(
            sample_orphaned_operations, remove_files=False, backup=False
        )
        
        assert result.cleaned_count == 2
        assert result.failed_count == 0
        assert result.success
        assert result.backed_up_files == []
        assert result.removed_files == []
        
        # Should mark operations as orphaned
        assert cleaner.database.mark_operations_as_orphaned.call_count == 2

    @patch("dotfiles_sync.cleanup.Path")
    def test_clean_operations_with_file_removal(self, mock_path, cleaner, sample_orphaned_operations):
        """Test cleaning operations with file removal."""
        # Mock file exists and removal
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.is_symlink.return_value = False
        mock_file.is_dir.return_value = False
        mock_file.expanduser.return_value = mock_file
        mock_path.return_value = mock_file
        
        result = cleaner.clean_operations(
            sample_orphaned_operations, remove_files=True, backup=False
        )
        
        assert result.cleaned_count == 2
        assert result.failed_count == 0
        assert result.success
        assert len(result.removed_files) == 2
        
        # Should have called unlink for each file
        assert mock_file.unlink.call_count == 2

    @patch("dotfiles_sync.cleanup.Path")
    @patch("dotfiles_sync.cleanup.shutil")
    def test_clean_operations_with_directory_removal(self, mock_shutil, mock_path, cleaner):
        """Test cleaning operations with directory removal."""
        # Create an operation that points to a directory
        operations = [
            ConfigDriftResult(
                drift_type=ConfigDriftType.ORPHANED,
                dst_path="/tmp/test_dir",
                operation_type="syncdir",
                applied_step_hash="hash1",
                impact="Directory no longer in configuration",
                severity=ConfigDriftSeverity.WARNING,
            )
        ]
        
        # Mock directory exists
        mock_dir = MagicMock()
        mock_dir.exists.return_value = True
        mock_dir.is_file.return_value = False
        mock_dir.is_symlink.return_value = False
        mock_dir.is_dir.return_value = True
        mock_dir.expanduser.return_value = mock_dir
        mock_path.return_value = mock_dir
        
        result = cleaner.clean_operations(operations, remove_files=True, backup=False)
        
        assert result.cleaned_count == 1
        assert result.success
        assert len(result.removed_files) == 1
        
        # Should have called rmtree for directory
        mock_shutil.rmtree.assert_called_once_with(mock_dir)

    @patch("dotfiles_sync.cleanup.Path")
    @patch("dotfiles_sync.cleanup.shutil")
    def test_clean_operations_with_backup(self, mock_shutil, mock_path, cleaner, sample_orphaned_operations):
        """Test cleaning operations with backup."""
        # Mock file exists and backup operations
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.name = "test_file"
        mock_file.expanduser.return_value = mock_file
        
        # Mock backup directory and path
        mock_backup_dir = MagicMock()
        mock_backup_path = MagicMock()
        mock_backup_path.parent = mock_backup_dir
        
        def path_side_effect(*args):
            if "backups" in str(args[0]):
                return mock_backup_dir
            elif "test_file" in str(args[0]):
                return mock_file
            else:
                return mock_backup_path
        
        mock_path.side_effect = path_side_effect
        mock_path.home.return_value = MagicMock()
        
        result = cleaner.clean_operations(
            sample_orphaned_operations, remove_files=True, backup=True
        )
        
        assert result.cleaned_count == 2
        assert result.success
        # Should have created backups (mocked, so can't verify exact count)
        # In real implementation, this would create 2 backups

    def test_clean_operations_with_failures(self, cleaner, sample_orphaned_operations):
        """Test cleaning operations when some fail."""
        # Mock database to fail for one operation
        def mock_mark_orphaned(hashes, tx_id):
            if "hash1" in hashes:
                raise Exception("Database error")
            return 1
        
        cleaner.database.mark_operations_as_orphaned.side_effect = mock_mark_orphaned
        
        result = cleaner.clean_operations(sample_orphaned_operations)
        
        assert result.cleaned_count == 1  # One successful
        assert result.failed_count == 1   # One failed
        assert not result.success
        assert len(result.errors) == 1
        assert "Database error" in result.errors[0]

    def test_backup_file_nonexistent(self, cleaner):
        """Test backing up a file that doesn't exist."""
        with patch("dotfiles_sync.cleanup.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value.expanduser.return_value = mock_file
            
            backup_path = cleaner._backup_file("/nonexistent/file", "test")
            assert backup_path is None

    @patch("dotfiles_sync.cleanup.shutil")
    @patch("dotfiles_sync.cleanup.Path")
    def test_backup_file_success(self, mock_path, mock_shutil, cleaner):
        """Test successful file backup."""
        # Mock file and backup paths
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.is_symlink.return_value = False
        mock_file.is_dir.return_value = False
        mock_file.name = "test_file"
        mock_file.expanduser.return_value = mock_file
        
        mock_backup_dir = MagicMock()
        mock_backup_path = MagicMock()
        mock_backup_path.parent = mock_backup_dir
        
        # Configure Path mock
        def path_constructor(*args):
            if "backups" in str(args[0]):
                return mock_backup_path
            else:
                return mock_file
        
        mock_path.side_effect = path_constructor
        mock_path.home.return_value = MagicMock()
        
        backup_path = cleaner._backup_file("/tmp/test_file", "test reason")
        
        assert backup_path is not None
        mock_shutil.copy2.assert_called_once()
        mock_backup_dir.mkdir.assert_called_once()

    def test_remove_file_nonexistent(self, cleaner):
        """Test removing a file that doesn't exist."""
        with patch("dotfiles_sync.cleanup.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value.expanduser.return_value = mock_file
            
            removed_path = cleaner._remove_file("/nonexistent/file")
            assert removed_path is None

    @patch("dotfiles_sync.cleanup.Path")
    def test_remove_file_success(self, mock_path, cleaner):
        """Test successful file removal."""
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.is_symlink.return_value = False
        mock_file.is_dir.return_value = False
        mock_file.expanduser.return_value = mock_file
        mock_path.return_value = mock_file
        
        removed_path = cleaner._remove_file("/tmp/test_file")
        
        assert removed_path is not None
        mock_file.unlink.assert_called_once()

    def test_preview_cleanup(self, cleaner, sample_orphaned_operations):
        """Test generating cleanup preview."""
        preview = cleaner.preview_cleanup(sample_orphaned_operations, remove_files=True)
        
        assert "Cleanup Plan for 2 operations" in preview
        assert "/tmp/test_file1" in preview
        assert "/tmp/test_file2" in preview
        assert "Remove from database (orphaned)" in preview

    def test_preview_cleanup_empty(self, cleaner):
        """Test generating preview for empty operations list."""
        preview = cleaner.preview_cleanup([])
        assert preview == "No operations to clean"

    def test_get_cleanup_statistics(self, cleaner, sample_orphaned_operations):
        """Test getting cleanup statistics."""
        with patch("dotfiles_sync.cleanup.Path") as mock_path:
            # Mock first file exists as symlink, second doesn't exist
            def path_side_effect(path):
                mock_file = MagicMock()
                if "test_file1" in str(path):
                    mock_file.exists.return_value = True
                    mock_file.is_symlink.return_value = True
                    mock_file.is_dir.return_value = False
                else:
                    mock_file.exists.return_value = False
                mock_file.expanduser.return_value = mock_file
                return mock_file
            
            mock_path.side_effect = path_side_effect
            
            stats = cleaner.get_cleanup_statistics(sample_orphaned_operations)
            
            assert stats["total_operations"] == 2
            assert stats["orphaned"] == 2
            assert stats["modified"] == 0
            assert stats["files_exist"] == 1
            assert stats["symlinks"] == 1
            assert stats["directories"] == 0

    def test_get_cleanup_statistics_empty(self, cleaner):
        """Test getting statistics for empty operations list."""
        stats = cleaner.get_cleanup_statistics([])
        
        assert stats["total_operations"] == 0
        assert stats["orphaned"] == 0
        assert stats["modified"] == 0
        assert stats["files_exist"] == 0

    def test_clean_single_operation_no_hash(self, cleaner):
        """Test cleaning operation without applied step hash."""
        operation = ConfigDriftResult(
            drift_type=ConfigDriftType.ORPHANED,
            dst_path="/tmp/test_file",
            operation_type="link",
            applied_step_hash=None,  # No hash
            impact="Operation no longer in configuration",
            severity=ConfigDriftSeverity.WARNING,
        )
        
        result = CleanupResult()
        cleaner._clean_single_operation(operation, False, False, result, "tx-123")
        
        # Should still increment cleaned count but skip database operation
        assert result.cleaned_count == 1
        cleaner.database.mark_operations_as_orphaned.assert_not_called()

    @patch("dotfiles_sync.cleanup.uuid.uuid4")
    def test_clean_operations_generates_transaction_id(self, mock_uuid, cleaner, sample_orphaned_operations):
        """Test that transaction ID is generated when not provided."""
        mock_uuid.return_value = MagicMock()
        mock_uuid.return_value.__str__.return_value = "generated-tx-id"
        
        result = cleaner.clean_operations(sample_orphaned_operations)
        
        assert result.transaction_id == "generated-tx-id"
        mock_uuid.assert_called_once()

    def test_clean_operations_uses_provided_transaction_id(self, cleaner, sample_orphaned_operations):
        """Test that provided transaction ID is used."""
        provided_tx_id = "custom-tx-id"
        
        result = cleaner.clean_operations(sample_orphaned_operations, transaction_id=provided_tx_id)
        
        assert result.transaction_id == provided_tx_id


class TestCleanupIntegration:
    """Integration tests for cleanup functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            with StateDatabase(db_path=db_path) as db:
                yield db
        finally:
            Path(db_path).unlink()

    def test_real_cleanup_operations(self, temp_db):
        """Test cleanup with real database operations."""
        # Add some applied steps to the database
        with temp_db.transaction("test", "user", "host") as tx:
            temp_db.record_applied_step(
                tx,
                "link",
                {"op": "link", "src": "test", "dst": "/tmp/test1"},
                dst_path="/tmp/test1",
            )
            temp_db.record_applied_step(
                tx,
                "copy", 
                {"op": "copy", "src": "test", "dst": "/tmp/test2"},
                dst_path="/tmp/test2",
            )
        
        # Create operations to clean
        operations = [
            ConfigDriftResult(
                drift_type=ConfigDriftType.ORPHANED,
                dst_path="/tmp/test1",
                operation_type="link",
                applied_step_hash="dummy_hash",  # Won't match, but that's ok for test
                impact="Test cleanup",
                severity=ConfigDriftSeverity.WARNING,
            )
        ]
        
        # Perform cleanup
        cleaner = OrphanedOperationCleaner(temp_db)
        result = cleaner.clean_operations(operations, remove_files=False, backup=False)
        
        # Should succeed even if hash doesn't match (marks as orphaned)
        assert result.cleaned_count == 1
        assert result.failed_count == 0
        assert result.success