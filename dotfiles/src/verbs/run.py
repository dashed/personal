"""
Command execution verb implementation.

This module provides command execution functionality with
safety checks and command whitelisting.
"""

import subprocess
from typing import Any, Dict, List

from dotfiles_sync.models import StepConfig, OperationResult
from dotfiles_sync.context import OperationContext

from .base import Verb


class RunVerb(Verb):
    """
    Execute shell commands.

    Features:
    - Command whitelisting for safety
    - Sudo support
    - Working directory specification
    - Environment variable support
    - Timeout handling
    """

    def __init__(self) -> None:
        """Initialize the run verb."""
        super().__init__("run")
        self.default_timeout = 300  # 5 minutes

    def validate(self, step: StepConfig, context: OperationContext) -> List[str]:
        """
        Validate run operation.

        Args:
            step: Step configuration
            context: Operation context

        Returns:
            List of validation error messages
        """
        errors = []

        if not step.command:
            errors.append("Command is required for run operation")

        # Note: Command whitelisting is done by SafetyValidator
        # in the main executor, not here

        return errors

    def dry_run(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Perform a dry run of command execution.

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
                operation_type="run",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=True,
            )

        command = step.command or ""

        # Check if sudo is required
        if step.sudo:
            command = f"sudo {command}"

        message = f"Would run command: {command}"

        return OperationResult(
            success=True, operation_id=0, operation_type="run", message=message, dry_run=True
        )

    def apply(self, step: StepConfig, context: OperationContext) -> OperationResult:
        """
        Apply command execution.

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
                operation_type="run",
                message=f"Validation failed: {'; '.join(validation_errors)}",
                dry_run=False,
            )

        command = step.command

        if not command:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="run",
                message="Missing command",
                dry_run=False,
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
                env=env,
            )

            if result.returncode != 0:
                return OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="run",
                    message=f"Command failed with exit code {result.returncode}",
                    dry_run=False,
                    error=result.stderr,
                )

            # No rollback data for run commands
            # (we can't undo arbitrary commands)

            return OperationResult(
                success=True,
                operation_id=0,
                operation_type="run",
                message=f"Successfully executed: {command}",
                dry_run=False,
            )

        except subprocess.TimeoutExpired:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="run",
                message=f"Command timed out after {self.default_timeout} seconds",
                dry_run=False,
                error="Timeout",
            )
        except Exception as e:
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type="run",
                message=f"Failed to execute command: {e}",
                dry_run=False,
                error=str(e),
            )

    def rollback(
        self, step: StepConfig, context: OperationContext, rollback_data: Dict[str, Any]
    ) -> bool:
        """
        Rollback run operation.

        Note: Run operations generally cannot be rolled back as we don't
        know what the command did. This is a no-op.

        Args:
            step: Step configuration
            context: Operation context
            rollback_data: Data from the original operation

        Returns:
            True (no-op)
        """
        self.logger.warning("Run operations cannot be rolled back")
        return True
