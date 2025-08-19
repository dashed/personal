# dotfiles.toml Complete Reference

This is the complete technical reference for the `dotfiles.toml` configuration file. For user-friendly documentation, see the main [README.md](../README.md).

## Overview

The `dotfiles.toml` file uses TOML format and is inspired by Cargo.toml structure. It defines all dotfile operations in a declarative, safety-first manner with four main sections:

- **[package]** - Required metadata about your dotfiles
- **[safety]** - Optional safety and behavior settings  
- **[security]** - Optional security and path restrictions
- **[[step]]** - Array of operations to perform

## Complete Schema

### [package] Section (Required)

Package metadata section - **always required**.

```toml
[package]
name = "my-dotfiles"                    # Required: string, min 1 character
version = "1.0.0"                       # Required: semantic version (X.Y.Z format)
author = "Your Name <email@example.com>" # Optional: author information
description = "My dotfiles setup"       # Optional: package description
```

**Field Details:**
- `name`: Package identifier, must be non-empty string
- `version`: Must follow semantic versioning (e.g., "1.0.0", "2.1.3")
- `author`: Free-form string, typically "Name <email>"
- `description`: Free-form description string

**Validation:**
- Version must match pattern `^\d+\.\d+\.\d+$` (three numeric parts)
- Name cannot be empty string

### [safety] Section (Optional)

Safety and operational behavior settings. All fields have sensible defaults.

```toml
[safety]
dry_run_default = true          # Default: true - Preview changes by default
backup_before_modify = true     # Default: true - Create backups before changes
backup_retention_days = 30      # Default: 30 - Days to keep backups (0-365)
verify_checksums = true         # Default: true - Verify file integrity
fail_on_error = true           # Default: true - Stop on first error
max_operations = 1000          # Default: 1000 - Max operations per transaction
require_confirmation = true    # Default: true - Ask before destructive operations
```

**Field Details:**
- `dry_run_default`: If true, operations preview by default (use --apply to execute)
- `backup_before_modify`: Create timestamped backups before modifying files
- `backup_retention_days`: How long to keep backups (0 = forever, max 365)
- `verify_checksums`: Validate file integrity using checksums
- `fail_on_error`: If true, stop on first error; if false, continue with remaining operations
- `max_operations`: Safety limit on operations per transaction (min 1, max 1000)
- `require_confirmation`: Prompt for confirmation before destructive operations

**Validation:**
- `backup_retention_days`: Must be 0-365
- `max_operations`: Must be ≥ 1

### [security] Section (Optional)

Security and access control settings.

```toml
[security]
# Path access control
whitelist_paths = [              # Default: ["~/.config", "~/.local"]
    "~/.config/**",              # Allow home config directory
    "~/.local/**",               # Allow home local directory
    "~/.bashrc",                 # Specific files
    "~/Library/Application Support/Code/**"  # App-specific paths
]

blacklist_paths = [              # Default: ["/etc", "/usr", "/System"]
    "/etc/**",                   # System configuration
    "/usr/**",                   # System binaries
    "/System/**",                # macOS system files
    "~/.ssh/id_*",              # SSH private keys
    "~/.gnupg/**",              # GPG keys
]

# Secret management
secret_provider = "environment"  # Default: "environment"
                                # Options: "environment", "keychain", "onepassword", "lastpass"

# Command whitelisting for run/run_once operations
enable_command_whitelist = false # Default: false
allowed_commands = [             # Default: [] (empty)
    "chmod *",                   # File permissions
    "git config *",              # Git configuration
    "mkdir -p *",               # Directory creation
]
```

**Field Details:**
- `whitelist_paths`: Paths where operations are allowed (glob patterns supported)
- `blacklist_paths`: Paths that are forbidden (takes precedence over whitelist)
- `secret_provider`: Backend for secret management operations
- `enable_command_whitelist`: If true, only `allowed_commands` can be executed
- `allowed_commands`: Commands allowed when whitelisting is enabled (glob patterns supported)

