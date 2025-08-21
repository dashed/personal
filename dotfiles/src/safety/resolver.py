"""
Conflict resolution for the Dotfiles Management System.

This module provides conflict detection and resolution capabilities for
operations that have conflicting targets or modifications.

Phase 4: Safety Features & Confirmation implementation.
"""

import hashlib
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from dotfiles_sync.models import StepConfig, OperationType


class ConflictType(str, Enum):
    """Types of conflicts that can occur."""

    MULTIPLE_TARGETS = "multiple_targets"  # Multiple operations target same destination
    LOCAL_MODIFICATION = "local_modification"  # Local file has been modified
    EXISTING_SYMLINK = "existing_symlink"  # Destination is already a symlink
    PERMISSION_CONFLICT = "permission_conflict"  # Permission/access conflicts
    DEPENDENCY_CONFLICT = "dependency_conflict"  # Operation breaks dependencies
    VERSION_CONFLICT = "version_conflict"  # Configuration version mismatch


class ResolutionStrategy(str, Enum):
    """Strategies for resolving conflicts."""

    SKIP = "skip"  # Skip the conflicting operation
    OVERWRITE = "overwrite"  # Proceed and overwrite existing
    BACKUP_AND_PROCEED = "backup_and_proceed"  # Create backup then proceed
    MERGE = "merge"  # Attempt to merge changes (for text files)
    ASK_USER = "ask_user"  # Let user decide
    PRIORITY_BASED = "priority_based"  # Use operation priority rules


class ConflictDetail(BaseModel):
    """Detailed information about a specific conflict."""

    type: ConflictType
    description: str
    affected_path: str
    conflicting_operations: List[int] = Field(
        default_factory=list, description="Operation indices involved"
    )
    local_file_hash: Optional[str] = None
    recommended_strategy: ResolutionStrategy = ResolutionStrategy.ASK_USER
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConflictReport(BaseModel):
    """Report of all detected conflicts for a set of operations."""

    conflicts: List[ConflictDetail] = Field(default_factory=list)
    resolutions: Dict[int, ResolutionStrategy] = Field(
        default_factory=dict, description="Chosen resolutions by operation index"
    )

    def add_conflict(self, conflict: ConflictDetail) -> None:
        """Add a conflict to the report."""
        self.conflicts.append(conflict)

    def has_conflicts(self) -> bool:
        """Check if there are any unresolved conflicts."""
        return len(self.conflicts) > 0

    def get_conflicts_for_operation(self, operation_index: int) -> List[ConflictDetail]:
        """Get all conflicts affecting a specific operation."""
        return [
            conflict
            for conflict in self.conflicts
            if operation_index in conflict.conflicting_operations
        ]


