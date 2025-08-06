# Claude Memory - Dotfiles Management System

## ⚠️ CRITICAL SAFETY WARNINGS ⚠️

### **DO NOT RUN SYNC COMMANDS DURING DEVELOPMENT**
- **NEVER run `uv run dotfiles-sync sync` or `dotfiles-sync --apply sync` during development**
- **These commands will modify real dotfiles on the host system**
- **Use Docker testing instead: `make docker-test` or `make docker-test-all`**
- **Only run sync commands in isolated Docker containers**

### **Safe Development Commands**
- ✅ `uv run dotfiles-sync --version` - Safe
- ✅ `uv run dotfiles-sync validate` - Safe  
- ✅ `uv run dotfiles-sync --help` - Safe
- ✅ `make docker-test` - Safe (uses Docker isolation)
- ✅ `make test` - Safe (unit tests only)
- ❌ `uv run dotfiles-sync sync` - **DANGEROUS** (modifies real dotfiles)
- ❌ `uv run dotfiles-sync --apply sync` - **VERY DANGEROUS**

## Project Overview

This is a **safety-first, declarative dotfiles management system** written in Python with the following key characteristics:

- **Phase-based implementation** (currently implementing Phase 1: Core MVP)
- **Pydantic v2 models** for type-safe configuration
- **SQLite state tracking** with transaction support and rollback
- **Docker-based testing** for safe development
- **TOML configuration** (dotfiles.toml) similar to Cargo.toml

## Current Implementation Status

### ✅ Phase 0: Foundation (COMPLETED)
- Project structure with uv package management
- TOML configuration parsing with Pydantic validation
- SQLite state database with comprehensive schema
- CLI with Click framework and Rich output
- 39 unit tests with 72% coverage
- Development tooling (Makefile, ruff, mypy, ty)

### 🚧 Phase 1: Core MVP (IN PROGRESS)
- **Verb system**: Base class and link/copy operations implemented
- **Transaction support**: Full rollback capabilities
- **Docker testing**: Safe isolated testing environment
- **Current focus**: Fixing integration bugs and testing

### ⏳ Future Phases
- Phase 2: Safety Layer (backups, validation, drift detection)
- Phase 3: Extended Operations (package managers, templates, secrets)
- Phase 4: Testing Infrastructure (CI/CD, performance benchmarks)
- Phase 5: Production Readiness (optimization, documentation)

## Architecture

### Core Components
```
src/dotfiles_sync/
├── cli.py              # Click-based command interface
├── config.py           # TOML configuration loading
├── context.py          # Execution context management
├── models.py           # Pydantic v2 data models
├── database.py         # Database interface wrapper
└── state_database.py   # Full SQLite implementation

src/verbs/
├── __init__.py         # Verb registry and executor
├── base.py             # Abstract Verb base class
├── link.py             # Symlink operations
└── copy.py             # File copy operations
```

### Key Models (Pydantic v2)
- `DotfilesConfig`: Root configuration with package, safety, security, steps
- `StepConfig`: Individual operation configuration
- `ExecutionContext`: Runtime context (dry_run, variant, system_info)
- `OperationResult`: Operation outcome with rollback data
- `TransactionContext`: Database transaction management

## Development Workflow

### Safe Testing Process
1. **Unit Tests**: `make test` (safe, no system modification)
2. **Type Checking**: `make ty` (fast) or `make typecheck` (comprehensive)  
3. **Linting**: `make lint` or `make quick-check`
4. **Docker Testing**: `make docker-test` (safe, isolated environment)
5. **Integration Testing**: `make docker-test-all` (all variants)

### Docker Testing Commands
- `make docker-test` - Single test with default variant
- `make docker-test-all` - All variants and platforms
- `make docker-test-variant` - Interactive variant selection
- `make docker-clean` - Clean up Docker artifacts

### Configuration Files
- `dotfiles.toml` - Example production configuration
- `test-config.toml` - Generated in Docker for safe testing
- `pyproject.toml` - Python project configuration with uv

## Important Implementation Notes

