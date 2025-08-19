"""
Configuration drift detection for the Dotfiles Management System.

This module provides functionality to detect differences between the current
TOML configuration and the applied state in the database, including:
- New operations (in TOML but not in database)
- Modified operations (same destination, different configuration)
- Orphaned operations (in database but not in TOML)
"""

import hashlib
import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from dotfiles_sync.models import DotfilesConfig, Platform, StepConfig
from dotfiles_sync.state_database import StateDatabase


class ConfigDriftType(Enum):
    """Types of configuration drift that can be detected."""

    NEW = "new"  # In TOML, not in DB
    MODIFIED = "modified"  # Same dst, different hash
    ORPHANED = "orphaned"  # In DB, not in TOML


class ConfigDriftSeverity(Enum):
    """Severity levels for configuration drift."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ConfigDriftResult(BaseModel):
    """Result of configuration drift detection for a single operation."""

    drift_type: ConfigDriftType = Field(..., description="Type of drift detected")
    dst_path: str = Field(..., description="Destination path affected")
    operation_type: str = Field(..., description="Operation type (link, copy, etc.)")
    current_step_hash: Optional[str] = Field(None, description="Hash from current TOML")
    applied_step_hash: Optional[str] = Field(None, description="Hash from database")
    current_config: Optional[Dict[str, Any]] = Field(None, description="Current TOML config")
    applied_config: Optional[Dict[str, Any]] = Field(None, description="Applied config from DB")
    impact: str = Field(..., description="Description of what will happen")
    severity: ConfigDriftSeverity = Field(
        default=ConfigDriftSeverity.INFO, description="Severity of the drift"
    )

    def __str__(self) -> str:
        return f"{self.drift_type.value}: {self.dst_path} ({self.operation_type})"


class ConfigDriftSummary(BaseModel):
    """Summary of configuration drift analysis."""

    total_drift: int = Field(0, description="Total number of drift items")
    new_operations: List[ConfigDriftResult] = Field(
        default_factory=list, description="Operations in TOML but not in DB"
    )
    modified_operations: List[ConfigDriftResult] = Field(
        default_factory=list, description="Operations with changed configuration"
    )
    orphaned_operations: List[ConfigDriftResult] = Field(
        default_factory=list, description="Operations in DB but not in TOML"
    )
    recommended_action: str = Field("", description="Recommended action to resolve drift")
    checked_variant: str = Field("default", description="Variant that was checked")

    @property
    def has_drift(self) -> bool:
        """Check if any drift was detected."""
        return self.total_drift > 0

    @property
    def critical_drift_count(self) -> int:
        """Count of critical drift issues."""
        all_drift = self.new_operations + self.modified_operations + self.orphaned_operations
        return sum(1 for drift in all_drift if drift.severity == ConfigDriftSeverity.ERROR)


class ConfigDriftDetector:
    """
    Detects configuration drift between TOML configuration and database state.

    This class compares the current configuration file with the applied state
    in the database to identify:
    - New operations that need to be applied
    - Modified operations that have changed configuration
    - Orphaned operations that are no longer in the configuration
    """

    def __init__(self, database: StateDatabase):
        """
        Initialize the drift detector.

        Args:
            database: State database instance for accessing applied operations
        """
        self.database = database
        self.logger = logging.getLogger(__name__)

    def detect_drift(
        self, config: DotfilesConfig, variant: str = "default", platform: Optional[Platform] = None
    ) -> ConfigDriftSummary:
        """
        Detect all types of configuration drift.

        Args:
            config: Current dotfiles configuration from TOML
            variant: Variant to check for drift
            platform: Platform to filter steps (if None, uses current platform)

        Returns:
            Summary of detected configuration drift
        """
        self.logger.info(f"Detecting configuration drift for variant: {variant}")

        # Get current configuration step hashes
        current_steps = self._get_current_step_configs(config, variant, platform)
        current_hashes = self._calculate_step_hashes(current_steps)

        # Get applied step hashes from database
        applied_hashes = self._get_applied_step_hashes()

        # Detect different types of drift
        new_ops = self._find_new_operations(current_steps, current_hashes, applied_hashes)
        modified_ops = self._find_modified_operations(current_steps, current_hashes, applied_hashes)
        orphaned_ops = self._find_orphaned_operations(current_hashes, applied_hashes)

        # Calculate total and recommendation
        total = len(new_ops) + len(modified_ops) + len(orphaned_ops)
        recommendation = self._recommend_action(new_ops, modified_ops, orphaned_ops)

        return ConfigDriftSummary(
            total_drift=total,
            new_operations=new_ops,
            modified_operations=modified_ops,
            orphaned_operations=orphaned_ops,
            recommended_action=recommendation,
            checked_variant=variant,
        )

    def _get_current_step_configs(
        self, config: DotfilesConfig, variant: str, platform: Optional[Platform] = None
    ) -> Dict[str, Tuple[StepConfig, str]]:
        """
        Get current step configurations filtered by variant and platform.

        Returns:
            Dict mapping dst_path to (StepConfig, step_hash) tuple
        """
        steps = {}

        # Filter by variant
        variant_steps = config.filter_steps_by_variant(variant)

        # Filter by platform if specified
        if platform:
            variant_steps = [
                step
                for step in variant_steps
                if step.platforms is None
                or platform in step.platforms
                or Platform.ALL in step.platforms
            ]
        else:
            # Use current platform
            from dotfiles_sync.models import SystemInfo

            current_platform = SystemInfo.from_current_system().platform
            variant_steps = [
                step
                for step in variant_steps
                if step.platforms is None
                or current_platform in step.platforms
                or Platform.ALL in step.platforms
            ]

        # Build mapping of dst_path to step config and hash
        for step in variant_steps:
            if step.dst:
                # Expand user path for consistency
                from pathlib import Path

                dst_path = str(Path(step.dst).expanduser())
                step_dict = step.model_dump(exclude_none=True)
                step_hash = self._calculate_single_step_hash(step_dict)
                steps[dst_path] = (step, step_hash)

        return steps

    def _calculate_step_hashes(self, steps: Dict[str, Tuple[StepConfig, str]]) -> Dict[str, str]:
        """
        Calculate hashes for step configurations.

        Returns:
            Dict mapping dst_path to step_hash
        """
        return {dst_path: step_hash for dst_path, (_, step_hash) in steps.items()}

    def _calculate_single_step_hash(self, step_config: Dict[str, Any]) -> str:
        """
        Calculate hash for a single step configuration.

        This must match the hashing algorithm used in StateDatabase.record_applied_step.

        Args:
            step_config: Step configuration dictionary

        Returns:
            SHA256 hash of the configuration
        """
        # Sort keys for consistent hashing
        config_json = json.dumps(step_config, sort_keys=True)
        return hashlib.sha256(config_json.encode()).hexdigest()

    def _get_applied_step_hashes(self) -> Dict[str, Dict[str, Any]]:
        """
        Get applied step hashes from database.

        Returns:
            Dict mapping dst_path to applied step information
        """
        applied_steps = self.database.get_current_applied_steps()
        result = {}

        for step in applied_steps:
            if step.get("dst_path"):
                # Normalize path for comparison
                from pathlib import Path

                dst_path = str(Path(step["dst_path"]).expanduser())
                result[dst_path] = {
                    "step_hash": step.get("step_hash"),
                    "operation_type": step.get("operation_type"),
                    "config": json.loads(step.get("config", "{}"))
                    if isinstance(step.get("config"), str)
                    else step.get("config", {}),
                    "applied_at": step.get("applied_at"),
                }

        return result

    def _find_new_operations(
        self,
        current_steps: Dict[str, Tuple[StepConfig, str]],
        current_hashes: Dict[str, str],
        applied_hashes: Dict[str, Dict[str, Any]],
    ) -> List[ConfigDriftResult]:
        """
        Find operations that are in current config but not in database.

        Args:
            current_steps: Current step configurations with hashes
            current_hashes: Current step hashes
            applied_hashes: Applied step information from database

        Returns:
            List of new operations
        """
        new_operations = []

        for dst_path, (step, step_hash) in current_steps.items():
            if dst_path not in applied_hashes:
                new_operations.append(
                    ConfigDriftResult(
                        drift_type=ConfigDriftType.NEW,
                        dst_path=dst_path,
                        operation_type=step.op.value,
                        current_step_hash=step_hash,
                        applied_step_hash=None,
                        current_config=step.model_dump(exclude_none=True),
                        applied_config=None,
                        impact=f"New {step.op.value} operation will be applied on next sync",
                        severity=ConfigDriftSeverity.INFO,
                    )
                )

        return new_operations

    def _find_modified_operations(
        self,
        current_steps: Dict[str, Tuple[StepConfig, str]],
        current_hashes: Dict[str, str],
        applied_hashes: Dict[str, Dict[str, Any]],
    ) -> List[ConfigDriftResult]:
        """
        Find operations that have changed configuration.

        Args:
            current_steps: Current step configurations with hashes
            current_hashes: Current step hashes
            applied_hashes: Applied step information from database

        Returns:
            List of modified operations
        """
        modified_operations = []

        for dst_path, (step, step_hash) in current_steps.items():
            if dst_path in applied_hashes:
                applied_info = applied_hashes[dst_path]
                applied_hash = applied_info.get("step_hash")

                if step_hash != applied_hash:
                    # Configuration has changed
                    severity = ConfigDriftSeverity.WARNING
                    impact = f"Configuration changed for {step.op.value} operation"

                    # Check if operation type changed
                    if step.op.value != applied_info.get("operation_type"):
                        severity = ConfigDriftSeverity.ERROR
                        impact = (
                            f"Operation type changed from {applied_info.get('operation_type')} "
                            f"to {step.op.value}"
                        )

                    modified_operations.append(
                        ConfigDriftResult(
                            drift_type=ConfigDriftType.MODIFIED,
                            dst_path=dst_path,
                            operation_type=step.op.value,
                            current_step_hash=step_hash,
                            applied_step_hash=applied_hash,
                            current_config=step.model_dump(exclude_none=True),
                            applied_config=applied_info.get("config"),
                            impact=impact,
                            severity=severity,
                        )
                    )

        return modified_operations

    def _find_orphaned_operations(
        self, current_hashes: Dict[str, str], applied_hashes: Dict[str, Dict[str, Any]]
    ) -> List[ConfigDriftResult]:
        """
        Find operations that are in database but not in current config.

        Args:
            current_hashes: Current step hashes
            applied_hashes: Applied step information from database

        Returns:
            List of orphaned operations
        """
        orphaned_operations = []

        for dst_path, applied_info in applied_hashes.items():
            if dst_path not in current_hashes:
                orphaned_operations.append(
                    ConfigDriftResult(
                        drift_type=ConfigDriftType.ORPHANED,
                        dst_path=dst_path,
                        operation_type=applied_info.get("operation_type", "unknown"),
                        current_step_hash=None,
                        applied_step_hash=applied_info.get("step_hash"),
                        current_config=None,
                        applied_config=applied_info.get("config"),
                        impact="Operation no longer in configuration, file remains managed",
                        severity=ConfigDriftSeverity.WARNING,
                    )
                )

        return orphaned_operations

    def _recommend_action(
        self,
        new_ops: List[ConfigDriftResult],
        modified_ops: List[ConfigDriftResult],
        orphaned_ops: List[ConfigDriftResult],
    ) -> str:
        """
        Generate a recommendation based on detected drift.

        Args:
            new_ops: New operations
            modified_ops: Modified operations
            orphaned_ops: Orphaned operations

        Returns:
            Recommended action string
        """
        if not (new_ops or modified_ops or orphaned_ops):
            return "No action needed - configuration is in sync"

        actions = []

        if orphaned_ops:
            actions.append(f"clean {len(orphaned_ops)} orphaned operations")

        if modified_ops:
            actions.append(f"update {len(modified_ops)} modified operations")

        if new_ops:
            actions.append(f"apply {len(new_ops)} new operations")

        if len(actions) == 1:
            return f"Run 'dotfiles-sync sync' to {actions[0]}"
        else:
            return f"Run 'dotfiles-sync reconcile' to {', '.join(actions)}"

    def get_orphaned_step_hashes(self) -> Set[str]:
        """
        Get the step hashes of all orphaned operations.

        Returns:
            Set of step hashes for orphaned operations
        """
        # Get current config hashes
        from pathlib import Path
        from dotfiles_sync.config import ConfigLoader

        # Use default config path
        config_path = Path("dotfiles.toml")
        loader = ConfigLoader(config_path)
        config = loader.load()

        current_steps = self._get_current_step_configs(config, "default")
        current_hashes = set(self._calculate_step_hashes(current_steps).values())

        # Get applied hashes
        applied_steps = self.database.get_current_applied_steps()
        applied_hashes = {step.get("step_hash") for step in applied_steps if step.get("step_hash")}

        # Find orphaned hashes
        return applied_hashes - current_hashes