class ConflictResolver:
    """
    Detects and resolves conflicts between operations.

    Provides comprehensive conflict detection including multiple operations
    targeting the same destination, local file modifications, and dependency conflicts.
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the conflict resolver.

        Args:
            console: Rich console for output (creates default if None)
        """
        self.console = console or Console()

    def detect_conflicts(
        self, steps: List[StepConfig], operation_contexts: Optional[List[Any]] = None
    ) -> ConflictReport:
        """
        Detect conflicts between a set of operations.

        Args:
            steps: List of step configurations to analyze
            operation_contexts: Optional operation contexts for additional analysis

        Returns:
            Conflict report with detected issues
        """
        report = ConflictReport()

        # Detect various types of conflicts
        self._detect_multiple_target_conflicts(steps, report)
        self._detect_local_modification_conflicts(steps, report)
        self._detect_symlink_conflicts(steps, report)
        self._detect_dependency_conflicts(steps, report)

        return report

    def resolve_conflicts(
        self, report: ConflictReport, steps: List[StepConfig], interactive: bool = True
    ) -> ConflictReport:
        """
        Resolve detected conflicts using various strategies.

        Args:
            report: Conflict report to resolve
            steps: Original step configurations
            interactive: Whether to prompt user for resolution choices

        Returns:
            Updated conflict report with resolutions
        """
        if not report.has_conflicts():
            return report

        if interactive:
            self._show_conflict_summary(report)

        for i, conflict in enumerate(report.conflicts):
            if interactive:
                strategy = self._get_user_resolution_choice(conflict, steps)
            else:
                strategy = self._get_automatic_resolution(conflict)

            # Apply resolution to all affected operations
            for op_index in conflict.conflicting_operations:
                report.resolutions[op_index] = strategy

        return report

    def _detect_multiple_target_conflicts(
        self, steps: List[StepConfig], report: ConflictReport
    ) -> None:
        """Detect operations that target the same destination."""
        # Group operations by destination path
        destination_map: Dict[str, List[int]] = {}

        for i, step in enumerate(steps):
            if step.dst:
                # Normalize path for comparison
                dst_path = Path(step.dst).expanduser().resolve()
                dst_str = str(dst_path)

                if dst_str not in destination_map:
                    destination_map[dst_str] = []
                destination_map[dst_str].append(i)

        # Find conflicts (multiple operations with same destination)
        for dst_path, operation_indices in destination_map.items():
            if len(operation_indices) > 1:
                # Analyze the conflict
                operations = [steps[i] for i in operation_indices]
                conflict_description = self._analyze_multiple_target_conflict(operations, dst_path)

                report.add_conflict(
                    ConflictDetail(
                        type=ConflictType.MULTIPLE_TARGETS,
                        description=conflict_description,
                        affected_path=dst_path,
                        conflicting_operations=operation_indices,
                        recommended_strategy=self._recommend_multiple_target_strategy(operations),
                    )
                )

    def _detect_local_modification_conflicts(
        self, steps: List[StepConfig], report: ConflictReport
    ) -> None:
        """Detect conflicts with locally modified files."""
        for i, step in enumerate(steps):
            if not step.dst:
                continue

            try:
                dst_path = Path(step.dst).expanduser().resolve()

                if dst_path.exists() and dst_path.is_file():
                    # Check if file appears to be locally modified
                    if self._has_local_modifications(dst_path):
                        file_hash = self._calculate_file_hash(dst_path)

                        report.add_conflict(
                            ConflictDetail(
                                type=ConflictType.LOCAL_MODIFICATION,
                                description=f"File {dst_path} has local modifications that will be lost",
                                affected_path=str(dst_path),
                                conflicting_operations=[i],
                                local_file_hash=file_hash,
                                recommended_strategy=ResolutionStrategy.BACKUP_AND_PROCEED,
                            )
                        )

            except Exception:
                # Skip files we can't analyze
                continue

    def _detect_symlink_conflicts(self, steps: List[StepConfig], report: ConflictReport) -> None:
        """Detect conflicts with existing symlinks."""
        for i, step in enumerate(steps):
            if not step.dst:
                continue

            try:
                dst_path = Path(step.dst).expanduser().resolve()

                if dst_path.exists() and dst_path.is_symlink():
                    current_target = dst_path.readlink()

                    # Check if operation would change symlink target
                    if step.op == OperationType.LINK and step.src:
                        intended_target = Path(step.src).expanduser().resolve()

                        if current_target != intended_target:
                            report.add_conflict(
                                ConflictDetail(
                                    type=ConflictType.EXISTING_SYMLINK,
                                    description=f"Symlink currently points to {current_target}, will change to {intended_target}",
                                    affected_path=str(dst_path),
                                    conflicting_operations=[i],
                                    recommended_strategy=ResolutionStrategy.OVERWRITE,
                                    metadata={
                                        "current_target": str(current_target),
                                        "intended_target": str(intended_target),
                                    },
                                )
                            )
                    elif step.op != OperationType.LINK:
                        # Non-link operation targeting existing symlink
                        report.add_conflict(
                            ConflictDetail(
                                type=ConflictType.EXISTING_SYMLINK,
                                description=f"Will replace symlink (pointing to {current_target}) with {step.op.value}",
                                affected_path=str(dst_path),
                                conflicting_operations=[i],
                                recommended_strategy=ResolutionStrategy.ASK_USER,
                                metadata={"current_target": str(current_target)},
                            )
                        )

            except Exception:
                continue

    def _detect_dependency_conflicts(self, steps: List[StepConfig], report: ConflictReport) -> None:
        """Detect conflicts that break file dependencies."""
        # This is a simplified implementation - in practice, you might want
        # to integrate with the DependencyAnalyzer from the impact module

        for i, step in enumerate(steps):
            if step.op in [OperationType.RUN, OperationType.RUN_ONCE] and step.command:
                # Check for potentially dangerous commands
                dangerous_patterns = ["rm -rf", "delete", "format"]

                if any(pattern in step.command.lower() for pattern in dangerous_patterns):
                    report.add_conflict(
                        ConflictDetail(
                            type=ConflictType.DEPENDENCY_CONFLICT,
                            description=f"Command may break system dependencies: {step.command}",
                            affected_path="system",
                            conflicting_operations=[i],
                            recommended_strategy=ResolutionStrategy.ASK_USER,
                        )
                    )

    def _analyze_multiple_target_conflict(self, operations: List[StepConfig], dst_path: str) -> str:
        """Analyze conflict between multiple operations targeting same destination."""
        op_types = [op.op.value for op in operations]

        if all(op_type == op_types[0] for op_type in op_types):
            return f"{len(operations)} {op_types[0]} operations target {dst_path}"
        else:
            return f"Mixed operations ({', '.join(set(op_types))}) target {dst_path}"

    def _recommend_multiple_target_strategy(
        self, operations: List[StepConfig]
    ) -> ResolutionStrategy:
        """Recommend strategy for multiple target conflicts."""
        op_types = [op.op for op in operations]

        # If all operations are the same type, use priority rules
        if all(op_type == op_types[0] for op_type in op_types):
            return ResolutionStrategy.PRIORITY_BASED
        else:
            # Mixed operation types - ask user
            return ResolutionStrategy.ASK_USER

    def _has_local_modifications(self, file_path: Path) -> bool:
        """Check if a file appears to have local modifications."""
        try:
            stat = file_path.stat()
            # Simple heuristic: file modified in last 7 days
            import time

            return (time.time() - stat.st_mtime) < (7 * 24 * 3600)
        except Exception:
            return False

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""

    def _show_conflict_summary(self, report: ConflictReport) -> None:
        """Display a summary of detected conflicts."""
        self.console.print("\n[bold red]⚠️  Conflicts Detected[/bold red]")

        conflict_table = Table(show_header=True, header_style="bold magenta")
        conflict_table.add_column("#", style="dim")
        conflict_table.add_column("Type", style="cyan")
        conflict_table.add_column("Path", style="blue", overflow="ellipsis", max_width=40)
        conflict_table.add_column("Description", overflow="ellipsis", max_width=50)
        conflict_table.add_column("Operations", style="yellow")

        for i, conflict in enumerate(report.conflicts, 1):
            ops_str = ", ".join(str(idx) for idx in conflict.conflicting_operations)
            conflict_table.add_row(
                str(i),
                conflict.type.value.replace("_", " ").title(),
                conflict.affected_path,
                conflict.description,
                ops_str,
            )

        self.console.print(Panel(conflict_table, title="Conflict Summary", border_style="red"))

    def _get_user_resolution_choice(
        self, conflict: ConflictDetail, steps: List[StepConfig]
    ) -> ResolutionStrategy:
        """Get user's choice for resolving a conflict."""
        self.console.print(
            f"\n[bold yellow]Resolving Conflict: {conflict.type.value.replace('_', ' ').title()}[/bold yellow]"
        )
        self.console.print(f"Path: [blue]{conflict.affected_path}[/blue]")
        self.console.print(f"Description: {conflict.description}")

        if conflict.conflicting_operations:
            self.console.print("\nAffected operations:")
            for op_idx in conflict.conflicting_operations:
                if 0 <= op_idx < len(steps):
                    step = steps[op_idx]
                    self.console.print(
                        f"  {op_idx}: {step.op.value} {step.src or ''} -> {step.dst or ''}"
                    )

        # Show resolution options
        options = {
            "skip": "Skip the conflicting operation(s)",
            "overwrite": "Proceed and overwrite existing files",
            "backup": "Create backup and proceed",
        }

        # Add conflict-specific options
        if conflict.type == ConflictType.LOCAL_MODIFICATION:
            options["merge"] = "Attempt to merge changes (text files only)"

        self.console.print("\n[bold]Resolution options:[/bold]")
        for key, description in options.items():
            self.console.print(f"  [bold cyan]{key}[/bold cyan]: {description}")

        choice = Prompt.ask(
            "\n[bold green]How would you like to resolve this conflict?[/bold green]",
            choices=list(options.keys()),
            default="backup"
            if conflict.recommended_strategy == ResolutionStrategy.BACKUP_AND_PROCEED
            else "skip",
        )

        # Map user choice to strategy
        strategy_map = {
            "skip": ResolutionStrategy.SKIP,
            "overwrite": ResolutionStrategy.OVERWRITE,
            "backup": ResolutionStrategy.BACKUP_AND_PROCEED,
            "merge": ResolutionStrategy.MERGE,
        }

        return strategy_map.get(choice, ResolutionStrategy.SKIP)

    def _get_automatic_resolution(self, conflict: ConflictDetail) -> ResolutionStrategy:
        """Get automatic resolution for a conflict (non-interactive mode)."""
        # Use recommended strategy for automatic resolution
        return conflict.recommended_strategy

    def apply_resolution(
        self,
        step: StepConfig,
        strategy: ResolutionStrategy,
        conflict: Optional[ConflictDetail] = None,
    ) -> bool:
        """
        Apply a resolution strategy to a step.

        Args:
            step: Step configuration to modify
            strategy: Resolution strategy to apply
            conflict: Optional conflict detail for context

        Returns:
            True if step should proceed, False if it should be skipped
        """
        if strategy == ResolutionStrategy.SKIP:
            return False
        elif strategy == ResolutionStrategy.OVERWRITE:
            # Ensure overwrite flag is set
            if hasattr(step, "overwrite"):
                step.overwrite = True
            return True
        elif strategy == ResolutionStrategy.BACKUP_AND_PROCEED:
            # Ensure backup flag is set
            if hasattr(step, "backup"):
                step.backup = True
            return True
        elif strategy == ResolutionStrategy.MERGE:
            # Set merge mode if supported
            if hasattr(step, "merge_mode"):
                setattr(step, "merge_mode", True)  # Use setattr for dynamic attribute
            return True
        else:
            # Default to proceeding
            return True

    def get_operation_priority(self, step: StepConfig) -> int:
        """
        Get priority for an operation (higher = more important).

        Used for priority-based conflict resolution.
        """
        # Priority rules based on operation type
        priority_map = {
            OperationType.SECRET_REF: 100,  # Secrets have highest priority
            OperationType.TEMPLATE: 90,  # Templates are important
            OperationType.LINK: 80,  # Links are core functionality
            OperationType.COPY: 70,  # Copies are important
            OperationType.SYNCDIR: 60,  # Directory sync
            OperationType.RUN_ONCE: 50,  # One-time commands
            OperationType.RUN: 40,  # Regular commands
            OperationType.APPEND: 30,  # Text modifications
            OperationType.PREPEND: 30,  # Text modifications
            OperationType.BREW_INSTALL: 20,  # Package management
            OperationType.APT_INSTALL: 20,  # Package management
        }

        base_priority = priority_map.get(step.op, 10)

        # Boost priority for variant-specific operations
        if hasattr(step, "variants") and step.variants and "all" not in step.variants:
            base_priority += 10

        return base_priority


