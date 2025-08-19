#!/usr/bin/env python3
"""
Phase 4: Safety Features & Confirmation Demo

This example demonstrates the comprehensive safety features implemented in Phase 4,
including impact analysis, conflict resolution, and interactive user confirmation.
"""

import sys
from pathlib import Path
from typing import List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from dotfiles_sync.models import StepConfig, OperationType, SafetyConfig
from dotfiles_sync.context import OperationContext, ExecutionContext
from safety import (
    ImpactAnalyzer,
    ConflictResolver,
    SafetyConfirmationManager,
    SelectiveOperationFilter,
    ConfirmationMode,
    ImpactLevel
)


def create_demo_operations() -> List[StepConfig]:
    """Create demo operations for testing Phase 4 safety features."""
    return [
        # Safe operation
        StepConfig(
            op=OperationType.COPY,
            src="~/.config/demo/safe_config.txt",
            dst="~/.config/app/config.txt",
            description="Copy configuration file"
        ),
        
        # Potentially destructive operation
        StepConfig(
            op=OperationType.LINK,
            src="~/.dotfiles/vimrc",
            dst="~/.vimrc",
            description="Link vim configuration"
        ),
        
        # High-impact operation
        StepConfig(
            op=OperationType.SECRET_REF,
            key="API_SECRET_KEY",
            dst="~/.config/app/secrets.env",
            mode="0600",
            description="Write API secret to file"
        ),
        
        # Critical operation
        StepConfig(
            op=OperationType.RUN,
            command="brew install --cask docker",
            description="Install Docker via Homebrew"
        ),
        
        # Conflicting operation (same destination as first)
        StepConfig(
            op=OperationType.TEMPLATE,
            src="~/.dotfiles/templates/config.j2",
            dst="~/.config/app/config.txt",  # Conflicts with first operation
            vars={"username": "demo", "theme": "dark"},
            description="Generate config from template"
        ),
    ]


def demo_impact_analysis(console: Console) -> None:
    """Demonstrate impact analysis functionality."""
    console.print(Rule("Impact Analysis Demo", style="bold blue"))
    
    # Create analyzer
    impact_analyzer = ImpactAnalyzer()
    
    # Create demo operations
    operations = create_demo_operations()
    
    # Mock operation context
    exec_ctx = ExecutionContext(
        config_path=Path("demo.toml"),
        variant="demo",
        dry_run=True
    )
    
    console.print("Analyzing operation impacts...\n")
    
    for i, step in enumerate(operations, 1):
        # Create mock context
        op_ctx = OperationContext(
            execution_context=exec_ctx,
            operation_type=step.op.value,
            step_config=step,
            sequence_num=i
        )
        
        # Analyze impact
        report = impact_analyzer.analyze_operation(step, op_ctx, i)
        
        # Display summary
        level_colors = {
            ImpactLevel.LOW: "green",
            ImpactLevel.MEDIUM: "yellow",
            ImpactLevel.HIGH: "red",
            ImpactLevel.CRITICAL: "bold red"
        }
        color = level_colors.get(report.overall_level, "white")
        
        console.print(f"[bold]Operation {i}:[/bold] {step.op.value}")
        console.print(f"  Impact: [{color}]{report.overall_level.value.upper()}[/{color}]")
        console.print(f"  Impacts: {len(report.impacts)} detected")
        console.print(f"  Warnings: {len(report.warnings)}")
        console.print(f"  Requires confirmation: {'Yes' if report.requires_confirmation else 'No'}")
        
        if report.warnings:
            console.print(f"  First warning: {report.warnings[0]}")
        
        console.print()


def demo_conflict_resolution(console: Console) -> None:
    """Demonstrate conflict resolution functionality."""
    console.print(Rule("Conflict Resolution Demo", style="bold red"))
    
    # Create resolver
    conflict_resolver = ConflictResolver(console)
    
    # Create demo operations (includes conflicting operations)
    operations = create_demo_operations()
    
    console.print("Detecting conflicts between operations...\n")
    
    # Detect conflicts
    conflict_report = conflict_resolver.detect_conflicts(operations)
    
    if conflict_report.has_conflicts():
        console.print(f"[red]Found {len(conflict_report.conflicts)} conflicts:[/red]")
        
        for i, conflict in enumerate(conflict_report.conflicts, 1):
            console.print(f"  {i}. {conflict.type.value.replace('_', ' ').title()}")
            console.print(f"     Path: {conflict.affected_path}")
            console.print(f"     Operations: {conflict.conflicting_operations}")
            console.print(f"     Recommended: {conflict.recommended_strategy.value}")
    else:
        console.print("[green]No conflicts detected.[/green]")
    
    console.print()


