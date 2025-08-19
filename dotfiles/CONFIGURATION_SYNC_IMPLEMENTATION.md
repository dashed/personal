# Configuration Synchronization Implementation Plan

## Overview

This plan addresses the critical gap: **"When we do changes to `/Users/me/aaa/github/personal/dotfiles/dotfiles.toml`, how do we 'sync' the state.db towards our latest config?"**

The current system lacks configuration drift detection and cleanup capabilities, leading to orphaned operations in the database when configuration files change.

## Problem Statement

### Current Behavior
- System loads `dotfiles.toml` and executes all steps from current config
- Operations are recorded in `state.db` with step hashes
- No detection of "orphaned" operations (removed from config but still in database)
- No detection of modified steps (same destination, different configuration)
- No cleanup commands for removing obsolete database entries

### Impact
- Database accumulates stale entries over time
- Files remain managed even after removal from configuration
- Configuration changes create unclear system state
- No way to reconcile database with current configuration

## Architecture Analysis

### Current System Capabilities ✅
- Step hash mechanism (SHA256 of JSON config) for change detection
- `applied_steps` table with `is_current` flag and `step_hash`
- Transaction support with rollback capabilities
- Safety features (dry-run, backups, path validation)
- CLI commands: `validate`, `status`, `rollback`, `sync`, `diff`

### Identified Gaps ❌
- No configuration drift detection (TOML vs database comparison)
- No orphaned operation cleanup commands
- No modified step detection and reconciliation
- No impact analysis for configuration changes
- No configuration versioning or history tracking

## Implementation Phases

---

## Phase 1: Configuration Drift Detection Core

**Goal**: Build foundational drift detection capability without changing existing workflows.

### New Components

#### `ConfigDriftDetector` Class
```python
# src/dotfiles_sync/config_drift.py

from enum import Enum
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field
from dotfiles_sync.models import DotfilesConfig, StepConfig
from dotfiles_sync.state_database import StateDatabase

class ConfigDriftType(Enum):
    """Types of configuration drift."""
    NEW = "new"           # In TOML, not in DB
    MODIFIED = "modified"  # Same dst, different hash  
    ORPHANED = "orphaned" # In DB, not in TOML

class ConfigDriftResult(BaseModel):
    """Result of configuration drift detection."""
    drift_type: ConfigDriftType
    dst_path: str
    current_step_hash: Optional[str] = Field(None, description="Hash from TOML")
    applied_step_hash: Optional[str] = Field(None, description="Hash from DB")
    current_config: Optional[StepConfig] = None
    applied_config: Optional[Dict[str, Any]] = None
    impact: str = Field(..., description="Description of what will happen")
    severity: str = Field(default="info", description="info, warning, error")

class ConfigDriftSummary(BaseModel):
    """Summary of configuration drift analysis."""
    total_drift: int
    new_operations: List[ConfigDriftResult]
    modified_operations: List[ConfigDriftResult]
    orphaned_operations: List[ConfigDriftResult]
    recommended_action: str

class ConfigDriftDetector:
    """Detects configuration drift between TOML and database."""
    
    def __init__(self, database: StateDatabase):
        self.database = database
    
    def detect_drift(self, config: DotfilesConfig, variant: str) -> ConfigDriftSummary:
        """Detect all types of configuration drift."""
        current_hashes = self._get_current_step_hashes(config, variant)
        applied_hashes = self._get_applied_step_hashes(variant)
        
        new_ops = self._find_new_operations(current_hashes, applied_hashes)
        modified_ops = self._find_modified_operations(current_hashes, applied_hashes)
        orphaned_ops = self._find_orphaned_operations(current_hashes, applied_hashes)
        
        return ConfigDriftSummary(
            total_drift=len(new_ops) + len(modified_ops) + len(orphaned_ops),
            new_operations=new_ops,
            modified_operations=modified_ops,
            orphaned_operations=orphaned_ops,
            recommended_action=self._recommend_action(new_ops, modified_ops, orphaned_ops)
        )
    
    def _get_current_step_hashes(self, config: DotfilesConfig, variant: str) -> Dict[str, str]:
        """Get step hashes from current configuration."""
        # Implementation details
        pass
    
    def _get_applied_step_hashes(self, variant: str) -> Dict[str, str]:
        """Get step hashes from database."""
        # Implementation details
        pass
    
    def _find_orphaned_operations(self, current: Set[str], applied: Set[str]) -> List[ConfigDriftResult]:
        """Find operations in database but not in current config."""
        # Implementation details
        pass
    
    def _analyze_drift_impact(self, drift_type: ConfigDriftType, step: StepConfig) -> str:
        """Analyze the impact of a drift."""
        # Implementation details
        pass
```

