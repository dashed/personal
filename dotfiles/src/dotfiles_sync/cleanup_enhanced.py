"""
Enhanced cleanup functionality for Phase 4: Advanced Safety and Rollback.

This module extends the cleanup functionality with:
- Orphaned operations tracking for restoration
- Selective cleanup with filters
- Interactive cleanup mode
- Restoration capabilities
"""

import getpass
import hashlib
import json
import logging
import shutil
import socket
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from pydantic import BaseModel, Field

from dotfiles_sync.config_drift import ConfigDriftResult, ConfigDriftType
from dotfiles_sync.state_database import StateDatabase
from dotfiles_sync.models import StepConfig, OperationType

# Import Phase 4 safety components
from safety.impact import ImpactAnalyzer, ImpactReport
from safety.confirmation import ConfirmationPrompt, SafetyConfirmationManager, ConfirmationChoice
from safety.resolver import SelectiveOperationFilter


logger = logging.getLogger(__name__)


class CleanupFilters(BaseModel):
    """Filters for selective cleanup operations."""
    
    paths: Optional[List[str]] = Field(None, description="Specific paths to clean")
    operations: Optional[List[str]] = Field(None, description="Operation types to clean")
    before: Optional[datetime] = Field(None, description="Clean operations before this date")
    interactive: bool = Field(False, description="Use interactive mode")
    variant: Optional[str] = Field(None, description="Specific variant to clean")


class EnhancedCleanupResult(BaseModel):
    """Enhanced result of cleanup operation with restoration tracking."""
    
    cleaned_count: int = Field(0, description="Number of operations cleaned")
    failed_count: int = Field(0, description="Number of operations that failed to clean")
    backed_up_files: List[str] = Field(default_factory=list, description="Files backed up")
    removed_files: List[str] = Field(default_factory=list, description="Files removed")
    orphaned_operations: List[int] = Field(default_factory=list, description="IDs of orphaned operations stored")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    transaction_id: Optional[str] = Field(None, description="Transaction ID used")
    cleanup_type: str = Field("selective", description="Type of cleanup performed")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Filters that were applied")
    
    @property
    def success(self) -> bool:
        """Check if cleanup was successful."""
        return self.failed_count == 0


class RestorationResult(BaseModel):
    """Result of restoration operation."""
    
    restored_count: int = Field(0, description="Number of operations restored")
    failed_count: int = Field(0, description="Number of operations that failed to restore")
    restored_files: List[str] = Field(default_factory=list, description="Files restored")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    transaction_id: Optional[str] = Field(None, description="Transaction ID used")
    
    @property
    def success(self) -> bool:
        """Check if restoration was successful."""
        return self.failed_count == 0