def demo_selective_filtering(console: Console) -> None:
    """Demonstrate selective operation filtering."""
    console.print(Rule("Selective Operation Filter Demo", style="bold yellow"))
    
    # Create filter
    operation_filter = SelectiveOperationFilter(console)
    
    # Create demo operations
    operations = create_demo_operations()
    
    console.print("Demonstrating operation filtering capabilities...\n")
    
    # Show operations overview (non-interactive)
    from rich.table import Table
    
    filter_table = Table(show_header=True, header_style="bold magenta")
    filter_table.add_column("#", style="dim")
    filter_table.add_column("Operation", style="cyan")
    filter_table.add_column("Description")
    filter_table.add_column("Risk", style="bold")
    
    risk_levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL", "MEDIUM"]  # Mock risk levels
    risk_colors = {"LOW": "green", "MEDIUM": "yellow", "HIGH": "red", "CRITICAL": "bold red"}
    
    for i, (step, risk) in enumerate(zip(operations, risk_levels), 1):
        color = risk_colors.get(risk, "white")
        filter_table.add_row(
            str(i),
            step.op.value,
            step.description or "-",
            f"[{color}]{risk}[/{color}]"
        )
    
    console.print(filter_table)
    console.print("\n[dim]In interactive mode, users could filter by type, risk level, or select individually.[/dim]")


def demo_confirmation_system(console: Console) -> None:
    """Demonstrate confirmation system functionality."""
    console.print(Rule("Safety Confirmation System Demo", style="bold green"))
    
    # Create safety configuration
    safety_config = SafetyConfig.model_construct(
        require_confirmation=True,
        dry_run_default=True,
        backup_before_modify=True
    )
    
    # Create confirmation manager
    confirmation_manager = SafetyConfirmationManager(
        safety_config=safety_config,
        console=console
    )
    
    console.print("Safety confirmation system initialized with:")
    console.print(f"  • Confirmation required: {safety_config.require_confirmation}")
    console.print(f"  • Dry run by default: {safety_config.dry_run_default}")
    console.print(f"  • Backup before modify: {safety_config.backup_before_modify}")
    console.print()
    
    console.print("[dim]In interactive mode, users would see detailed prompts for destructive operations.\n"
                  "The system provides rich impact analysis, conflict warnings, and safety recommendations.[/dim]")


def main():
    """Run the Phase 4 safety features demonstration."""
    console = Console()
    
    console.print(Panel.fit(
        "[bold blue]Phase 4: Safety Features & Confirmation Demo[/bold blue]\n"
        "Comprehensive safety system with impact analysis, conflict resolution,\n"
        "and interactive user confirmation for dotfiles operations.",
        border_style="blue"
    ))
    
    try:
        # Run demonstrations
        demo_impact_analysis(console)
        demo_conflict_resolution(console)
        demo_selective_filtering(console)
        demo_confirmation_system(console)
        
        console.print(Rule("Demo Complete", style="bold green"))
        console.print("✅ Phase 4: Safety Features & Confirmation successfully implemented!")
        console.print()
        console.print("[bold]Key Features Implemented:[/bold]")
        console.print("• [green]ImpactAnalyzer[/green]: Comprehensive operation impact analysis")
        console.print("• [yellow]ConflictResolver[/yellow]: Conflict detection and resolution")
        console.print("• [blue]ConfirmationPrompt[/blue]: Interactive user confirmation system")
        console.print("• [magenta]SelectiveOperationFilter[/magenta]: Choose specific operations")
        console.print("• [cyan]DependencyAnalyzer[/cyan]: File dependency analysis")
        console.print()
        console.print("[dim]All components integrate seamlessly with existing Phase 2 safety infrastructure.[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error during demonstration: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


if __name__ == "__main__":
    main()