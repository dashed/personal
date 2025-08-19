"""
Interactive confirmation system for the Dotfiles Management System.

This module provides user confirmation prompts for operations based on impact analysis,
with support for batch confirmations and different confirmation modes.

Phase 4: Safety Features & Confirmation implementation.
"""

import sys
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.columns import Columns
from rich.rule import Rule

from dotfiles_sync.models import SafetyConfig
from .impact import ImpactReport, ImpactLevel, ImpactType, ImpactDetail


class ConfirmationMode(str, Enum):
    """Different modes for confirmation prompts."""
    
    ALWAYS = "always"           # Always prompt for confirmation
    DESTRUCTIVE_ONLY = "destructive_only"  # Only prompt for destructive operations
    INTERACTIVE = "interactive" # Smart prompting based on operation analysis
    NEVER = "never"            # Never prompt (dangerous!)


class ConfirmationChoice(str, Enum):
    """User choices for operation confirmation."""
    
    YES = "yes"           # Proceed with this operation
    NO = "no"            # Skip this operation
    ALL = "all"          # Proceed with all remaining operations
    NONE = "none"        # Skip all remaining operations
    QUIT = "quit"        # Abort entire process
    DETAILS = "details"  # Show more details about the operation


class ConfirmationResult(BaseModel):
    """Result of a confirmation prompt."""
    
    choice: ConfirmationChoice
    apply_to_all: bool = Field(False, description="Whether to apply choice to all similar operations")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional confirmation data")


