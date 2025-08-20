#!/usr/bin/env python3
"""
Unit tests for Phase 4 CLI commands.

This module tests the enhanced clean command with filters and the new
restore-orphaned command functionality.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import click
import pytest
from click.testing import CliRunner

from dotfiles_sync.cli import cli
from dotfiles_sync.cleanup_enhanced import (
    EnhancedCleanupResult,
    RestorationResult,
)
from dotfiles_sync.config_drift import (
    ConfigDriftResult,
    ConfigDriftType,
    ConfigDriftSeverity,
    ConfigDriftSummary,
)


class TestCleanCommandWithFilters:
    """Test the enhanced clean command with Phase 4 filters."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_config_and_drift(self):
        """Mock configuration loading and drift detection."""
        with patch('dotfiles_sync.cli.ConfigLoader') as mock_loader:
            with patch('dotfiles_sync.cli.StateDatabase') as mock_db:
                with patch('dotfiles_sync.cli.ConfigDriftDetector') as mock_detector:
                    # Mock config
                    mock_config = MagicMock()
                    mock_loader.return_value.load.return_value = mock_config
                    
                    # Mock drift results
                    mock_drift = ConfigDriftSummary(
                        orphaned_operations=[
                            ConfigDriftResult(
                                drift_type=ConfigDriftType.ORPHANED,
                                dst_path="/home/user/.zshrc",
                                operation_type="link",
                                current_config=None,
                                applied_config={"src": "zsh/zshrc"},
                                applied_step_hash="hash1",
                                impact="Will be cleaned from database",
                                severity=ConfigDriftSeverity.WARNING
                            ),
                            ConfigDriftResult(
                                drift_type=ConfigDriftType.ORPHANED,
                                dst_path="/home/user/.vimrc",
                                operation_type="copy",
                                current_config=None,
                                applied_config={"src": "vim/vimrc"},
                                applied_step_hash="hash2",
                                impact="Will be cleaned from database",
                                severity=ConfigDriftSeverity.INFO
                            ),
                        ],
                        modified_operations=[],
                        new_operations=[],
                    )
                    mock_detector.return_value.detect_drift.return_value = mock_drift
                    
                    yield mock_loader, mock_db, mock_detector

    def test_clean_with_paths_filter(self, runner, mock_config_and_drift):
        """Test clean command with --paths filter."""
        mock_loader, mock_db, mock_detector = mock_config_and_drift
        
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner') as mock_cleaner:
            # Mock cleanup result
            mock_result = EnhancedCleanupResult(
                cleaned_count=1,
                failed_count=0,
                orphaned_operations=[1],
            )
            mock_cleaner.return_value.clean_operations_selective.return_value = mock_result
            
            # Run command with path filter
            result = runner.invoke(cli, [
                '--force',  # Global option must come before subcommand
                'clean',
                '--paths', '/home/user/.zshrc'
            ])
            
            assert result.exit_code == 0
            assert "Enhanced Cleanup Analysis" in result.output
            assert "Path filters: /home/user/.zshrc" in result.output
            
            # Verify cleaner was called with filters
            mock_cleaner.return_value.clean_operations_selective.assert_called_once()
            call_args = mock_cleaner.return_value.clean_operations_selective.call_args
            assert call_args[1]['filters'].paths == ['/home/user/.zshrc']

    def test_clean_with_operations_filter(self, runner, mock_config_and_drift):
        """Test clean command with --operations filter."""
        mock_loader, mock_db, mock_detector = mock_config_and_drift
        
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner') as mock_cleaner:
            # Mock cleanup result
            mock_result = EnhancedCleanupResult(
                cleaned_count=1,
                failed_count=0,
            )
            mock_cleaner.return_value.clean_operations_selective.return_value = mock_result
            
            # Run command with operation filter
            result = runner.invoke(cli, [
                'clean',
                '--operations', 'link',
                '--operations', 'copy',
                '--preview'
            ])
            
            assert result.exit_code == 0
            assert "Operation filters: link, copy" in result.output

    def test_clean_with_before_filter(self, runner, mock_config_and_drift):
        """Test clean command with --before date filter."""
        mock_loader, mock_db, mock_detector = mock_config_and_drift
        
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner') as mock_cleaner:
            # Mock cleanup result
            mock_result = EnhancedCleanupResult(
                cleaned_count=2,
                failed_count=0,
            )
            mock_cleaner.return_value.clean_operations_selective.return_value = mock_result
            
            # Run command with date filter
            before_date = "2024-01-01"
            result = runner.invoke(cli, [
                'clean',
                '--before', before_date,
                '--preview'
            ])
            
            assert result.exit_code == 0
            assert "Before date:" in result.output

    def test_clean_with_interactive_mode(self, runner, mock_config_and_drift):
        """Test clean command with --interactive mode."""
        mock_loader, mock_db, mock_detector = mock_config_and_drift
        
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner') as mock_cleaner:
            # Mock cleanup result
            mock_result = EnhancedCleanupResult(
                cleaned_count=1,
                failed_count=0,
            )
            mock_cleaner.return_value.clean_operations_selective.return_value = mock_result
            
            # Run command with interactive mode
            result = runner.invoke(cli, [
                'clean',
                '--interactive'
            ])
            
            assert result.exit_code == 0
            assert "Interactive mode: Yes" in result.output
            
            # Verify cleaner was called with interactive flag
            mock_cleaner.return_value.clean_operations_selective.assert_called_once()
            call_args = mock_cleaner.return_value.clean_operations_selective.call_args
            assert call_args[1]['filters'].interactive is True

    def test_clean_with_multiple_filters(self, runner, mock_config_and_drift):
        """Test clean command with multiple filters combined."""
        mock_loader, mock_db, mock_detector = mock_config_and_drift
        
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner') as mock_cleaner:
            # Mock cleanup result
            mock_result = EnhancedCleanupResult(
                cleaned_count=1,
                failed_count=0,
                orphaned_operations=[1],
                backed_up_files=["/tmp/backup1"],
            )
            mock_cleaner.return_value.clean_operations_selective.return_value = mock_result
            
            # Run command with multiple filters
            result = runner.invoke(cli, [
                'clean',
                '--paths', '/home/user/.zshrc',
                '--operations', 'link',
                '--remove-files',
                '--preview'
            ])
            
            assert result.exit_code == 0
            assert "Path filters: /home/user/.zshrc" in result.output
            assert "Operation filters: link" in result.output
            assert "Remove files: Yes" in result.output

    def test_clean_standard_mode_without_filters(self, runner, mock_config_and_drift):
        """Test that clean command uses standard mode when no filters are provided."""
        mock_loader, mock_db, mock_detector = mock_config_and_drift
        
        with patch('dotfiles_sync.cli.OrphanedOperationCleaner') as mock_cleaner:
            # Mock standard cleanup result
            from dotfiles_sync.cleanup import CleanupResult
            mock_result = CleanupResult(
                cleaned_count=2,
                failed_count=0,
            )
            mock_cleaner.return_value.clean_operations.return_value = mock_result
            
            # Run command without filters
            result = runner.invoke(cli, [
                'clean',
                '--preview'
            ])
            
            assert result.exit_code == 0
            assert "Cleanup Analysis" in result.output
            # Should not mention "Enhanced"
            assert "Enhanced Cleanup Analysis" not in result.output


