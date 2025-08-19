# Unimplemented and Incomplete Features Analysis

## Overview

This document analyzes the gap between the comprehensive specification in `spec.md` and the current implementation of the Dotfiles Management System. The analysis covers missing verbs, incomplete CLI features, and architectural components that are defined in the spec but not yet implemented.

**Analysis Date**: August 8, 2025  
**Spec File**: `spec.md` (1,184 lines)  
**Current Implementation**: Phases 0-2 complete, Phase 3 in progress

## Summary

The current implementation is **feature-complete for core functionality** (linking, copying, basic operations) but **missing advanced features** for package management, templating, secrets, and extensibility.

### Implementation Status
- ✅ **Core Operations**: 7/7 basic verbs implemented
- ❌ **Extended Operations**: 0/6 advanced verbs implemented  
- ✅ **Safety Features**: 100% implemented (backup, validation, transactions)
- ✅ **CLI Core Commands**: 100% implemented (sync, status, validate, rollback, diff, backup)
- ❌ **Plugin Architecture**: 0% implemented
- ❌ **Advanced Bootstrap**: Partial implementation

---

## Unimplemented Verbs (6 missing)

The `OperationType` enum in `src/dotfiles_sync/models.py` defines 11 operation types, but only 7 are implemented in `src/verbs/__init__.py`.

### Package Manager Integration
| Verb | Status | Description | Priority |
|------|--------|-------------|----------|
| `brew_install` | ❌ Not implemented | Homebrew package installation for macOS | **High** |
| `apt_install` | ❌ Not implemented | APT package management for Debian/Ubuntu | **High** |
| `dnf_install` | ❌ Not implemented | DNF package management for Red Hat/Fedora | **Medium** |

**Spec Requirements** (lines 250-255):
- Version pinning support
- Platform-specific installation
- Sudo awareness for system packages
- Installation verification
- Rollback support (package removal)

### Advanced Operations
| Verb | Status | Description | Priority |
|------|--------|-------------|----------|
| `template` | ❌ Not implemented | Jinja2 template rendering with variable substitution | **High** |
| `secret_ref` | ❌ Not implemented | External secret management (env, keychain, 1password) | **Medium** |
| `vscode_extensions` | ❌ Not implemented | VS Code extension installation and management | **Medium** |

**Template System Requirements** (spec line 250):
- Jinja2 template engine with sandboxing
- Variable substitution from context
- Security: injection prevention
- Template include/import support

**Secret Management Requirements**:
- Multiple providers: environment, keychain, 1password, lastpass
- Runtime injection only (never stored)
- Audit logging without exposing secrets

**VS Code Extensions Requirements** (spec lines 189-194):
- Extension installation verification
- Version management
- Cross-platform compatibility

---

## Missing Architecture Components

### 1. Plugin System (❌ Not Implemented)
**Spec Evidence**: Lines 1136-1147 show `asdf_plugins` example

The spec demonstrates a plugin architecture where custom verbs can be implemented:

```toml
[[step]]
op = "asdf_plugins"  
plugins = ["nodejs", "python", "golang"]
```

**Missing Components**:
- Plugin discovery mechanism
- Plugin loading system
- Custom verb registration
- Plugin sandboxing and validation
- Plugin documentation system

### 2. Advanced Bootstrap System (⚠️ Partially Implemented)
**Spec Evidence**: Lines 1058-1114 show comprehensive bootstrap script

The spec defines a sophisticated bootstrap process with:

**Missing Features**:
- Cross-platform binary installation
- Checksum verification for downloads
- Retry logic and error recovery
- XDG directory compliance
- Platform detection and mapping
- Virtual environment management
- Advanced CLI flag support (`--repo`, `--variant`)

### 3. Configuration Generation/Scaffolding (❌ Not Implemented)
While not explicitly detailed in the spec, the architecture suggests:
- Configuration templates
- Interactive setup wizards  
- Migration tools from other dotfile systems
- Configuration validation and suggestion system

---

## Incomplete CLI Features

### Missing CLI Options
Based on spec analysis and bootstrap script examples:

| Feature | Status | Description | Evidence |
|---------|--------|-------------|----------|
| `--repo` flag | ❌ Missing | Specify dotfiles repository path | Spec line 1103 |
| `--list-backups` | ⚠️ Partial | Implemented as `backup list` subcommand | Spec line 1090 |
| Interactive mode | ❌ Missing | Configuration wizards and prompts | Architecture inference |
| Plugin commands | ❌ Missing | Management of plugin system | Architecture requirement |

### Advanced Backup/Restore Features
Current implementation has basic backup/restore but spec suggests:
- Backup compression and metadata
- Remote backup storage  
- Backup retention policies (partially implemented)
- Disaster recovery workflows

---

## Implementation Completeness by Area

