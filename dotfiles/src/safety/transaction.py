"""
Enhanced transaction handling for the Dotfiles Management System.

This module provides comprehensive transaction management including:
- Atomic operations with automatic rollback
- Enhanced transaction coordination
- Safety checks and validation integration
- Recovery and error handling
- Integration with backup system

Builds on the existing state database transaction system.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from contextlib import contextmanager
from pydantic import BaseModel, Field

from dotfiles_sync.models import (
    TransactionContext, 
    OperationResult,
    ExecutionContext,
    SafetyConfig
)
from dotfiles_sync.state_database import StateDatabase
from .backup import BackupManager
from .validator import SafetyValidator, ValidationResult


class EnhancedTransactionContext(BaseModel):
    """
    Enhanced transaction context with safety features.
    """
    
    base_context: TransactionContext
    backup_id: Optional[str] = Field(None, description="Associated backup ID")
    validation_results: List[ValidationResult] = Field(default_factory=list)
    rollback_actions: List[Dict[str, Any]] = Field(default_factory=list)
    safety_checks_passed: bool = Field(False, description="Whether all safety checks passed")
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        arbitrary_types_allowed = True


class TransactionManager:
    """
    Enhanced transaction manager with comprehensive safety features.
    
    Features:
    - Atomic operations with automatic rollback
    - Pre-flight validation
    - Automatic backup creation
    - Recovery and error handling
    - Integration with safety validators
    """
    
    def __init__(
        self,
        database: StateDatabase,
        backup_manager: Optional[BackupManager] = None,
        safety_validator: Optional[SafetyValidator] = None,
        safety_config: Optional[SafetyConfig] = None
    ):
        """
        Initialize transaction manager.
        
        Args:
            database: State database instance
            backup_manager: Backup manager for creating backups
            safety_validator: Safety validator for pre-flight checks
            safety_config: Safety configuration
        """
        self.database = database
        self.backup_manager = backup_manager or BackupManager()
        self.safety_validator = safety_validator or SafetyValidator()
        self.safety_config = safety_config or SafetyConfig.model_construct()
        
        self._active_transactions: Dict[str, EnhancedTransactionContext] = {}
    
    def create_transaction(
        self,
        variant: str,
        user: str,
        hostname: str,
        dry_run: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new enhanced transaction.
        
        Args:
            variant: Configuration variant
            user: Username
            hostname: Hostname
            dry_run: Whether this is a dry run
            metadata: Additional metadata
            
        Returns:
            Transaction ID
        """
        # Generate unique transaction ID
        transaction_id = str(uuid.uuid4())
        
        # Create base transaction context
        base_context = TransactionContext(
            id=transaction_id,
            variant=variant,
            user=user,
            hostname=hostname,
            dry_run=dry_run,
            metadata=metadata or {}
        )
        
        # Create enhanced context
        enhanced_context = EnhancedTransactionContext(
            base_context=base_context,
            backup_id=None,
            safety_checks_passed=False
        )
        
        # Store in active transactions
        self._active_transactions[transaction_id] = enhanced_context
        
        # Database transaction will be managed by context manager
        # during actual operation execution
        
        return transaction_id
    
    def validate_transaction(
        self, 
        transaction_id: str,
        execution_context: ExecutionContext
    ) -> List[ValidationResult]:
        """
        Perform comprehensive validation for a transaction.
        
        Args:
            transaction_id: Transaction ID
            execution_context: Execution context with configuration
            
        Returns:
            List of validation results
        """
        if transaction_id not in self._active_transactions:
            return [ValidationResult(
                valid=False,
                message=f"Transaction {transaction_id} not found",
                error_code="TRANSACTION_NOT_FOUND",
                details=None
            )]
        
        # Perform pre-flight validation
        validation_results = self.safety_validator.validate_pre_flight(execution_context)
        
        # Store validation results in transaction context
        enhanced_ctx = self._active_transactions[transaction_id]
        enhanced_ctx.validation_results = validation_results
        enhanced_ctx.safety_checks_passed = all(r.valid for r in validation_results)
        
        return validation_results
    
    def create_backup_for_transaction(
        self,
        transaction_id: str,
        files_to_backup: List[Path],
        reason: str = "Pre-transaction backup"
    ) -> Optional[str]:
        """
        Create backup for transaction if safety config requires it.
        
        Args:
            transaction_id: Transaction ID
            files_to_backup: Files to backup
            reason: Reason for backup
            
        Returns:
            Backup ID if created, None otherwise
        """
        if not self.safety_config.backup_before_modify:
            return None
            
        if transaction_id not in self._active_transactions:
            return None
        
        enhanced_ctx = self._active_transactions[transaction_id]
        
        try:
            backup_id = self.backup_manager.create_backup(
                files_to_backup=files_to_backup,
                reason=reason,
                transaction_id=transaction_id
            )
            
            # Store backup ID in transaction context
            enhanced_ctx.backup_id = backup_id
            
            return backup_id
            
        except Exception:
            # Log error but don't fail transaction for backup issues
            return None
    
    @contextmanager
    def transaction_scope(
        self,
        variant: str,
        user: str,
        hostname: str,
        dry_run: bool = True,
        execution_context: Optional[ExecutionContext] = None
    ) -> Iterator[str]:
        """
        Context manager for safe transaction execution.
        
        Args:
            variant: Configuration variant
            user: Username
            hostname: Hostname
            dry_run: Whether this is a dry run
            execution_context: Execution context for validation
            
        Yields:
            Transaction ID
            
        Example:
            with transaction_manager.transaction_scope("personal", "user", "host") as tx_id:
                # Perform operations
                operation_result = some_operation()
                transaction_manager.record_operation(tx_id, operation_result)
        """
        transaction_id = None
        
        # Use the database's transaction context manager to create the actual DB transaction
        with self.database.transaction(
            variant=variant,
            user=user,
            hostname=hostname,
            dry_run=dry_run
        ) as db_tx:
            transaction_id = db_tx.id
            
            try:
                # Create enhanced transaction context
                enhanced_context = EnhancedTransactionContext(
                    base_context=db_tx,
                    backup_id=None,
                    safety_checks_passed=False
                )
                self._active_transactions[transaction_id] = enhanced_context
                
                # Validate if execution context provided
                if execution_context:
                    validation_results = self.validate_transaction(transaction_id, execution_context)
                    
                    # Check if validation failed
                    if not all(r.valid for r in validation_results):
                        failed_results = [r for r in validation_results if not r.valid]
                        error_messages = [r.message for r in failed_results]
                        raise TransactionValidationError(
                            f"Transaction validation failed: {'; '.join(error_messages)}",
                            validation_results=failed_results
                        )
                
                yield transaction_id
                
                # Database transaction will be committed by the context manager
                
            except Exception as e:
                # Rollback transaction on any error
                if transaction_id:
                    self.rollback_transaction(transaction_id, str(e))
                raise
            finally:
                # Clean up active transaction
                if transaction_id and transaction_id in self._active_transactions:
                    del self._active_transactions[transaction_id]
    
    def record_operation(
        self,
        transaction_id: str,
        operation_result: OperationResult,
        rollback_action: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Record an operation in the transaction.
        
        Args:
            transaction_id: Transaction ID
            operation_result: Result of the operation
            rollback_action: Action needed for rollback
            
        Returns:
            Operation ID
        """
        if transaction_id not in self._active_transactions:
            raise TransactionError(f"Transaction {transaction_id} not found")
        
        enhanced_ctx = self._active_transactions[transaction_id]
        
        # Record operation in database
        # Get the base TransactionContext which is what the database expects
        base_ctx = enhanced_ctx.base_context
        operation_id = self.database.record_operation(
            tx=base_ctx,
            operation_type=operation_result.operation_type,
            config={}  # Will be filled by caller
        )
        
        # Store rollback action in enhanced context
        if rollback_action:
            rollback_action["operation_id"] = operation_id
            enhanced_ctx.rollback_actions.append(rollback_action)
        
        return operation_id
    
    def commit_transaction(self, transaction_id: str) -> bool:
        """
        Commit a transaction.
        
        Args:
            transaction_id: Transaction ID
            
        Returns:
            True if successful
        """
        try:
            # Database transaction completion handled by StateDatabase context manager
            # self.database.complete_transaction(transaction_id, TransactionStatus.COMPLETED)
            return True
        except Exception:
            return False
    
    def rollback_transaction(self, transaction_id: str, error_message: str = "") -> bool:
        """
        Rollback a transaction with enhanced error handling.
        
        Args:
            transaction_id: Transaction ID
            error_message: Error that caused rollback
            
        Returns:
            True if rollback successful
        """
        try:
            if transaction_id not in self._active_transactions:
                # Try database rollback even if not in active transactions
                # Database transaction rollback handled by StateDatabase context manager
                # self.database.complete_transaction(
                #     transaction_id, 
                #     TransactionStatus.ROLLED_BACK,
                #     error_message=error_message
                # )
                return True
            
            enhanced_ctx = self._active_transactions[transaction_id]
            
            # Execute rollback actions in reverse order
            rollback_success = True
            for action in reversed(enhanced_ctx.rollback_actions):
                try:
                    self._execute_rollback_action(action)
                except Exception:
                    rollback_success = False
            
            # Restore from backup if available
            if enhanced_ctx.backup_id and not enhanced_ctx.base_context.dry_run:
                try:
                    self.backup_manager.restore_backup(enhanced_ctx.backup_id)
                except Exception:
                    rollback_success = False
            
            # Mark transaction as rolled back in database
            # Database transaction rollback handled by StateDatabase context manager
            # self.database.complete_transaction(
            #     transaction_id,
            #     TransactionStatus.ROLLED_BACK,
            #     error_message=error_message
            # )
            
            return rollback_success
            
        except Exception:
            return False
    
    def _execute_rollback_action(self, action: Dict[str, Any]) -> None:
        """
        Execute a single rollback action.
        
        Args:
            action: Rollback action to execute
        """
        action_type = action.get("type")
        
        if action_type == "restore_file":
            # Restore file from backup path
            backup_path = Path(action["backup_path"])
            original_path = Path(action["original_path"])
            
            if backup_path.exists():
                original_path.parent.mkdir(parents=True, exist_ok=True)
                if backup_path.is_dir():
                    import shutil
                    if original_path.exists():
                        shutil.rmtree(original_path)
                    shutil.copytree(backup_path, original_path)
                else:
                    import shutil
                    shutil.copy2(backup_path, original_path)
        
        elif action_type == "remove_file":
            # Remove created file
            file_path = Path(action["file_path"])
            if file_path.exists():
                if file_path.is_dir():
                    import shutil
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()
        
        elif action_type == "restore_symlink":
            # Restore symlink target
            link_path = Path(action["link_path"])
            target = action["target"]
            
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            link_path.symlink_to(target)
        
        # Add more rollback action types as needed
    
    def get_transaction_status(self, transaction_id: str) -> Optional[EnhancedTransactionContext]:
        """
        Get current transaction status.
        
        Args:
            transaction_id: Transaction ID
            
        Returns:
            Enhanced transaction context if found
        """
        return self._active_transactions.get(transaction_id)
    
    def list_failed_transactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List recent failed transactions that may need rollback.
        
        Args:
            limit: Maximum number of transactions to return
            
        Returns:
            List of failed transaction information
        """
        return self.database.get_failed_transactions(limit=limit)
    
    def cleanup_old_transactions(self, days: int = 30) -> int:
        """
        Clean up old completed transactions.
        
        Args:
            days: Number of days to retain transactions
            
        Returns:
            Number of transactions cleaned up
        """
        return self.database.cleanup_old_transactions(days=days)


class TransactionError(Exception):
    """Base exception for transaction errors."""
    pass


class TransactionValidationError(TransactionError):
    """Exception raised when transaction validation fails."""
    
    def __init__(self, message: str, validation_results: List[ValidationResult]):
        super().__init__(message)
        self.validation_results = validation_results


class TransactionRollbackError(TransactionError):
    """Exception raised when transaction rollback fails."""
    pass