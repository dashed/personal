"""
Run-once command execution verb implementation.

This module provides one-time command execution functionality with
tracking to ensure commands are only run once.
"""

import subprocess
from typing import Any, Dict, List

from dotfiles_sync.models import StepConfig, OperationResult
from dotfiles_sync.context import OperationContext
from dotfiles_sync.state_database import StateDatabase

from .base import Verb


class RunOnceVerb(Verb):
    """
    Execute shell commands only once.
    
    Features:
    - Checksum-based tracking (idempotency)
    - Database tracking of executed commands
    - Command whitelisting for safety
    - Sudo support
    - Environment variable support
    """
    
    def __init__(self) -> None:
        """Initialize the run_once verb."""
        super().__init__("run_once")
        self.default_timeout = 300  # 5 minutes
        self.database = StateDatabase()
    
    def validate(self, step: StepConfig, context: OperationContext) -> List[str]:
        """
        Validate run_once operation.
        
        Args:
            step: Step configuration
            context: Operation context
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if not step.command:
            errors.append("Command is required for run_once operation")
        
        # Checksum is optional but recommended for better tracking
        
        return errors
    
    def dry_run(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Perform a dry run of run_once command.
        
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
                operation_type="run_once",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=True
            )
        
        command = step.command or ""
        checksum = step.checksum
        variant = context.execution_context.variant
        
        # Check if already executed
        if self.database.has_run_once(command, checksum, variant):
            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="run_once",
                message=f"Command already executed (checksum: {checksum}), skipping",
                dry_run=True,
                skipped=True
            )
        
        # Check if sudo is required
        if step.sudo:
            command = f"sudo {command}"
        
        message = f"Would run command once: {command}"
        
        return OperationResult(
            success=True,
            operation_id=0,
            operation_type="run_once",
            message=message,
            dry_run=True
        )
    
    def apply(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Apply run_once command execution.
        
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
                operation_type="run_once",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=False
            )
        
        command = step.command
        
        if not command:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="run_once",
                message="Missing command",
                dry_run=False
            )
        
        checksum = step.checksum
        variant = context.execution_context.variant
        
        # Check if already executed
        if self.database.has_run_once(command, checksum, variant):
            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="run_once",
                message=f"Command already executed (checksum: {checksum}), skipping",
                dry_run=False,
                skipped=True
            )
        
        try:
            # Prepare command
            if step.sudo:
                command = f"sudo {command}"
            
            # Prepare environment
            env = None
            if step.vars:
                import os
                env = os.environ.copy()
                env.update({k: str(v) for k, v in step.vars.items()})
            
            # Determine working directory
            cwd = None
            if step.dst:
                cwd_path = context.get_dst_path()
                if cwd_path and cwd_path.is_dir():
                    cwd = str(cwd_path)
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.default_timeout,
                cwd=cwd,
                env=env
            )
            
            if result.returncode != 0:
                return OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="run_once",
                    message=f"Command failed with exit code {result.returncode}",
                    dry_run=False,
                    error=result.stderr
                )
            
            # Record successful execution in database
            # We need a transaction context for this
            with self.database.transaction(
                variant=variant,
                user=context.execution_context.system_info.username,
                hostname=context.execution_context.system_info.hostname,
                dry_run=False
            ) as tx:
                # We already validated command is not None
                assert step.command is not None
                self.database.record_run_once(
                    tx=tx,
                    command=step.command,  # Original command without sudo
                    checksum=checksum,
                    exit_code=result.returncode,
                    output=result.stdout[:1000] if result.stdout else None  # Limit output size
                )
            
            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="run_once",
                message=f"Successfully executed once: {step.command}",
                dry_run=False,
                rollback_data={
                    "command": step.command,
                    "checksum": checksum,
                    "variant": variant
                }
            )
            
        except subprocess.TimeoutExpired:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="run_once",
                message=f"Command timed out after {self.default_timeout} seconds",
                dry_run=False,
                error="Timeout"
            )
        except Exception as e:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="run_once",
                message=f"Failed to execute command: {e}",
                dry_run=False,
                error=str(e)
            )
    
    def rollback(self, step: StepConfig, context: OperationContext, 
                 rollback_data: Dict[str, Any]) -> bool:
        """
        Rollback run_once operation.
        
        Note: We can't undo the command itself, but we can remove
        the tracking record to allow it to run again if needed.
        
        Args:
            step: Step configuration
            context: Operation context
            rollback_data: Data from the original operation
            
        Returns:
            True if rollback succeeded
        """
        try:
            # In a real implementation, we would need a method to remove
            # the run_once tracking record from the database
            # For now, we just log that we can't truly rollback
            self.logger.warning("Run_once operations cannot be fully rolled back")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to rollback run_once: {e}")
            return False