### Current Bugs (Being Fixed)
1. **ExecutionContext._config missing**: Needs config reference for security validation
2. **OperationResult.operation_id**: Missing required field in Pydantic model
3. **Database transaction methods**: Interface mismatch between TransactionContext and StateDatabase

### Safety Features Implemented
- **Dry-run by default**: All operations preview changes first
- **Backup system**: Automatic backups before modifications  
- **Transaction rollback**: Complete undo capability
- **Path validation**: Security whitelist/blacklist support
- **Checksum verification**: File integrity validation
- **State database**: Persistent operation tracking

### Configuration Schema
The system uses TOML configuration with these main sections:
- `[package]` - Project metadata
- `[safety]` - Safety settings (dry_run_default, backup_retention_days, etc.)
- `[security]` - Path whitelists/blacklists, safe commands
- `[[step]]` - Array of operations (link, copy, etc.)

### Development Tools
- **uv**: Fast Python package management
- **ruff**: Linting and formatting  
- **mypy**: Static type checking
- **ty**: Fast type checking (Rust-based)
- **pytest**: Testing framework with coverage
- **Rich**: CLI output formatting
- **Click**: Command-line interface framework

## Testing Strategy

### Unit Tests (Safe)
- 39 tests covering core functionality
- 72% overall coverage, 94% for models
- Tests Pydantic validation, path handling, context management
- Run with: `make test`

### Integration Tests (Docker Only)
- **Phase 1 MVP verification**
- Tests link and copy operations in isolation
- Verifies dry-run safety and actual application
- Multiple variants (default, personal, work)
- Multiple platforms (Ubuntu, Debian)

### Test Files Structure
```
tests/
├── unit/
│   ├── test_cli.py       # CLI command testing
│   ├── test_config.py    # Configuration parsing
│   └── test_context.py   # Context management
├── fixtures/
│   └── test_config.toml  # Test configuration
└── integration/          # Docker integration tests
```

## Common Development Tasks

### Adding New Operations
1. Create new verb class in `src/verbs/`
2. Inherit from `Verb` base class
3. Implement `validate()`, `apply()`, `rollback()` methods
4. Register in `VerbRegistry` 
5. Add to `OperationType` enum in models.py
6. Write unit tests
7. Test in Docker environment

### Configuration Changes
- Modify Pydantic models in `models.py`
- Update validation logic as needed
- Update example `dotfiles.toml`
- Run `make validate` to test parsing

### Database Schema Changes
- Modify `state_database_schema.sql`
- Update `StateDatabase` class methods
- Consider migration strategy for existing databases

## Dependencies

### Production
- `click>=8.2.1` - CLI framework
- `rich>=14.1.0` - Terminal formatting
- `pydantic>=2.11.0` - Data validation
- `pydantic-settings` - Configuration management

### Development
- `pytest>=8.4.1` - Testing
- `pytest-cov>=5.0.0` - Coverage reporting
- `mypy>=1.13.0` - Static type checking  
- `ruff>=0.8.0` - Linting and formatting
- `ty>=0.0.1a16` - Fast type checking

## Files to Never Modify Directly During Development
- Real `~/.zshrc`, `~/.gitconfig`, or any dotfiles in home directory
- Any files outside the project repository
- System configuration files

## Emergency Procedures

### If Sync Command Was Run Accidentally
1. **Check backups**: `~/.local/state/dotfiles/backups/`
2. **Use rollback**: `dotfiles-sync rollback --rollback-to <transaction_id>`
3. **Check state database**: `dotfiles-sync status`
4. **Manual restoration** from backups if needed

### If Development Environment is Broken
1. **Clean Docker**: `make docker-clean`
2. **Reset Python environment**: `uv sync --reinstall`
3. **Run tests**: `make test`
4. **Validate configuration**: `make validate`

## Best Practices

1. **Always test in Docker first**
2. **Use dry-run mode by default**
3. **Commit frequently with descriptive messages**
4. **Run `make quick-check` before committing**
5. **Update tests when adding features**
6. **Document safety considerations for new operations**
7. **Keep CLAUDE.md updated with important findings**

---

**Last Updated**: Phase 1 development - Docker testing infrastructure complete
**Next Priority**: Fix integration bugs and complete Phase 1 MVP testing