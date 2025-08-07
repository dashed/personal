"""
Copy verb implementation for copying files and directories.

This module implements the 'copy' operation which copies files or directories
from the dotfiles repository to destination paths.
"""

import shutil
import os
from pathlib import Path
from typing import List, Dict, Any

from dotfiles_sync.models import StepConfig, OperationResult
from dotfiles_sync.context import OperationContext
from .base import Verb


class CopyVerb(Verb):
    """
    Copies files or directories from src to dst.
    
    The copy operation creates a physical copy of the source file/directory
    at the destination path, with checksum verification.
    """
    
    def __init__(self) -> None:
        """Initialize the copy verb."""
        super().__init__("copy")
    
    def validate(self, spec: StepConfig, ctx: OperationContext) -> List[str]:
        """
        Validate the copy operation.
        
        Checks:
        - Source and destination are specified
        - Source exists in the repository
        - Destination parent directory exists or can be created
        - Platform and variant requirements are met
        """
        errors = []
        
        # Use base class path validation
        errors.extend(self._validate_paths(spec, ctx))
        
        # Check required fields
        if not spec.src:
            errors.append("Copy operation requires 'src' field")
        if not spec.dst:
            errors.append("Copy operation requires 'dst' field")
        
        if errors:
            return errors
        
        # Additional copy-specific validation
        dst_path = ctx.get_dst_path()
        
        # Check if parent directory exists or can be created
        if dst_path:
            parent = dst_path.parent
            if not parent.exists() and not spec.create_parent_dirs:
                errors.append(f"Parent directory does not exist: {parent}. Set create_parent_dirs=true to auto-create.")
        
        return errors
    
    def apply(self, spec: StepConfig, ctx: OperationContext) -> OperationResult:
        """
        Copy the file or directory.
        
        This will:
        1. Check if copy is needed (via checksum comparison)
        2. Backup any existing file at destination
        3. Create parent directories if needed
        4. Copy the file/directory
        5. Set permissions if specified
        """
        # Validate first
        errors = self.validate(spec, ctx)
        if errors:
            return OperationResult(
                success=False,
                operation_id=0,  # Will be updated by executor
                operation_type=self.name,
                message=f"Validation failed: {'; '.join(errors)}",
                dry_run=ctx.execution_context.dry_run
            )
        
        src_path = ctx.get_src_path()
        dst_path = ctx.get_dst_path()
        
        if not src_path or not dst_path:
            return OperationResult(
                success=False,
                operation_id=0,  # Will be updated by executor
                operation_type=self.name,
                message="Could not resolve source or destination paths",
                dry_run=ctx.execution_context.dry_run
            )
        
        # Check if copy is needed
        needs_copy = self._needs_copy(src_path, dst_path)
        
        # Dry run mode
        if ctx.execution_context.dry_run:
            if not needs_copy:
                message = f"File already up to date: {dst_path}"
            elif dst_path.exists():
                message = f"Would update file: {src_path} -> {dst_path}"
            else:
                message = f"Would copy: {src_path} -> {dst_path}"
            
            return OperationResult(
                success=True,
                operation_id=0,  # Will be updated by executor
                operation_type=self.name,
                message=message,
                dry_run=True
            )
        
        # Skip if not needed
        if not needs_copy:
            message = f"File already up to date: {dst_path}"
            self.logger.info(message)
            return OperationResult(
                success=True,
                operation_id=0,  # Will be updated by executor
                operation_type=self.name,
                message=message,
                dry_run=False,
                skipped=True
            )
        
        # Apply mode
        try:
            # Prepare rollback data
            original_state = self._capture_original_state(dst_path)
            
            # Backup existing file if needed
            backup_path = None
            if dst_path.exists():
                backup_path = self._backup_file(dst_path, ctx)
            
            # Create parent directories if needed
            if spec.create_parent_dirs and not dst_path.parent.exists():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                if spec.parent_dir_mode:
                    # Set directory permissions if specified
                    mode = int(spec.parent_dir_mode, 8) if isinstance(spec.parent_dir_mode, str) else spec.parent_dir_mode
                    dst_path.parent.chmod(mode)
                self.logger.info(f"Created parent directory: {dst_path.parent}")
            
            # Remove existing file/directory if present
            if dst_path.exists():
                if dst_path.is_dir() and not dst_path.is_symlink():
                    shutil.rmtree(dst_path)
                else:
                    dst_path.unlink()
            
            # Copy the file or directory
            if src_path.is_dir():
                shutil.copytree(src_path, dst_path, dirs_exist_ok=False)
                message = f"Copied directory: {src_path} -> {dst_path}"
            else:
                shutil.copy2(src_path, dst_path)
                message = f"Copied file: {src_path} -> {dst_path}"
            
            # Set permissions if specified
            if spec.mode:
                mode = int(spec.mode, 8) if isinstance(spec.mode, str) else spec.mode
                if dst_path.is_dir():
                    # Apply mode recursively for directories
                    for root, dirs, files in os.walk(dst_path):
                        root_path = Path(root)
                        root_path.chmod(mode)
                        for d in dirs:
                            (root_path / d).chmod(mode)
                        for f in files:
                            (root_path / f).chmod(mode)
                else:
                    dst_path.chmod(mode)
            
            # Calculate checksums for verification
            if dst_path.is_file():
                src_checksum = self._calculate_checksum(src_path)
                dst_checksum = self._calculate_checksum(dst_path)
                if src_checksum != dst_checksum:
                    raise Exception(f"Checksum mismatch after copy: {src_checksum} != {dst_checksum}")
                self.logger.debug(f"Checksum verified: {dst_checksum}")
            
            self.logger.info(message)
            
            # Prepare rollback data
            rollback_data = self._prepare_rollback_data(
                spec, ctx, 
                backup_path=backup_path,
                original_state=original_state
            )
            
            return OperationResult(
                success=True,
                operation_id=0,  # Will be updated by executor
                operation_type=self.name,
                message=message,
                dry_run=False,
                rollback_data=rollback_data
            )
            
        except Exception as e:
            message = f"Failed to copy {src_path} -> {dst_path}: {e}"
            self.logger.error(message)
            return OperationResult(
                success=False,
                operation_id=0,  # Will be updated by executor
                operation_type=self.name,
                message=message,
                dry_run=False,
                error=str(e)
            )
    
    def rollback(self, spec: StepConfig, ctx: OperationContext, rollback_data: Dict[str, Any]) -> bool:
        """
        Rollback a copy operation.
        
        This will:
        1. Remove the copied file/directory
        2. Restore the backed-up file if one exists
        """
        try:
            dst_path = Path(rollback_data["dst_path"]) if "dst_path" in rollback_data else ctx.get_dst_path()
            
            if not dst_path:
                self.logger.error("No destination path for rollback")
                return False
            
            # Remove the file/directory we copied
            if dst_path.exists():
                if dst_path.is_dir() and not dst_path.is_symlink():
                    shutil.rmtree(dst_path)
                    self.logger.info(f"Removed copied directory: {dst_path}")
                else:
                    dst_path.unlink()
                    self.logger.info(f"Removed copied file: {dst_path}")
            
            # Restore backup if it exists
            if "backup_path" in rollback_data:
                backup_path = Path(rollback_data["backup_path"])
                if backup_path.exists():
                    if backup_path.is_dir():
                        shutil.copytree(backup_path, dst_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(backup_path, dst_path)
                    self.logger.info(f"Restored backup: {dst_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False
    
    def _needs_copy(self, src_path: Path, dst_path: Path) -> bool:
        """
        Check if a copy is needed based on checksum comparison.
        
        Returns True if:
        - Destination doesn't exist
        - Source and destination have different checksums
        - Source is a directory and destination is not
        """
        if not dst_path.exists():
            return True
        
        # Type mismatch
        if src_path.is_dir() != dst_path.is_dir():
            return True
        
        # For directories, do a shallow comparison
        if src_path.is_dir():
            # Simple check: compare file counts and names
            src_files = set(p.name for p in src_path.iterdir())
            dst_files = set(p.name for p in dst_path.iterdir())
            if src_files != dst_files:
                return True
            
            # Deep comparison would be expensive, so we'll copy if requested
            return False
        
        # For files, compare checksums
        src_checksum = self._calculate_checksum(src_path)
        dst_checksum = self._calculate_checksum(dst_path)
        
        return src_checksum != dst_checksum
    
    def _capture_original_state(self, dst_path: Path) -> Dict[str, Any]:
        """Capture the original state of the destination."""
        state: Dict[str, Any] = {
            "existed": dst_path.exists(),
        }
        
        if dst_path.exists():
            state["was_file"] = dst_path.is_file()
            state["was_dir"] = dst_path.is_dir()
            state["was_symlink"] = dst_path.is_symlink()
            
            if dst_path.is_file():
                state["checksum"] = self._calculate_checksum(dst_path)
                state["size"] = dst_path.stat().st_size
            elif dst_path.is_dir():
                # Store directory contents for rollback
                state["dir_contents"] = [str(p.relative_to(dst_path)) for p in dst_path.rglob("*")]
        
        return state