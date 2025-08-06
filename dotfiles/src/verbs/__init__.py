"""
Verb registry and operation executor.

This module provides the registry for all available verbs and the executor
that runs operations with transaction support and rollback capabilities.
"""

from typing import Dict, List, Optional, Type
import logging

from dotfiles_sync.models import DotfilesConfig, StepConfig, OperationType, OperationResult
from dotfiles_sync.context import ExecutionContext, OperationContext
from dotfiles_sync.state_database import StateDatabase

from .base import Verb
from .link import LinkVerb
from .copy import CopyVerb

logger = logging.getLogger(__name__)


class VerbRegistry:
    """
    Registry of all available verb implementations.
    
    This registry maps operation types to their corresponding verb implementations
    and provides factory methods for creating verb instances.
    """
    
    def __init__(self):
        """Initialize the verb registry with built-in verbs."""
        self._verbs: Dict[str, Type[Verb]] = {}
        self._register_builtin_verbs()
    
    def _register_builtin_verbs(self):
        """Register all built-in verb implementations."""
        self.register("link", LinkVerb)
        self.register("copy", CopyVerb)
    
    def register(self, operation_type: str, verb_class: Type[Verb]):
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
            return verb_class()
        return None
    
    def list_verbs(self) -> List[str]:
        """Get list of all registered verb names."""
        return list(self._verbs.keys())