**Validation:**
- Whitelist and blacklist paths cannot overlap
- Secret provider must be valid enum value
- Glob patterns supported: `*`, `**`, `?`, `[...]`

### [[step]] Section (Required Array)

Array of operations to perform. At least one step is required.

#### Common Fields (All Operations)

These fields are available for all operation types:

```toml
[[step]]
op = "link"                      # Required: operation type
src = "config/file"             # Source path (relative to config file)
dst = "~/.config/file"          # Destination path (absolute or ~/ relative)
description = "Link config"     # Human-readable description
variants = ["all"]              # Default: ["all"] - applicable variants
platforms = ["macos", "linux"]  # Default: all platforms

# File/directory creation options
create_parent_dirs = false      # Default: false - create missing parent dirs
parent_dir_mode = "0755"       # Default: system default - parent dir permissions
overwrite = false              # Default: false - overwrite existing files
backup = true                  # Default: true - backup before overwrite

# Operation control
sudo = false                   # Default: false - require sudo privileges
```

**Field Details:**
- `op`: Operation type (see Operation Types below)
- `src`: Source file/directory path, relative to dotfiles.toml location
- `dst`: Destination path, supports `~` for home directory
- `description`: Human-readable description shown during operations
- `variants`: List of variants this step applies to (default: ["all"])
- `platforms`: List of platforms (default: all). Valid: "macos", "linux", "windows"
- `create_parent_dirs`: Automatically create missing parent directories
- `parent_dir_mode`: Permissions for created parent directories (octal string)
- `overwrite`: Allow overwriting existing files
- `backup`: Create backup before overwriting (requires `overwrite = true`)
- `sudo`: Run operation with sudo privileges (security risk - use carefully)

## Operation Types

The system supports 12 operation types. Here are the details for each:

### 1. link - Create Symbolic Links

Creates symbolic links from destination to source.

**Required Fields:** `src`, `dst`

```toml
[[step]]
op = "link"
src = "config/vimrc"
dst = "~/.vimrc"
description = "Link Vim configuration"
create_parent_dirs = true
```

**Use Cases:**
- Configuration files you actively edit
- Files that need real-time synchronization
- Development configurations

### 2. copy - Copy Files

Creates physical copies of files.

**Required Fields:** `src`, `dst`

```toml
[[step]]
op = "copy"
src = "ssh/config"
dst = "~/.ssh/config"
mode = "0600"                   # Set file permissions
description = "Copy SSH config"
create_parent_dirs = true
overwrite = true
backup = true
```

**Additional Fields:**
- `mode`: File permissions (octal string like "0600", "0644")

**Use Cases:**
- Files requiring specific permissions
- Files that should be independent copies
- Sensitive configuration files

### 3. syncdir - Synchronize Directories

Synchronizes entire directories, copying all files from source to destination.

**Required Fields:** `src`, `dst`

```toml
[[step]]
op = "syncdir"
src = "vscode"
dst = "~/Library/Application Support/Code/User"
exclude = ["*.log", "workspaceStorage"]  # Skip these patterns
description = "Sync VS Code settings"
create_parent_dirs = true
```

**Additional Fields:**
- `exclude`: List of glob patterns to exclude from sync

**Use Cases:**
- Application configuration directories
- Multiple related configuration files
- Plugin/extension directories

### 4. append - Append Text to Files

Appends text to the end of files with idempotency support.

**Required Fields:** `text`, `dst`

```toml
[[step]]
op = "append"
text = """
# Custom aliases
alias ll='ls -la'
alias gs='git status'
"""
dst = "~/.bashrc"
marker = "# DOTFILES_ALIASES"    # Idempotency marker
description = "Add custom aliases"
create_parent_dirs = true
```

**Additional Fields:**
- `marker`: Unique marker string to prevent duplicate additions

**Use Cases:**
- Adding to existing configuration files
- Shell aliases and functions
- PATH additions