#### Database Methods
```python
# Enhanced src/dotfiles_sync/state_database.py

def get_applied_step_hashes_by_variant(self, variant: str) -> Dict[str, Dict[str, Any]]:
    """Get all applied step hashes for a variant, keyed by dst_path."""
    cursor = self.conn.execute("""
        SELECT 
            dst_path,
            step_hash,
            operation_type,
            config,
            applied_at
        FROM applied_steps
        WHERE is_current = 1
        ORDER BY dst_path
    """)
    
    result = {}
    for row in cursor.fetchall():
        result[row['dst_path']] = dict(row)
    return result

def find_orphaned_operations(self, current_step_hashes: Set[str]) -> List[Dict[str, Any]]:
    """Find applied operations not represented in current config."""
    placeholders = ','.join(['?'] * len(current_step_hashes))
    cursor = self.conn.execute(f"""
        SELECT * FROM applied_steps
        WHERE is_current = 1
        AND step_hash NOT IN ({placeholders})
    """, list(current_step_hashes))
    
    return [dict(row) for row in cursor.fetchall()]

def get_config_drift_summary(self, variant: str) -> Dict[str, Any]:
    """Get summary of configuration drift for variant."""
    # Count orphaned, modified, and new operations
    # Return summary statistics
    pass
```

### Testing
- Unit tests for drift detection logic
- Integration tests with various configuration scenarios
- Edge cases: empty configs, large configs, complex modifications

**Deliverable**: Core drift detection logic with comprehensive test coverage

---

## Phase 2: CLI Integration - Visibility Commands

**Goal**: Make configuration drift visible to users through new CLI commands.

### New CLI Commands

#### `check-config` Command
```python
# src/dotfiles_sync/cli.py

@cli.command()
@click.option('--variant', default='default', help='Variant to check')
@click.option('--format', type=click.Choice(['table', 'json']), default='table')
@click.option('--detailed', is_flag=True, help='Show detailed drift information')
@click.pass_obj
def check_config(ctx: ExecutionContext, variant: str, format: str, detailed: bool) -> None:
    """Check for configuration drift between TOML and database."""
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        loader = ConfigLoader(ctx.config_path)
        config = loader.load()
        
        # Detect drift
        with StateDatabase() as db:
            detector = ConfigDriftDetector(db)
            drift_summary = detector.detect_drift(config, variant)
        
        # Display results
        if format == 'json':
            console.print_json(drift_summary.model_dump_json())
        else:
            _display_drift_table(drift_summary, detailed)
        
        # Exit with appropriate code
        if drift_summary.total_drift > 0:
            sys.exit(1)  # Indicate drift exists
    
    except Exception as e:
        console.print(f"[red]✗[/red] Configuration check failed: {e}")
        logger.exception("Configuration check failed")
        sys.exit(1)
```

**Output Example**:
```
Configuration Drift Report
══════════════════════════════════════════════════════════════════
Current Config: dotfiles.toml (modified 2 hours ago)
Database State: 3 applied operations

⚠️  ORPHANED OPERATIONS (2):
  • ~/.test_file1 (link) - Operation no longer in config
  • ~/.old_setting (copy) - Removed from TOML

🔄 MODIFIED OPERATIONS (1):
  • ~/.gitconfig (copy) - Configuration changed
    Old: mode=0644, src=git/gitconfig-old
    New: mode=0600, src=git/gitconfig

✅ NEW OPERATIONS (1):
  • ~/.zshrc (link) - Will be created on next sync

Impact: 3 operations need reconciliation
Recommendation: Run 'dotfiles-sync reconcile' to fix
```

#### Enhanced `status` Command
```python
@cli.command()
@click.option('--config-drift', is_flag=True, help='Show configuration drift')
@click.pass_obj
def status(ctx: ExecutionContext, config_drift: bool) -> None:
    """Show current system status and applied configurations."""
    # Existing status code...
    
    if config_drift:
        # Load config and detect drift
        loader = ConfigLoader(ctx.config_path)
        config = loader.load()
        
        with StateDatabase() as db:
            detector = ConfigDriftDetector(db)
            drift = detector.detect_drift(config, ctx.variant)
            
            if drift.total_drift > 0:
                console.print("\n[bold yellow]Configuration Drift Detected[/bold yellow]")
                console.print(f"  Orphaned: {len(drift.orphaned_operations)}")
                console.print(f"  Modified: {len(drift.modified_operations)}")
                console.print(f"  New: {len(drift.new_operations)}")
                console.print(f"\n  Run 'dotfiles-sync check-config' for details")
```

#### Enhanced `validate` Command
```python
@cli.command()
@click.option('--check-database', is_flag=True, help='Validate against database state')
@click.pass_obj
def validate(ctx: ExecutionContext, check_database: bool) -> None:
    """Validate the configuration file."""
    # Existing validation code...
    
    if check_database:
        with StateDatabase() as db:
            detector = ConfigDriftDetector(db)
            drift = detector.detect_drift(config, ctx.variant)
            
            if drift.orphaned_operations:
                console.print(f"[yellow]⚠[/yellow] {len(drift.orphaned_operations)} orphaned operations found")
            
            if drift.modified_operations:
                console.print(f"[yellow]⚠[/yellow] {len(drift.modified_operations)} modified operations found")
```

**Deliverable**: Users can see configuration drift and understand impact

---

## Phase 3: Cleanup and Reconciliation Commands

**Goal**: Provide commands to actually fix configuration drift.

