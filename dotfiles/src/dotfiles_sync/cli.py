"""
CLI interface for the Dotfiles Management System.

This module provides the command-line interface using Click framework.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from dotfiles_sync import __version__
from dotfiles_sync.config import ConfigLoader, ConfigValidationError
from dotfiles_sync.context import ExecutionContext
from dotfiles_sync.database import StateDatabase
from dotfiles_sync.config_drift import ConfigDriftDetector, ConfigDriftType, ConfigDriftSummary
from dotfiles_sync.cleanup import OrphanedOperationCleaner

sys.path.insert(0, str(Path(__file__).parent.parent))
from verbs import OperationExecutor

console = Console()


def setup_logging(level: str = "INFO") -> None:
    """Configure logging with Rich handler for better formatting."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def _display_drift_table(drift_summary: ConfigDriftSummary, detailed: bool = False) -> None:
    """Display configuration drift in a formatted table."""
    from rich.table import Table
    from rich.panel import Panel

    # Create header panel
    header_text = "[bold]Configuration Drift Report[/bold]\n"
    header_text += f"Variant: {drift_summary.checked_variant}\n"
    header_text += f"Total Drift: {drift_summary.total_drift} operations"

    console.print(Panel(header_text, title="Drift Analysis", border_style="blue"))

    # Display orphaned operations
    if drift_summary.orphaned_operations:
        console.print(
            "\n[bold yellow]⚠ ORPHANED OPERATIONS[/bold yellow] (in database but not in config):"
        )
        table = Table(show_header=True, header_style="bold")
        table.add_column("Path", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Impact", style="yellow")

        for op in drift_summary.orphaned_operations:
            table.add_row(op.dst_path, op.operation_type, op.impact)

        console.print(table)

        if detailed:
            for op in drift_summary.orphaned_operations:
                console.print(f"\n  Details for {op.dst_path}:")
                console.print(f"    Applied config: {op.applied_config}")

    # Display modified operations
    if drift_summary.modified_operations:
        console.print("\n[bold blue]🔄 MODIFIED OPERATIONS[/bold blue] (configuration changed):")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Path", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Change", style="blue")

        for op in drift_summary.modified_operations:
            table.add_row(op.dst_path, op.operation_type, op.impact)

        console.print(table)

        if detailed:
            for op in drift_summary.modified_operations:
                console.print(f"\n  Details for {op.dst_path}:")
                console.print(f"    Old config: {op.applied_config}")
                console.print(f"    New config: {op.current_config}")

    # Display new operations
    if drift_summary.new_operations:
        console.print(
            "\n[bold green]✨ NEW OPERATIONS[/bold green] (in config but not yet applied):"
        )
        table = Table(show_header=True, header_style="bold")
        table.add_column("Path", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Action", style="green")

        for op in drift_summary.new_operations:
            table.add_row(op.dst_path, op.operation_type, op.impact)

        console.print(table)

        if detailed:
            for op in drift_summary.new_operations:
                console.print(f"\n  Details for {op.dst_path}:")
                console.print(f"    Config: {op.current_config}")

    # Display recommendation
    if drift_summary.recommended_action:
        console.print(f"\n[bold]Recommendation:[/bold] {drift_summary.recommended_action}")


def _display_drift_summary(drift_summary: ConfigDriftSummary) -> None:
    """Display a brief summary of configuration drift."""
    if drift_summary.total_drift == 0:
        console.print("[green]✓[/green] No configuration drift detected")
    else:
        console.print(
            f"[yellow]⚠[/yellow] Configuration drift detected: {drift_summary.total_drift} operations"
        )
        if drift_summary.orphaned_operations:
            console.print(f"  Orphaned: {len(drift_summary.orphaned_operations)}")
        if drift_summary.modified_operations:
            console.print(f"  Modified: {len(drift_summary.modified_operations)}")
        if drift_summary.new_operations:
            console.print(f"  New: {len(drift_summary.new_operations)}")
        console.print("\n  Run 'dotfiles-sync drift-check --detailed' for full report")


def _display_cleanup_plan(operations: list, remove_files: bool = False) -> None:
    """Display what cleanup operations would be performed."""
    from rich.table import Table
    from rich.panel import Panel

    if not operations:
        console.print(Panel("[green]No operations need cleanup[/green]", title="Cleanup Plan"))
        return

    # Create cleanup plan table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Path", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Action", style="yellow")
    table.add_column("Files", style="red" if remove_files else "dim")

    for op in operations:
        # Determine action based on drift type
        action = "Remove from DB"
        if op.drift_type == ConfigDriftType.ORPHANED:
            action = "Mark as orphaned"
        elif op.drift_type == ConfigDriftType.MODIFIED:
            action = "Reset state"

        # Check file status
        file_status = "—"
        if remove_files and op.dst_path:
            file_path = Path(op.dst_path).expanduser()
            if file_path.exists():
                if file_path.is_symlink():
                    file_status = "DELETE symlink"
                elif file_path.is_dir():
                    file_status = "DELETE directory"
                else:
                    file_status = "DELETE file"
            else:
                file_status = "File not found"

        table.add_row(op.dst_path, op.operation_type, action, file_status)

    console.print(table)


def _display_reconciliation_plan(
    drift_summary: ConfigDriftSummary, remove_files: bool = False
) -> None:
    """Display the complete reconciliation plan."""
    from rich.panel import Panel

    plan_text = f"[bold]Reconciliation Plan for {drift_summary.total_drift} operations[/bold]\n\n"

    if drift_summary.orphaned_operations:
        plan_text += f"[yellow]Step 1: Clean {len(drift_summary.orphaned_operations)} orphaned operations[/yellow]\n"
        for op in drift_summary.orphaned_operations:
            file_action = ""
            if remove_files:
                file_path = Path(op.dst_path).expanduser() if op.dst_path else None
                if file_path and file_path.exists():
                    file_action = " + DELETE file"
            plan_text += f"  • {op.dst_path} (remove from database{file_action})\n"
        plan_text += "\n"

    if drift_summary.modified_operations or drift_summary.new_operations:
        total_sync = len(drift_summary.modified_operations) + len(drift_summary.new_operations)
        plan_text += f"[blue]Step 2: Sync {total_sync} configuration operations[/blue]\n"

        for op in drift_summary.modified_operations:
            plan_text += f"  • {op.dst_path} (update configuration)\n"

        for op in drift_summary.new_operations:
            plan_text += f"  • {op.dst_path} (apply new operation)\n"

    console.print(Panel(plan_text.strip(), title="Reconciliation Plan", border_style="blue"))


@click.group(invoke_without_command=True)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default="dotfiles.toml",
    help="Path to configuration file",
)
@click.option(
    "--variant",
    "-v",
    type=str,
    default="default",
    help="Configuration variant to use",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=True,
    help="Preview changes without applying them (default: true)",
)
@click.option(
    "--apply",
    is_flag=True,
    default=False,
    help="Actually apply changes (overrides dry-run)",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force operations without confirmation",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Set logging level",
)
@click.version_option(version=__version__, prog_name="dotfiles-sync")
@click.pass_context
def cli(
    ctx: click.Context,
    config: Path,
    variant: str,
    dry_run: bool,
    apply: bool,
    force: bool,
    log_level: str,
) -> None:
    """
    Dotfiles Management System - A declarative, safety-first approach to dotfiles.

    This tool helps you manage your dotfiles with automatic backups, rollback
    capabilities, and cross-platform support.
    """
    setup_logging(log_level)

    # If apply is set, override dry_run
    if apply:
        dry_run = False

    # Create execution context
    ctx.obj = ExecutionContext(
        config_path=config,
        variant=variant,
        dry_run=dry_run,
        force=force,
    )

    # If no command specified, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option("--check-database", is_flag=True, help="Validate against database state")