class OperationExecutor:
    """
    Executes operations with transaction support and rollback capabilities.
    
    This class handles the execution of operations defined in the configuration,
    with proper error handling, rollback support, and state tracking.
    """
    
    def __init__(self, verb_registry: Optional[VerbRegistry] = None):
        """
        Initialize the operation executor.
        
        Args:
            verb_registry: Optional verb registry (creates default if None)
        """
        self.registry = verb_registry or VerbRegistry()
        self.logger = logging.getLogger(__name__)
    
    def execute_all(self, config: DotfilesConfig, exec_ctx: ExecutionContext) -> List[OperationResult]:
        """
        Execute all applicable operations from the configuration.
        
        Args:
            config: The loaded dotfiles configuration
            exec_ctx: Execution context with settings and system info
            
        Returns:
            List of operation results
        """
        results = []
        
        # Filter steps by platform and variant
        applicable_steps = self._filter_applicable_steps(config.step, exec_ctx)
        
        if not applicable_steps:
            self.logger.info("No applicable operations found")
            return results
        
        self.logger.info(f"Found {len(applicable_steps)} applicable operations")
        
        # Execute with transaction support
        with StateDatabase() as db:
            with db.transaction(
                variant=exec_ctx.variant,
                user=exec_ctx.system_info.username,
                hostname=exec_ctx.system_info.hostname,
                dry_run=exec_ctx.dry_run
            ) as tx:
                
                for i, step in enumerate(applicable_steps):
                    result = self._execute_step(step, exec_ctx, db, tx, i + 1)
                    results.append(result)
                    
                    # Stop on failure unless forced
                    if not result.success and not exec_ctx.force:
                        self.logger.error(f"Operation failed, stopping execution: {result.message}")
                        break
        
        return results
    
    def _execute_step(self, step: StepConfig, exec_ctx: ExecutionContext, 
                     db: StateDatabase, transaction, sequence_num: int) -> OperationResult:
        """
        Execute a single step operation.
        
        Args:
            step: Step configuration
            exec_ctx: Execution context
            transaction: Database transaction
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
                operation_id=0,  # Use 0 for unknown operations
                operation_type=step.op.value,
                message=error,
                dry_run=exec_ctx.dry_run
            )
        
        # Create operation context
        op_ctx = OperationContext(
            execution_context=exec_ctx,
            operation_type=step.op.value,
            step_config=step,
            sequence_num=sequence_num
        )
        
        # Record operation start in database
        operation_id = db.record_operation(
            tx=transaction,
            operation_type=step.op.value,
            config=step.model_dump(),
            src_path=str(op_ctx.get_src_path()) if op_ctx.get_src_path() else None,
            dst_path=str(op_ctx.get_dst_path()) if op_ctx.get_dst_path() else None
        )
        
        # Update operation context with the operation_id
        op_ctx.operation_id = operation_id
        
        try:
            # Update operation status
            db.update_operation_status(operation_id, 'executing')
            
            # Execute the operation (dry run or apply)
            if exec_ctx.dry_run:
                result = verb.dry_run(step, op_ctx)
            else:
                result = verb.apply(step, op_ctx)
            
            # Add operation_id to the result (verbs don't know about it)
            result = self._add_operation_id_to_result(result, operation_id)
            
            # Update operation status based on result
            if result.success:
                db.update_operation_status(
                    operation_id, 'success',
                    rollback_data=result.rollback_data
                )
                
                # Record applied step if not a dry run
                if not exec_ctx.dry_run:
                    db.record_applied_step(
                        tx=transaction,
                        operation_type=step.op.value,
                        config=step.model_dump(),
                        src_path=str(op_ctx.get_src_path()) if op_ctx.get_src_path() else None,
                        dst_path=str(op_ctx.get_dst_path()) if op_ctx.get_dst_path() else None
                    )
            else:
                db.update_operation_status(
                    operation_id, 'failed',
                    error_message=result.message
                )
            
            return result
            
        except Exception as e:
            # Update operation status on exception
            db.update_operation_status(
                operation_id, 'failed',
                error_message=str(e)
            )
            
            error = f"Exception executing {step.op}: {e}"
            self.logger.error(error, exc_info=True)
            return OperationResult(
                success=False,
                operation_id=operation_id,
                operation_type=step.op.value,
                message=error,
                dry_run=exec_ctx.dry_run,
                error=str(e)
            )
    
    def _add_operation_id_to_result(self, result: OperationResult, operation_id: int) -> OperationResult:
        """Add operation_id to a result, creating a new instance since results are frozen."""
        # Create a new result with the same data plus operation_id
        result_dict = result.model_dump()
        result_dict['operation_id'] = operation_id
        return OperationResult(**result_dict)
    
    def rollback_transaction(self, transaction_id: str) -> bool:
        """
        Rollback a specific transaction.
        
        Args:
            transaction_id: ID of the transaction to rollback
            
        Returns:
            True if rollback succeeded
        """
        with StateDatabase() as db:
            return db.perform_rollback(transaction_id)
    
    def _filter_applicable_steps(self, steps: List[StepConfig], 
                                exec_ctx: ExecutionContext) -> List[StepConfig]:
        """
        Filter steps that are applicable for the current context.
        
        Args:
            steps: All steps from configuration
            exec_ctx: Execution context
            
        Returns:
            List of applicable steps
        """
        applicable = []
        
        for step in steps:
            # Check platform requirements
            if step.platforms:
                platform_match = any(
                    platform.value == exec_ctx.system_info.platform.value or platform.value == "all"
                    for platform in step.platforms
                )
                if not platform_match:
                    self.logger.debug(f"Skipping step (platform): {step.op} {step.src} -> {step.dst}")
                    continue
            
            # Check variant requirements
            if step.variants:
                variant_match = any(
                    variant == exec_ctx.variant or variant == "all"
                    for variant in step.variants
                )
                if not variant_match:
                    self.logger.debug(f"Skipping step (variant): {step.op} {step.src} -> {step.dst}")
                    continue
            
            applicable.append(step)
        
        # Sort by priority (higher numbers first) - use 0 if no priority field
        applicable.sort(key=lambda s: getattr(s, 'priority', 0), reverse=True)
        
        return applicable


# Global registry instance
_default_registry = VerbRegistry()

def get_default_registry() -> VerbRegistry:
    """Get the default verb registry."""
    return _default_registry