### New CLI Commands

#### `clean` Command
```python
@cli.command()
@click.option('--orphaned-only', is_flag=True, help='Only clean orphaned operations')
@click.option('--dry-run', is_flag=True, help='Preview cleanup without applying')
@click.option('--backup', is_flag=True, default=True, help='Backup before cleanup')
@click.option('--remove-files', is_flag=True, help='Remove files for orphaned operations')
@click.option('--force', is_flag=True, help='Force cleanup without confirmation')
@click.pass_obj
def clean(ctx: ExecutionContext, orphaned_only: bool, dry_run: bool, 
          backup: bool, remove_files: bool, force: bool) -> None:
    """Clean up configuration drift in database."""
    logger = logging.getLogger(__name__)
    
    try:
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
            
            # Show what will be cleaned
            console.print(f"[bold]Cleanup Plan[/bold]")
            console.print(f"  Operations to clean: {len(to_clean)}")
            console.print(f"  Remove files: {remove_files}")
            console.print(f"  Backup: {backup}")
            
            # Confirm unless forced
            if not force and not dry_run:
                if not click.confirm("Proceed with cleanup?"):
                    console.print("[yellow]Cleanup cancelled[/yellow]")
                    return
            
            if dry_run:
                console.print("\n[yellow]DRY RUN - No changes will be made[/yellow]")
                _display_cleanup_plan(to_clean, remove_files)
            else:
                # Perform cleanup
                cleaner = OrphanedOperationCleaner(db)
                result = cleaner.clean_operations(
                    to_clean, 
                    remove_files=remove_files,
                    backup=backup
                )
                
                console.print(f"[green]✓[/green] Cleaned {result.cleaned_count} operations")
                
                if result.errors:
                    console.print(f"[red]✗[/red] {len(result.errors)} errors occurred")
                    for error in result.errors:
                        console.print(f"  - {error}")
    
    except Exception as e:
        console.print(f"[red]✗[/red] Cleanup failed: {e}")
        logger.exception("Cleanup failed")
        sys.exit(1)
```

#### `reconcile` Command
```python
@cli.command()
@click.option('--preview', is_flag=True, help='Preview reconciliation plan')
@click.option('--clean-first', is_flag=True, default=True, help='Clean before sync')
@click.option('--remove-files', is_flag=True, help='Remove orphaned files')
@click.pass_obj
def reconcile(ctx: ExecutionContext, preview: bool, clean_first: bool, remove_files: bool) -> None:
    """Reconcile configuration drift (clean + sync)."""
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
                console.print("[green]✓[/green] No reconciliation needed")
                return
            
            # Show reconciliation plan
            console.print(f"\n[bold]Reconciliation Plan[/bold]")
            console.print(f"  Orphaned to clean: {len(drift.orphaned_operations)}")
            console.print(f"  Modified to update: {len(drift.modified_operations)}")
            console.print(f"  New to apply: {len(drift.new_operations)}")
            
            if preview:
                _display_reconciliation_plan(drift, remove_files)
                return
            
            # Confirm
            if not click.confirm("\nProceed with reconciliation?"):
                console.print("[yellow]Reconciliation cancelled[/yellow]")
                return
            
            # Step 1: Clean orphaned operations
            if clean_first and drift.orphaned_operations:
                console.print("\n[bold]Step 1: Cleaning orphaned operations[/bold]")
                cleaner = OrphanedOperationCleaner(db)
                cleaner.clean_operations(drift.orphaned_operations, remove_files=remove_files)
            
            # Step 2: Sync new and modified operations
            console.print("\n[bold]Step 2: Syncing configuration[/bold]")
            executor = OperationExecutor()
            results = executor.execute_all(config, ctx)
            
            # Display results
            success_count = sum(1 for r in results if r.success)
            console.print(f"\n[green]✓[/green] Reconciliation complete")
            console.print(f"  Cleaned: {len(drift.orphaned_operations)}")
            console.print(f"  Applied: {success_count}")
    
    except Exception as e:
        console.print(f"[red]✗[/red] Reconciliation failed: {e}")
        logger.exception("Reconciliation failed")
        sys.exit(1)
```

#### Enhanced `sync` Command
```python
@cli.command()
@click.option('--clean', is_flag=True, help='Clean orphaned operations before sync')
@click.option('--no-clean', is_flag=True, help='Skip cleanup (preserve old behavior)')
@click.pass_obj
def sync(ctx: ExecutionContext, clean: bool, no_clean: bool) -> None:
    """Synchronize dotfiles according to configuration."""
    # Existing sync code...
    
    if clean and not no_clean:
        # Clean orphaned operations first
        with StateDatabase() as db:
            detector = ConfigDriftDetector(db)
            drift = detector.detect_drift(config, ctx.variant)
            
            if drift.orphaned_operations:
                console.print(f"[yellow]Cleaning {len(drift.orphaned_operations)} orphaned operations[/yellow]")
                cleaner = OrphanedOperationCleaner(db)
                cleaner.clean_operations(drift.orphaned_operations)
    
    # Continue with normal sync...
```

