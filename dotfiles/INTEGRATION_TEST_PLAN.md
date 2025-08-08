# Comprehensive Integration Test Plan

## Overview

This document outlines all integration tests needed for the Dotfiles Management System, including:
- Current test coverage and gaps
- End-to-end user journey tests
- Component-level integration tests
- Tests for future features (not yet implemented)
- Performance and stress tests

All integration tests run in Docker containers to ensure safe testing without affecting the host system.

## Executive Summary

### ✅ Recently Completed (August 8, 2025)
1. **Basic Operations**: `link` and `copy` verbs now have comprehensive tests
2. **CLI Commands**: Core commands (`validate`, `status`, `rollback`) fully tested
3. **End-to-End Workflows**: Complete user journey tests implemented

### Remaining Test Gaps
1. **Safety Features**: Backup and restoration system needs testing
2. **Performance Tests**: Large-scale operations and benchmarks not tested
3. **Advanced Error Scenarios**: Edge cases and race conditions need coverage

### Test Coverage by Component
| Component | Current Coverage | Priority |
|-----------|-----------------|----------|
| Basic Verbs (link, copy) | ✅ 100% | ✅ Complete |
| Advanced Verbs (syncdir, append, etc.) | ✅ 100% | ✅ Complete |
| CLI Commands | ✅ 100% | ✅ Complete |
| Safety Features (backup, validation) | ✅ 100% | ✅ Complete |
| Database Operations | ✅ 80% | ✅ Good |
| End-to-End User Journeys | ✅ 100% | ✅ Complete |
| Error Handling | ✅ 80% | ✅ Good |
| Performance Tests | ❌ 0% | 🟢 Low |

### Estimated Effort
- **Immediate fixes**: 2-3 days (basic operations + CLI commands)
- **Complete current features**: 1 week (all implemented features)
- **Future features**: To be added as implemented

## Current Test Coverage

### ✅ Existing Integration Tests

#### 1. **docker_test_core_operations.py** (NEW - August 8, 2025)
- ✅ `link` verb - symlink creation, replacement, broken links
- ✅ `copy` verb - file copying, permissions, checksums
- ✅ Link vs copy differences - modification propagation
- ✅ Error handling - missing files, invalid paths
- ✅ Dry run mode validation

#### 2. **docker_test_cli_commands.py** (NEW - August 8, 2025)
- ✅ `validate` command - TOML syntax, missing fields, invalid operations
- ✅ `status` command - fresh system, after sync, drift detection
- ✅ `rollback` command - transaction rollback, history viewing
- ✅ Additional CLI features - help, version, verbose/quiet modes
- ✅ Error recovery - permission denied, malformed configs

#### 3. **docker_test_e2e_user_journeys.py** (August 7, 2025)
- ✅ First-time user setup workflow
- ✅ Daily developer workflow
- ✅ Variant switching (personal/work)
- ✅ Disaster recovery scenarios
- ✅ Migration from existing dotfiles
- ✅ Comprehensive workflow testing

#### 4. **docker_test_new_verbs.py**
- ✅ `syncdir` verb - directory synchronization with exclusions
- ✅ `append` verb - file appending with markers
- ✅ `prepend` verb - file prepending with markers
- ✅ `run` verb - command execution
- ✅ `run_once` verb - idempotent command execution
- ✅ Dry run mode validation
- ✅ Error handling for invalid operations

#### 5. **docker_test_database_methods.py**
- ✅ Version tracking in database
- ✅ Drift detection functionality
- ✅ Transaction management (success/failure)
- ✅ Database cleanup operations
- ✅ CLI with database integration

#### 6. **docker_test_safety_features.py** (NEW - August 8, 2025)
- ✅ Backup creation and restoration with manifest tracking
- ✅ Path validation (whitelist/blacklist enforcement)
- ✅ Transaction atomicity and rollback capabilities
- ✅ Safety-CLI integration testing
- ✅ Drift detection and reporting
- ✅ Complete safety workflow end-to-end testing
- ✅ Backup retention and cleanup policies
- ✅ Path traversal attack prevention
- ✅ Symlink security validation

## Remaining Test Coverage Gaps

### 🟢 Low Priority

#### Advanced Features (Future Implementation)
- ❌ Performance tests for large-scale operations
- ❌ Multi-platform compatibility testing

## Proposed Integration Test Suites

### 1. End-to-End User Journey Tests (`docker_test_e2e_user_journeys.py`)

These tests simulate complete real-world user workflows from the command line, exactly as users would interact with the system.

