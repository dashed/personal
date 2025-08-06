"""
State Database Interface for Dotfiles Management System

This module provides a high-level interface to the SQLite state database,
handling transactions, operations tracking, backups, and rollback functionality.
"""

import sqlite3
import json
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from contextlib import contextmanager
import logging

from dotfiles_sync.models import TransactionContext, OperationResult

logger = logging.getLogger(__name__)


class StateDatabase:
    """
    Interface to the dotfiles state database.
    
    Handles all state tracking, transactions, backups, and rollback operations.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection and ensure schema exists."""
        if db_path is None:
            db_path = Path.home() / ".local" / "state" / "dotfiles" / "state.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connect with better defaults
        self.conn = sqlite3.connect(
            str(self.db_path),
            isolation_level=None,  # Autocommit mode
            check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Enable foreign keys and WAL mode
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        
        # Initialize schema if needed
        self._init_schema()
        self._update_system_info()
    
    def _init_schema(self):
        """Initialize database schema from SQL file."""
        schema_file = Path(__file__).parent / "state_database_schema.sql"
        if schema_file.exists():
            with open(schema_file, 'r') as f:
                self.conn.executescript(f.read())
        else:
            logger.warning(f"Schema file not found: {schema_file}")
    
    def _update_system_info(self):
        """Update system information."""
        import platform
        import getpass
        
        self.conn.execute("""
            INSERT OR REPLACE INTO system_info 
            (hostname, username, platform, arch, dotfiles_version, python_version, last_sync_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            platform.node(),
            getpass.getuser(),
            platform.system().lower(),
            platform.machine(),
            "1.0.0",  # TODO: Get from package version
            platform.python_version()
        ))
    
    # ============================================================================
    # TRANSACTION MANAGEMENT
    # ============================================================================
    
    @contextmanager
    def transaction(self, variant: str, user: str, hostname: str, 
                   dry_run: bool = False, metadata: Optional[Dict] = None):
        """
        Context manager for atomic transactions.
        
        Usage:
            with db.transaction('personal', 'john', 'laptop') as tx:
                db.record_operation(tx, 'link', {...})
        """
        tx_id = str(uuid.uuid4())
        tx = TransactionContext(
            id=tx_id,
            variant=variant,
            user=user,
            hostname=hostname,
            dry_run=dry_run,
            metadata=metadata
        )
        
        try:
            # Start transaction
            self.conn.execute("""
                INSERT INTO transactions (id, variant, user, hostname, dry_run, metadata, status)
                VALUES (?, ?, ?, ?, ?, ?, 'in_progress')
            """, (tx.id, tx.variant, tx.user, tx.hostname, tx.dry_run, 
                  json.dumps(tx.metadata) if tx.metadata else None))
            
            yield tx
            
            # Mark as completed if no exception
            self.conn.execute("""
                UPDATE transactions 
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (tx.id,))
            
        except Exception as e:
            # Mark as failed and potentially trigger rollback
            self.conn.execute("""
                UPDATE transactions 
                SET status = 'failed', 
                    error_message = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (str(e), tx.id))
            raise
    
    def record_operation(self, tx: TransactionContext, operation_type: str,
                        config: Dict[str, Any], src_path: Optional[str] = None,
                        dst_path: Optional[str] = None) -> int:
        """Record a new operation within a transaction."""
        
        # Get next sequence number
        cursor = self.conn.execute("""
            SELECT COALESCE(MAX(sequence_num), 0) + 1 as next_seq
            FROM operations WHERE transaction_id = ?
        """, (tx.id,))
        next_seq = cursor.fetchone()['next_seq']
        
        # Insert operation
        cursor = self.conn.execute("""
            INSERT INTO operations 
            (transaction_id, sequence_num, operation_type, src_path, dst_path, config, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (tx.id, next_seq, operation_type, src_path, dst_path, json.dumps(config)))
        
        return cursor.lastrowid
    
    def update_operation_status(self, operation_id: int, status: str,
                               error_message: Optional[str] = None,
                               rollback_data: Optional[Dict] = None,
                               checksums: Optional[Tuple[str, str]] = None):
        """Update operation status and metadata."""
        params = [status]
        query_parts = ["UPDATE operations SET status = ?"]
        
        if error_message:
            query_parts.append("error_message = ?")
            params.append(error_message)
        
        if rollback_data:
            query_parts.append("rollback_data = ?")
            params.append(json.dumps(rollback_data))
        
        if checksums:
            query_parts.append("original_checksum = ?, new_checksum = ?")
            params.extend(checksums)
        
        if status in ('executing',):
            query_parts.append("started_at = CURRENT_TIMESTAMP")
        elif status in ('success', 'failed', 'rolled_back'):
            query_parts.append("completed_at = CURRENT_TIMESTAMP")
        
        query_parts.append("WHERE id = ?")
        params.append(operation_id)
        
        query = ", ".join(query_parts[1:])
        self.conn.execute(f"{query_parts[0]}, {query}", params)
    
    # ============================================================================
    # APPLIED CONFIGURATION TRACKING
    # ============================================================================
    
    def record_applied_step(self, tx: TransactionContext, operation_type: str,
                           config: Dict, src_path: Optional[str] = None,
                           dst_path: Optional[str] = None, 
                           checksum: Optional[str] = None):
        """Record a successfully applied configuration step."""
        
        # Generate hash of the step configuration
        step_hash = hashlib.sha256(
            json.dumps(config, sort_keys=True).encode()
        ).hexdigest()
        
        self.conn.execute("""
            INSERT OR REPLACE INTO applied_steps
            (step_hash, operation_type, src_path, dst_path, checksum, config, 
             applied_by_transaction, is_current)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (step_hash, operation_type, src_path, dst_path, checksum,
              json.dumps(config), tx.id))
    
    def get_current_state(self, dst_path: Optional[str] = None) -> List[Dict]:
        """Get currently applied configuration."""
        if dst_path:
            cursor = self.conn.execute("""
                SELECT * FROM current_state WHERE dst_path = ?
            """, (dst_path,))
        else:
            cursor = self.conn.execute("SELECT * FROM current_state")
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ============================================================================
    # BACKUP MANAGEMENT
    # ============================================================================
    
    def record_backup(self, operation_id: int, backup_path: Path,
                     original_path: Path, backup_type: str,
                     checksum: Optional[str] = None,
                     retention_days: int = 30) -> int:
        """Record a backup for an operation."""
        
        size_bytes = backup_path.stat().st_size if backup_path.exists() else 0
        expires_at = datetime.now() + timedelta(days=retention_days)
        
        cursor = self.conn.execute("""
            INSERT INTO backups
            (operation_id, backup_path, original_path, backup_type, 
             size_bytes, checksum, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (operation_id, str(backup_path), str(original_path),
              backup_type, size_bytes, checksum, expires_at))
        
        return cursor.lastrowid
    
    def get_backup_for_operation(self, operation_id: int) -> Optional[Dict]:
        """Get backup information for an operation."""
        cursor = self.conn.execute("""
            SELECT * FROM backups 
            WHERE operation_id = ? AND is_deleted = 0
            ORDER BY created_at DESC LIMIT 1
        """, (operation_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def cleanup_expired_backups(self) -> int:
        """Mark expired backups for deletion."""
        cursor = self.conn.execute("""
            UPDATE backups 
            SET is_deleted = 1 
            WHERE expires_at < CURRENT_TIMESTAMP AND is_deleted = 0
        """)
        return cursor.rowcount
    
    # ============================================================================
    # RUN-ONCE TRACKING
    # ============================================================================
    
    def has_run_once(self, command: str, checksum: Optional[str] = None,
                     variant: Optional[str] = None) -> bool:
        """Check if a run-once operation has already been executed."""
        
        # Generate operation hash
        hash_input = f"{command}:{checksum}:{variant}"
        operation_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        cursor = self.conn.execute("""
            SELECT 1 FROM run_once_tracking WHERE operation_hash = ?
        """, (operation_hash,))
        
        return cursor.fetchone() is not None
    
    def record_run_once(self, tx: TransactionContext, command: str,
                       checksum: Optional[str] = None, exit_code: int = 0,
                       output: Optional[str] = None):
        """Record execution of a run-once operation."""
        
        hash_input = f"{command}:{checksum}:{tx.variant}"
        operation_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        
        self.conn.execute("""
            INSERT INTO run_once_tracking
            (operation_hash, command, checksum, variant, 
             executed_by_transaction, exit_code, output)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (operation_hash, command, checksum, tx.variant,
              tx.id, exit_code, output))
    
    # ============================================================================
    # PACKAGE TRACKING
    # ============================================================================
    
    def record_package_installation(self, tx: TransactionContext,
                                   package_manager: str, package_name: str,
                                   version: Optional[str] = None,
                                   is_pinned: bool = False,
                                   metadata: Optional[Dict] = None):
        """Record package installation."""
        self.conn.execute("""
            INSERT OR REPLACE INTO installed_packages
            (package_manager, package_name, version, installed_by_transaction,
             is_pinned, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (package_manager, package_name, version, tx.id,
              is_pinned, json.dumps(metadata) if metadata else None))
    
    def get_installed_packages(self, package_manager: Optional[str] = None) -> List[Dict]:
        """Get list of installed packages."""
        if package_manager:
            cursor = self.conn.execute("""
                SELECT * FROM installed_packages WHERE package_manager = ?
            """, (package_manager,))
        else:
            cursor = self.conn.execute("SELECT * FROM installed_packages")
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ============================================================================
    # ROLLBACK OPERATIONS
    # ============================================================================
    
    def get_rollback_operations(self, transaction_id: str) -> List[Dict]:
        """Get operations that need to be rolled back for a transaction."""
        cursor = self.conn.execute("""
            SELECT * FROM operations 
            WHERE transaction_id = ? 
              AND status = 'success'
              AND rollback_data IS NOT NULL
            ORDER BY sequence_num DESC
        """, (transaction_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def perform_rollback(self, transaction_id: str) -> bool:
        """
        Perform rollback for a failed transaction.
        
        Returns True if rollback succeeded, False otherwise.
        """
        operations = self.get_rollback_operations(transaction_id)
        
        if not operations:
            logger.warning(f"No operations to rollback for transaction {transaction_id}")
            return True
        
        success = True
        for op in operations:
            try:
                # Here you would call the actual rollback logic
                # based on the operation type and rollback_data
                logger.info(f"Rolling back operation {op['id']}: {op['operation_type']}")
                
                # Mark as rolled back
                self.update_operation_status(op['id'], 'rolled_back')
                
            except Exception as e:
                logger.error(f"Failed to rollback operation {op['id']}: {e}")
                success = False
        
        # Update transaction status
        status = 'rolled_back' if success else 'failed'
        self.conn.execute("""
            UPDATE transactions SET status = ? WHERE id = ?
        """, (status, transaction_id))
        
        return success
    
    # ============================================================================
    # DRIFT DETECTION
    # ============================================================================
    
    def record_drift(self, applied_step_id: int, expected_checksum: str,
                    actual_checksum: str, drift_type: str,
                    details: Optional[Dict] = None):
        """Record detected drift."""
        self.conn.execute("""
            INSERT INTO drift_detection
            (applied_step_id, expected_checksum, actual_checksum, drift_type, details)
            VALUES (?, ?, ?, ?, ?)
        """, (applied_step_id, expected_checksum, actual_checksum,
              drift_type, json.dumps(details) if details else None))
    
    def get_drift_summary(self) -> List[Dict]:
        """Get summary of detected drift."""
        cursor = self.conn.execute("SELECT * FROM drift_summary")
        return [dict(row) for row in cursor.fetchall()]
    
    # ============================================================================
    # AUDIT LOGGING
    # ============================================================================
    
    def audit_log(self, event_type: str, message: str, 
                 severity: str = 'info',
                 transaction_id: Optional[str] = None,
                 operation_id: Optional[int] = None,
                 details: Optional[Dict] = None):
        """Add entry to audit log."""
        import platform
        import getpass
        
        self.conn.execute("""
            INSERT INTO audit_log
            (event_type, severity, transaction_id, operation_id, 
             user, hostname, message, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (event_type, severity, transaction_id, operation_id,
              getpass.getuser(), platform.node(), message,
              json.dumps(details) if details else None))
    
    def get_audit_log(self, limit: int = 100, 
                     severity: Optional[str] = None) -> List[Dict]:
        """Get recent audit log entries."""
        if severity:
            cursor = self.conn.execute("""
                SELECT * FROM audit_log 
                WHERE severity = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (severity, limit))
        else:
            cursor = self.conn.execute("""
                SELECT * FROM audit_log 
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # ============================================================================
    # STATISTICS AND REPORTS
    # ============================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        
        # Transaction stats
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'rolled_back' THEN 1 ELSE 0 END) as rolled_back
            FROM transactions
        """)
        stats['transactions'] = dict(cursor.fetchone())
        
        # Backup stats
        cursor = self.conn.execute("SELECT * FROM backup_stats")
        row = cursor.fetchone()
        stats['backups'] = dict(row) if row else {}
        
        # Applied steps
        cursor = self.conn.execute("""
            SELECT COUNT(*) as total FROM applied_steps WHERE is_current = 1
        """)
        stats['applied_steps'] = cursor.fetchone()['total']
        
        # Installed packages
        cursor = self.conn.execute("""
            SELECT package_manager, COUNT(*) as count 
            FROM installed_packages 
            GROUP BY package_manager
        """)
        stats['packages'] = {row['package_manager']: row['count'] 
                            for row in cursor.fetchall()}
        
        return stats
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Example usage
    db = StateDatabase()
    
    # Create a transaction
    with db.transaction('personal', 'john', 'laptop') as tx:
        # Record an operation
        op_id = db.record_operation(
            tx, 'link',
            config={'src': 'zsh/zshrc', 'dst': '~/.zshrc'},
            src_path='zsh/zshrc',
            dst_path='~/.zshrc'
        )
        
        # Update operation status
        db.update_operation_status(op_id, 'success')
        
        # Record applied step
        db.record_applied_step(
            tx, 'link',
            config={'src': 'zsh/zshrc', 'dst': '~/.zshrc'},
            src_path='zsh/zshrc',
            dst_path='~/.zshrc'
        )
        
        # Add audit log
        db.audit_log('sync', 'Successfully linked zsh config', 
                    transaction_id=tx.id, operation_id=op_id)
    
    # Get statistics
    stats = db.get_statistics()
    print(json.dumps(stats, indent=2))
    
    db.close()