class TestRestoreOrphanedCommand:
    """Test the restore-orphaned command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_database_with_orphaned(self):
        """Mock database with orphaned operations."""
        with patch('dotfiles_sync.cli.StateDatabase') as mock_db:
            # Mock cursor for listing orphaned operations
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                (1, '/home/user/.zshrc', 'link', '2024-01-01 12:00:00', 
                 'tx-123-456', 'removed_from_config'),
                (2, '/home/user/.vimrc', 'copy', '2024-01-02 13:00:00',
                 'tx-789-012', 'modified'),
            ]
            
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            
            mock_db.return_value.__enter__.return_value.conn = mock_conn
            
            yield mock_db

    def test_restore_orphaned_list(self, runner, mock_database_with_orphaned):
        """Test restore-orphaned --list command."""
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner'):
            result = runner.invoke(cli, ['restore-orphaned', '--list'])
            
            assert result.exit_code == 0
            assert "Restorable Orphaned Operations" in result.output
            assert "Found 2 restorable operation(s):" in result.output
            assert "/home/user/.zshrc" in result.output
            assert "/home/user/.vimrc" in result.output
            assert "Type: link" in result.output
            assert "Type: copy" in result.output

    def test_restore_orphaned_by_transaction_id(self, runner, mock_database_with_orphaned):
        """Test restore-orphaned with --transaction-id."""
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner') as mock_cleaner:
            # Mock restoration result
            mock_result = RestorationResult(
                restored_count=2,
                failed_count=0,
                restored_files=['/home/user/.zshrc', '/home/user/.vimrc'],
                transaction_id='restore-tx-123',
            )
            mock_cleaner.return_value.restore_orphaned_operations.return_value = mock_result
            
            result = runner.invoke(cli, [
                'restore-orphaned',
                '--transaction-id', 'tx-123-456'
            ])
            
            assert result.exit_code == 0
            assert "Successfully restored 2 operations" in result.output
            assert "/home/user/.zshrc" in result.output
            assert "/home/user/.vimrc" in result.output
            
            # Verify restoration was called with correct transaction ID
            mock_cleaner.return_value.restore_orphaned_operations.assert_called_once()
            call_args = mock_cleaner.return_value.restore_orphaned_operations.call_args
            assert call_args[1]['transaction_id'] == 'tx-123-456'

    def test_restore_orphaned_by_operation_ids(self, runner, mock_database_with_orphaned):
        """Test restore-orphaned with --operation-ids."""
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner') as mock_cleaner:
            # Mock restoration result
            mock_result = RestorationResult(
                restored_count=1,
                failed_count=0,
                restored_files=['/home/user/.zshrc'],
            )
            mock_cleaner.return_value.restore_orphaned_operations.return_value = mock_result
            
            result = runner.invoke(cli, [
                'restore-orphaned',
                '--operation-ids', '1',
                '--operation-ids', '3'
            ])
            
            assert result.exit_code == 0
            assert "Successfully restored 1 operations" in result.output
            
            # Verify restoration was called with correct operation IDs
            mock_cleaner.return_value.restore_orphaned_operations.assert_called_once()
            call_args = mock_cleaner.return_value.restore_orphaned_operations.call_args
            assert call_args[1]['operation_ids'] == [1, 3]

    def test_restore_orphaned_preview_mode(self, runner, mock_database_with_orphaned):
        """Test restore-orphaned with --preview."""
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner') as mock_cleaner:
            # Mock restoration result for preview
            mock_result = RestorationResult(
                restored_count=2,
                failed_count=0,
                restored_files=['/home/user/.zshrc', '/home/user/.vimrc'],
            )
            mock_cleaner.return_value.restore_orphaned_operations.return_value = mock_result
            
            result = runner.invoke(cli, [
                'restore-orphaned',
                '--transaction-id', 'tx-123-456',
                '--preview'
            ])
            
            assert result.exit_code == 0
            assert "PREVIEW MODE" in result.output
            assert "Successfully restored 2 operations" in result.output
            assert "This was a preview" in result.output
            
            # Verify dry_run was set to True
            mock_cleaner.return_value.restore_orphaned_operations.assert_called_once()
            call_args = mock_cleaner.return_value.restore_orphaned_operations.call_args
            assert call_args[1]['dry_run'] is True

    def test_restore_orphaned_with_failures(self, runner, mock_database_with_orphaned):
        """Test restore-orphaned with some failures."""
        with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner') as mock_cleaner:
            # Mock restoration result with failures
            mock_result = RestorationResult(
                restored_count=1,
                failed_count=1,
                restored_files=['/home/user/.zshrc'],
                errors=['Failed to restore /home/user/.vimrc: File exists'],
            )
            mock_cleaner.return_value.restore_orphaned_operations.return_value = mock_result
            
            result = runner.invoke(cli, [
                'restore-orphaned',
                '--operation-ids', '1',
                '--operation-ids', '2'
            ])
            
            assert result.exit_code == 1  # Should exit with error
            assert "Restored 1 operations with 1 failures" in result.output
            assert "Failed to restore /home/user/.vimrc" in result.output

    def test_restore_orphaned_no_operations(self, runner):
        """Test restore-orphaned when no operations are found."""
        with patch('dotfiles_sync.cli.StateDatabase') as mock_db:
            # Mock empty result
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            
            mock_db.return_value.__enter__.return_value.conn = mock_conn
            
            with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner'):
                result = runner.invoke(cli, ['restore-orphaned', '--list'])
                
                assert result.exit_code == 0
                assert "No restorable operations found" in result.output

    def test_restore_orphaned_missing_arguments(self, runner):
        """Test restore-orphaned without required arguments."""
        with patch('dotfiles_sync.cli.StateDatabase'):
            with patch('dotfiles_sync.cleanup_enhanced.EnhancedOrphanedOperationCleaner'):
                result = runner.invoke(cli, ['restore-orphaned'])
                
                assert result.exit_code == 0
                assert "Specify --transaction-id or --operation-ids" in result.output
                assert "Use --list to see restorable operations" in result.output