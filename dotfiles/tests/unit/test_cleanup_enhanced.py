#!/usr/bin/env python3
"""
Unit tests for enhanced cleanup functionality (Phase 4).

This module tests the EnhancedOrphanedOperationCleaner class and related
Phase 4 cleanup operations including selective filtering and restoration.
"""

import json
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from dotfiles_sync.cleanup_enhanced import (
    CleanupFilters,
    EnhancedCleanupResult,
    EnhancedOrphanedOperationCleaner,
    RestorationResult,
)
from dotfiles_sync.config_drift import (
    ConfigDriftResult,
    ConfigDriftType,
    ConfigDriftSeverity,
)
from dotfiles_sync.models import StepConfig, OperationType
from dotfiles_sync.state_database import StateDatabase


class TestCleanupFilters:
    """Test the CleanupFilters model."""

    def test_cleanup_filters_creation(self):
        """Test creating cleanup filters."""
        filters = CleanupFilters(
            paths=["/home/user/.zshrc", "/home/user/.vimrc"],
            operations=["link", "copy"],
            before=datetime.now() - timedelta(days=7),
            interactive=True,
            variant="personal",
        )

        assert len(filters.paths) == 2
        assert len(filters.operations) == 2
        assert filters.interactive is True
        assert filters.variant == "personal"
        assert filters.before is not None

    def test_cleanup_filters_defaults(self):
        """Test default values for cleanup filters."""
        filters = CleanupFilters()
        assert filters.paths is None
        assert filters.operations is None
        assert filters.before is None
        assert filters.interactive is False
        assert filters.variant is None


class TestEnhancedCleanupResult:
    """Test the EnhancedCleanupResult model."""

    def test_enhanced_cleanup_result_creation(self):
        """Test creating an enhanced cleanup result."""
        result = EnhancedCleanupResult(
            cleaned_count=5,
            failed_count=1,
            backed_up_files=["/tmp/backup1", "/tmp/backup2"],
            removed_files=["/tmp/removed1"],
            orphaned_operations=[1, 2, 3],
            errors=["Error message"],
            transaction_id="test-tx-123",
            cleanup_type="selective",
            filters_applied={"paths": ["/home/user/.zshrc"]},
        )

        assert result.cleaned_count == 5
        assert result.failed_count == 1
        assert len(result.backed_up_files) == 2
        assert len(result.removed_files) == 1
        assert len(result.orphaned_operations) == 3
        assert len(result.errors) == 1
        assert result.transaction_id == "test-tx-123"
        assert result.cleanup_type == "selective"
        assert result.filters_applied is not None
        assert not result.success  # Has failures

    def test_enhanced_cleanup_result_success_property(self):
        """Test the success property of enhanced cleanup result."""
        # Successful cleanup
        success_result = EnhancedCleanupResult(cleaned_count=3, failed_count=0)
        assert success_result.success

        # Failed cleanup
        failed_result = EnhancedCleanupResult(cleaned_count=2, failed_count=1)
        assert not failed_result.success


class TestRestorationResult:
    """Test the RestorationResult model."""

    def test_restoration_result_creation(self):
        """Test creating a restoration result."""
        result = RestorationResult(
            restored_count=3,
            failed_count=1,
            restored_files=["/home/user/.zshrc", "/home/user/.vimrc"],
            errors=["Failed to restore .tmux.conf"],
            transaction_id="restore-tx-456",
        )

        assert result.restored_count == 3
        assert result.failed_count == 1
        assert len(result.restored_files) == 2
        assert len(result.errors) == 1
        assert result.transaction_id == "restore-tx-456"
        assert not result.success  # Has failures

    def test_restoration_result_success_property(self):
        """Test the success property of restoration result."""
        # Successful restoration
        success_result = RestorationResult(restored_count=5, failed_count=0)
        assert success_result.success

        # Failed restoration
        failed_result = RestorationResult(restored_count=3, failed_count=2)
        assert not failed_result.success


