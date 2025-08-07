"""
Text prepend verb implementation.

This module provides text prepending functionality with
idempotency support using markers.
"""

from pathlib import Path
from typing import Any, Dict, List

from dotfiles_sync.models import StepConfig, OperationResult
from dotfiles_sync.context import OperationContext

from .base import Verb


class PrependVerb(Verb):
    """
    Prepend text to files with idempotency.
    
    Features:
    - Marker-based idempotency (won't prepend if marker exists)
    - Create file if it doesn't exist
    - Preserve file permissions
    - Support for multi-line text
    """
    
    def __init__(self) -> None:
        """Initialize the prepend verb."""
        super().__init__("prepend")
    
    def validate(self, step: StepConfig, context: OperationContext) -> List[str]:
        """
        Validate prepend operation.
        
        Args:
            step: Step configuration
            context: Operation context
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if not step.text:
            errors.append("Text is required for prepend operation")
        if not step.dst:
            errors.append("Destination file is required for prepend")
        
        return errors
    
    def dry_run(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Perform a dry run of text prepend.
        
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
                operation_type="prepend",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=True
            )
        
        dst_path = context.get_dst_path()
        
        if not dst_path:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="prepend",
                message="Missing destination path",
                dry_run=True
            )
        
        # Check if marker already exists (idempotency)
        if step.marker and dst_path.exists():
            try:
                content = dst_path.read_text()
                if step.marker in content:
                    return OperationResult(
                        success=True,
                        operation_id=0,
                        operation_type="prepend",
                        message=f"Marker '{step.marker}' already exists in {dst_path}, skipping",
                        dry_run=True,
                        skipped=True
                    )
            except Exception:
                pass
        
        if dst_path.exists():
            message = f"Would prepend {len(step.text or '')} characters to {dst_path}"
        else:
            message = f"Would create {dst_path} and prepend {len(step.text or '')} characters"
        
        return OperationResult(
            success=True,
            operation_id=0,
            operation_type="prepend",
            message=message,
            dry_run=True
        )
    
    def apply(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Apply text prepend operation.
        
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
                operation_type="prepend",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=False
            )
        
        dst_path = context.get_dst_path()
        
        if not dst_path or not step.text:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="prepend",
                message="Missing destination path or text",
                dry_run=False
            )
        
        try:
            # Check if file exists
            file_existed = dst_path.exists()
            original_content = ""
            
            if file_existed:
                original_content = dst_path.read_text()
                
                # Check for marker (idempotency)
                if step.marker and step.marker in original_content:
                    return OperationResult(
                        success=True,
                        operation_id=0,
                        operation_type="prepend",
                        message=f"Marker '{step.marker}' already exists, skipping",
                        dry_run=False,
                        skipped=True
                    )
            else:
                # Create parent directories if needed
                dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare text to prepend
            text_to_prepend = step.text
            
            # Add marker if specified
            if step.marker:
                text_to_prepend = f"# {step.marker}\n{text_to_prepend}\n"
            
            # Ensure newline after prepended text if original content exists
            if original_content and not text_to_prepend.endswith('\n'):
                text_to_prepend = text_to_prepend + '\n'
            
            # Write prepended text + original content
            new_content = text_to_prepend + original_content
            dst_path.write_text(new_content)
            
            # Set permissions if specified
            if step.mode:
                import os
                mode = int(step.mode, 8)
                os.chmod(dst_path, mode)
            
            rollback_data = {
                "file_existed": file_existed,
                "original_content": original_content if file_existed else None,
                "dst_path": str(dst_path),
                "prepended_text": text_to_prepend
            }
            
            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="prepend",
                message=f"Prepended text to {dst_path}",
                dry_run=False,
                rollback_data=rollback_data
            )
            
        except Exception as e:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="prepend",
                message=f"Failed to prepend text: {e}",
                dry_run=False,
                error=str(e)
            )
    
    def rollback(self, step: StepConfig, context: OperationContext, 
                 rollback_data: Dict[str, Any]) -> bool:
        """
        Rollback prepend operation.
        
        Args:
            step: Step configuration
            context: Operation context
            rollback_data: Data from the original operation
            
        Returns:
            True if rollback succeeded
        """
        try:
            dst_path = Path(rollback_data["dst_path"])
            file_existed = rollback_data["file_existed"]
            
            if not file_existed:
                # File didn't exist before, remove it
                if dst_path.exists():
                    dst_path.unlink()
            else:
                # Restore original content
                original_content = rollback_data.get("original_content", "")
                dst_path.write_text(original_content)
            
            self.logger.info(f"Rolled back prepend operation on {dst_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to rollback prepend: {e}")
            return False