class EnhancedOrphanedOperationCleaner:
    """
    Enhanced cleanup with Phase 4 features including restoration capability.
    
    Features:
    - Stores orphaned operations for potential restoration
    - Supports selective cleanup with filters
    - Interactive mode with impact analysis
    - Restoration of previously cleaned operations
    - Cleanup history tracking
    """
    
    def __init__(self, database: StateDatabase):
        """
        Initialize the enhanced cleaner.
        
        Args:
            database: State database instance for cleanup operations
        """
        self.database = database
        self.logger = logging.getLogger(__name__)
        self.impact_analyzer = ImpactAnalyzer()
        self.confirmation_prompt = ConfirmationPrompt()
        self.operation_filter = SelectiveOperationFilter()
    
    def clean_operations_selective(
        self,
        operations: List[ConfigDriftResult],
        filters: CleanupFilters,
        remove_files: bool = False,
        backup: bool = True,
        dry_run: bool = False,
    ) -> EnhancedCleanupResult:
        """
        Enhanced cleanup with selective filtering and restoration tracking.
        
        Args:
            operations: List of drift results to potentially clean
            filters: Filters to apply for selective cleanup
            remove_files: Whether to remove files from filesystem
            backup: Whether to backup files before removal
            dry_run: Preview mode without making changes
            
        Returns:
            Enhanced cleanup result with restoration tracking
        """
        result = EnhancedCleanupResult(
            cleanup_type="selective" if filters else "all",
            filters_applied=filters.model_dump() if filters else None
        )
        
        # Apply filters
        filtered_operations = self._apply_filters(operations, filters)
        
        if not filtered_operations:
            self.logger.info("No operations match the cleanup filters")
            return result
        
        # Interactive mode - get user confirmation for each operation
        if filters.interactive:
            filtered_operations = self._interactive_selection(filtered_operations)
            if not filtered_operations:
                self.logger.info("No operations selected for cleanup")
                return result
        
        # Generate transaction ID
        transaction_id = str(uuid.uuid4())
        result.transaction_id = transaction_id
        
        # Start transaction for cleanup
        with self.database.transaction(
            variant=filters.variant or "cleanup",
            user=getpass.getuser(),
            hostname=socket.gethostname()
        ) as tx:
            try:
                for op in filtered_operations:
                    try:
                        if dry_run:
                            result.cleaned_count += 1
                            self.logger.info(f"DRY RUN: Would clean {op.dst_path}")
                            continue
                        
                        # Store orphaned operation for potential restoration
                        orphaned_id = self._store_orphaned_operation(
                            op, tx.id, remove_files, backup
                        )
                        if orphaned_id:
                            result.orphaned_operations.append(orphaned_id)
                        
                        # Perform actual cleanup
                        self._clean_single_operation_enhanced(
                            op, remove_files, backup, result, tx.id
                        )
                        
                    except Exception as e:
                        result.failed_count += 1
                        error_msg = f"{op.dst_path}: {str(e)}"
                        result.errors.append(error_msg)
                        self.logger.error(f"Failed to clean operation {op.dst_path}: {e}")
                
                # Record cleanup in history
                if not dry_run:
                    self._record_cleanup_history(
                        tx.id, result, filters, dry_run
                    )
                
                self.logger.info(
                    f"Cleanup complete: {result.cleaned_count} cleaned, "
                    f"{result.failed_count} failed, "
                    f"{len(result.orphaned_operations)} stored for restoration"
                )
                
            except Exception as e:
                self.logger.error(f"Cleanup transaction failed: {e}")
                raise
        
        return result
    
    def restore_orphaned_operations(
        self,
        transaction_id: Optional[str] = None,
        operation_ids: Optional[List[int]] = None,
        dry_run: bool = False
    ) -> RestorationResult:
        """
        Restore previously orphaned operations.
        
        Args:
            transaction_id: Restore all operations from a specific cleanup transaction
            operation_ids: Specific orphaned operation IDs to restore
            dry_run: Preview mode without making changes
            
        Returns:
            Result of restoration operation
        """
        result = RestorationResult()
        
        # Get orphaned operations to restore
        orphaned_ops = self._get_restorable_operations(transaction_id, operation_ids)
        
        if not orphaned_ops:
            self.logger.info("No orphaned operations found to restore")
            return result
        
        # Generate new transaction ID for restoration
        restore_tx_id = str(uuid.uuid4())
        result.transaction_id = restore_tx_id
        
        with self.database.transaction(
            variant="restore",
            user=getpass.getuser(),
            hostname=socket.gethostname()
        ) as tx:
            try:
                for op_data in orphaned_ops:
                    try:
                        if dry_run:
                            self.logger.info(
                                f"DRY RUN: Would restore {op_data['dst_path']} "
                                f"({op_data['operation_type']})"
                            )
                            result.restored_count += 1
                            continue
                        
                        # Restore the operation
                        restored = self._restore_single_operation(op_data, tx.id)
                        if restored:
                            result.restored_count += 1
                            if op_data.get('dst_path'):
                                result.restored_files.append(op_data['dst_path'])
                            
                            # Mark as restored in database
                            self._mark_operation_restored(op_data['id'], tx.id)
                        else:
                            result.failed_count += 1
                            
                    except Exception as e:
                        result.failed_count += 1
                        error_msg = f"Failed to restore operation {op_data.get('id')}: {str(e)}"
                        result.errors.append(error_msg)
                        self.logger.error(error_msg)
                
                self.logger.info(
                    f"Restoration complete: {result.restored_count} restored, "
                    f"{result.failed_count} failed"
                )
                
            except Exception as e:
                self.logger.error(f"Restoration transaction failed: {e}")
                raise
        
        return result
    
    def _apply_filters(
        self,
        operations: List[ConfigDriftResult],
        filters: CleanupFilters
    ) -> List[ConfigDriftResult]:
        """Apply filters to operation list."""
        filtered = operations
        
        # Filter by paths
        if filters.paths:
            path_set = set(filters.paths)
            filtered = [
                op for op in filtered
                if op.dst_path and any(
                    op.dst_path.startswith(path) or path in op.dst_path
                    for path in path_set
                )
            ]
        
        # Filter by operation types
        if filters.operations:
            op_types = set(filters.operations)
            filtered = [
                op for op in filtered
                if op.operation_type in op_types
            ]
        
        # Filter by date
        if filters.before:
            # This would require timestamp information from the operations
            # For now, we'll skip this filter
            pass
        
        # Filter by variant
        if filters.variant:
            # Filter operations by variant if available
            pass
        
        return filtered
    
    def _interactive_selection(
        self,
        operations: List[ConfigDriftResult]
    ) -> List[ConfigDriftResult]:
        """Interactively select operations to clean."""
        selected = []
        
        for i, op in enumerate(operations, 1):
            # Create a mock StepConfig for impact analysis
            # Use applied_config src if available, otherwise use a placeholder
            src = "unknown"
            if op.applied_config and 'src' in op.applied_config:
                src = op.applied_config['src']
            
            step = StepConfig(
                op=OperationType.LINK if op.operation_type == "link" else OperationType.COPY,
                src=src,
                dst=op.dst_path
            )
            
            # Analyze impact
            from dotfiles_sync.context import OperationContext
            mock_context = OperationContext(
                execution_context=None,
                operation_type=op.operation_type,
                step_config=step,
                sequence_num=i
            )
            
            impact_report = self.impact_analyzer.analyze_operation(
                step, mock_context, i
            )
            
            # Get user confirmation
            confirmation = self.confirmation_prompt.confirm_operation(
                impact_report, i, len(operations)
            )
            
            if confirmation.choice == ConfirmationChoice.YES:
                selected.append(op)
            elif confirmation.choice == ConfirmationChoice.ALL:
                # Add all remaining
                selected.extend(operations[i-1:])
                break
            elif confirmation.choice == ConfirmationChoice.NONE:
                # Skip all remaining
                break
            elif confirmation.choice == ConfirmationChoice.QUIT:
                # Abort entirely
                return []
        
        return selected
    
    def _store_orphaned_operation(
        self,
        op: ConfigDriftResult,
        transaction_id: str,
        remove_files: bool,
        backup: bool
    ) -> Optional[int]:
        """Store orphaned operation in database for potential restoration."""
        try:
            # Prepare restoration data
            restoration_data = {
                "restorable": True,
                "remove_files": remove_files,
                "backup": backup,
                "original_config": op.applied_config,
                "backup_path": None,
                "backup_exists": False
            }
            
            # Check if backup exists
            if backup and op.dst_path:
                backup_path = self._get_backup_path_for_operation(op)
                if backup_path and Path(backup_path).exists():
                    restoration_data["backup_path"] = backup_path
                    restoration_data["backup_exists"] = True
            
            # Store in orphaned_operations table
            cursor = self.database.conn.cursor()
            
            # Get the original applied step ID if not provided
            applied_step_id = None
            if hasattr(op, 'applied_step_id'):
                applied_step_id = op.applied_step_id
            else:
                # Query for the step ID based on dst_path and hash
                cursor.execute("""
                    SELECT id FROM applied_steps 
                    WHERE dst_path = ? AND step_hash = ?
                    ORDER BY applied_at DESC
                    LIMIT 1
                """, (op.dst_path, op.applied_step_hash))
                result = cursor.fetchone()
                if result:
                    applied_step_id = result[0]
            
            if not applied_step_id:
                self.logger.warning(f"No applied step ID found for {op.dst_path}")
                # Skip storing orphaned operation if we can't find the original step
                return None
            
            cursor.execute("""
                INSERT INTO orphaned_operations (
                    original_applied_step_id,
                    step_hash,
                    dst_path,
                    operation_type,
                    config,
                    orphaned_by_transaction,
                    orphaned_reason,
                    restoration_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                applied_step_id,
                op.applied_step_hash,
                op.dst_path,
                op.operation_type,
                json.dumps(op.applied_config) if op.applied_config else None,
                transaction_id,
                op.drift_type.value,
                json.dumps(restoration_data)
            ))
            
            return cursor.lastrowid
            
        except Exception as e:
            self.logger.error(f"Failed to store orphaned operation: {e}")
            return None
    
    def _clean_single_operation_enhanced(
        self,
        op: ConfigDriftResult,
        remove_files: bool,
        backup: bool,
        result: EnhancedCleanupResult,
        transaction_id: str
    ) -> None:
        """Enhanced single operation cleanup."""
        # Backup file if requested
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
        
        # Remove file if requested
        if remove_files and op.dst_path:
            removed_path = self._remove_file(op.dst_path)
            if removed_path:
                result.removed_files.append(removed_path)
        
        result.cleaned_count += 1
        self.logger.info(f"Cleaned operation: {op.dst_path} ({op.operation_type})")
    
    def _record_cleanup_history(
        self,
        transaction_id: str,
        result: EnhancedCleanupResult,
        filters: CleanupFilters,
        dry_run: bool
    ) -> None:
        """Record cleanup operation in history table."""
        try:
            cursor = self.database.conn.cursor()
            cursor.execute("""
                INSERT INTO cleanup_history (
                    transaction_id,
                    operation_count,
                    files_removed,
                    files_backed_up,
                    cleanup_type,
                    cleanup_filters,
                    cleanup_result,
                    dry_run
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction_id,
                result.cleaned_count,
                len(result.removed_files),
                len(result.backed_up_files),
                result.cleanup_type,
                json.dumps(filters.model_dump() if filters else {}),
                json.dumps(result.model_dump()),
                1 if dry_run else 0
            ))
            self.database.conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to record cleanup history: {e}")
    
    def _get_restorable_operations(
        self,
        transaction_id: Optional[str] = None,
        operation_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Get orphaned operations that can be restored."""
        try:
            cursor = self.database.conn.cursor()
            
            if operation_ids:
                placeholders = ','.join('?' * len(operation_ids))
                query = f"""
                    SELECT * FROM orphaned_operations
                    WHERE id IN ({placeholders})
                      AND restored_at IS NULL
                """
                cursor.execute(query, operation_ids)
            elif transaction_id:
                query = """
                    SELECT * FROM orphaned_operations
                    WHERE orphaned_by_transaction = ?
                      AND restored_at IS NULL
                """
                cursor.execute(query, (transaction_id,))
            else:
                # Get all restorable operations
                query = """
                    SELECT * FROM orphaned_operations
                    WHERE restored_at IS NULL
                      AND json_extract(restoration_data, '$.restorable') = 1
                    ORDER BY orphaned_at DESC
                    LIMIT 100
                """
                cursor.execute(query)
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            self.logger.error(f"Failed to get restorable operations: {e}")
            return []
    
    def _restore_single_operation(
        self,
        op_data: Dict[str, Any],
        transaction_id: str
    ) -> bool:
        """Restore a single orphaned operation."""
        try:
            # Parse restoration data
            restoration_data = json.loads(op_data.get('restoration_data', '{}'))
            config = json.loads(op_data.get('config', '{}'))
            
            # Check if backup exists and restore from it
            if restoration_data.get('backup_path'):
                backup_path = Path(restoration_data['backup_path'])
                if backup_path.exists():
                    dst_path = Path(op_data['dst_path']).expanduser()
                    
                    # Restore from backup
                    if backup_path.is_file():
                        shutil.copy2(backup_path, dst_path)
                    elif backup_path.is_dir():
                        shutil.copytree(backup_path, dst_path)
                    
                    self.logger.info(f"Restored {op_data['dst_path']} from backup")
            
            # Re-apply the operation in the database
            cursor = self.database.conn.cursor()
            cursor.execute("""
                UPDATE applied_steps
                SET is_orphaned = 0
                WHERE step_hash = ?
            """, (op_data['step_hash'],))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore operation: {e}")
            return False
    
    def _mark_operation_restored(self, operation_id: int, transaction_id: str) -> None:
        """Mark an orphaned operation as restored."""
        try:
            cursor = self.database.conn.cursor()
            cursor.execute("""
                UPDATE orphaned_operations
                SET restored_at = CURRENT_TIMESTAMP,
                    restored_by_transaction = ?
                WHERE id = ?
            """, (transaction_id, operation_id))
            self.database.conn.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to mark operation as restored: {e}")
    
    def _backup_file(self, dst_path: str, reason: str) -> Optional[str]:
        """Create a backup of a file before cleanup."""
        try:
            file_path = Path(dst_path).expanduser()
            if not file_path.exists():
                return None
            
            # Create backup directory
            backup_dir = Path.home() / ".local" / "state" / "dotfiles" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.name}.{timestamp}.cleanup-backup"
            
            # Include relative path structure
            try:
                rel_path = file_path.relative_to(Path.home())
                backup_path = backup_dir / rel_path.parent / backup_name
                backup_path.parent.mkdir(parents=True, exist_ok=True)
            except ValueError:
                backup_path = backup_dir / backup_name
            
            # Create backup
            if file_path.is_file() or file_path.is_symlink():
                shutil.copy2(file_path, backup_path)
            elif file_path.is_dir():
                shutil.copytree(file_path, backup_path)
            else:
                return None
            
            self.logger.info(f"Backed up {dst_path} to {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Failed to backup {dst_path}: {e}")
            return None
    
    def _remove_file(self, dst_path: str) -> Optional[str]:
        """Remove a file from the filesystem."""
        try:
            file_path = Path(dst_path).expanduser()
            if not file_path.exists():
                return None
            
            if file_path.is_symlink() or file_path.is_file():
                file_path.unlink()
            elif file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                return None
            
            self.logger.info(f"Removed {dst_path}")
            return str(file_path)
            
        except Exception as e:
            self.logger.error(f"Failed to remove {dst_path}: {e}")
            return None
    
    def _get_backup_path_for_operation(self, op: ConfigDriftResult) -> Optional[str]:
        """Get the backup path for an operation if it exists."""
        # This would check for existing backups in the backup directory
        # Implementation depends on backup naming convention
        return None