### 5. prepend - Prepend Text to Files

Adds text to the beginning of files with idempotency support.

**Required Fields:** `text`, `dst`

```toml
[[step]]
op = "prepend"
text = "# Managed by dotfiles-sync\n"
dst = "~/.zshrc"
marker = "# DOTFILES_HEADER"     # Idempotency marker
description = "Add dotfiles header"
```

**Additional Fields:**
- `marker`: Unique marker string to prevent duplicate additions

**Use Cases:**
- Adding headers or important settings
- Environment variable exports that must load first
- Shell configuration that needs priority

### 6. brew_install - Homebrew Package Installation

Installs packages using Homebrew (macOS/Linux).

**Required Fields:** `packages`

```toml
[[step]]
op = "brew_install"
packages = [
    "git",
    "ripgrep",
    "fd",
    "bat",
    "starship"
]
platforms = ["macos"]           # Usually macOS only
description = "Install development tools"
```

**Use Cases:**
- Installing command-line tools
- Development environment setup
- System dependencies

### 7. apt_install - APT Package Installation

Installs packages using APT package manager (Debian/Ubuntu).

**Required Fields:** `packages`

```toml
[[step]]
op = "apt_install"
packages = [
    "git",
    "ripgrep",
    "fd-find",
    "bat"
]
platforms = ["linux"]
sudo = true                     # Usually required for package installation
description = "Install essential packages"
```

**Use Cases:**
- Linux system package installation
- Development dependencies
- System utilities

### 8. dnf_install - DNF Package Installation

Installs packages using DNF package manager (Fedora/RHEL).

**Required Fields:** `packages`

```toml
[[step]]
op = "dnf_install"
packages = [
    "git",
    "ripgrep",
    "fd-find",
    "bat"
]
platforms = ["linux"]
sudo = true                     # Usually required
description = "Install Fedora packages"
```

**Use Cases:**
- Fedora/RHEL system packages
- Development tools installation

### 9. template - Template Processing

Processes Jinja2 templates with variable substitution.

**Required Fields:** `src`, `dst`, `vars`

```toml
[[step]]
op = "template"
src = "config/gitconfig.j2"
dst = "~/.gitconfig"
vars = {
    email = "${WORK_EMAIL}",
    name = "John Doe",
    signing_key = "${GPG_KEY}"
}
description = "Generate work git config"
variants = ["work"]
```

**Additional Fields:**
- `vars`: Dictionary of template variables (supports environment variable expansion)

**Use Cases:**
- Configuration files with variable content
- Environment-specific configurations
- Dynamic configuration generation

### 10. secret_ref - Secret Management

References secrets from external secret providers.

**Required Fields:** `key`, `dst`

```toml
[[step]]
op = "secret_ref"
key = "work/api-token"          # Secret identifier
dst = "~/.config/app/token"
mode = "0600"                   # Usually private
description = "Install API token"
variants = ["work"]
```

**Use Cases:**
- API keys and tokens
- Certificates and private keys
- Sensitive configuration data

### 11. run - Execute Commands

Executes shell commands with safety checks.

**Required Fields:** `command`

```toml
[[step]]
op = "run"
command = "chmod 700 ~/.ssh"
description = "Secure SSH directory"
sudo = false                    # Avoid sudo when possible
```

**Use Cases:**
- File permission changes
- Directory creation
- System configuration commands

### 12. run_once - Execute Commands Once

Executes commands only once per machine, tracked by checksum.

**Required Fields:** `command`

```toml
[[step]]
op = "run_once"
command = "git config --global init.defaultBranch main"
checksum = "git_default_branch_v1"  # Version tracking
description = "Set git default branch"
```

**Additional Fields:**
- `checksum`: Version identifier to track command changes

**Use Cases:**
- One-time system setup
- Initial configuration commands
- Setup that shouldn't be repeated

## Platform Support

Operations can be limited to specific platforms:

```toml
# All platforms (default)
platforms = ["macos", "linux", "windows"]

# macOS only
platforms = ["macos"]

# Unix-like systems
platforms = ["macos", "linux"]

# Cross-platform (explicit)
platforms = ["all"]  # Same as omitting the field
```

**Valid Platform Values:**
- `"macos"` - macOS systems
- `"linux"` - Linux systems  
- `"windows"` - Windows systems
- `"all"` - All platforms (default)

## Variant Support

Variants allow different configurations for different machine types:

```toml
# Default variant (always applies)
variants = ["all"]

# Specific variants
variants = ["work"]
variants = ["personal"]
variants = ["development"]

# Multiple variants
variants = ["work", "development"]
```

**Usage:**
```bash
# Use specific variant
dotfiles-sync --variant work sync

# Use default variant
dotfiles-sync sync
```

## Path Handling

### Path Types

1. **Absolute paths**: `/home/user/.config/app`
2. **Home-relative paths**: `~/.config/app` (recommended)
3. **Relative paths**: `config/app` (relative to dotfiles.toml location)

### Path Expansion

- `~` expands to user home directory
- Environment variables: `${HOME}/.config` or `$HOME/.config`
- Relative paths are resolved relative to dotfiles.toml location

### Glob Patterns

Supported in `whitelist_paths`, `blacklist_paths`, and `exclude`:

- `*` - matches any characters except `/`
- `**` - matches any characters including `/`
- `?` - matches single character
- `[abc]` - matches any character in brackets
- `[!abc]` - matches any character not in brackets

## Validation Rules

### Path Validation
- Source paths must exist (for file operations)
- Destination paths must be within whitelisted paths
- Blacklisted paths are forbidden (takes precedence)

### Operation Validation
- Required fields must be present for each operation type
- Platform values must be valid
- File modes must be valid octal strings
- Version must follow semantic versioning

### Safety Validation
- `backup_retention_days` must be 0-365
- `max_operations` must be ≥ 1
- Whitelist/blacklist paths cannot overlap

## Error Handling

### Common Validation Errors

```toml
# ERROR: Invalid version format
version = "1.0"  # Must be X.Y.Z

# ERROR: Missing required field
[[step]]
op = "link"
# src = "missing"  # Required for link operations
dst = "~/.file"

# ERROR: Invalid platform
platforms = ["invalid"]  # Must be macos, linux, windows, or all

# ERROR: Path overlap
[security]
whitelist_paths = ["~/.config"]
blacklist_paths = ["~/.config"]  # Cannot be in both lists
```

### Runtime Errors

- **Permission denied**: File/directory not writable
- **Path not whitelisted**: Destination outside allowed paths
- **File exists**: Destination exists and overwrite=false
- **Source not found**: Source file doesn't exist
- **Command failed**: Shell command returned non-zero exit code

## Best Practices

### Security
1. Use minimal whitelist paths
2. Never whitelist system directories (`/etc`, `/usr`, `/System`)
3. Use `copy` for sensitive files requiring specific permissions
4. Avoid `sudo = true` unless absolutely necessary
5. Use secure `mode` for sensitive files (e.g., `"0600"`)

### Organization
1. Group related operations together
2. Use descriptive names and descriptions
3. Use variants for different machine types
4. Use platform restrictions appropriately
5. Test with dry-run before applying

### Maintenance
1. Use semantic versioning in package.version
2. Keep backups enabled
3. Use checksums for run_once operations
4. Document complex operations in descriptions
5. Review and update configurations regularly

## Migration Guide

### From Basic to Advanced Configuration

**Basic Configuration:**
```toml
[package]
name = "dotfiles"
version = "1.0.0"

[[step]]
op = "link"
src = "vimrc"
dst = "~/.vimrc"
```

