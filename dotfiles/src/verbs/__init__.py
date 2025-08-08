"""
Verb registry and operation executor.

This module provides the registry for all available verbs and the executor
that runs operations with transaction support and rollback capabilities.

Enhanced with Phase 2 safety features including:
- Pre-flight validation
- Automatic backup creation
- Enhanced transaction management
- Safety checks and validation
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Type
import logging

from dotfiles_sync.models import DotfilesConfig, StepConfig, OperationResult
from dotfiles_sync.context import ExecutionContext, OperationContext
from dotfiles_sync.state_database import StateDatabase

# Import safety components - always required
from safety import BackupManager, SafetyValidator, TransactionManager, ValidationError

from .base import Verb
from .link import LinkVerb
from .copy import CopyVerb
from .syncdir import SyncDirVerb
from .append import AppendVerb
from .prepend import PrependVerb
from .run import RunVerb
from .run_once import RunOnceVerb

logger = logging.getLogger(__name__)


class VerbRegistry:
    """
    Registry of all available verb implementations.

    This registry maps operation types to their corresponding verb implementations
    and provides factory methods for creating verb instances.
    """

    def __init__(self) -> None:
        """Initialize the verb registry with built-in verbs."""
        self._verbs: Dict[str, Type[Verb]] = {}
        self._register_builtin_verbs()

    def _register_builtin_verbs(self) -> None:
        """Register all built-in verb implementations."""
        self.register("link", LinkVerb)
        self.register("copy", CopyVerb)
        self.register("syncdir", SyncDirVerb)
        self.register("append", AppendVerb)
        self.register("prepend", PrependVerb)
        self.register("run", RunVerb)
        self.register("run_once", RunOnceVerb)

    def register(self, operation_type: str, verb_class: Type[Verb]) -> None:
        """
        Register a verb implementation for an operation type.

        Args:
            operation_type: The operation type string (e.g., 'link', 'copy')
            verb_class: The verb class that implements the operation
        """
        self._verbs[operation_type] = verb_class
        logger.debug(f"Registered verb: {operation_type} -> {verb_class.__name__}")

    def get_verb(self, operation_type: str) -> Optional[Verb]:
        """
        Get a verb instance for an operation type.

        Args:
            operation_type: The operation type string

        Returns:
            Verb instance, or None if not found
        """
        verb_class = self._verbs.get(operation_type)
        if verb_class:
            return verb_class()  # type: ignore[call-arg]
        return None

    def list_verbs(self) -> List[str]:
        """Get list of all registered verb names."""
        return list(self._verbs.keys())


class EnhancedOperationExecutor:
    """
    Enhanced operation executor with comprehensive safety features.

    This class handles the execution of operations defined in the configuration,
    with proper error handling, rollback support, state tracking, and Phase 2
    safety features including pre-flight validation, automatic backups, and
    enhanced transaction management.
    """

    def __init__(
        self,
        verb_registry: Optional[VerbRegistry] = None,
        backup_manager: Optional[BackupManager] = None,
        safety_validator: Optional[SafetyValidator] = None,
        transaction_manager: Optional[TransactionManager] = None,
    ):
        """
        Initialize the enhanced operation executor.

        Args:
            verb_registry: Optional verb registry (creates default if None)
            backup_manager: Optional backup manager for safety features
            safety_validator: Optional safety validator for pre-flight checks
            transaction_manager: Optional enhanced transaction manager
        """
        self.registry = verb_registry or VerbRegistry()
        # Initialize safety components - always available
        self.backup_manager = backup_manager or BackupManager()
        self.safety_validator = safety_validator or SafetyValidator()
        self.logger = logging.getLogger(__name__)

        # Initialize database (will be managed by transaction manager)
        self.database = StateDatabase()

        # Initialize transaction manager with integrated components
        self.transaction_manager = transaction_manager or TransactionManager(
            database=self.database,
            backup_manager=self.backup_manager,
            safety_validator=self.safety_validator,
        )

    def execute_all(
        self, config: DotfilesConfig, exec_ctx: ExecutionContext
    ) -> List[OperationResult]:
        """
        Execute all applicable operations from the configuration with enhanced safety.

        Args:
            config: The loaded dotfiles configuration
            exec_ctx: Execution context with settings and system info

        Returns:
            List of operation results
        """
        results: List[OperationResult] = []

        # Filter steps by platform and variant
        applicable_steps = self._filter_applicable_steps(config.step, exec_ctx)

        if not applicable_steps:
            self.logger.info("No applicable operations found")
            return results

        self.logger.info(f"Found {len(applicable_steps)} applicable operations")

        # Always use enhanced safety features (Phase 2)
        return self._execute_with_enhanced_safety(config, exec_ctx, applicable_steps)

    def _execute_with_enhanced_safety(
        self, config: DotfilesConfig, exec_ctx: ExecutionContext, applicable_steps: List[StepConfig]
    ) -> List[OperationResult]:
        """Execute operations with full Phase 2 safety features."""
        results = []

        # Ensure config is available in ExecutionContext for safety validation
        exec_ctx.config = config

        # Update safety validator with actual config from loaded configuration
        self.safety_validator = SafetyValidator(config.security, config.safety)
        self.transaction_manager.safety_validator = self.safety_validator

        # Enhanced transaction management with safety features
        try:
            with self.transaction_manager.transaction_scope(
                variant=exec_ctx.variant,
                user=exec_ctx.system_info.username,
                hostname=exec_ctx.system_info.hostname,
                dry_run=exec_ctx.dry_run,
                execution_context=exec_ctx,
            ) as transaction_id:
                # Collect files that will be modified for backup
                if config.safety.backup_before_modify and not exec_ctx.dry_run:
                    files_to_backup = self._collect_files_for_backup(applicable_steps, exec_ctx)
                    if files_to_backup:
                        backup_id = self.transaction_manager.create_backup_for_transaction(
                            transaction_id=transaction_id,
                            files_to_backup=files_to_backup,
                            reason="Pre-execution backup",
                        )
                        if backup_id:
                            self.logger.info(f"Created backup: {backup_id}")

                # Execute operations
                for i, step in enumerate(applicable_steps):
                    result = self._execute_step_enhanced(step, exec_ctx, transaction_id, i + 1)
                    results.append(result)

                    # Record operation in enhanced transaction
                    rollback_action = self._create_rollback_action(step, exec_ctx, result)
                    self.transaction_manager.record_operation(
                        transaction_id=transaction_id,
                        operation_result=result,
                        rollback_action=rollback_action,
                    )

                    # Stop on failure unless forced
                    if not result.success and not exec_ctx.force:
                        self.logger.error(f"Operation failed, stopping execution: {result.message}")
                        break

        except ValidationError as e:
            # Handle validation errors
            self.logger.error(f"Pre-flight validation failed: {e}")
            failed_validations = [str(vr.message) for vr in e.validation_results]
            results.append(
                OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="validation",
                    message=f"Validation failed: {'; '.join(failed_validations)}",
                    dry_run=exec_ctx.dry_run,
                    error=str(e),
                )
            )

        except Exception as e:
            # Handle other errors
            self.logger.error(f"Execution failed: {e}", exc_info=True)
            results.append(
                OperationResult(
                    success=False,
                    operation_id=0,
                    operation_type="execution",
                    message=f"Execution failed: {e}",
                    dry_run=exec_ctx.dry_run,
                    error=str(e),
                )
            )

        return results

    def _add_operation_id_to_result(
        self, result: OperationResult, operation_id: int
    ) -> OperationResult:
        """Add operation_id to a result, creating a new instance since results are frozen."""
        # Use model_copy to create a new instance with updated field
        return result.model_copy(update={"operation_id": operation_id})

    def _collect_files_for_backup(
        self, steps: List[StepConfig], exec_ctx: ExecutionContext
    ) -> List[Path]:
        """
        Collect all files that will be modified by the given steps.

        Args:
            steps: List of steps to analyze
            exec_ctx: Execution context

        Returns:
            List of file paths that need backup
        """
        files_to_backup = []

        for step in steps:
            if step.dst and step.op.value in ["link", "copy", "syncdir", "template"]:
                dst_path = exec_ctx.expand_path(step.dst)
                if dst_path.exists():
                    files_to_backup.append(dst_path)

        return files_to_backup

    def _execute_step_enhanced(
        self, step: StepConfig, exec_ctx: ExecutionContext, transaction_id: str, sequence_num: int
    ) -> OperationResult:
        """
        Execute a single step with enhanced safety features.

        Args:
            step: Step configuration
            exec_ctx: Execution context
            transaction_id: Enhanced transaction ID
            sequence_num: Sequence number in the transaction

        Returns:
            Operation result
        """
        # Get the appropriate verb
        verb = self.registry.get_verb(step.op.value)
        if not verb:
            error = f"Unknown operation type: {step.op}"
            self.logger.error(error)
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type=step.op.value,
                message=error,
                dry_run=exec_ctx.dry_run,
            )

        # Create operation context
        op_ctx = OperationContext(
            execution_context=exec_ctx,
            operation_type=step.op.value,
            step_config=step,
            sequence_num=sequence_num,
        )

        # Perform safety validation for this specific operation
        validation_results = self.safety_validator.validate_operation(
            operation_type=step.op.value,
            src_path=op_ctx.get_src_path(),
            dst_path=op_ctx.get_dst_path(),
            command=step.command,
            expected_checksum=step.checksum,
        )

        # Check for validation failures
        failed_validations = [vr for vr in validation_results if not vr.valid]
        if failed_validations:
            error_messages = [vr.message for vr in failed_validations]
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type=step.op.value,
                message=f"Validation failed: {'; '.join(error_messages)}",
                dry_run=exec_ctx.dry_run,
                error="Validation failure",
            )

        try:
            # Execute the operation (dry run or apply)
            if exec_ctx.dry_run:
                result = verb.dry_run(step, op_ctx)
            else:
                result = verb.apply(step, op_ctx)

            # Add transaction context to result
            if result.rollback_data is None:
                result = result.model_copy(
                    update={"rollback_data": {"transaction_id": transaction_id}}
                )

            return result

        except Exception as e:
            error = f"Exception executing {step.op}: {e}"
            self.logger.error(error, exc_info=True)
            return OperationResult(
                success=False,
                operation_id=0,
                operation_type=step.op.value,
                message=error,
                dry_run=exec_ctx.dry_run,
                error=str(e),
            )

    def _create_rollback_action(
        self, step: StepConfig, exec_ctx: ExecutionContext, result: OperationResult
    ) -> Optional[Dict[str, Any]]:
        """
        Create rollback action for a step result.

        Args:
            step: Step configuration
            exec_ctx: Execution context
            result: Operation result

        Returns:
            Rollback action dictionary or None
        """
        if not result.success or exec_ctx.dry_run:
            return None

        op_ctx = OperationContext(
            execution_context=exec_ctx,
            operation_type=step.op.value,
            step_config=step,
            sequence_num=1,  # Not used for rollback
        )

        if step.op.value == "link" and step.dst:
            dst_path = op_ctx.get_dst_path()
            return {"type": "remove_file", "file_path": str(dst_path), "operation_type": "link"}

        elif step.op.value == "copy" and step.dst:
            dst_path = op_ctx.get_dst_path()
            return {"type": "remove_file", "file_path": str(dst_path), "operation_type": "copy"}

        # Add more rollback actions as needed for other operation types
        return None

    def _filter_applicable_steps(
        self, steps: List[StepConfig], exec_ctx: ExecutionContext
    ) -> List[StepConfig]:
        """
        Filter steps by platform and variant.

        Args:
            steps: All configured steps
            exec_ctx: Execution context with variant and system info

        Returns:
            List of steps applicable to current context
        """
        applicable_steps = []

        for step in steps:
            # Check variant filter
            if exec_ctx.variant not in step.variants and "all" not in step.variants:
                continue

            # Check platform filter
            if step.platforms:
                if not exec_ctx.system_info.matches_platform(step.platforms):
                    continue

            applicable_steps.append(step)

        return applicable_steps


# Use EnhancedOperationExecutor as the primary executor
OperationExecutor = EnhancedOperationExecutor


# Global registry instance
_default_registry = VerbRegistry()


def get_default_registry() -> VerbRegistry:
    """Get the default verb registry."""
    return _default_registry