@click.pass_obj
def validate(ctx: ExecutionContext, check_database: bool) -> None:
    """Validate the configuration file without executing any operations."""
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Validating configuration: {ctx.config_path}")
        loader = ConfigLoader(ctx.config_path)
        config = loader.load()
        loader.validate(config)

        console.print("[green]✓[/green] Configuration is valid!")
        console.print(f"  Package: {config.package.name} v{config.package.version}")
        console.print(f"  Safety: dry_run_default={config.safety.dry_run_default}")
        console.print(f"  Steps: {len(config.step)} operations defined")

        # Check against database if requested
        if check_database:
            console.print("\n[bold]Database Validation[/bold]")
            with StateDatabase() as db:
                detector = ConfigDriftDetector(db)
                drift = detector.detect_drift(config, ctx.variant)

                has_issues = False

                if drift.orphaned_operations:
                    console.print(
                        f"[yellow]⚠[/yellow] {len(drift.orphaned_operations)} orphaned operations found"
                    )
                    has_issues = True

                if drift.modified_operations:
                    console.print(
                        f"[yellow]⚠[/yellow] {len(drift.modified_operations)} modified operations found"
                    )
                    has_issues = True

                if drift.new_operations:
                    console.print(
                        f"[blue]ℹ[/blue] {len(drift.new_operations)} new operations ready to apply"
                    )

                if not has_issues and not drift.new_operations:
                    console.print("[green]✓[/green] Configuration matches database state")

    except ConfigValidationError as e:
        console.print(f"[red]✗[/red] Configuration validation failed: {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        logger.exception("Validation failed")
        sys.exit(1)


@cli.command("drift-check")
@click.option("--detailed", is_flag=True, help="Show detailed drift information")
@click.option(
    "--format", type=click.Choice(["table", "json"]), default="table", help="Output format"
)
@click.pass_obj
def drift_check(ctx: ExecutionContext, detailed: bool, format: str) -> None:
    """Check for configuration drift between TOML and database.

    This command compares the current configuration file with the applied
    state in the database to identify:
    - New operations that need to be applied
    - Modified operations that have changed configuration
    - Orphaned operations that are no longer in the configuration
    """
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        loader = ConfigLoader(ctx.config_path)
        config = loader.load()

        # Detect drift
        with StateDatabase() as db:
            detector = ConfigDriftDetector(db)
            drift_summary = detector.detect_drift(config, ctx.variant)

        # Display results
        if format == "json":
            # Use model_dump_json for proper enum serialization
            console.print(drift_summary.model_dump_json(indent=2))
        else:
            _display_drift_table(drift_summary, detailed)

        # Exit with appropriate code
        if drift_summary.total_drift > 0:
            sys.exit(1)  # Indicate drift exists

    except Exception as e:
        console.print(f"[red]✗[/red] Configuration drift check failed: {e}")
        logger.exception("Drift check failed")
        sys.exit(1)


@cli.command()
@click.option("--orphaned-only", is_flag=True, help="Only clean orphaned operations")
@click.option("--remove-files", is_flag=True, help="Remove files for orphaned operations")
@click.option("--no-backup", is_flag=True, help="Skip backing up files before removal")
@click.option("--preview", is_flag=True, help="Preview cleanup without applying")
@click.option(
    "--paths", multiple=True, help="Clean only specific paths (can be used multiple times)"
)
@click.option(
    "--operations",
    multiple=True,
    help="Clean only specific operation types (can be used multiple times)",
)
@click.option("--before", type=click.DateTime(), help="Clean only operations before this date")
@click.option("--interactive", is_flag=True, help="Interactive mode - confirm each operation")
@click.pass_obj
def clean(
    ctx: ExecutionContext,
    orphaned_only: bool,
    remove_files: bool,
    no_backup: bool,
    preview: bool,
    paths: tuple,
    operations: tuple,
    before: Optional[datetime],
    interactive: bool,
) -> None:
    """Clean up configuration drift in database.

    This command removes orphaned operations from the database and optionally
    removes the associated files from the filesystem. Use --preview to see
    what would be cleaned without making changes.

    Selective cleanup options:
    - --paths: Clean only specific paths (e.g., --paths ~/.zshrc --paths ~/.gitconfig)
    - --operations: Clean only specific operation types (e.g., --operations link --operations copy)
    - --before: Clean operations before a specific date
    - --interactive: Confirm each operation individually
    """
    logger = logging.getLogger(__name__)

    try:
        # Check if enhanced cleanup should be used
        use_enhanced = bool(paths or operations or before or interactive)

        # Load config and detect drift
        loader = ConfigLoader(ctx.config_path)
        config = loader.load()

        with StateDatabase() as db:
            detector = ConfigDriftDetector(db)
            drift = detector.detect_drift(config, ctx.variant)

            # Determine what to clean
            to_clean = []
            if orphaned_only:
                to_clean = drift.orphaned_operations
            else:
                to_clean = drift.orphaned_operations + drift.modified_operations

            if not to_clean:
                console.print("[green]✓[/green] No cleanup needed")
                return

            # Use enhanced cleanup if filters are provided
            if use_enhanced:
                from dotfiles_sync.cleanup_enhanced import (
                    EnhancedOrphanedOperationCleaner,
                    CleanupFilters,
                )

                # Create filters
                filters = CleanupFilters(
                    paths=list(paths) if paths else None,
                    operations=list(operations) if operations else None,
                    before=before,
                    interactive=interactive,
                    variant=ctx.variant,
                )

                # Show what will be cleaned
                console.print("[bold]Enhanced Cleanup Analysis[/bold]")
                console.print(f"  Operations to evaluate: {len(to_clean)}")
                if filters.paths:
                    console.print(f"  Path filters: {', '.join(filters.paths)}")
                if filters.operations:
                    console.print(f"  Operation filters: {', '.join(filters.operations)}")
                if filters.before:
                    console.print(f"  Before date: {filters.before}")
                console.print(f"  Interactive mode: {'Yes' if interactive else 'No'}")
                console.print(f"  Remove files: {'Yes' if remove_files else 'No'}")
                console.print(f"  Backup files: {'No' if no_backup else 'Yes'}")
                console.print()

                if preview:
                    console.print("[yellow]PREVIEW MODE - No changes will be made[/yellow]\n")
                    _display_cleanup_plan(to_clean, remove_files)
                    return

                # Confirm unless forced or dry-run
                if not ctx.force and not interactive:
                    console.print(
                        "[bold yellow]⚠ WARNING:[/bold yellow] This will modify your database and potentially remove files."
                    )
                    console.print("Make sure you have backups before proceeding.\n")
                    if not click.confirm("Proceed with cleanup?"):
                        console.print("[yellow]Cleanup cancelled[/yellow]")
                        return

                # Perform enhanced cleanup
                console.print("[bold]Performing enhanced cleanup...[/bold]\n")
                enhanced_cleaner = EnhancedOrphanedOperationCleaner(db)
                result = enhanced_cleaner.clean_operations_selective(
                    to_clean,
                    filters=filters,
                    remove_files=remove_files,
                    backup=not no_backup,
                    dry_run=ctx.dry_run,
                )

                # Display enhanced results
                if result.success:
                    console.print(
                        f"[green]✓[/green] Successfully cleaned {result.cleaned_count} operations"
                    )
                    if result.orphaned_operations:
                        console.print(
                            f"  Stored for restoration: {len(result.orphaned_operations)} operations"
                        )
                else:
                    console.print(
                        f"[yellow]⚠[/yellow] Cleaned {result.cleaned_count} operations with {result.failed_count} failures"
                    )

                if result.backed_up_files:
                    console.print(f"  Backed up: {len(result.backed_up_files)} files")

                if result.removed_files:
                    console.print(f"  [red]Removed: {len(result.removed_files)} files[/red]")

                if result.errors:
                    console.print(f"\n[red]Errors ({len(result.errors)}):[/red]")
                    for error in result.errors:
                        console.print(f"  • {error}")
                    sys.exit(1)
            else:
                # Use standard cleanup
                # Show what will be cleaned
                console.print("[bold]Cleanup Analysis[/bold]")
                console.print(f"  Operations to clean: {len(to_clean)}")
                console.print(f"  Remove files: {'Yes' if remove_files else 'No'}")
                console.print(f"  Backup files: {'No' if no_backup else 'Yes'}")
                console.print(f"  Orphaned only: {'Yes' if orphaned_only else 'No'}")
                console.print()

                if preview:
                    console.print("[yellow]PREVIEW MODE - No changes will be made[/yellow]\n")
                    _display_cleanup_plan(to_clean, remove_files)
                    return

                # Confirm unless forced or dry-run
                if not ctx.force:
                    console.print(
                        "[bold yellow]⚠ WARNING:[/bold yellow] This will modify your database and potentially remove files."
                    )
                    console.print("Make sure you have backups before proceeding.\n")
                    if not click.confirm("Proceed with cleanup?"):
                        console.print("[yellow]Cleanup cancelled[/yellow]")
                        return

                # Perform cleanup
                console.print("[bold]Performing cleanup...[/bold]\n")
                cleaner = OrphanedOperationCleaner(db)
                result = cleaner.clean_operations(
                    to_clean, remove_files=remove_files, backup=not no_backup, dry_run=ctx.dry_run
                )

                # Display results for standard cleanup
                if result.success:
                    console.print(
                        f"[green]✓[/green] Successfully cleaned {result.cleaned_count} operations"
                    )
                else:
                    console.print(
                        f"[yellow]⚠[/yellow] Cleaned {result.cleaned_count} operations with {result.failed_count} failures"
                    )

                if result.backed_up_files:
                    console.print(f"  Backed up: {len(result.backed_up_files)} files")

                if result.removed_files:
                    console.print(f"  [red]Removed: {len(result.removed_files)} files[/red]")

                if result.errors:
                    console.print(f"\n[red]Errors ({len(result.errors)}):[/red]")
                    for error in result.errors:
                        console.print(f"  • {error}")
                    sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗[/red] Cleanup failed: {e}")
        logger.exception("Cleanup failed")
        sys.exit(1)


@cli.command()
@click.option("--preview", is_flag=True, help="Preview reconciliation plan without applying")
@click.option(
    "--clean-first", is_flag=True, default=True, help="Clean orphaned operations before sync"
)
@click.option("--remove-files", is_flag=True, help="Remove orphaned files during cleanup")
@click.pass_obj
def reconcile(ctx: ExecutionContext, preview: bool, clean_first: bool, remove_files: bool) -> None:
    """Reconcile configuration drift by cleaning and syncing.

    This command performs a complete reconciliation of configuration drift:
    1. Clean orphaned operations (optionally removing files)
    2. Apply new and modified operations through sync

    Use --preview to see the reconciliation plan without making changes.
    """
    logger = logging.getLogger(__name__)

    try:
        console.print("[bold]Configuration Reconciliation[/bold]")

        # Load config
        loader = ConfigLoader(ctx.config_path)
        config = loader.load()

        # Detect drift
        with StateDatabase() as db:
            detector = ConfigDriftDetector(db)
            drift = detector.detect_drift(config, ctx.variant)

            if drift.total_drift == 0:
                console.print(
                    "[green]✓[/green] No reconciliation needed - configuration is in sync"
                )
                return

            # Show reconciliation plan
            console.print("\n[bold]Reconciliation Analysis[/bold]")
            console.print(f"  Orphaned to clean: {len(drift.orphaned_operations)}")
            console.print(f"  Modified to update: {len(drift.modified_operations)}")
            console.print(f"  New to apply: {len(drift.new_operations)}")
            console.print(f"  Remove files: {'Yes' if remove_files else 'No'}")
            console.print(f"  Clean first: {'Yes' if clean_first else 'No'}")
            console.print()

            if preview:
                console.print("[yellow]PREVIEW MODE - No changes will be made[/yellow]\n")
                _display_reconciliation_plan(drift, remove_files)
                return

            # Confirm unless forced
            if not ctx.force:
                console.print(
                    "[bold yellow]⚠ WARNING:[/bold yellow] This will modify your system and database."
                )
                console.print("Orphaned files may be removed if --remove-files is used.\n")
                if not click.confirm("Proceed with reconciliation?"):
                    console.print("[yellow]Reconciliation cancelled[/yellow]")
                    return

            # Step 1: Clean orphaned operations
            cleaned_count = 0
            if clean_first and drift.orphaned_operations:
                console.print("\n[bold]Step 1: Cleaning orphaned operations[/bold]")
                cleaner = OrphanedOperationCleaner(db)
                cleanup_result = cleaner.clean_operations(
                    drift.orphaned_operations,
                    remove_files=remove_files,
                    backup=True,
                    dry_run=ctx.dry_run,
                )
                cleaned_count = cleanup_result.cleaned_count

                if cleanup_result.success:
                    console.print(f"[green]✓[/green] Cleaned {cleaned_count} orphaned operations")
                else:
                    console.print(
                        f"[yellow]⚠[/yellow] Cleaned {cleaned_count} operations with {cleanup_result.failed_count} failures"
                    )
                    if cleanup_result.errors:
                        for error in cleanup_result.errors:
                            console.print(f"  Error: {error}")

            # Step 2: Sync new and modified operations
            operations_to_sync = drift.new_operations + drift.modified_operations
            if operations_to_sync:
                console.print(
                    f"\n[bold]Step 2: Syncing {len(operations_to_sync)} operations[/bold]"
                )

                # Use the existing sync functionality
                executor = OperationExecutor()
                results = executor.execute_all(config, ctx)

                # Display sync results
                success_count = sum(1 for r in results if r.success)
                failure_count = len(results) - success_count

                if failure_count == 0:
                    console.print(
                        f"[green]✓[/green] Successfully applied {success_count} operations"
                    )
                else:
                    console.print(
                        f"[yellow]⚠[/yellow] Applied {success_count} operations, {failure_count} failed"
                    )

            # Final summary
            console.print("\n[green]✓[/green] Reconciliation complete")
            console.print(f"  Cleaned: {cleaned_count} orphaned operations")
            console.print(f"  Synced: {len(operations_to_sync)} configuration operations")

    except Exception as e:
        console.print(f"[red]✗[/red] Reconciliation failed: {e}")
        logger.exception("Reconciliation failed")
        sys.exit(1)


@cli.command()
@click.option("--config-drift", is_flag=True, help="Show configuration drift summary")
@click.pass_obj
def status(ctx: ExecutionContext, config_drift: bool) -> None:
    """Show current system status and applied configurations."""
    logger = logging.getLogger(__name__)

    try:
        with StateDatabase() as db:
            stats = db.get_statistics()
            current_state = db.get_current_state()

            console.print("\n[bold]System Status[/bold]")
            console.print(f"  Database: {db.db_path}")
            console.print(f"  Applied steps: {stats['applied_steps']}")

            if stats["transactions"]:
                tx_stats = stats["transactions"]
                console.print("\n[bold]Transaction Statistics[/bold]")
                console.print(f"  Total: {tx_stats['total']}")
                console.print(f"  Completed: {tx_stats['completed']}")
                console.print(f"  Failed: {tx_stats['failed']}")
                console.print(f"  Rolled back: {tx_stats['rolled_back']}")

            if current_state:
                console.print("\n[bold]Current Configuration[/bold]")
                for item in current_state[:10]:  # Show first 10 items
                    console.print(f"  • {item['dst_path']} ({item['operation_type']})")
                if len(current_state) > 10:
                    console.print(f"  ... and {len(current_state) - 10} more")

            # Show configuration drift if requested
            if config_drift:
                try:
                    # Load config and detect drift
                    loader = ConfigLoader(ctx.config_path)
                    config = loader.load()

                    detector = ConfigDriftDetector(db)
                    drift = detector.detect_drift(config, ctx.variant)

                    console.print("\n[bold]Configuration Drift[/bold]")
                    _display_drift_summary(drift)

                except Exception as e:
                    console.print(f"\n[yellow]⚠[/yellow] Could not check drift: {e}")

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to get status: {e}")
        logger.exception("Status check failed")
        sys.exit(1)


@cli.command()
@click.pass_obj
@click.option(
    "--rollback-to",
    type=str,
    help="Transaction ID to rollback to",
)
@click.option(
    "--file",
    type=str,
    help="Specific file to rollback (restores from managed source)",
)
def rollback(ctx: ExecutionContext, rollback_to: Optional[str], file: Optional[str]) -> None:
    """Rollback to a previous state or specific transaction.

    Use --rollback-to to rollback an entire transaction.
    Use --file to restore a specific file from its managed source.
    """
    logger = logging.getLogger(__name__)

    if file:
        # File-specific rollback - restore from managed source
        try:
            from pathlib import Path

            file_path = Path(file).expanduser().resolve()
            console.print(f"[yellow]Restoring file from managed source:[/yellow] {file_path}")

            with StateDatabase() as db:
                # Find the applied step for this file
                applied_step = db.find_applied_step_by_path(str(file_path))
                if not applied_step:
                    # Debug: Check what paths are actually in the database
                    cursor = db.conn.execute(
                        "SELECT dst_path, is_current FROM applied_steps ORDER BY dst_path"
                    )
                    all_paths = cursor.fetchall()
                    console.print(f"[red]✗[/red] File not managed by dotfiles-sync: {file}")
                    console.print(f"[yellow]Debug:[/yellow] Looking for: {str(file_path)}")
                    console.print("[yellow]Debug:[/yellow] Available paths in DB:")
                    for path_row in all_paths:
                        console.print(f"  - {path_row[0]} (current={path_row[1]})")
                    sys.exit(1)

                # Type assertion: applied_step is not None after the check above
                assert applied_step is not None

                if ctx.dry_run:
                    console.print(f"[yellow]DRY RUN:[/yellow] Would restore {file_path}")
                    console.print(f"  Source: {applied_step['src_path']}")
                    console.print(f"  Operation: {applied_step['operation_type']}")
                else:
                    # Import required modules for restoration
                    from verbs import VerbRegistry
                    from dotfiles_sync.models import StepConfig, OperationType
                    from dotfiles_sync.context import OperationContext
                    import json

                    # Reconstruct the original step configuration
                    try:
                        original_config = (
                            json.loads(applied_step["config"]) if applied_step["config"] else {}
                        )

                        # Remove conflicting keys to avoid duplicate arguments
                        config_to_use = {
                            k: v
                            for k, v in original_config.items()
                            if k not in ("op", "src", "dst")
                        }

                        # Create StepConfig from the applied step data
                        step_config = StepConfig(
                            op=OperationType(applied_step["operation_type"]),
                            src=applied_step["src_path"],
                            dst=str(file_path),
                            **config_to_use,  # Include any additional configuration
                        )

                        # Create operation context
                        op_ctx = OperationContext(
                            execution_context=ctx,
                            operation_type=applied_step["operation_type"],
                            step_config=step_config,
                            sequence_num=1,
                        )

                        # Get and apply the verb
                        verb_registry = VerbRegistry()
                        verb = verb_registry.get_verb(applied_step["operation_type"])
                        if not verb:
                            console.print(
                                f"[red]✗[/red] Unknown operation type: {applied_step['operation_type']}"
                            )
                            sys.exit(1)

                        # Type assertion: verb is not None after the check above
                        assert verb is not None

                        result = verb.apply(step_config, op_ctx)
                        if result.success:
                            console.print(f"[green]✓[/green] Successfully restored: {file_path}")
                        else:
                            console.print(
                                f"[red]✗[/red] Failed to restore {file_path}: {result.message}"
                            )
                            sys.exit(1)
                    except Exception as restore_error:
                        console.print(
                            f"[red]✗[/red] Failed to restore {file_path}: {restore_error}"
                        )
                        sys.exit(1)

        except Exception as e:
            console.print(f"[red]✗[/red] File rollback failed: {e}")
            logger.exception("File rollback failed")
            sys.exit(1)
            return

    if not rollback_to and not file:
        console.print("[yellow]![/yellow] No transaction ID or file specified")
        console.print("Use 'dotfiles-sync status' to see recent transactions")
        console.print("Use --rollback-to to rollback a transaction")
        console.print("Use --file to restore a specific file")
        sys.exit(1)

    if rollback_to:
        # Transaction rollback
        try:
            with StateDatabase() as db:
                if ctx.dry_run:
                    console.print(
                        f"[yellow]DRY RUN:[/yellow] Would rollback transaction {rollback_to}"
                    )
                    operations = db.get_rollback_operations(rollback_to)
                    for op in operations:
                        console.print(
                            f"  • Would rollback: {op['operation_type']} on {op['dst_path']}"
                        )
                else:
                    if not ctx.force:
                        if not click.confirm(f"Rollback transaction {rollback_to}?"):
                            console.print("Rollback cancelled")
                            return

                    success = db.perform_rollback(rollback_to)
                    if success:
                        console.print(
                            f"[green]✓[/green] Successfully rolled back transaction {rollback_to}"
                        )
                    else:
                        console.print(f"[red]✗[/red] Rollback failed for transaction {rollback_to}")
                        sys.exit(1)

        except Exception as e:
            console.print(f"[red]✗[/red] Rollback failed: {e}")
            logger.exception("Rollback failed")
            sys.exit(1)


@cli.command()
@click.option("--show-drift", is_flag=True, help="Show configuration drift before syncing")
@click.pass_obj
def sync(ctx: ExecutionContext, show_drift: bool) -> None:
    """Synchronize dotfiles according to configuration."""
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        loader = ConfigLoader(ctx.config_path)
        config = loader.load()
        loader.validate(config)

        console.print("[bold]Syncing dotfiles[/bold]")
        console.print(f"  Config: {ctx.config_path}")
        console.print(f"  Variant: {ctx.variant}")
        console.print(f"  Mode: {'DRY RUN' if ctx.dry_run else 'APPLY'}")
        console.print()

        # Show drift if requested
        if show_drift:
            console.print("[bold]Pre-sync Drift Analysis[/bold]")
            with StateDatabase() as db:
                detector = ConfigDriftDetector(db)
                drift = detector.detect_drift(config, ctx.variant)
                _display_drift_summary(drift)

                if drift.total_drift > 0 and not ctx.force:
                    console.print()
                    if not click.confirm("Continue with sync?"):
                        console.print("[yellow]Sync cancelled[/yellow]")
                        return
            console.print()

        # Execute operations using the OperationExecutor
        executor = OperationExecutor()
        results = executor.execute_all(config, ctx)

        # Display results
        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count
        skipped_count = sum(1 for r in results if r.success and getattr(r, "skipped", False))

        console.print("\n[bold]Results Summary[/bold]")
        console.print(f"  Total operations: {len(results)}")
        console.print(f"  Successful: [green]{success_count}[/green]")
        if skipped_count > 0:
            console.print(f"  Skipped (no changes): [yellow]{skipped_count}[/yellow]")
        if failure_count > 0:
            console.print(f"  Failed: [red]{failure_count}[/red]")

        # Show individual operation results
        console.print("\n[bold]Operation Details[/bold]")
        for result in results:
            status_color = "green" if result.success else "red"
            status_symbol = "✓" if result.success else "✗"
            mode_indicator = " (dry run)" if result.dry_run else ""

            console.print(
                f"  [{status_color}]{status_symbol}[/{status_color}] {result.message}{mode_indicator}"
            )

        # Show next steps for dry run
        if ctx.dry_run and success_count > 0:
            console.print("\n[yellow]ℹ[/yellow] This was a dry run. To apply changes, run:")
            console.print("  dotfiles-sync --apply sync")

        # Exit with error code if any operations failed
        if failure_count > 0:
            sys.exit(1)

    except ConfigValidationError as e:
        console.print(f"[red]✗[/red] Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Sync failed: {e}")
        logger.exception("Sync failed")
        sys.exit(1)


@cli.command()
@click.argument("file_path", required=False)
@click.pass_context
def diff(ctx: click.Context, file_path: Optional[str]) -> None:
    """Show differences between managed files and their sources.

    If FILE_PATH is provided, shows diff for specific file.
    Otherwise shows all files with drift.
    """
    logger = logging.getLogger(__name__)

    try:
        # Import required modules
        from .state_database import StateDatabase
        from safety.drift import DriftDetector
        from pathlib import Path

        # Initialize database and drift detector
        with StateDatabase() as db:
            drift_detector = DriftDetector(db)

            if file_path:
                # Show diff for specific file
                file_path_obj = Path(file_path).expanduser().resolve()
                console.print(f"[bold blue]Checking drift for:[/bold blue] {file_path}")

                # Find the applied step for this file
                applied_step = db.find_applied_step_by_path(str(file_path_obj))
                if not applied_step:
                    console.print(
                        f"[yellow]![/yellow] File not managed by dotfiles-sync: {file_path}"
                    )
                    return

                # Check for drift
                drift_report = drift_detector.check_specific_files([file_path_obj])
                if drift_report.drift_results:
                    for item in drift_report.drift_results:
                        console.print(f"[red]✗[/red] {item.drift_type.value}: {item.file_path}")
                        if item.details:
                            console.print(f"   Details: {item.details}")
                else:
                    console.print("[green]✓[/green] No drift detected")
            else:
                # Show all files with drift
                console.print("[bold blue]Checking all managed files for drift...[/bold blue]")
                drift_report = drift_detector.check_all_managed_files()

                if not drift_report.drift_results:
                    console.print("[green]✓[/green] No drift detected in any managed files")
                else:
                    console.print(
                        f"\n[yellow]Found {len(drift_report.drift_results)} file(s) with drift:[/yellow]"
                    )
                    for item in drift_report.drift_results:
                        console.print(f"  [red]✗[/red] {item.file_path}: {item.drift_type.value}")
                        if item.details:
                            console.print(f"     Details: {item.details}")

    except Exception as e:
        console.print(f"[red]✗[/red] Diff failed: {e}")
        logger.exception("Diff failed")
        sys.exit(1)


@cli.group()
@click.pass_context
def backup(ctx: click.Context) -> None:
    """Manage backups created by dotfiles-sync."""
    pass


@backup.command("list")
@click.pass_context
def backup_list(ctx: click.Context) -> None:
    """List all available backups."""
    logger = logging.getLogger(__name__)

    try:
        from safety.backup import BackupManager

        backup_manager = BackupManager()
        backups = backup_manager.list_backups()

        if not backups:
            console.print("[yellow]No backups found[/yellow]")
            return

        console.print(f"[bold blue]Found {len(backups)} backup(s):[/bold blue]")
        for backup_manifest in backups:
            created_at = backup_manifest.created_at.strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"  [green]{backup_manifest.backup_id}[/green]")
            console.print(f"    Created: {created_at}")
            console.print(f"    Reason: {backup_manifest.reason}")
            console.print(f"    Files: {len(backup_manifest.files_backed_up)}")
            if backup_manifest.created_by_transaction:
                console.print(f"    Transaction: {backup_manifest.created_by_transaction}")
            console.print()

    except Exception as e:
        console.print(f"[red]✗[/red] Failed to list backups: {e}")
        logger.exception("Backup list failed")
        sys.exit(1)