class TestEnhancedOrphanedOperationCleaner:
    """Test the EnhancedOrphanedOperationCleaner class."""

    @pytest.fixture
    def mock_database(self):
        """Create a mock database."""
        db = MagicMock(spec=StateDatabase)
        
        # Mock connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 123
        mock_cursor.fetchall.return_value = []
        mock_cursor.execute.return_value = None
        
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit.return_value = None
        
        db.conn = mock_conn
        
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
        """Create an EnhancedOrphanedOperationCleaner instance."""
        with patch('dotfiles_sync.cleanup_enhanced.ImpactAnalyzer'):
            with patch('dotfiles_sync.cleanup_enhanced.ConfirmationPrompt'):
                with patch('dotfiles_sync.cleanup_enhanced.SelectiveOperationFilter'):
                    return EnhancedOrphanedOperationCleaner(mock_database)

    @pytest.fixture
    def sample_operations(self):
        """Create sample operations for testing."""
        return [
            ConfigDriftResult(
                drift_type=ConfigDriftType.ORPHANED,
                dst_path="/home/user/.zshrc",
                operation_type="link",
                current_config=None,
                applied_config={"src": "zsh/zshrc"},
                applied_step_hash="hash1",
                impact="Will be cleaned",
                severity=ConfigDriftSeverity.WARNING
            ),
            ConfigDriftResult(
                drift_type=ConfigDriftType.ORPHANED,
                dst_path="/home/user/.vimrc",
                operation_type="copy",
                current_config=None,
                applied_config={"src": "vim/vimrc"},
                applied_step_hash="hash2",
                impact="Will be cleaned",
                severity=ConfigDriftSeverity.INFO
            ),
            ConfigDriftResult(
                drift_type=ConfigDriftType.MODIFIED,
                dst_path="/home/user/.gitconfig",
                operation_type="link",
                current_config={"src": "git/gitconfig.new"},
                applied_config={"src": "git/gitconfig"},
                applied_step_hash="hash3",
                impact="Will be updated",
                severity=ConfigDriftSeverity.ERROR
            ),
        ]

    def test_apply_filters_by_paths(self, cleaner, sample_operations):
        """Test filtering operations by paths."""
        filters = CleanupFilters(paths=["/home/user/.zshrc"])
        
        filtered = cleaner._apply_filters(sample_operations, filters)
        
        assert len(filtered) == 1
        assert filtered[0].dst_path == "/home/user/.zshrc"

    def test_apply_filters_by_operations(self, cleaner, sample_operations):
        """Test filtering operations by operation types."""
        filters = CleanupFilters(operations=["copy"])
        
        filtered = cleaner._apply_filters(sample_operations, filters)
        
        assert len(filtered) == 1
        assert filtered[0].operation_type == "copy"

    def test_apply_filters_multiple_criteria(self, cleaner, sample_operations):
        """Test filtering with multiple criteria."""
        filters = CleanupFilters(
            paths=["/home/user/.zshrc", "/home/user/.vimrc"],
            operations=["link"],
        )
        
        filtered = cleaner._apply_filters(sample_operations, filters)
        
        # Should only include .zshrc (it's both in paths and has operation type "link")
        assert len(filtered) == 1
        assert filtered[0].dst_path == "/home/user/.zshrc"

    def test_clean_operations_selective_dry_run(self, cleaner, mock_database, sample_operations):
        """Test selective cleanup in dry run mode."""
        filters = CleanupFilters(paths=["/home/user/.zshrc"])
        
        result = cleaner.clean_operations_selective(
            sample_operations,
            filters=filters,
            remove_files=False,
            backup=True,
            dry_run=True,
        )
        
        assert result.cleaned_count == 1
        assert result.failed_count == 0
        assert result.cleanup_type == "selective"
        assert result.filters_applied is not None
        
        # In dry run, database should not be modified
        mock_database.conn.cursor().execute.assert_not_called()

    @patch('dotfiles_sync.cleanup_enhanced.Path')
    def test_clean_operations_selective_with_backup(self, mock_path, cleaner, mock_database, sample_operations):
        """Test selective cleanup with backup."""
        filters = CleanupFilters(operations=["link"])
        
        # Mock file existence
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_path.return_value.expanduser.return_value = mock_file
        
        with patch('dotfiles_sync.cleanup_enhanced.shutil.copy2'):
            result = cleaner.clean_operations_selective(
                sample_operations,
                filters=filters,
                remove_files=False,
                backup=True,
                dry_run=False,
            )
        
        # Should clean 2 link operations
        assert result.cleaned_count == 2
        assert len(result.orphaned_operations) == 2

    def test_store_orphaned_operation(self, cleaner, mock_database):
        """Test storing an orphaned operation in the database."""
        op = ConfigDriftResult(
            drift_type=ConfigDriftType.ORPHANED,
            dst_path="/home/user/.zshrc",
            operation_type="link",
            current_config=None,
            applied_config={"src": "zsh/zshrc"},
            applied_step_hash="hash1",
            impact="Will be cleaned",
            severity=ConfigDriftSeverity.WARNING
        )
        
        orphaned_id = cleaner._store_orphaned_operation(
            op, "tx-123", remove_files=True, backup=True
        )
        
        assert orphaned_id == 123  # Mock lastrowid
        
        # Verify database insert was called
        mock_database.conn.cursor().execute.assert_called_once()
        call_args = mock_database.conn.cursor().execute.call_args[0]
        assert "INSERT INTO orphaned_operations" in call_args[0]

    def test_restore_orphaned_operations_empty(self, cleaner, mock_database):
        """Test restoration when no orphaned operations exist."""
        mock_database.conn.cursor().fetchall.return_value = []
        
        result = cleaner.restore_orphaned_operations(transaction_id="tx-123")
        
        assert result.restored_count == 0
        assert result.failed_count == 0
        assert result.success

    def test_restore_orphaned_operations_with_data(self, cleaner, mock_database):
        """Test restoration with orphaned operations."""
        # Mock the _get_restorable_operations method to return data directly
        mock_op_data = [{
            'id': 1,
            'dst_path': '/home/user/.zshrc',
            'operation_type': 'link',
            'config': '{"src": "zsh/zshrc"}',
            'restoration_data': '{"restorable": true, "backup_path": "/tmp/backup"}',
            'step_hash': 'hash1',
        }]
        
        with patch.object(cleaner, '_get_restorable_operations', return_value=mock_op_data):
            with patch('dotfiles_sync.cleanup_enhanced.Path') as mock_path:
                mock_backup = MagicMock()
                mock_backup.exists.return_value = True
                mock_backup.is_file.return_value = True
                mock_path.return_value = mock_backup
                
                with patch('dotfiles_sync.cleanup_enhanced.shutil.copy2'):
                    # Mock the mark_operation_restored method
                    with patch.object(cleaner, '_mark_operation_restored'):
                        result = cleaner.restore_orphaned_operations(
                            operation_ids=[1], dry_run=False
                        )
        
        assert result.restored_count == 1
        assert result.failed_count == 0
        assert len(result.restored_files) == 1

    def test_interactive_selection_quit(self, cleaner, sample_operations):
        """Test interactive selection when user quits."""
        # Mock the impact analyzer
        mock_impact_report = MagicMock()
        mock_impact_report.operation_type = "link"
        mock_impact_report.dst_path = "/home/user/.zshrc"
        
        with patch.object(cleaner.impact_analyzer, 'analyze_operation', return_value=mock_impact_report):
            # Mock the confirmation prompt to return QUIT
            with patch.object(cleaner.confirmation_prompt, 'confirm_operation') as mock_confirm:
                from safety.confirmation import ConfirmationChoice, ConfirmationResult
                mock_confirm.return_value = ConfirmationResult(
                    choice=ConfirmationChoice.QUIT,
                    message="User quit"
                )
                
                selected = cleaner._interactive_selection(sample_operations)
                
                assert selected == []

    def test_interactive_selection_yes_all(self, cleaner, sample_operations):
        """Test interactive selection when user selects all."""
        # Mock the impact analyzer
        mock_impact_report = MagicMock()
        mock_impact_report.operation_type = "link"
        mock_impact_report.dst_path = "/home/user/.zshrc"
        
        with patch.object(cleaner.impact_analyzer, 'analyze_operation', return_value=mock_impact_report):
            # Mock the confirmation prompt to return ALL
            with patch.object(cleaner.confirmation_prompt, 'confirm_operation') as mock_confirm:
                from safety.confirmation import ConfirmationChoice, ConfirmationResult
                mock_confirm.return_value = ConfirmationResult(
                    choice=ConfirmationChoice.ALL,
                    message="User selected all"
                )
                
                selected = cleaner._interactive_selection(sample_operations)
                
                assert len(selected) == len(sample_operations)

    def test_record_cleanup_history(self, cleaner, mock_database):
        """Test recording cleanup history in the database."""
        result = EnhancedCleanupResult(
            cleaned_count=3,
            failed_count=0,
            backed_up_files=["/tmp/backup1"],
            removed_files=["/tmp/removed1"],
            cleanup_type="selective",
        )
        
        filters = CleanupFilters(paths=["/home/user/.zshrc"])
        
        cleaner._record_cleanup_history("tx-123", result, filters, dry_run=False)
        
        # Verify database insert was called
        mock_database.conn.cursor().execute.assert_called_once()
        call_args = mock_database.conn.cursor().execute.call_args[0]
        assert "INSERT INTO cleanup_history" in call_args[0]
        
        # Verify commit was called
        mock_database.conn.commit.assert_called_once()