"""
Safety components for the Dotfiles Management System.

This package provides comprehensive safety and security features including:
- Backup management and restoration
- Path validation and permission checking
- Enhanced transaction handling
- Drift detection and reporting
- Impact analysis and confirmation prompts (Phase 4)
- Conflict resolution and selective operations (Phase 4)

Phase 2: Safety Layer implementation.
Phase 4: Safety Features & Confirmation implementation.
"""

from .backup import BackupManager, BackupManifest, BackupError
from .validator import (
    PathValidator,
    PermissionValidator,
    ChecksumValidator,
    CommandValidator,
    SafetyValidator,
    ValidationResult,
    ValidationError,
)
from .transaction import (
    TransactionManager,
    EnhancedTransactionContext,
    TransactionError,
    TransactionValidationError,
    TransactionRollbackError,
)
from .drift import DriftDetector, DriftMonitor, DriftResult, DriftReport, DriftType, DriftSeverity

# Phase 4: Safety Features & Confirmation
from .impact import (
    ImpactAnalyzer,
    DependencyAnalyzer,
    ImpactReport,
    ImpactDetail,
    ImpactLevel,
    ImpactType,
)
from .confirmation import (
    ConfirmationPrompt,
    SafetyConfirmationManager,
    ConfirmationMode,
    ConfirmationChoice,
    ConfirmationResult,
)
from .resolver import (
    ConflictResolver,
    SelectiveOperationFilter,
    ConflictReport,
    ConflictDetail,
    ConflictType,
    ResolutionStrategy,
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
    # Phase 4: Impact analysis components
    "ImpactAnalyzer",
    "DependencyAnalyzer",
    "ImpactReport",
    "ImpactDetail", 
    "ImpactLevel",
    "ImpactType",
    # Phase 4: Confirmation components
    "ConfirmationPrompt",
    "SafetyConfirmationManager",
    "ConfirmationMode",
    "ConfirmationChoice",
    "ConfirmationResult",
    # Phase 4: Conflict resolution components
    "ConflictResolver",
    "SelectiveOperationFilter",
    "ConflictReport",
    "ConflictDetail",
    "ConflictType",
    "ResolutionStrategy",
]