@backup.command("restore")
@click.argument("backup_id")
@click.pass_context
def backup_restore(ctx: click.Context, backup_id: str) -> None:
    """Restore files from a specific backup."""
    logger = logging.getLogger(__name__)

    try:
        from safety.backup import BackupManager

        backup_manager = BackupManager()

        console.print(f"[yellow]Restoring from backup:[/yellow] {backup_id}")
        success = backup_manager.restore_backup(backup_id)

        if success:
            console.print(f"[green]✓[/green] Successfully restored from backup: {backup_id}")
        else:
            console.print(f"[red]✗[/red] Failed to restore from backup: {backup_id}")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗[/red] Backup restore failed: {e}")
        logger.exception("Backup restore failed")
        sys.exit(1)


@cli.command("restore-orphaned")
@click.option("--transaction-id", help="Restore all operations from a specific cleanup transaction")
@click.option(
    "--operation-ids", multiple=True, type=int, help="Specific orphaned operation IDs to restore"
)
@click.option("--preview", is_flag=True, help="Preview restoration without applying")
@click.option("--list", "list_orphaned", is_flag=True, help="List restorable orphaned operations")
@click.pass_obj
def restore_orphaned(
    ctx: ExecutionContext,
    transaction_id: Optional[str],
    operation_ids: tuple,
    preview: bool,
    list_orphaned: bool,
) -> None:
    """Restore previously cleaned/orphaned operations.

    This command restores operations that were previously cleaned using the
    enhanced cleanup feature. Operations can be restored by:
    - Transaction ID: Restore all operations from a specific cleanup transaction
    - Operation IDs: Restore specific orphaned operations by their IDs
    - Interactive: List available operations and select which to restore
    """
    logger = logging.getLogger(__name__)

    try:
        from dotfiles_sync.cleanup_enhanced import EnhancedOrphanedOperationCleaner

        with StateDatabase() as db:
            cleaner = EnhancedOrphanedOperationCleaner(db)

            # List mode - show restorable operations
            if list_orphaned:
                console.print("[bold]Restorable Orphaned Operations[/bold]\n")

                # Query orphaned operations
                cursor = db.conn.cursor()
                cursor.execute("""
                    SELECT id, dst_path, operation_type, orphaned_at, 
                           orphaned_by_transaction, orphaned_reason
                    FROM orphaned_operations
                    WHERE restored_at IS NULL
                    ORDER BY orphaned_at DESC
                    LIMIT 50
                """)

                operations = cursor.fetchall()
                if not operations:
                    console.print("[yellow]No restorable operations found[/yellow]")
                    return

                console.print(f"Found {len(operations)} restorable operation(s):\n")
                for op in operations:
                    op_id, dst_path, op_type, orphaned_at, tx_id, reason = op
                    console.print(f"  [green]{op_id}[/green]: {dst_path}")
                    console.print(f"    Type: {op_type}")
                    console.print(f"    Orphaned: {orphaned_at}")
                    console.print(f"    Transaction: {tx_id[:8]}...")
                    console.print(f"    Reason: {reason}")
                    console.print()

                console.print("\n[dim]Use --operation-ids to restore specific operations[/dim]")
                console.print("[dim]Use --transaction-id to restore all from a transaction[/dim]")
                return

            # Validate input
            if not transaction_id and not operation_ids:
                console.print("[yellow]![/yellow] Specify --transaction-id or --operation-ids")
                console.print("Use --list to see restorable operations")
                return

            # Preview or execute restoration
            if preview:
                console.print("[yellow]PREVIEW MODE - No changes will be made[/yellow]\n")

            result = cleaner.restore_orphaned_operations(
                transaction_id=transaction_id,
                operation_ids=list(operation_ids) if operation_ids else None,
                dry_run=preview or ctx.dry_run,
            )

            # Display results
            if result.success:
                console.print(
                    f"[green]✓[/green] Successfully restored {result.restored_count} operations"
                )
                if result.restored_files:
                    console.print("\nRestored files:")
                    for file in result.restored_files:
                        console.print(f"  • {file}")
            else:
                console.print(
                    f"[yellow]⚠[/yellow] Restored {result.restored_count} operations with {result.failed_count} failures"
                )

            if result.errors:
                console.print(f"\n[red]Errors ({len(result.errors)}):[/red]")
                for error in result.errors:
                    console.print(f"  • {error}")
                sys.exit(1)

            if preview and result.restored_count > 0:
                console.print(
                    "\n[yellow]ℹ[/yellow] This was a preview. To apply restoration, run without --preview"
                )

    except Exception as e:
        console.print(f"[red]✗[/red] Restoration failed: {e}")
        logger.exception("Restoration failed")
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]![/yellow] Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