### Cleanup Logic Implementation

```python
# src/dotfiles_sync/cleanup.py

class CleanupResult(BaseModel):
    """Result of cleanup operation."""
    cleaned_count: int
    failed_count: int
    backed_up_files: List[str]
    removed_files: List[str]
    errors: List[str]

class OrphanedOperationCleaner:
    """Handles cleanup of orphaned operations."""
    
    def __init__(self, database: StateDatabase):
        self.database = database
        self.backup_manager = BackupManager()
        self.transaction_manager = TransactionManager(database)
    
    def clean_operations(
        self,
        operations: List[ConfigDriftResult],
        remove_files: bool = False,
        backup: bool = True,
        transaction_id: Optional[str] = None
    ) -> CleanupResult:
        """Clean up orphaned or modified operations."""
        result = CleanupResult(
            cleaned_count=0,
            failed_count=0,
            backed_up_files=[],
            removed_files=[],
            errors=[]
        )
        
        # Start transaction if not provided
        if not transaction_id:
            transaction_id = self.transaction_manager.start_transaction(
                variant="cleanup",
                user=getpass.getuser(),
                hostname=socket.gethostname()
            )
        
        try:
            for op in operations:
                try:
                    # Backup file if requested
                    if backup and op.dst_path and Path(op.dst_path).exists():
                        backup_path = self.backup_manager.backup_file(
                            Path(op.dst_path),
                            reason=f"Cleanup of {op.drift_type.value} operation"
                        )
                        result.backed_up_files.append(str(backup_path))
                    
                    # Mark operation as not current
                    self.database.mark_operation_as_orphaned(
                        op.applied_step_hash,
                        transaction_id
                    )
                    
                    # Remove file if requested
                    if remove_files and op.dst_path:
                        file_path = Path(op.dst_path).expanduser()
                        if file_path.exists():
                            if file_path.is_symlink() or file_path.is_file():
                                file_path.unlink()
                            elif file_path.is_dir():
                                shutil.rmtree(file_path)
                            result.removed_files.append(str(file_path))
                    
                    result.cleaned_count += 1
                    
                except Exception as e:
                    result.failed_count += 1
                    result.errors.append(f"{op.dst_path}: {str(e)}")
            
            # Commit transaction
            self.transaction_manager.commit_transaction(transaction_id)
            
        except Exception as e:
            # Rollback on failure
            self.transaction_manager.rollback_transaction(transaction_id)
            raise
        
        return result
    
    def restore_orphaned_operations(
        self,
        transaction_id: str
    ) -> int:
        """Restore operations that were previously cleaned."""
        # Find operations orphaned by this transaction
        # Mark them as current again
        # Restore files from backup if available
        pass
```

**Deliverable**: Users can reconcile configuration changes safely

---

## Phase 4: Advanced Safety and Rollback

**Goal**: Production-ready safety features for configuration changes.

### Enhanced Safety Features

#### Impact Analysis
```python
class ImpactAnalyzer:
    """Analyzes impact of configuration changes."""
    
    def analyze_cleanup_impact(
        self,
        operations: List[ConfigDriftResult]
    ) -> ImpactReport:
        """Analyze what will happen during cleanup."""
        report = ImpactReport()
        
        for op in operations:
            # Check if file is modified
            if self._is_file_modified(op.dst_path, op.applied_config):
                report.add_warning(f"{op.dst_path} has been modified locally")
            
            # Check dependencies
            deps = self._find_dependencies(op.dst_path)
            if deps:
                report.add_info(f"{op.dst_path} is referenced by: {deps}")
            
            # Check for conflicts
            conflicts = self._find_conflicts(op)
            if conflicts:
                report.add_error(f"{op.dst_path} has conflicts: {conflicts}")
        
        return report
```

#### Selective Cleanup
```python
@cli.command()
@click.option('--paths', multiple=True, help='Specific paths to clean')
@click.option('--operations', multiple=True, help='Operation types to clean')
@click.option('--before', type=click.DateTime(), help='Clean operations before date')
@click.option('--interactive', is_flag=True, help='Interactive cleanup mode')
def clean_selective(paths, operations, before, interactive):
    """Selectively clean specific operations."""
    # Filter operations based on criteria
    # Interactive mode asks for each operation
    # Provide detailed information for decisions
```

#### Restoration Commands
```python
@cli.command()
@click.argument('transaction_id')
def restore_orphaned(transaction_id: str):
    """Restore operations that were previously cleaned."""
    with StateDatabase() as db:
        cleaner = OrphanedOperationCleaner(db)
        count = cleaner.restore_orphaned_operations(transaction_id)
        console.print(f"[green]✓[/green] Restored {count} operations")
```

### Conflict Resolution
```python
class ConflictResolver:
    """Resolves conflicts in configuration changes."""
    
    def resolve_destination_conflict(
        self,
        dst_path: str,
        operations: List[StepConfig]
    ) -> StepConfig:
        """Resolve multiple operations targeting same destination."""
        # Priority rules:
        # 1. Variant-specific over "all"
        # 2. Later in config over earlier
        # 3. User choice if ambiguous
        pass
    
    def resolve_modification_conflict(
        self,
        old_config: Dict,
        new_config: StepConfig,
        local_changes: bool
    ) -> Resolution:
        """Resolve conflicts when modifying operations."""
        # Options:
        # - Keep local changes
        # - Apply new config
        # - Merge changes
        # - Ask user
        pass
```

