"""
Safety components for the Dotfiles Management System.

This package provides comprehensive safety and security features including:
- Backup management and restoration
- Path validation and permission checking  
- Enhanced transaction handling
- Drift detection and reporting

Phase 2: Safety Layer implementation.
"""

from .backup import BackupManager, BackupManifest, BackupError
from .validator import (
    PathValidator,
    PermissionValidator, 
    ChecksumValidator,
    CommandValidator,
    SafetyValidator,
    ValidationResult,
    ValidationError
)
from .transaction import (
    TransactionManager,
    EnhancedTransactionContext,
    TransactionError,
    TransactionValidationError,
    TransactionRollbackError
)
from .drift import (
    DriftDetector,
    DriftMonitor,
    DriftResult,
    DriftReport,
    DriftType,
    DriftSeverity
)

__all__ = [
    # Backup components
    "BackupManager",
    "BackupManifest", 
    "BackupError",
    
    # Validation components
    "PathValidator",
    "PermissionValidator",
    "ChecksumValidator", 
    "CommandValidator",
    "SafetyValidator",
    "ValidationResult",
    "ValidationError",
    
    # Transaction components
    "TransactionManager",
    "EnhancedTransactionContext",
    "TransactionError",
    "TransactionValidationError", 
    "TransactionRollbackError",
    
    # Drift detection components
    "DriftDetector",
    "DriftMonitor",
    "DriftResult",
    "DriftReport",
    "DriftType",
    "DriftSeverity",
]