class ConfirmationPrompt:
    """
    Interactive confirmation system for operations.
    
    Provides rich, interactive prompts for user confirmation of operations
    based on impact analysis results.
    """
    
    def __init__(
        self, 
        console: Optional[Console] = None,
        mode: ConfirmationMode = ConfirmationMode.DESTRUCTIVE_ONLY,
        safety_config: Optional[SafetyConfig] = None
    ):
        """
        Initialize the confirmation prompt system.
        
        Args:
            console: Rich console for output (creates default if None)
            mode: Confirmation mode to use
            safety_config: Safety configuration settings
        """
        self.console = console or Console()
        self.mode = mode
        self.safety_config = safety_config or SafetyConfig.model_construct()
        
        # Track user preferences during session
        self._batch_choices: Dict[str, ConfirmationChoice] = {}
        self._skip_similar = False
        self._approve_all = False
    
    def should_confirm(self, report: ImpactReport) -> bool:
        """
        Determine if an operation should prompt for confirmation.
        
        Args:
            report: Impact analysis report
            
        Returns:
            True if confirmation is needed
        """
        # Check if confirmation is disabled globally
        if not self.safety_config.require_confirmation:
            return False
        
        # Check confirmation mode
        if self.mode == ConfirmationMode.NEVER:
            return False
        elif self.mode == ConfirmationMode.ALWAYS:
            return True
        elif self.mode == ConfirmationMode.DESTRUCTIVE_ONLY:
            return report.is_destructive
        elif self.mode == ConfirmationMode.INTERACTIVE:
            # Smart confirmation based on analysis
            return (
                report.is_destructive or 
                report.has_conflicts or 
                len(report.errors) > 0 or
                report.overall_level in [ImpactLevel.HIGH, ImpactLevel.CRITICAL]
            )
        
        return False
    
    def confirm_operation(
        self, 
        report: ImpactReport, 
        operation_number: int = 1,
        total_operations: int = 1
    ) -> ConfirmationResult:
        """
        Get user confirmation for an operation.
        
        Args:
            report: Impact analysis report
            operation_number: Current operation number (1-based)
            total_operations: Total number of operations
            
        Returns:
            User's confirmation choice
        """
        # Check if we should skip confirmation
        if not self.should_confirm(report):
            return ConfirmationResult(choice=ConfirmationChoice.YES)
        
        # Check for batch choices
        if self._approve_all:
            return ConfirmationResult(choice=ConfirmationChoice.YES)
        
        if self._skip_similar:
            return ConfirmationResult(choice=ConfirmationChoice.NO)
        
        # Check for operation-specific batch choices
        batch_key = self._get_batch_key(report)
        if batch_key in self._batch_choices:
            return ConfirmationResult(choice=self._batch_choices[batch_key])
        
        # Show the confirmation prompt
        return self._show_confirmation_prompt(report, operation_number, total_operations)
    
    def _show_confirmation_prompt(
        self, 
        report: ImpactReport,
        operation_number: int,
        total_operations: int
    ) -> ConfirmationResult:
        """Display interactive confirmation prompt."""
        self.console.print()
        self.console.rule(f"[bold blue]Operation {operation_number}/{total_operations}")
        
        # Show operation summary
        self._show_operation_summary(report)
        
        # Show impact analysis
        self._show_impact_analysis(report)
        
        # Show warnings and errors
        if report.warnings or report.errors:
            self._show_warnings_and_errors(report)
        
        # Show recommendations
        if report.recommendations:
            self._show_recommendations(report)
        
        # Get user choice
        return self._get_user_choice(report, operation_number, total_operations)
    
    def _show_operation_summary(self, report: ImpactReport) -> None:
        """Display a summary of the operation."""
        summary_table = Table(show_header=False, box=None, padding=(0, 1))
        summary_table.add_column("Key", style="bold")
        summary_table.add_column("Value")
        
        summary_table.add_row("Operation", report.operation_type.upper())
        
        if report.src_path:
            summary_table.add_row("Source", report.src_path)
        
        if report.dst_path:
            summary_table.add_row("Destination", report.dst_path)
        
        # Impact level with color coding
        level_colors = {
            ImpactLevel.LOW: "green",
            ImpactLevel.MEDIUM: "yellow",
            ImpactLevel.HIGH: "red",
            ImpactLevel.CRITICAL: "bold red"
        }
        level_color = level_colors.get(report.overall_level, "white")
        summary_table.add_row("Impact Level", f"[{level_color}]{report.overall_level.value.upper()}[/{level_color}]")
        
        self.console.print(Panel(summary_table, title="Operation Summary", border_style="blue"))
    
    def _show_impact_analysis(self, report: ImpactReport) -> None:
        """Display detailed impact analysis."""
        if not report.impacts:
            return
        
        impact_table = Table(show_header=True, header_style="bold magenta")
        impact_table.add_column("Type", style="cyan")
        impact_table.add_column("Level", style="bold")
        impact_table.add_column("Path", style="blue") 
        impact_table.add_column("Description")
        
        # Sort impacts by severity
        level_order = {
            ImpactLevel.CRITICAL: 0,
            ImpactLevel.HIGH: 1,
            ImpactLevel.MEDIUM: 2,
            ImpactLevel.LOW: 3
        }
        sorted_impacts = sorted(report.impacts, key=lambda x: level_order.get(x.level, 4))
        
        for impact in sorted_impacts:
            level_colors = {
                ImpactLevel.LOW: "green",
                ImpactLevel.MEDIUM: "yellow", 
                ImpactLevel.HIGH: "red",
                ImpactLevel.CRITICAL: "bold red"
            }
            level_color = level_colors.get(impact.level, "white")
            level_text = f"[{level_color}]{impact.level.value.upper()}[/{level_color}]"
            
            path_text = impact.path if impact.path else ""
            impact_table.add_row(
                impact.type.value.replace("_", " ").title(),
                level_text,
                path_text,
                impact.description
            )
        
        self.console.print(Panel(impact_table, title="Impact Analysis", border_style="magenta"))
    
    def _show_warnings_and_errors(self, report: ImpactReport) -> None:
        """Display warnings and errors."""
        if report.errors:
            error_text = Text()
            for error in report.errors:
                error_text.append("❌ ", style="bold red")
                error_text.append(f"{error}\n", style="red")
            
            self.console.print(Panel(error_text, title="Errors", border_style="red"))
        
        if report.warnings:
            warning_text = Text()
            for warning in report.warnings:
                warning_text.append("⚠️  ", style="bold yellow")
                warning_text.append(f"{warning}\n", style="yellow")
            
            self.console.print(Panel(warning_text, title="Warnings", border_style="yellow"))
    
    def _show_recommendations(self, report: ImpactReport) -> None:
        """Display safety recommendations."""
        rec_text = Text()
        for rec in report.recommendations:
            rec_text.append("💡 ", style="bold blue")
            rec_text.append(f"{rec}\n", style="blue")
        
        self.console.print(Panel(rec_text, title="Recommendations", border_style="blue"))
    
    def _get_user_choice(
        self, 
        report: ImpactReport,
        operation_number: int,
        total_operations: int
    ) -> ConfirmationResult:
        """Get the user's choice for this operation."""
        choices = {
            "y": "Yes - proceed with this operation",
            "n": "No - skip this operation",
            "d": "Details - show more information"
        }
        
        if total_operations > 1:
            choices.update({
                "a": "All - proceed with all remaining operations",
                "s": "Skip - skip all remaining operations", 
                "q": "Quit - abort the entire process"
            })
        
        # Display choices
        self.console.print("\n[bold]Choices:[/bold]")
        for key, description in choices.items():
            self.console.print(f"  [bold cyan]{key}[/bold cyan]: {description}")
        
        while True:
            choice = Prompt.ask(
                "\n[bold green]What would you like to do?[/bold green]",
                choices=list(choices.keys()),
                default="n" if report.errors else "y"
            ).lower()
            
            if choice == "y":
                return ConfirmationResult(choice=ConfirmationChoice.YES)
            elif choice == "n":
                return ConfirmationResult(choice=ConfirmationChoice.NO)
            elif choice == "a":
                self._approve_all = True
                return ConfirmationResult(choice=ConfirmationChoice.ALL, apply_to_all=True)
            elif choice == "s":
                self._skip_similar = True
                return ConfirmationResult(choice=ConfirmationChoice.NONE, apply_to_all=True)
            elif choice == "q":
                return ConfirmationResult(choice=ConfirmationChoice.QUIT)
            elif choice == "d":
                self._show_detailed_analysis(report)
                continue
    
    def _show_detailed_analysis(self, report: ImpactReport) -> None:
        """Show detailed analysis information."""
        self.console.print("\n[bold magenta]Detailed Analysis:[/bold magenta]")
        
        # Show dependencies if any
        for impact in report.impacts:
            if impact.dependencies:
                self.console.print(f"\n[bold]Dependencies for {impact.path}:[/bold]")
                for dep in impact.dependencies:
                    self.console.print(f"  • {dep}")
            
            if impact.conflicts:
                self.console.print(f"\n[bold red]Conflicts for {impact.path}:[/bold red]")
                for conflict in impact.conflicts:
                    self.console.print(f"  ⚠️  {conflict}", style="red")
        
        # Show metadata
        for impact in report.impacts:
            if impact.metadata:
                self.console.print(f"\n[bold]Additional information for {impact.path}:[/bold]")
                for key, value in impact.metadata.items():
                    self.console.print(f"  {key}: {value}")
    
    def _get_batch_key(self, report: ImpactReport) -> str:
        """Generate a key for batch confirmation decisions."""
        return f"{report.operation_type}_{report.overall_level.value}"
    
    def confirm_batch_operations(
        self, 
        reports: List[ImpactReport]
    ) -> Dict[int, ConfirmationResult]:
        """
        Confirm a batch of operations with smart grouping.
        
        Args:
            reports: List of impact analysis reports
            
        Returns:
            Dictionary mapping operation index to confirmation result
        """
        results: Dict[int, ConfirmationResult] = {}
        
        # Group operations by similarity
        groups = self._group_similar_operations(reports)
        
        self.console.print(f"\n[bold blue]Analyzing {len(reports)} operations...[/bold blue]")
        
        for group_key, indices in groups.items():
            if len(indices) > 1:
                # Show group summary and ask for batch confirmation
                result = self._confirm_operation_group(
                    [reports[i] for i in indices], 
                    group_key
                )
                
                for idx in indices:
                    results[idx] = result
            else:
                # Single operation - use individual confirmation
                idx = indices[0]
                results[idx] = self.confirm_operation(
                    reports[idx], 
                    idx + 1, 
                    len(reports)
                )
                
                # Check if user wants to quit
                if results[idx].choice == ConfirmationChoice.QUIT:
                    break
        
        return results
    
    def _group_similar_operations(self, reports: List[ImpactReport]) -> Dict[str, List[int]]:
        """Group similar operations for batch confirmation."""
        groups: Dict[str, List[int]] = {}
        
        for i, report in enumerate(reports):
            # Group by operation type and impact level
            key = f"{report.operation_type}_{report.overall_level.value}"
            
            # Also consider if operations are destructive
            if report.is_destructive:
                key += "_destructive"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(i)
        
        return groups
    
    def _confirm_operation_group(
        self, 
        reports: List[ImpactReport],
        group_key: str
    ) -> ConfirmationResult:
        """Confirm a group of similar operations."""
        self.console.print(f"\n[bold magenta]Batch Operations: {group_key}[/bold magenta]")
        self.console.print(f"Found {len(reports)} similar operations:")
        
        # Show summary table
        summary_table = Table(show_header=True)
        summary_table.add_column("#", style="dim")
        summary_table.add_column("Operation")
        summary_table.add_column("Source", overflow="ellipsis", max_width=30)
        summary_table.add_column("Destination", overflow="ellipsis", max_width=30)
        summary_table.add_column("Impact", style="bold")
        
        for i, report in enumerate(reports, 1):
            level_colors = {
                ImpactLevel.LOW: "green",
                ImpactLevel.MEDIUM: "yellow",
                ImpactLevel.HIGH: "red", 
                ImpactLevel.CRITICAL: "bold red"
            }
            level_color = level_colors.get(report.overall_level, "white")
            
            summary_table.add_row(
                str(i),
                report.operation_type,
                report.src_path or "-",
                report.dst_path or "-",
                f"[{level_color}]{report.overall_level.value.upper()}[/{level_color}]"
            )
        
        self.console.print(summary_table)
        
        # Get batch decision
        batch_choice = Confirm.ask(
            f"\n[bold green]Apply to all {len(reports)} operations?[/bold green]",
            default=not any(r.is_destructive for r in reports)
        )
        
        if batch_choice:
            return ConfirmationResult(choice=ConfirmationChoice.YES, apply_to_all=True)
        else:
            return ConfirmationResult(choice=ConfirmationChoice.NO, apply_to_all=True)
    
    def reset_session_choices(self) -> None:
        """Reset all session-based confirmation choices."""
        self._batch_choices.clear()
        self._skip_similar = False
        self._approve_all = False