**Deliverable**: Production-ready safety and advanced cleanup capabilities

---

## Phase 5: Database Schema Enhancements

**Goal**: Database support for advanced configuration change tracking.

### New Tables

```sql
-- Track configuration file versions
CREATE TABLE IF NOT EXISTS config_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_hash TEXT UNIQUE NOT NULL,
    config_content TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_mtime TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);

-- Store configuration drift detection results
CREATE TABLE IF NOT EXISTS config_drift_detection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config_version_id INTEGER,
    variant TEXT,
    total_drift INTEGER,
    drift_results JSON,  -- Serialized drift analysis
    resolved_at TIMESTAMP,
    resolved_by_transaction TEXT,
    FOREIGN KEY (config_version_id) REFERENCES config_versions(id),
    FOREIGN KEY (resolved_by_transaction) REFERENCES transactions(id)
);

-- Track operations that have been orphaned
CREATE TABLE IF NOT EXISTS orphaned_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_applied_step_id INTEGER NOT NULL,
    step_hash TEXT NOT NULL,
    dst_path TEXT,
    operation_type TEXT,
    config JSON,
    orphaned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    orphaned_by_transaction TEXT,
    orphaned_reason TEXT,  -- 'removed_from_config', 'modified', etc.
    restoration_data JSON,  -- Data needed to restore
    restored_at TIMESTAMP,
    restored_by_transaction TEXT,
    FOREIGN KEY (original_applied_step_id) REFERENCES applied_steps(id),
    FOREIGN KEY (orphaned_by_transaction) REFERENCES transactions(id),
    FOREIGN KEY (restored_by_transaction) REFERENCES transactions(id)
);

-- Configuration change history
CREATE TABLE IF NOT EXISTS config_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    old_version_id INTEGER,
    new_version_id INTEGER,
    change_type TEXT,  -- 'add_step', 'remove_step', 'modify_step', etc.
    affected_path TEXT,
    old_config JSON,
    new_config JSON,
    FOREIGN KEY (old_version_id) REFERENCES config_versions(id),
    FOREIGN KEY (new_version_id) REFERENCES config_versions(id)
);
```

### Enhanced Tables

```sql
-- Add config version tracking to applied_steps
ALTER TABLE applied_steps ADD COLUMN config_version_id INTEGER
    REFERENCES config_versions(id);

-- Add drift handling to transactions
ALTER TABLE transactions ADD COLUMN config_drift_handled BOOLEAN DEFAULT 0;
ALTER TABLE transactions ADD COLUMN config_version_id INTEGER
    REFERENCES config_versions(id);

-- Add config events to audit log
-- (No schema change needed, just new event_type values)
```

### New Views

```sql
-- Current configuration drift summary
CREATE VIEW IF NOT EXISTS configuration_drift_summary AS
SELECT 
    cd.checked_at,
    cd.variant,
    cd.total_drift,
    cv.config_hash,
    cv.file_path,
    cd.resolved_at IS NOT NULL as is_resolved
FROM config_drift_detection cd
JOIN config_versions cv ON cd.config_version_id = cv.id
WHERE cd.id IN (
    SELECT MAX(id) FROM config_drift_detection
    GROUP BY variant
);

-- All currently orphaned operations
CREATE VIEW IF NOT EXISTS orphaned_operations_view AS
SELECT 
    oo.*,
    as2.dst_path as original_dst_path,
    as2.operation_type as original_operation_type
FROM orphaned_operations oo
JOIN applied_steps as2 ON oo.original_applied_step_id = as2.id
WHERE oo.restored_at IS NULL
ORDER BY oo.orphaned_at DESC;

-- Configuration change history with impact
CREATE VIEW IF NOT EXISTS config_change_history AS
SELECT 
    cc.changed_at,
    cc.change_type,
    cc.affected_path,
    old_v.config_hash as old_hash,
    new_v.config_hash as new_hash,
    COUNT(DISTINCT cdd.id) as drift_detections,
    COUNT(DISTINCT oo.id) as orphaned_operations
FROM config_changes cc
LEFT JOIN config_versions old_v ON cc.old_version_id = old_v.id
LEFT JOIN config_versions new_v ON cc.new_version_id = new_v.id
LEFT JOIN config_drift_detection cdd ON cdd.config_version_id = new_v.id
LEFT JOIN orphaned_operations oo ON oo.orphaned_at >= cc.changed_at
    AND oo.orphaned_at < COALESCE(
        (SELECT MIN(changed_at) FROM config_changes WHERE changed_at > cc.changed_at),
        CURRENT_TIMESTAMP
    )
GROUP BY cc.id
ORDER BY cc.changed_at DESC;
```

### Database Migration