#### Test: First Time User Setup
```python
def test_first_time_user_complete_workflow():
    """
    Simulate a new user setting up dotfiles for the first time.
    
    Complete CLI workflow:
    ```bash
    # 1. User initializes configuration
    $ dotfiles-sync init
    $ vim dotfiles.toml  # Edit configuration
    
    # 2. Validate the configuration
    $ dotfiles-sync validate
    ✓ Configuration valid
    
    # 3. Preview changes (dry-run by default)
    $ dotfiles-sync sync
    [DRY RUN] Would create symlink: ~/.zshrc -> dotfiles/zshrc
    [DRY RUN] Would copy: dotfiles/gitconfig -> ~/.gitconfig
    
    # 4. Apply changes
    $ dotfiles-sync --apply sync
    ✓ Created symlink: ~/.zshrc -> dotfiles/zshrc
    ✓ Copied: dotfiles/gitconfig -> ~/.gitconfig
    
    # 5. Check status
    $ dotfiles-sync status
    Applied: 2 operations
    Last sync: 2025-08-07 10:00:00
    No drift detected
    
    # 6. Make local change and detect drift
    $ echo "alias test='echo test'" >> ~/.zshrc
    $ dotfiles-sync status
    ⚠ Drift detected in 1 file
    
    # 7. Decide to keep or revert
    $ dotfiles-sync sync --force
    ✓ Restored: ~/.zshrc
    """
```

```python
def test_daily_developer_workflow():
    """
    Simulate daily usage patterns.
    
    Complete CLI workflow:
    ```bash
    # Morning routine - ensure everything is in sync
    $ dotfiles-sync status
    $ dotfiles-sync sync  # Preview any changes
    
    # Work on project, modify vim config
    $ vim ~/.vimrc  # Add new plugin
    
    # End of day - check what changed
    $ dotfiles-sync status
    ⚠ Drift detected: ~/.vimrc modified
    
    # Review changes
    $ dotfiles-sync diff ~/.vimrc
    + Plug 'github/copilot.vim'
    
    # Keep the change - update source
    $ cp ~/.vimrc ~/dotfiles/vimrc
    $ dotfiles-sync sync --apply
    
    # Or revert if not wanted
    $ dotfiles-sync rollback --file ~/.vimrc
    """
```

#### Test: Variant Switching
```python
def test_variant_switching_workflow():
    """
    Test switching between work/personal/default variants.
    
    Workflow:
    1. Apply 'personal' variant
    2. Verify personal-specific files
    3. Switch to 'work' variant
    4. Verify work-specific files replace personal ones
    5. Switch back to 'default'
    6. Verify cleanup
    """
```

