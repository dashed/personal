"""
Link verb implementation for creating symlinks.

This module implements the 'link' operation which creates symbolic links
from destination paths to source files in the dotfiles repository.
"""

from pathlib import Path
from typing import List, Dict, Any

from dotfiles_sync.models import StepConfig, OperationResult
from dotfiles_sync.context import OperationContext
from .base import Verb


class LinkVerb(Verb):
    """
    Creates symbolic links from dst to src.
    
    The link operation creates a symbolic link at the destination path
    pointing to the source file in the dotfiles repository.
    """
    
    def __init__(self) -> None:
        """Initialize the link verb."""
        super().__init__("link")
    
    def validate(self, spec: StepConfig, ctx: OperationContext) -> List[str]:
        """
        Validate the link operation.
        
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
            errors.append("Link operation requires 'src' field")
        if not spec.dst:
            errors.append("Link operation requires 'dst' field")
        
        if errors:
            return errors
        
        # Additional link-specific validation
        src_path = ctx.get_src_path()
        dst_path = ctx.get_dst_path()
        
        if dst_path and dst_path.exists():
            if dst_path.is_symlink():
                # Check if it already points to the right place
                current_target = dst_path.resolve()
                if src_path and current_target == src_path.resolve():
                    self.logger.debug(f"Link already exists and is correct: {dst_path} -> {src_path}")
                else:
                    self.logger.debug(f"Link exists but points elsewhere: {dst_path} -> {current_target}")
            else:
                self.logger.debug(f"Destination exists and is not a symlink: {dst_path}")
        
        # Check if parent directory exists or can be created
        if dst_path:
            parent = dst_path.parent
            if not parent.exists() and not spec.create_parent_dirs:
                errors.append(f"Parent directory does not exist: {parent}. Set create_parent_dirs=true to auto-create.")
        
        return errors
    
    def apply(self, spec: StepConfig, ctx: OperationContext) -> OperationResult:
        """
        Create the symbolic link.
        
        This will:
        1. Backup any existing file at destination
        2. Remove existing file/link if present
        3. Create parent directories if needed
        4. Create the symbolic link
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
        
        # Dry run mode
        if ctx.execution_context.dry_run:
            if dst_path.exists():
                if dst_path.is_symlink():
                    current = dst_path.resolve()
                    if current == src_path.resolve():
                        message = f"Link already correct: {dst_path} -> {src_path}"
                    else:
                        message = f"Would update link: {dst_path} -> {src_path} (currently -> {current})"
                else:
                    message = f"Would replace file with link: {dst_path} -> {src_path}"
            else:
                message = f"Would create link: {dst_path} -> {src_path}"
            
            return OperationResult(
                success=True,
                operation_id=0,  # Will be updated by executor
                operation_type=self.name,
                message=message,
                dry_run=True
            )
        
        # Apply mode
        try:
            # Prepare rollback data
            original_state = self._capture_original_state(dst_path)
            
            # Backup existing file if needed
            backup_path = None
            if dst_path.exists() and not self._is_correct_link(src_path, dst_path):
                backup_path = self._backup_file(dst_path, ctx)
            
            # Create parent directories if needed
            if spec.create_parent_dirs and not dst_path.parent.exists():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                if spec.parent_dir_mode:
                    # Set directory permissions if specified
                    mode = int(spec.parent_dir_mode, 8) if isinstance(spec.parent_dir_mode, str) else spec.parent_dir_mode
                    dst_path.parent.chmod(mode)
                self.logger.info(f"Created parent directory: {dst_path.parent}")
            
            # Remove existing file/link if present
            if dst_path.exists() or dst_path.is_symlink():
                if dst_path.is_symlink():
                    dst_path.unlink()
                elif dst_path.is_file():
                    dst_path.unlink()
                elif dst_path.is_dir():
                    import shutil
                    shutil.rmtree(dst_path)
            
            # Create the symbolic link
            dst_path.symlink_to(src_path)
            
            # Set permissions if specified
            if spec.mode and not dst_path.is_symlink():
                mode = int(spec.mode, 8) if isinstance(spec.mode, str) else spec.mode
                dst_path.chmod(mode)
            
            message = f"Created link: {dst_path} -> {src_path}"
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
            message = f"Failed to create link {dst_path} -> {src_path}: {e}"
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
        Rollback a link operation.
        
        This will:
        1. Remove the created symlink
        2. Restore the backed-up file if one exists
        """
        try:
            dst_path = Path(rollback_data["dst_path"]) if "dst_path" in rollback_data else ctx.get_dst_path()
            
            if not dst_path:
                self.logger.error("No destination path for rollback")
                return False
            
            # Remove the link we created
            if dst_path.exists() and dst_path.is_symlink():
                dst_path.unlink()
                self.logger.info(f"Removed link: {dst_path}")
            
            # Restore backup if it exists
            if "backup_path" in rollback_data:
                backup_path = Path(rollback_data["backup_path"])
                if backup_path.exists():
                    import shutil
                    if backup_path.is_dir():
                        shutil.copytree(backup_path, dst_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(backup_path, dst_path)
                    self.logger.info(f"Restored backup: {dst_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False
    
    def _is_correct_link(self, src_path: Path, dst_path: Path) -> bool:
        """Check if dst already points to src correctly."""
        if not dst_path.is_symlink():
            return False
        
        try:
            current_target = dst_path.resolve()
            expected_target = src_path.resolve()
            return current_target == expected_target
        except Exception:
            return False
    
    def _capture_original_state(self, dst_path: Path) -> Dict[str, Any]:
        """Capture the original state of the destination."""
        state: Dict[str, Any] = {
            "existed": dst_path.exists(),
            "was_symlink": dst_path.is_symlink() if dst_path.exists() else False,
        }
        
        if dst_path.is_symlink():
            try:
                state["original_target"] = str(dst_path.readlink())
            except Exception:
                pass
        
        if dst_path.exists() and not dst_path.is_symlink():
            state["was_file"] = dst_path.is_file()
            state["was_dir"] = dst_path.is_dir()
            if dst_path.is_file():
                state["checksum"] = self._calculate_checksum(dst_path)
        
        return state