```sql
-- Migration script for existing databases
-- Run this in a transaction

BEGIN TRANSACTION;

-- Check current schema version
SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;

-- Add new tables (see above)

-- Add columns to existing tables
ALTER TABLE applied_steps ADD COLUMN config_version_id INTEGER;
ALTER TABLE transactions ADD COLUMN config_drift_handled BOOLEAN DEFAULT 0;
ALTER TABLE transactions ADD COLUMN config_version_id INTEGER;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_config_versions_hash ON config_versions(config_hash);
CREATE INDEX IF NOT EXISTS idx_config_drift_variant ON config_drift_detection(variant);
CREATE INDEX IF NOT EXISTS idx_orphaned_ops_restored ON orphaned_operations(restored_at);
CREATE INDEX IF NOT EXISTS idx_config_changes_path ON config_changes(affected_path);

-- Update schema version
INSERT INTO schema_version (version, description)
VALUES (2, 'Added configuration drift detection support');

COMMIT;
```

**Deliverable**: Rich database support for configuration lifecycle management

---

## Phase 6: Automation and Workflow Integration

**Goal**: Streamlined user experience and automation support.

### Automation Features

#### Auto-cleanup Mode
```python
# Configuration option in dotfiles.toml
[safety]
auto_clean_orphaned = true  # Automatically clean during sync
orphaned_file_action = "backup"  # "keep", "backup", "remove"
confirm_cleanup = true  # Ask before auto-cleanup
```

#### Git Hooks Integration
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for configuration drift
dotfiles-sync check-config --format json > /tmp/drift.json
if [ $? -ne 0 ]; then
    echo "Warning: Configuration drift detected"
    cat /tmp/drift.json | jq '.recommended_action'
    read -p "Continue commit? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
```

#### Scheduled Cleanup
```python
# Cron job or systemd timer
@daily dotfiles-sync clean --orphaned-only --quiet
```

#### CI/CD Integration
```yaml
# GitHub Actions example
- name: Check Configuration Drift
  run: |
    dotfiles-sync check-config --format json > drift.json
    if [ -s drift.json ]; then
      echo "::warning::Configuration drift detected"
      cat drift.json | jq '.recommended_action'
    fi

- name: Validate Against Production
  run: |
    dotfiles-sync validate --check-database
```

### Workflow Improvements

#### Interactive Mode
```python
@cli.command()
@click.option('--interactive', is_flag=True, help='Interactive resolution mode')
def reconcile_interactive(interactive):
    """Interactively resolve configuration drift."""
    if interactive:
        # For each drift item:
        # 1. Show detailed information
        # 2. Explain impact
        # 3. Offer choices
        # 4. Execute user choice
        # 5. Show result
        pass
```

#### Preview Mode
```python
class PreviewRenderer:
    """Renders preview of changes."""
    
    def render_cleanup_preview(self, operations: List[ConfigDriftResult]) -> str:
        """Render a preview of cleanup operations."""
        # Use Rich tables for nice formatting
        # Show before/after state
        # Highlight important changes
        # Include file diffs if relevant
        pass
```

#### Batch Operations
```python
@cli.command()
@click.argument('config_files', nargs=-1, type=click.Path(exists=True))
def batch_reconcile(config_files):
    """Reconcile multiple configuration files."""
    for config_file in config_files:
        # Process each configuration
        # Track overall progress
        # Summarize results
        pass
```

#### Migration Assistance
```python
class ConfigMigrator:
    """Helps migrate configuration formats."""
    
    def migrate_v1_to_v2(self, old_config: Dict) -> DotfilesConfig:
        """Migrate from v1 to v2 configuration format."""
        # Handle breaking changes
        # Preserve user settings
        # Generate migration report
        pass
    
    def suggest_improvements(self, config: DotfilesConfig) -> List[str]:
        """Suggest configuration improvements."""
        suggestions = []
        
        # Check for deprecated features
        # Suggest better patterns
        # Recommend safety settings
        
        return suggestions
```

### User Experience Enhancements

#### Better Error Messages
```python
class DriftError(Exception):
    """Base class for drift-related errors."""
    
    def __init__(self, message: str, resolution: str = None):
        super().__init__(message)
        self.resolution = resolution

class OrphanedOperationError(DriftError):
    """Error when orphaned operation causes issues."""
    
    def __init__(self, path: str, operation: str):
        message = f"Orphaned {operation} operation for {path}"
        resolution = f"Run 'dotfiles-sync clean --paths {path}' to resolve"
        super().__init__(message, resolution)