### ✅ Fully Implemented (100%)
- **Core Verbs**: link, copy, syncdir, append, prepend, run, run_once
- **Safety Features**: backup system, path validation, transaction management
- **Database**: SQLite state tracking, transaction logs, drift detection
- **CLI Core**: sync, status, validate, rollback, diff, backup subcommands
- **Security**: whitelist/blacklist paths, command validation, checksum verification
- **Testing**: Comprehensive Docker test suite with 100% coverage of implemented features

### ⚠️ Partially Implemented (60-80%)
- **Bootstrap System**: Basic functionality exists, missing advanced features
- **CLI Flags**: Core flags implemented, missing advanced options
- **Error Handling**: Good coverage, some edge cases missing

### ❌ Not Implemented (0%)
- **Package Manager Integration**: brew_install, apt_install, dnf_install
- **Template System**: Jinja2 rendering with variables
- **Secret Management**: External secret provider integration  
- **VS Code Integration**: Extension management
- **Plugin Architecture**: Custom verb system
- **Configuration Generation**: Interactive setup tools

---

## Priority Implementation Order

### Phase 1: Package Management (High Priority)
**Estimated Effort**: 2-3 weeks
1. Implement `brew_install` verb for macOS
2. Implement `apt_install` verb for Debian/Ubuntu  
3. Implement `dnf_install` verb for Red Hat/Fedora
4. Add package management integration tests
5. Update Docker test matrix for package operations

### Phase 2: Template System (High Priority)  
**Estimated Effort**: 1-2 weeks
1. Implement `template` verb with Jinja2
2. Add variable substitution and context management
3. Implement template security sandboxing
4. Add template rendering tests
5. Create template example configurations

### Phase 3: Advanced Features (Medium Priority)
**Estimated Effort**: 3-4 weeks
1. Implement `secret_ref` verb with multiple providers
2. Implement `vscode_extensions` verb
3. Add advanced bootstrap features
4. Enhance CLI with missing flags and options

### Phase 4: Plugin Architecture (Medium Priority)
**Estimated Effort**: 2-3 weeks  
1. Design and implement plugin system
2. Add plugin discovery and loading
3. Create plugin development documentation
4. Add plugin validation and sandboxing
5. Create example plugins

---

## Testing Gaps for Unimplemented Features

The integration test plan in `INTEGRATION_TEST_PLAN.md` already includes placeholder tests for unimplemented features:

### Future Feature Tests (Planned but not executable)
- `docker_test_package_managers.py` - Package manager integration
- `docker_test_templates.py` - Template rendering and security
- `docker_test_secrets.py` - Secret provider integration  
- `docker_test_plugins.py` - Plugin system functionality

These test files should be implemented alongside their corresponding features.

---

## Dependencies for Unimplemented Features

### New Python Dependencies Required
```toml
# For template system
jinja2 = "^3.1.0"
markupsafe = "^2.1.0"

# For secret management
keyring = "^24.0.0"          # System keychain
python-dotenv = "^1.0.0"     # Environment variables

# For VS Code integration  
subprocess-timeout = "^1.0.0" # Command execution with timeout

# For package managers
packaging = "^23.0"           # Version parsing and comparison
```

### System Dependencies
- **macOS**: Homebrew CLI (`brew` command)
- **Linux**: Package managers (`apt`, `dnf`, `yum`)
- **VS Code**: VS Code CLI (`code --install-extension`)
- **Secrets**: Provider CLIs (1password, lastpass, etc.)

---

## Configuration Schema Extensions

The current `models.py` defines the required fields for unimplemented operations:

### StepConfig Validation
Lines 197-203 in `models.py` already define required fields for unimplemented verbs:
- `BREW_INSTALL`: requires `packages` field
- `APT_INSTALL`: requires `packages` field  
- `DNF_INSTALL`: requires `packages` field
- `TEMPLATE`: requires `src`, `dst`, `vars` fields
- `SECRET_REF`: requires `key`, `dst` fields

This validation will work immediately once the verbs are implemented.

---

## Risk Assessment

### Low Risk (Easy Implementation)
- Package manager verbs - straightforward subprocess calls
- Basic template rendering - well-established Jinja2 patterns
- VS Code extensions - simple CLI integration

### Medium Risk (Moderate Complexity)
- Secret management - requires external provider integration
- Plugin architecture - needs careful security design
- Advanced bootstrap features - cross-platform compatibility

### High Risk (Complex Implementation)  
- Plugin sandboxing - security isolation challenges
- Template security - injection prevention complexities
- Advanced error recovery - race condition handling

---

## Conclusion

The current implementation represents a **solid foundation** with excellent safety features and comprehensive testing. The missing features are primarily **advanced operations** rather than core functionality gaps.

**Recommendations**:
1. **Prioritize package management** - highest user value
2. **Implement template system** - enables configuration flexibility  
3. **Design plugin architecture carefully** - security implications
4. **Maintain test-driven development** - add tests with implementation

The specification is well-designed and the current architecture can support all missing features without major refactoring.

---

**Total Missing Features**: 14 major components  
**Implementation Readiness**: High (architecture supports all features)  
**Estimated Timeline**: 8-12 weeks for complete spec implementation