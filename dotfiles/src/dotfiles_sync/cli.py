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
        
        console.print(f"[green]✓[/green] Configuration is valid!")
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
            
            if stats['transactions']:
                tx_stats = stats['transactions']
                console.print(f"\n[bold]Transaction Statistics[/bold]")
                console.print(f"  Total: {tx_stats['total']}")
                console.print(f"  Completed: {tx_stats['completed']}")
                console.print(f"  Failed: {tx_stats['failed']}")
                console.print(f"  Rolled back: {tx_stats['rolled_back']}")
            
            if current_state:
                console.print(f"\n[bold]Current Configuration[/bold]")
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
def rollback(ctx: ExecutionContext, rollback_to: Optional[str]) -> None:
    """Rollback to a previous state or specific transaction."""
    logger = logging.getLogger(__name__)
    
    if not rollback_to:
        console.print("[yellow]![/yellow] No transaction ID specified")
        console.print("Use 'dotfiles-sync history' to see available transactions")
        sys.exit(1)
    
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
                    console.print(f"[green]✓[/green] Successfully rolled back transaction {rollback_to}")
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
        
        console.print(f"[bold]Syncing dotfiles[/bold]")
        console.print(f"  Config: {ctx.config_path}")
        console.print(f"  Variant: {ctx.variant}")
        console.print(f"  Mode: {'DRY RUN' if ctx.dry_run else 'APPLY'}")
        
        # TODO: Implement actual sync logic in later phases
        console.print("\n[yellow]![/yellow] Sync operation not yet implemented (Phase 1)")
        console.print("This will be implemented in the next phase with link/copy operations")
        
    except ConfigValidationError as e:
        console.print(f"[red]✗[/red] Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Sync failed: {e}")
        logger.exception("Sync failed")
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