class SelectiveOperationFilter:
    """
    Allows users to selectively choose which operations to execute.

    Provides interactive filtering and selection of operations based on
    various criteria including operation type, impact level, and paths.
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the selective operation filter.

        Args:
            console: Rich console for output (creates default if None)
        """
        self.console = console or Console()

    def filter_operations(
        self, steps: List[StepConfig], impact_reports: Optional[List[Any]] = None
    ) -> List[int]:
        """
        Interactively filter operations for execution.

        Args:
            steps: List of step configurations
            impact_reports: Optional impact analysis reports

        Returns:
            List of indices of operations to execute
        """
        if not steps:
            return []

        self._show_operations_overview(steps, impact_reports)

        # Get filtering preferences
        filter_mode = self._get_filter_mode()

        if filter_mode == "all":
            return list(range(len(steps)))
        elif filter_mode == "none":
            return []
        elif filter_mode == "selective":
            return self._interactive_selection(steps, impact_reports)
        elif filter_mode == "by_type":
            return self._filter_by_operation_type(steps)
        elif filter_mode == "by_impact":
            return self._filter_by_impact_level(steps, impact_reports)
        else:
            return list(range(len(steps)))

    def _show_operations_overview(
        self, steps: List[StepConfig], impact_reports: Optional[List[Any]] = None
    ) -> None:
        """Show an overview of all operations."""
        self.console.print(f"\n[bold blue]Operations Overview ({len(steps)} total)[/bold blue]")

        overview_table = Table(show_header=True, header_style="bold magenta")
        overview_table.add_column("#", style="dim")
        overview_table.add_column("Operation", style="cyan")
        overview_table.add_column("Source", overflow="ellipsis", max_width=25)
        overview_table.add_column("Destination", overflow="ellipsis", max_width=25)
        overview_table.add_column("Impact", style="bold")

        for i, step in enumerate(steps):
            impact_level = "UNKNOWN"
            if impact_reports and i < len(impact_reports):
                impact_level = impact_reports[i].overall_level.value.upper()

            overview_table.add_row(
                str(i + 1), step.op.value, step.src or "-", step.dst or "-", impact_level
            )

        self.console.print(overview_table)

    def _get_filter_mode(self) -> str:
        """Get the filtering mode from the user."""
        modes = {
            "all": "Execute all operations",
            "none": "Skip all operations",
            "selective": "Choose operations individually",
            "by_type": "Filter by operation type",
            "by_impact": "Filter by impact level",
        }

        self.console.print("\n[bold]Selection modes:[/bold]")
        for key, description in modes.items():
            self.console.print(f"  [bold cyan]{key}[/bold cyan]: {description}")

        return Prompt.ask(
            "\n[bold green]How would you like to select operations?[/bold green]",
            choices=list(modes.keys()),
            default="all",
        )

    def _interactive_selection(
        self, steps: List[StepConfig], impact_reports: Optional[List[Any]] = None
    ) -> List[int]:
        """Allow user to interactively select specific operations."""
        selected_indices = []

        for i, step in enumerate(steps):
            # Show operation details
            self.console.print(f"\n[bold]Operation {i + 1}/{len(steps)}:[/bold]")
            self.console.print(f"  Type: [cyan]{step.op.value}[/cyan]")
            if step.src:
                self.console.print(f"  Source: {step.src}")
            if step.dst:
                self.console.print(f"  Destination: {step.dst}")

            # Show impact if available
            if impact_reports and i < len(impact_reports):
                report = impact_reports[i]
                impact_color = {
                    "LOW": "green",
                    "MEDIUM": "yellow",
                    "HIGH": "red",
                    "CRITICAL": "bold red",
                }.get(report.overall_level.value.upper(), "white")

                self.console.print(
                    f"  Impact: [{impact_color}]{report.overall_level.value.upper()}[/{impact_color}]"
                )

                if report.warnings:
                    self.console.print("  Warnings:")
                    for warning in report.warnings[:3]:  # Show first 3 warnings
                        self.console.print(f"    ⚠️  {warning}")

            # Ask user
            if Confirm.ask("[bold green]Execute this operation?[/bold green]", default=True):
                selected_indices.append(i)

        return selected_indices

    def _filter_by_operation_type(self, steps: List[StepConfig]) -> List[int]:
        """Filter operations by type."""
        # Get available operation types
        available_types = list(set(step.op.value for step in steps))
        available_types.sort()

        self.console.print("\n[bold]Available operation types:[/bold]")
        for i, op_type in enumerate(available_types, 1):
            count = sum(1 for step in steps if step.op.value == op_type)
            self.console.print(f"  [bold cyan]{i}[/bold cyan]: {op_type} ({count} operations)")

        # Allow multiple selection
        choices = Prompt.ask(
            "\n[bold green]Select operation types (comma-separated numbers)[/bold green]",
            default="1",
        )

        try:
            selected_numbers = [int(x.strip()) for x in choices.split(",")]
            selected_types = [
                available_types[i - 1] for i in selected_numbers if 1 <= i <= len(available_types)
            ]

            return [i for i, step in enumerate(steps) if step.op.value in selected_types]
        except (ValueError, IndexError):
            self.console.print("[red]Invalid selection, executing all operations[/red]")
            return list(range(len(steps)))

    def _filter_by_impact_level(
        self, steps: List[StepConfig], impact_reports: Optional[List[Any]] = None
    ) -> List[int]:
        """Filter operations by impact level."""
        if not impact_reports:
            self.console.print(
                "[yellow]No impact reports available, cannot filter by impact level[/yellow]"
            )
            return list(range(len(steps)))

        # Get available impact levels

        available_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        self.console.print("\n[bold]Filter by impact level:[/bold]")
        for i, level in enumerate(available_levels, 1):
            count = sum(
                1 for report in impact_reports if report.overall_level.value.upper() == level
            )
            color = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red", "CRITICAL": "bold red"}.get(
                level, "white"
            )

            self.console.print(
                f"  [bold cyan]{i}[/bold cyan]: [{color}]{level}[/{color}] ({count} operations)"
            )

        # Allow multiple selection
        choices = Prompt.ask(
            "\n[bold green]Select impact levels to include (comma-separated numbers)[/bold green]",
            default="1,2",  # Default to LOW and MEDIUM
        )

        try:
            selected_numbers = [int(x.strip()) for x in choices.split(",")]
            selected_levels = [
                available_levels[i - 1] for i in selected_numbers if 1 <= i <= len(available_levels)
            ]

            return [
                i
                for i, report in enumerate(impact_reports)
                if report.overall_level.value.upper() in selected_levels
            ]
        except (ValueError, IndexError):
            self.console.print("[red]Invalid selection, executing all operations[/red]")
            return list(range(len(steps)))