**Advanced Configuration:**
```toml
[package]
name = "my-dotfiles"
version = "1.0.0"
author = "John Doe <john@example.com>"
description = "Personal development environment"

[safety]
dry_run_default = true
backup_before_modify = true
backup_retention_days = 60
require_confirmation = false    # For automation

[security]
whitelist_paths = [
    "~/.config/**",
    "~/.local/**",
    "~/.vim/**",
    "~/.bashrc",
    "~/.zshrc"
]
blacklist_paths = [
    "/etc/**",
    "/System/**",
    "~/.ssh/id_*"
]

[[step]]
op = "link"
src = "vim/vimrc"
dst = "~/.vimrc"
description = "Vim configuration"
variants = ["personal", "work"]
create_parent_dirs = true
```

## Complete Example

Here's a comprehensive example showing all major features:

```toml
# Complete dotfiles.toml example
[package]
name = "my-dotfiles"
version = "2.1.0"
author = "Developer <dev@example.com>"
description = "Complete development environment setup"

[safety]
dry_run_default = true
backup_before_modify = true
backup_retention_days = 60
verify_checksums = true
fail_on_error = true
max_operations = 500
require_confirmation = false

[security]
whitelist_paths = [
    "~/.config/**",
    "~/.local/**",
    "~/Library/Application Support/Code/**",
    "~/.vim/**",
    "~/.bashrc",
    "~/.zshrc",
    "~/.gitconfig",
    "~/.ssh/config"
]
blacklist_paths = [
    "/etc/**",
    "/usr/**",
    "/System/**",
    "~/.ssh/id_*",
    "~/.gnupg/**"
]
secret_provider = "environment"
enable_command_whitelist = true
allowed_commands = [
    "chmod *",
    "git config *",
    "mkdir -p *"
]

# Shell configuration
[[step]]
op = "link"
src = "shell/zshrc"
dst = "~/.zshrc"
description = "Zsh configuration"
variants = ["all"]
platforms = ["macos", "linux"]
create_parent_dirs = true

[[step]]
op = "template"
src = "shell/bashrc.j2"
dst = "~/.bashrc"
vars = { editor = "vim", shell_theme = "minimal" }
description = "Bash configuration"
variants = ["personal"]
platforms = ["linux"]

# Git configuration
[[step]]
op = "copy"
src = "git/gitconfig-personal"
dst = "~/.gitconfig"
description = "Personal Git configuration"
variants = ["personal"]

[[step]]
op = "template"
src = "git/gitconfig-work.j2"
dst = "~/.gitconfig"
vars = { 
    email = "${WORK_EMAIL}",
    signing_key = "${WORK_GPG_KEY}"
}
description = "Work Git configuration"
variants = ["work"]

# Development tools
[[step]]
op = "brew_install"
packages = ["git", "ripgrep", "fd", "bat", "starship"]
description = "Essential development tools"
platforms = ["macos"]
variants = ["all"]

[[step]]
op = "apt_install"
packages = ["git", "ripgrep", "fd-find", "bat"]
description = "Essential development tools"
platforms = ["linux"]
sudo = true

# VS Code
[[step]]
op = "syncdir"
src = "vscode"
dst = "~/Library/Application Support/Code/User"
exclude = ["workspaceStorage", "globalStorage"]
description = "VS Code settings"
platforms = ["macos"]
variants = ["personal", "work"]

# SSH configuration
[[step]]
op = "copy"
src = "ssh/config"
dst = "~/.ssh/config"
mode = "0600"
description = "SSH client configuration"
create_parent_dirs = true

# One-time setup
[[step]]
op = "run_once"
command = "git config --global init.defaultBranch main"
checksum = "git_default_branch_v1"
description = "Set Git default branch"

# Environment setup
[[step]]
op = "append"
text = 'export PATH="$HOME/.local/bin:$PATH"'
dst = "~/.zshenv"
marker = "# dotfiles-local-bin"
description = "Add local bin to PATH"
platforms = ["macos", "linux"]
```

This example demonstrates most features and can serve as a template for complex dotfiles setups.