class SafetyConfirmationManager:
    """
    High-level manager for safety confirmations.
    
    Integrates impact analysis with confirmation prompts to provide
    a complete safety confirmation system.
    """
    
    def __init__(
        self,
        safety_config: Optional[SafetyConfig] = None,
        console: Optional[Console] = None
    ):
        """
        Initialize the safety confirmation manager.
        
        Args:
            safety_config: Safety configuration settings
            console: Rich console for output
        """
        self.safety_config = safety_config or SafetyConfig.model_construct()
        self.console = console or Console()
        
        # Initialize confirmation mode based on safety config
        if not self.safety_config.require_confirmation:
            mode = ConfirmationMode.NEVER
        else:
            mode = ConfirmationMode.DESTRUCTIVE_ONLY
        
        self.confirmation_prompt = ConfirmationPrompt(
            console=self.console,
            mode=mode,
            safety_config=self.safety_config
        )
    
    def confirm_operations(
        self, 
        reports: List[ImpactReport]
    ) -> Tuple[List[int], List[int]]:
        """
        Confirm a list of operations and return approved/rejected indices.
        
        Args:
            reports: List of impact analysis reports
            
        Returns:
            Tuple of (approved_indices, rejected_indices)
        """
        if not reports:
            return [], []
        
        # Show overall summary
        self._show_operations_summary(reports)
        
        # Get confirmations
        confirmations = self.confirmation_prompt.confirm_batch_operations(reports)
        
        approved_indices = []
        rejected_indices = []
        
        for i, result in confirmations.items():
            if result.choice in [ConfirmationChoice.YES, ConfirmationChoice.ALL]:
                approved_indices.append(i)
            elif result.choice == ConfirmationChoice.QUIT:
                # Quit early - reject all remaining
                rejected_indices.extend(range(i, len(reports)))
                break
            else:
                rejected_indices.append(i)
        
        return approved_indices, rejected_indices
    
    def _show_operations_summary(self, reports: List[ImpactReport]) -> None:
        """Show a summary of all operations."""
        self.console.print(f"\n[bold blue]Safety Analysis Summary[/bold blue]")
        
        # Count by impact level
        level_counts = {}
        for report in reports:
            level = report.overall_level
            level_counts[level] = level_counts.get(level, 0) + 1
        
        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Level", style="bold")
        summary_table.add_column("Count")
        summary_table.add_column("Description")
        
        level_info = {
            ImpactLevel.LOW: ("green", "Safe operations"),
            ImpactLevel.MEDIUM: ("yellow", "Moderate impact operations"),
            ImpactLevel.HIGH: ("red", "Destructive operations"), 
            ImpactLevel.CRITICAL: ("bold red", "Critical system operations")
        }
        
        for level, count in level_counts.items():
            if count > 0:
                color, desc = level_info.get(level, ("white", "Unknown"))
                summary_table.add_row(
                    f"[{color}]{level.value.upper()}[/{color}]",
                    str(count),
                    desc
                )
        
        self.console.print(summary_table)
        
        # Show warnings for destructive operations
        destructive_count = sum(1 for r in reports if r.is_destructive)
        if destructive_count > 0:
            self.console.print(f"\n⚠️  [bold yellow]{destructive_count} operations require confirmation[/bold yellow]")
        
        conflicts_count = sum(1 for r in reports if r.has_conflicts)
        if conflicts_count > 0:
            self.console.print(f"❌ [bold red]{conflicts_count} operations have conflicts[/bold red]")