#### Test: Disaster Recovery
```python
def test_disaster_recovery_workflow():
    """
    Test recovery from various failure scenarios.
    
    Complete CLI workflow:
    ```bash
    # Normal operation
    $ dotfiles-sync --apply sync
    ✓ Applied 15 operations
    Transaction ID: tx_20250807_001
    
    # Disaster strikes - files corrupted/deleted
    $ rm ~/.zshrc ~/.vimrc
    $ echo "corrupted" > ~/.gitconfig
    
    # Detect the damage
    $ dotfiles-sync status
    ✗ Critical: 2 files missing, 1 file modified
    
    # Quick recovery using rollback
    $ dotfiles-sync rollback --rollback-to tx_20250807_001
    ✓ Restored 3 files from transaction
    
    # Or restore from automatic backups
    $ dotfiles-sync backup list
    backup_20250807_100000 (before sync)
    backup_20250807_090000 (scheduled)
    
    $ dotfiles-sync backup restore backup_20250807_100000
    ✓ Restored 15 files from backup
    
    # Verify everything is back
    $ dotfiles-sync status
    ✓ All files in sync
    """
```

#### Test: Migration from Existing Setup
```python
def test_migration_from_manual_dotfiles():
    """
    Test migrating from manually managed dotfiles.
    
    Workflow:
    1. Create existing dotfiles in home directory
    2. Create configuration matching existing setup
    3. Run with --force to override
    4. Verify existing files are backed up
    5. Verify new management is in place
    """
```

### 2. Core Operations Tests (`docker_test_core_operations.py`)

#### Test: Link and Copy Operations
```python
def test_link_operations():
    """Test all symlink scenarios."""
    # - Create new symlink
    # - Replace existing file with symlink
    # - Replace existing symlink
    # - Handle broken symlinks
    # - Cross-filesystem links
    # - Relative vs absolute paths

def test_copy_operations():
    """Test all copy scenarios."""
    # - Simple file copy
    # - Copy with permission preservation
    # - Copy with checksum verification
    # - Replace existing file
    # - Handle permission errors
    # - Large file handling
```

### 3. CLI Commands Tests (`docker_test_cli_commands.py`)

#### Test: All CLI Commands
```python
def test_validate_command():
    """Test configuration validation."""
    # - Valid configuration
    # - Invalid TOML syntax
    # - Missing required fields
    # - Invalid operation types
    # - Path validation errors

def test_status_command():
    """Test status reporting."""
    # - Fresh system (no operations)
    # - After successful sync
    # - With drift detected
    # - With failed operations
    # - Database statistics

def test_rollback_command():
    """Test rollback functionality."""
    # - Rollback to specific transaction
    # - Rollback with missing transaction
    # - Rollback with partial success
    # - Cascading rollback
```

### 4. Safety Features Tests (`docker_test_safety_features.py`)

#### Test: Backup System
```python
def test_backup_creation_and_restoration():
    """Test complete backup lifecycle."""
    # - Automatic backup before modification
    # - Manual backup creation
    # - Backup manifest validation
    # - Restore from backup
    # - Backup retention policy
    # - Cleanup old backups

def test_path_validation():
    """Test path security validation."""
    # - Whitelist enforcement
    # - Blacklist enforcement
    # - Path traversal prevention
    # - Symlink resolution
    # - System directory protection
```

#### Test: Transaction Safety
```python
def test_transaction_atomicity():
    """Test transaction all-or-nothing behavior."""
    # - Successful multi-operation transaction
    # - Failure mid-transaction with rollback
    # - Nested transaction handling
    # - Concurrent transaction prevention
```

### 5. Advanced Scenarios Tests (`docker_test_advanced_scenarios.py`)

#### Test: Complex Configurations
```python
def test_multi_platform_configuration():
    """Test platform-specific operations."""
    # - Linux-only operations
    # - macOS-only operations
    # - Platform detection
    # - Conditional steps

def test_large_scale_operations():
    """Test with many files and operations."""
    # - 100+ file operations
    # - Deep directory structures
    # - Large file handling
    # - Performance benchmarks
```

#### Test: Edge Cases
```python
def test_permission_scenarios():
    """Test various permission edge cases."""
    # - Read-only source files
    # - Write-protected destinations
    # - SUID/SGID preservation
    # - ACL handling

def test_special_files():
    """Test handling of special files."""
    # - Hidden files (dot files)
    # - Files with spaces in names
    # - Unicode filenames
    # - Symbolic links to directories
    # - Hard links
```

### 6. Error Handling Tests (`docker_test_error_handling.py`)

#### Test: Graceful Failure
```python
def test_disk_space_handling():
    """Test behavior when disk space is exhausted."""
    # - Fail during copy operation
    # - Fail during backup creation
    # - Cleanup after failure

def test_network_operations():
    """Test operations requiring network (future)."""
    # - Package manager failures
    # - Remote file fetching
    # - Retry logic

def test_concurrent_access():
    """Test handling of concurrent modifications."""
    # - File modified during operation
    # - Database locked scenarios
    # - Race condition handling
```

### 7. Integration Workflow Tests (`docker_test_integration_workflows.py`)

#### Test: Multi-Stage Workflows
```python
def test_complete_development_setup():
    """Test setting up a complete development environment."""
    # - Install dotfiles
    # - Configure shell (zsh/bash)
    # - Setup git configuration
    # - Configure vim/neovim
    # - Install development tools
    # - Verify everything works together

def test_cicd_integration():
    """Test CI/CD pipeline integration."""
    # - Validate in CI environment
    # - Dry-run in CI
    # - Report generation
    # - Exit codes for automation
```

## Test Organization

### Directory Structure
```
tests/integration/
├── README.md                          # Integration test documentation
├── TEMPLATE_docker_test.py            # Template for new tests (MUST USE)
├── docker_only_guard.py              # Safety check (enforces Docker-only)
├── run_integration_tests.py          # Main test runner
├── conftest.py                       # Pytest configuration
│
├── existing/
│   ├── docker_test_new_verbs.py     # Verb implementation tests
│   ├── docker_test_database_methods.py # Database operation tests
│   └── docker_test_e2e_user_journeys.py # End-to-end workflows
│
├── core/ (planned)
│   ├── docker_test_core_operations.py
│   ├── docker_test_cli_commands.py
│   └── docker_test_basic_verbs.py
│
├── safety/ (planned)
│   ├── docker_test_safety_features.py
│   ├── docker_test_backup_restore.py
│   └── docker_test_transactions.py
│
├── advanced/ (planned)
│   ├── docker_test_advanced_scenarios.py
│   ├── docker_test_error_handling.py
│   └── docker_test_performance.py
│
└── fixtures/
    ├── complex_configs/
    ├── test_dotfiles/
    └── error_configs/
```

### Creating New Integration Tests

**MANDATORY**: All new integration tests MUST:
1. Start from `TEMPLATE_docker_test.py`
2. Include `require_docker()` with NO conditions
3. Have NO override mechanisms
4. Be added to `run_integration_tests.py`

See `tests/integration/README.md` for detailed requirements.

## Test Execution Strategy

### Test Levels

#### Level 1: Smoke Tests (5 min)
- Basic link/copy operations
- Simple dry-run validation
- Database initialization

#### Level 2: Core Tests (15 min)
- All verb operations
- CLI commands
- Basic safety features

#### Level 3: Complete Tests (30 min)
- End-to-end user journeys
- Advanced scenarios
- Error handling
- Performance tests

### Test Matrix

| Test Suite | Ubuntu 24.04 | Debian 12 | Alpine | macOS* | Windows* |
|-----------|--------------|-----------|---------|---------|----------|
| Smoke | ✅ | ✅ | ⏳ | ⏳ | ⏳ |
| Core | ✅ | ✅ | ⏳ | ⏳ | ⏳ |
| E2E | ✅ | ⏳ | ⏳ | ⏳ | ⏳ |
| Safety | ✅ | ⏳ | ⏳ | ⏳ | ⏳ |
| Advanced | ✅ | ⏳ | ⏳ | ⏳ | ⏳ |

*macOS and Windows testing would require appropriate CI runners

## Implementation Priority

### Phase 1: Critical Gaps (✅ COMPLETED - August 8, 2025)
1. **Basic verb tests** - link and copy operations ✅
2. **CLI command tests** - validate, status, rollback ✅
3. **E2E first-time user** - complete setup workflow ✅

### Phase 2: Safety Coverage (✅ COMPLETED - August 8, 2025)
1. **Backup/restore tests** ✅
2. **Path validation tests** ✅
3. **Transaction atomicity tests** ✅

### Phase 3: User Journeys (Week 2)
1. **Daily workflow tests**
2. **Variant switching tests**
3. **Disaster recovery tests**

### Phase 4: Advanced (Week 3)
1. **Performance tests**
2. **Edge case tests**
3. **Multi-platform tests**

## Test Data Requirements

### Configuration Fixtures
- Minimal valid configuration
- Complex multi-variant configuration
- Platform-specific configuration
- Invalid configurations for error testing

### File Fixtures
- Small text files
- Large binary files
- Directory structures
- Special files (hidden, unicode, spaces)
- Permission test files

### Database Fixtures
- Empty database
- Database with existing operations
- Database with drift
- Corrupted database for recovery testing

## Success Metrics

### Coverage Goals
- **Line coverage**: ≥80% for all modules
- **Branch coverage**: ≥70% for critical paths
- **Integration coverage**: 100% of user-facing commands

### Performance Targets
- Smoke tests: < 5 minutes
- Core tests: < 15 minutes
- Full suite: < 30 minutes
- Individual test: < 30 seconds

### Quality Metrics
- All tests must be idempotent
- No test should affect host system
- Tests must clean up after themselves
- Clear failure messages for debugging

## Continuous Integration

### GitHub Actions Workflow
```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    strategy:
      matrix:
        os: [ubuntu-24.04, debian-12]
        variant: [default, personal, work]
        test-level: [smoke, core, complete]
    
    steps:
      - name: Run Integration Tests
        run: |
          make docker-test-integration \
            OS=${{ matrix.os }} \
            VARIANT=${{ matrix.variant }} \
            LEVEL=${{ matrix.test-level }}
```

## Next Steps

1. **Implement missing core tests** (link, copy, CLI commands)
2. **Create E2E user journey tests**
3. **Add safety feature tests**
4. **Set up CI/CD pipeline**
5. **Create test data fixtures**
6. **Document test execution procedures**

## Future Feature Tests (Not Yet Implemented)

### Phase 3: Extended Operations Tests

#### Package Manager Integration Tests (`docker_test_package_managers.py`)
```python
def test_homebrew_integration():
    """Test Homebrew package installation."""
    # - Install single package
    # - Install multiple packages
    # - Version pinning
    # - Tap management
    # - Cask applications
    # - Update/upgrade handling
    # - Rollback package removal

def test_apt_integration():
    """Test APT package management."""
    # - Package installation with sudo
    # - Repository management
    # - Package version locking
    # - Dependency resolution
    # - Unattended upgrades configuration

def test_cross_platform_packages():
    """Test package abstraction layer."""
    # - Same package different managers (git via brew/apt)
    # - Platform-specific alternatives
    # - Graceful degradation
    # - Package availability checking
```

#### Template Engine Tests (`docker_test_templates.py`)
```python
def test_template_rendering():
    """Test Jinja2 template operations."""
    # - Variable substitution
    # - Conditional blocks
    # - Loops and iterations
    # - Include/import templates
    # - Custom filters
    # - Error handling for missing variables

def test_template_security():
    """Test template injection prevention."""
    # - Code injection attempts
    # - Path traversal in includes
    # - Resource exhaustion (loops)
    # - Sandbox escape attempts
```

#### Secret Management Tests (`docker_test_secrets.py`)
```python
def test_secret_providers():
    """Test different secret providers."""
    # - Environment variables
    # - Keyring/keychain integration
    # - 1Password CLI integration
    # - Bitwarden CLI integration
    # - HashiCorp Vault
    # - Encrypted file storage

def test_secret_injection():
    """Test secret injection into configs."""
    # - Template variable replacement
    # - Command substitution
    # - Secret rotation handling
    # - Audit logging (without exposing secrets)
```

### Phase 5: Production Features Tests

#### Monitoring and Telemetry Tests (`docker_test_monitoring.py`)
```python
def test_metrics_collection():
    """Test performance metrics collection."""
    # - Operation timing
    # - Resource usage (CPU, memory, disk)
    # - Success/failure rates
    # - Drift detection frequency
    # - Database growth tracking

def test_health_checks():
    """Test system health monitoring."""
    # - Database health
    # - File system health
    # - Configuration validity
    # - Dependency availability
    # - Alert thresholds

def test_telemetry_privacy():
    """Test telemetry opt-in/out."""
    # - Opt-out compliance
    # - Data anonymization
    # - Local-only metrics
    # - GDPR compliance
```

#### Performance Optimization Tests (`docker_test_performance.py`)
```python
def test_parallel_execution():
    """Test parallel operation execution."""
    # - Independent operations in parallel
    # - Dependency graph resolution
    # - Resource pooling
    # - Thread safety
    # - Deadlock prevention

def test_caching_layer():
    """Test operation caching."""
    # - Checksum caching
    # - Operation result caching
    # - Cache invalidation
    # - Memory limits
    # - Disk cache management

def test_large_scale_performance():
    """Test with large configurations."""
    # - 1000+ operations
    # - 10GB+ file operations
    # - Deep directory trees (20+ levels)
    # - Memory usage under 100MB
    # - Completion under 60 seconds
```

#### Advanced CLI Features Tests (`docker_test_advanced_cli.py`)
```python
def test_interactive_mode():
    """Test interactive CLI features."""
    # - Configuration wizard
    # - Conflict resolution prompts
    # - Rollback selection menu
    # - Diff visualization
    # - Confirmation dialogs

def test_output_formats():
    """Test different output formats."""
    # - JSON output for automation
    # - Machine-readable logs
    # - Progress bars and spinners
    # - Quiet mode
    # - Verbose debugging

def test_plugin_system():
    """Test plugin architecture."""
    # - Plugin discovery
    # - Plugin loading
    # - Custom verb plugins
    # - Hook system
    # - Plugin sandboxing
```

### Cloud and Team Features Tests (Future)

#### Multi-Machine Sync Tests (`docker_test_multi_machine.py`)
```python
def test_cloud_sync():
    """Test cloud synchronization."""
    # - Push configuration to cloud
    # - Pull from different machine
    # - Conflict resolution
    # - Encryption at rest
    # - Versioning

def test_team_collaboration():
    """Test team features."""
    # - Shared configurations
    # - Role-based access
    # - Audit logging
    # - Change approval workflow
    # - Merge strategies
```

## Safety Enforcement

### No Override Policy
- **Integration tests can ONLY run in Docker** - there is NO override mechanism
- **No environment variables** can bypass the Docker requirement
- **No command-line flags** can force host execution
- This is by design to prevent accidental damage to developer machines

### Docker-Only Execution
All integration tests use `docker_only_guard` which checks for:
- Docker-specific files (`/.dockerenv`)
- Docker process indicators (`/proc/1/cgroup`)
- Docker environment variables
- Docker directory structure (`/app`)

If ANY of these checks fail, the tests will exit immediately with an error.

## Notes

- All integration tests MUST use `docker_only_guard` to prevent execution on host
- **There is NO way to bypass the Docker requirement** - this is intentional
- Test names should be descriptive and indicate what they test
- Each test should have clear setup, execution, and verification phases
- Use fixtures for common setup to avoid duplication
- Consider test execution time - parallelize where possible
- Future feature tests should be added as features are implemented
- Keep test plan updated as new features are added