```

#### Guided Resolution
```python
def guide_drift_resolution(drift: ConfigDriftSummary) -> None:
    """Guide user through drift resolution."""
    console.print("[bold]Configuration Drift Resolution Guide[/bold]\n")
    
    if drift.orphaned_operations:
        console.print("📋 [yellow]Orphaned Operations[/yellow]")
        console.print("These operations are no longer in your configuration:")
        for op in drift.orphaned_operations[:3]:
            console.print(f"  • {op.dst_path}")
        
        console.print("\n  Recommended: Run 'dotfiles-sync clean --orphaned-only'")
    
    if drift.modified_operations:
        console.print("\n🔄 [blue]Modified Operations[/blue]")
        console.print("These operations have changed configuration:")
        for op in drift.modified_operations[:3]:
            console.print(f"  • {op.dst_path}")
        
        console.print("\n  Recommended: Run 'dotfiles-sync sync' to apply changes")
    
    if drift.new_operations:
        console.print("\n✨ [green]New Operations[/green]")
        console.print("These operations will be applied on next sync:")
        for op in drift.new_operations[:3]:
            console.print(f"  • {op.dst_path}")
        
        console.print("\n  Recommended: Run 'dotfiles-sync sync' to apply")
    
    console.print(f"\n[bold]Quick Fix:[/bold] Run 'dotfiles-sync reconcile' to handle everything")
```

**Deliverable**: Production-ready system with excellent user experience

---

## File Organization

### New Files
```
src/dotfiles_sync/
├── config_drift.py          # ConfigDriftDetector and related models
├── cleanup.py               # OrphanedOperationCleaner class
├── impact.py                # ImpactAnalyzer for safety analysis
├── conflict.py              # ConflictResolver for handling conflicts
└── migration.py             # ConfigMigrator for version migrations

tests/unit/
├── test_config_drift.py     # Drift detection unit tests
├── test_cleanup.py          # Cleanup operation tests
├── test_impact.py           # Impact analysis tests
└── test_conflict.py         # Conflict resolution tests

tests/integration/
├── docker_test_config_drift.py     # End-to-end drift scenarios
├── docker_test_cleanup.py          # Cleanup integration tests
└── docker_test_reconciliation.py   # Full reconciliation tests

docs/
└── CONFIGURATION_DRIFT.md   # User documentation for drift handling
```

### Enhanced Files
- `src/dotfiles_sync/state_database.py` - Add config drift methods
- `src/dotfiles_sync/cli.py` - New commands and enhancements
- `src/dotfiles_sync/models.py` - Add ConfigDriftResult and related models
- `src/dotfiles_sync/state_database_schema.sql` - Add config versioning tables

## Testing Strategy

### Unit Tests

#### Configuration Drift Detection
```python
def test_detect_orphaned_operations():
    """Test detection of orphaned operations."""
    # Setup: Create database with applied operations
    # Remove operation from config
    # Verify: Drift detector identifies orphaned operation

def test_detect_modified_operations():
    """Test detection of modified operations."""
    # Setup: Apply operation with specific config
    # Modify operation config (same dst, different settings)
    # Verify: Drift detector identifies modification

def test_detect_new_operations():
    """Test detection of new operations."""
    # Setup: Empty database
    # Add operations to config
    # Verify: Drift detector identifies new operations
```

#### Cleanup Operations
```python
def test_clean_orphaned_operations():
    """Test cleanup of orphaned operations."""
    # Setup: Create orphaned operations
    # Execute: Clean operations
    # Verify: Operations marked not current, files handled correctly

def test_cleanup_rollback():
    """Test rollback of cleanup operations."""
    # Setup: Clean operations
    # Execute: Rollback
    # Verify: Operations restored, files recovered
```

### Integration Tests

#### End-to-End Scenarios
```python
def test_config_change_workflow():
    """Test complete configuration change workflow."""
    # 1. Apply initial configuration
    # 2. Modify configuration file
    # 3. Detect drift
    # 4. Clean orphaned operations
    # 5. Apply new configuration
    # 6. Verify final state

def test_complex_drift_scenario():
    """Test complex drift with multiple types."""
    # Setup: Create scenario with:
    #   - Orphaned operations
    #   - Modified operations
    #   - New operations
    #   - Conflicting operations
    # Execute: Reconcile
    # Verify: All drift resolved correctly
```

#### Error Scenarios
```python
def test_cleanup_with_modified_files():
    """Test cleanup when files have been modified."""
    # Setup: Apply operations, modify files locally
    # Execute: Attempt cleanup
    # Verify: Appropriate warnings, safe handling

def test_concurrent_configuration_changes():
    """Test handling of concurrent config changes."""
    # Setup: Start operation
    # Modify config during operation
    # Verify: Appropriate error handling
```

### Test Scenarios Matrix

| Scenario | Initial State | Action | Expected Result |
|----------|--------------|--------|-----------------|
| Remove step from config | Step applied | Detect drift | Orphaned operation found |
| Modify step config | Step applied | Detect drift | Modified operation found |
| Add new step | No step | Detect drift | New operation found |
| Clean orphaned | Orphaned op exists | Clean | Operation marked not current |
| Clean with file removal | Orphaned op with file | Clean --remove-files | File removed, op cleaned |
| Rollback cleanup | Cleaned operations | Rollback | Operations restored |
| Reconcile all | Mixed drift | Reconcile | All drift resolved |

## Safety Considerations

### Core Safety Requirements
1. **Reversible cleanup**: All cleanup operations must be reversible via rollback
2. **Optional file removal**: Users control whether files are removed during cleanup
3. **Backward compatibility**: Existing workflows continue to work unchanged
4. **Dry-run support**: All destructive operations support preview mode
5. **Clear warnings**: Users understand impact before making changes
6. **Transactional operations**: All database changes are transactional
7. **Backup before modify**: Files backed up before any modifications
8. **Audit trail**: All operations logged in audit_log table

### Error Handling Strategy

#### Configuration Changes During Operations
```python
def handle_config_change_during_operation():
    # Detect config file modification time
    # Warn user about concurrent changes
    # Option to abort or continue
    # Lock file mechanism for critical operations
