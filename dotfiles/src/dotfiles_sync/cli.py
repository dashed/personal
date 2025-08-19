"""
CLI interface for the Dotfiles Management System.

This module provides the command-line interface using Click framework.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from dotfiles_sync import __version__
from dotfiles_sync.config import ConfigLoader, ConfigValidationError
from dotfiles_sync.context import ExecutionContext
from dotfiles_sync.database import StateDatabase

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
@click.pass_obj
def validate(ctx: ExecutionContext) -> None:
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

    except ConfigValidationError as e:
        console.print(f"[red]✗[/red] Configuration validation failed: {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        logger.exception("Validation failed")
        sys.exit(1)


@cli.command()
@click.pass_obj
def status(ctx: ExecutionContext) -> None:
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
                    cursor = db.conn.execute("SELECT dst_path, is_current FROM applied_steps ORDER BY dst_path")
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
                        original_config = json.loads(applied_step['config']) if applied_step['config'] else {}
                        
                        # Remove conflicting keys to avoid duplicate arguments
                        config_to_use = {k: v for k, v in original_config.items() 
                                        if k not in ('op', 'src', 'dst')}
                        
                        # Create StepConfig from the applied step data
                        step_config = StepConfig(
                            op=OperationType(applied_step['operation_type']),
                            src=applied_step['src_path'],
                            dst=str(file_path),
                            **config_to_use  # Include any additional configuration
                        )
                        
                        # Create operation context
                        op_ctx = OperationContext(
                            execution_context=ctx,
                            operation_type=applied_step['operation_type'],
                            step_config=step_config,
                            sequence_num=1,
                        )
                        
                        # Get and apply the verb
                        verb_registry = VerbRegistry()
                        verb = verb_registry.get_verb(applied_step['operation_type'])
                        if not verb:
                            console.print(f"[red]✗[/red] Unknown operation type: {applied_step['operation_type']}")
                            sys.exit(1)
                        
                        # Type assertion: verb is not None after the check above
                        assert verb is not None
                        
                        result = verb.apply(step_config, op_ctx)
                        if result.success:
                            console.print(f"[green]✓[/green] Successfully restored: {file_path}")
                        else:
                            console.print(f"[red]✗[/red] Failed to restore {file_path}: {result.message}")
                            sys.exit(1)
                    except Exception as restore_error:
                        console.print(f"[red]✗[/red] Failed to restore {file_path}: {restore_error}")
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
                    console.print(f"[yellow]DRY RUN:[/yellow] Would rollback transaction {rollback_to}")
                    operations = db.get_rollback_operations(rollback_to)
                    for op in operations:
                        console.print(f"  • Would rollback: {op['operation_type']} on {op['dst_path']}")
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
@click.pass_obj
def sync(ctx: ExecutionContext) -> None:
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
                    console.print(f"[yellow]![/yellow] File not managed by dotfiles-sync: {file_path}")
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
                    console.print(f"\n[yellow]Found {len(drift_report.drift_results)} file(s) with drift:[/yellow]")
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
