"""
Directory synchronization verb implementation.

This module provides directory synchronization functionality with
safety limits and selective copying.
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List

from dotfiles_sync.models import StepConfig, OperationResult
from dotfiles_sync.context import OperationContext

from .base import Verb


class SyncDirVerb(Verb):
    """
    Synchronize directories with safety limits.
    
    Features:
    - Selective file copying based on patterns
    - Size limits to prevent accidental large copies
    - Preserve permissions and timestamps
    - Exclude patterns support
    """
    
    def __init__(self) -> None:
        """Initialize the syncdir verb."""
        super().__init__("syncdir")
        self.max_total_size = 100 * 1024 * 1024  # 100MB default limit
    
    def validate(self, step: StepConfig, context: OperationContext) -> List[str]:
        """
        Validate syncdir operation.
        
        Args:
            step: Step configuration
            context: Operation context
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if not step.src:
            errors.append("Source directory is required for syncdir")
        if not step.dst:
            errors.append("Destination directory is required for syncdir")
        
        if step.src:
            src_path = context.get_src_path()
            if src_path and not src_path.exists():
                errors.append(f"Source directory does not exist: {src_path}")
            elif src_path and not src_path.is_dir():
                errors.append(f"Source is not a directory: {src_path}")
        
        return errors
    
    def dry_run(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Perform a dry run of directory synchronization.
        
        Args:
            step: Step configuration
            context: Operation context
            
        Returns:
            Operation result
        """
        validation_errors = self.validate(step, context)
        if validation_errors:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="syncdir",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=True
            )
        
        src_path = context.get_src_path()
        dst_path = context.get_dst_path()
        
        if not src_path or not dst_path:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="syncdir",
                message="Missing source or destination path",
                dry_run=True
            )
        
        # Calculate what would be synced
        files_to_sync = self._get_files_to_sync(src_path, step.exclude or [])
        total_size = sum(f.stat().st_size for f in files_to_sync if f.is_file())
        
        if total_size > self.max_total_size:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="syncdir",
                message=f"Total size {total_size / 1024 / 1024:.1f}MB exceeds limit {self.max_total_size / 1024 / 1024:.1f}MB",
                dry_run=True
            )
        
        message = f"Would sync {len(files_to_sync)} files ({total_size / 1024:.1f}KB) from {src_path} to {dst_path}"
        
        return OperationResult(
            success=True,
            operation_id=0,
            operation_type="syncdir",
            message=message,
            dry_run=True
        )
    
    def apply(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Apply directory synchronization.
        
        Args:
            step: Step configuration
            context: Operation context
            
        Returns:
            Operation result
        """
        validation_errors = self.validate(step, context)
        if validation_errors:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="syncdir",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=False
            )
        
        src_path = context.get_src_path()
        dst_path = context.get_dst_path()
        
        if not src_path or not dst_path:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="syncdir",
                message="Missing source or destination path",
                dry_run=False
            )
        
        try:
            # Get files to sync
            files_to_sync = self._get_files_to_sync(src_path, step.exclude or [])
            total_size = sum(f.stat().st_size for f in files_to_sync if f.is_file())
            
            if total_size > self.max_total_size:
                return OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="syncdir",
                    message=f"Total size {total_size / 1024 / 1024:.1f}MB exceeds limit",
                    dry_run=False
                )
            
            # Create destination directory if needed
            dst_path.mkdir(parents=True, exist_ok=True)
            
            # Track what we're doing for rollback
            created_files = []
            
            # Sync each file
            for src_file in files_to_sync:
                relative_path = src_file.relative_to(src_path)
                dst_file = dst_path / relative_path
                
                # Create parent directories
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                if src_file.is_file():
                    shutil.copy2(src_file, dst_file)
                    created_files.append(str(dst_file))
            
            rollback_data = {
                "created_files": created_files,
                "dst_path": str(dst_path)
            }
            
            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="syncdir",
                message=f"Synced {len(files_to_sync)} files to {dst_path}",
                dry_run=False,
                rollback_data=rollback_data
            )
            
        except Exception as e:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="syncdir",
                message=f"Failed to sync directory: {e}",
                dry_run=False,
                error=str(e)
            )
    
    def rollback(self, step: StepConfig, context: OperationContext, 
                 rollback_data: Dict[str, Any]) -> bool:
        """
        Rollback directory synchronization.
        
        Args:
            step: Step configuration
            context: Operation context
            rollback_data: Data from the original operation
            
        Returns:
            True if rollback succeeded
        """
        try:
            created_files = rollback_data.get("created_files", [])
            
            # Remove created files
            for file_path in created_files:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
            
            # Note: We don't remove directories as they might contain other files
            self.logger.info(f"Rolled back syncdir operation, removed {len(created_files)} files")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to rollback syncdir: {e}")
            return False
    
    def _get_files_to_sync(self, src_path: Path, exclude_patterns: List[str]) -> List[Path]:
        """
        Get list of files to synchronize.
        
        Args:
            src_path: Source directory path
            exclude_patterns: Patterns to exclude
            
        Returns:
            List of file paths to sync
        """
        files_to_sync = []
        
        for item in src_path.rglob("*"):
            # Skip if matches exclude pattern
            if any(self._matches_pattern(item, pattern) for pattern in exclude_patterns):
                continue
            
            # Only sync files, not directories themselves
            if item.is_file():
                files_to_sync.append(item)
        
        return files_to_sync
    
    def _matches_pattern(self, path: Path, pattern: str) -> bool:
        """
        Check if path matches a pattern.
        
        Args:
            path: Path to check
            pattern: Pattern to match (simple glob)
            
        Returns:
            True if matches
        """
        import fnmatch
        return fnmatch.fnmatch(str(path), pattern) or fnmatch.fnmatch(path.name, pattern)