```

#### Database Corruption
```python
def handle_database_corruption():
    # Detect inconsistencies
    # Attempt automatic repair
    # Fallback to backup database
    # Clear error messages with recovery steps
```

#### Permission Issues
```python
def handle_permission_errors():
    # Check permissions before operations
    # Suggest fixes for common issues
    # Graceful degradation where possible
    # Clear error messages
```

## User Workflows

### Normal Workflow (After Config Changes)
```bash
# 1. Check what changed
$ dotfiles-sync check-config
Configuration drift detected: 3 operations affected

# 2. Preview cleanup impact
$ dotfiles-sync reconcile --preview
Will clean 2 orphaned operations
Will apply 1 new operation

# 3. Apply all changes
$ dotfiles-sync reconcile
✓ Reconciliation complete
```

### Conservative Workflow
```bash
# 1. See current drift status
$ dotfiles-sync status --config-drift
⚠ 2 orphaned operations detected

# 2. Apply only new operations (preserve orphaned)
$ dotfiles-sync sync
✓ Applied 1 new operation

# 3. Clean up later when ready
$ dotfiles-sync clean --orphaned-only
✓ Cleaned 2 orphaned operations
```

### Emergency Recovery
```bash
# Accidentally cleaned important operations
$ dotfiles-sync clean
✓ Cleaned 5 operations

# Realize mistake and restore
$ dotfiles-sync restore-orphaned abc123
✓ Restored 5 operations
```

### CI/CD Workflow
```bash
# In CI pipeline
$ dotfiles-sync validate --check-database
✓ Configuration valid
⚠ 1 orphaned operation detected

$ dotfiles-sync check-config --format json | jq '.total_drift'
1

# Fail build if drift exists
$ test $(dotfiles-sync check-config --format json | jq '.total_drift') -eq 0
```

## Performance Considerations

### Optimization Strategies
1. **Cache step hashes**: Avoid recalculating hashes for unchanged configs
2. **Batch database operations**: Group multiple operations in single transaction
3. **Lazy loading**: Only load full configs when needed
4. **Index optimization**: Ensure proper indexes on frequently queried columns
5. **Background cleanup**: Option to run cleanup in background
6. **Incremental drift detection**: Only check changed portions

### Scalability
- Support for large configurations (1000+ operations)
- Efficient handling of large file operations
- Parallel processing where possible
- Progress indicators for long operations

## Migration Path

### For Existing Users
1. **Phase 1-2**: No user impact, new features are opt-in
2. **Phase 3**: New commands available, old workflow unchanged
3. **Phase 4-5**: Enhanced safety, still backward compatible
4. **Phase 6**: Automation available but optional

### Breaking Changes
- None planned - all changes are additive
- Existing commands maintain current behavior
- New features accessed via new flags/commands
- Database schema changes are backward compatible

## Success Metrics

### Technical Metrics
- Zero breaking changes to existing functionality
- 100% test coverage for new code
- Performance: Drift detection < 1 second for typical configs
- Database migration success rate: 100%

### User Experience Metrics
- Clear error messages with resolution steps
- Drift detection accuracy: No false positives
- Cleanup safety: Zero data loss incidents
- User documentation completeness

## Documentation Requirements

### User Documentation
- **Getting Started**: Quick guide to configuration drift
- **Commands Reference**: Detailed documentation of new commands
- **Workflows**: Common scenarios and solutions
- **Troubleshooting**: Common issues and resolutions
- **Migration Guide**: For users with existing setups

### Developer Documentation
- **Architecture**: System design and component interaction
- **API Reference**: Public interfaces and methods
- **Testing Guide**: How to test drift detection
- **Contributing**: Guidelines for contributing to drift detection

## Summary

This implementation plan transforms the configuration synchronization gap from **"no way to handle config changes"** to **"comprehensive configuration lifecycle management"**.

### Key Benefits
- **Visibility**: Users can see configuration drift
- **Control**: Users decide when and how to reconcile
- **Safety**: All operations are reversible and safe
- **Automation**: Support for automated workflows
- **Compatibility**: No breaking changes to existing functionality

### Phased Delivery
Each phase delivers incremental value:
1. **Foundation**: Core drift detection capability
2. **Visibility**: Users can see configuration issues
3. **Resolution**: Tools to fix configuration drift
4. **Safety**: Production-ready safety features
5. **Scalability**: Advanced database capabilities
6. **Automation**: Streamlined user experience

The solution maintains the system's safety-first approach while providing the missing capability to synchronize `state.db` with `dotfiles.toml` changes, ensuring users can confidently manage their dotfiles configurations over time.