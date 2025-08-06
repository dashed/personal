"""
Extended context management for dotfiles operations.

This module provides additional context utilities beyond the Pydantic models,
including operation-specific context and path handling.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from dotfiles_sync.models import ExecutionContext as BaseExecutionContext, StepConfig

logger = logging.getLogger(__name__)


# Re-export the Pydantic ExecutionContext for compatibility
ExecutionContext = BaseExecutionContext


class OperationContext:
    """Context for a single operation within a transaction.
    
    Provides operation-specific context and utilities.
    """
    
    def __init__(
        self,
        execution_context: ExecutionContext,
        operation_type: str,
        step_config: StepConfig,
        sequence_num: int,
        operation_id: Optional[int] = None,
    ):
        """Initialize operation context.
        
        Args:
            execution_context: Parent execution context
            operation_type: Type of operation
            step_config: Step configuration
            sequence_num: Sequence number in transaction
            operation_id: Optional database operation ID
        """
        self.execution_context = execution_context
        self.operation_type = operation_type
        self.step_config = step_config
        self.sequence_num = sequence_num
        self.operation_id = operation_id
        
        logger.debug(
            f"OperationContext: {self.operation_type} "
            f"(seq={self.sequence_num}, dry_run={self.execution_context.dry_run})"
        )
    
    def get_src_path(self) -> Optional[Path]:
        """Get the source path for the operation if applicable.
        
        Returns:
            Expanded source path or None
        """
        if not self.step_config.src:
            return None
        
        return self.execution_context.expand_path(self.step_config.src)
    
    def get_dst_path(self) -> Optional[Path]:
        """Get the destination path for the operation if applicable.
        
        Returns:
            Expanded destination path or None
        """
        if not self.step_config.dst:
            return None
        
        return self.execution_context.expand_path(self.step_config.dst)
    
    def should_create_backup(self) -> bool:
        """Check if a backup should be created for this operation.
        
        Returns:
            True if backup should be created
        """
        # Don't backup in dry run mode
        if self.execution_context.dry_run:
            return False
        
        # Check if operation modifies existing files
        from dotfiles_sync.models import OperationType
        modifying_ops = [
            OperationType.LINK,
            OperationType.COPY,
            OperationType.SYNCDIR,
            OperationType.APPEND,
            OperationType.PREPEND,
            OperationType.TEMPLATE,
        ]
        
        if self.step_config.op not in modifying_ops:
            return False
        
        # Check if destination exists
        dst_path = self.get_dst_path()
        if dst_path and dst_path.exists():
            return True
        
        return False
    
    def get_backup_path(self) -> Optional[Path]:
        """Generate a backup path for the destination file.
        
        Returns:
            Path where backup should be stored, or None if no destination
        """
        dst_path = self.get_dst_path()
        if not dst_path:
            return None
        
        from datetime import datetime
        
        # Create backup directory in user's home
        backup_dir = Path.home() / ".local" / "state" / "dotfiles" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{dst_path.name}.{timestamp}.backup"
        
        # Include relative path structure in backup
        if dst_path.is_absolute():
            # Get relative path from home
            try:
                rel_path = dst_path.relative_to(Path.home())
                backup_path = backup_dir / rel_path.parent / backup_name
                backup_path.parent.mkdir(parents=True, exist_ok=True)
            except ValueError:
                # Path is not relative to home, use flat structure
                backup_path = backup_dir / backup_name
        else:
            backup_path = backup_dir / backup_name
        
        return backup_path
    
    def should_skip_platform(self) -> bool:
        """Check if operation should be skipped based on platform.
        
        Returns:
            True if operation should be skipped on current platform
        """
        if not self.step_config.platforms:
            return False
        
        return not self.execution_context.system_info.matches_platform(
            self.step_config.platforms
        )
    
    def should_skip_variant(self) -> bool:
        """Check if operation should be skipped based on variant.
        
        Returns:
            True if operation should be skipped for current variant
        """
        return (
            self.execution_context.variant not in self.step_config.variants
            and "all" not in self.step_config.variants
        )
    
    def get_rollback_data(self) -> Dict[str, Any]:
        """Generate rollback data for this operation.
        
        Returns:
            Dictionary containing information needed to rollback the operation
        """
        data = {
            "operation_type": self.operation_type,
            "sequence_num": self.sequence_num,
        }
        
        # Add paths if applicable
        src_path = self.get_src_path()
        dst_path = self.get_dst_path()
        
        if src_path:
            data["src_path"] = str(src_path)
        if dst_path:
            data["dst_path"] = str(dst_path)
        
        # Add backup path if created
        if self.should_create_backup():
            backup_path = self.get_backup_path()
            if backup_path:
                data["backup_path"] = str(backup_path)
        
        return data