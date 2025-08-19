# Verb Reference Guide

> Complete documentation for all available operations (verbs) in the Dotfiles Management System

## Table of Contents

- [Overview](#overview)
- [Link Verb](#link-verb)
- [Copy Verb](#copy-verb)
- [SyncDir Verb](#syncdir-verb)
- [Append Verb](#append-verb)
- [Prepend Verb](#prepend-verb)
- [Run Verb](#run-verb)
- [Run_Once Verb](#run_once-verb)
- [Common Options](#common-options)

## Overview

Each operation in the dotfiles system is called a "verb". Verbs are the building blocks that define what actions to perform on your files. All verbs share common characteristics:

- **Dry-run support**: Preview changes before applying
- **Validation**: Check for errors before execution
- **Rollback capability**: Most operations can be undone
- **Platform/variant filtering**: Conditional execution
- **Descriptive output**: Clear feedback about what's happening

## Link Verb

Creates symbolic links from destination to source files.

### Syntax

```toml
[[step]]
op = "link"
src = "path/to/source"         # Required: Source file in dotfiles repo
dst = "~/path/to/destination"  # Required: Where to create the link
description = "What this does"  # Optional: Human-readable description
```

### Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `src` | string | ✅ Yes | Source file path (relative to dotfiles root) |
| `dst` | string | ✅ Yes | Destination path (supports `~` and env vars) |
| `create_parent_dirs` | boolean | No | Create missing parent directories (default: false) |
| `parent_dir_mode` | string | No | Permissions for created directories (e.g., "0755") |
| `platforms` | array | No | Limit to specific OS (e.g., ["darwin", "linux"]) |
| `variants` | array | No | Limit to specific variants (e.g., ["work"]) |

### Behavior

1. **If destination doesn't exist**: Creates symlink
2. **If destination is a file**: Backs up and replaces with symlink
3. **If destination is already a symlink**: 
   - To same source: No action (idempotent)
   - To different source: Updates the symlink
4. **If destination is a directory**: Backs up and replaces

### Examples

#### Basic Link

```toml
[[step]]
op = "link"
src = "config/vimrc"
dst = "~/.vimrc"
description = "Link Vim configuration"
```

#### With Parent Directory Creation

```toml
[[step]]
op = "link"
src = "config/nvim/init.lua"
dst = "~/.config/nvim/init.lua"
create_parent_dirs = true
parent_dir_mode = "0755"
description = "Link Neovim configuration"
```

#### Platform-Specific

```toml
[[step]]
op = "link"
src = "mac/karabiner.json"
dst = "~/.config/karabiner/karabiner.json"
platforms = ["darwin"]
create_parent_dirs = true
description = "Link Karabiner configuration (macOS only)"
```

### When to Use

- ✅ Configuration files that should stay in sync
- ✅ Files you edit frequently
- ✅ When you want changes to reflect immediately
- ❌ Files that need different permissions than source
- ❌ Files that shouldn't be in version control

## Copy Verb

Creates a physical copy of files or directories.

### Syntax

```toml
[[step]]
op = "copy"
src = "path/to/source"
dst = "~/path/to/destination"
mode = "0644"                   # Optional: Set file permissions
```

### Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `src` | string | ✅ Yes | Source file/directory path |
| `dst` | string | ✅ Yes | Destination path |
| `mode` | string | No | File permissions (octal string like "0600") |
| `create_parent_dirs` | boolean | No | Create missing parent directories |
| `parent_dir_mode` | string | No | Permissions for created directories |
| `platforms` | array | No | OS-specific execution |
| `variants` | array | No | Variant-specific execution |

### Behavior

1. **Smart copying**: Only copies if source and destination differ (checksum-based)
2. **Directory support**: Can copy entire directories
3. **Permission setting**: Can set specific permissions on copied files
4. **Checksum verification**: Verifies integrity after copying

### Examples

#### Basic Copy

```toml
[[step]]
op = "copy"
src = "templates/gitconfig"
dst = "~/.gitconfig"
description = "Copy Git configuration"
```

#### With Permissions (SSH Config)

```toml
[[step]]
op = "copy"
src = "ssh/config"
dst = "~/.ssh/config"
mode = "0600"  # Read/write for owner only
create_parent_dirs = true
description = "Copy SSH configuration with secure permissions"
```

#### Directory Copy

```toml
[[step]]
op = "copy"
src = "fonts"
dst = "~/.local/share/fonts"
create_parent_dirs = true
description = "Copy font files"
```

### When to Use

- ✅ Files that need specific permissions
- ✅ Template files that will be modified locally
- ✅ Files that shouldn't be symlinked
- ✅ Binary files or assets
- ❌ Files that need to stay synchronized

## SyncDir Verb

Synchronizes directories by copying files from source to destination.

### Syntax

```toml
[[step]]
op = "syncdir"
src = "source/directory"
dst = "~/destination/directory"
exclude = ["*.log", "*.tmp"]    # Optional: Patterns to exclude
```

### Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `src` | string | ✅ Yes | Source directory path |
| `dst` | string | ✅ Yes | Destination directory path |
| `exclude` | array | No | Glob patterns to exclude |
| `platforms` | array | No | OS-specific execution |
| `variants` | array | No | Variant-specific execution |

### Behavior

1. **One-way sync**: Only copies from source to destination
2. **Size limit**: Default 100MB total size limit (safety feature)
3. **Exclude patterns**: Supports glob patterns for filtering
4. **Preserves structure**: Maintains directory hierarchy

### Examples

#### Basic Directory Sync

```toml
[[step]]
op = "syncdir"
src = "config/vscode"
dst = "~/.config/Code/User"
description = "Sync VS Code settings"
```

#### With Exclusions

```toml
[[step]]
op = "syncdir"
src = "vim"
dst = "~/.vim"
exclude = ["*.swp", "*.swo", "*.log", ".netrwhist"]
description = "Sync Vim directory excluding temporary files"
```

#### Platform-Specific Paths

```toml
# macOS VS Code
[[step]]
op = "syncdir"
src = "vscode"
dst = "~/Library/Application Support/Code/User"
platforms = ["darwin"]
exclude = ["workspaceStorage/*", "*.log"]

# Linux VS Code
[[step]]
op = "syncdir"
src = "vscode"
dst = "~/.config/Code/User"
platforms = ["linux"]
exclude = ["workspaceStorage/*", "*.log"]
```

### When to Use

- ✅ Multiple configuration files in a directory
- ✅ Plugin directories
- ✅ Theme collections
- ❌ Large binary directories (>100MB)
- ❌ Directories needing bidirectional sync

## Append Verb

Appends text to the end of files with idempotency support.

### Syntax

```toml
[[step]]
op = "append"
text = "Text to append"
dst = "~/target/file"
marker = "UNIQUE_MARKER"        # Optional: Idempotency marker
```

### Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | ✅ Yes | Text to append to file |
| `dst` | string | ✅ Yes | Target file path |
| `marker` | string | No | Marker for idempotency (won't append if exists) |
| `mode` | string | No | File permissions if creating new file |
| `platforms` | array | No | OS-specific execution |
| `variants` | array | No | Variant-specific execution |

### Behavior

1. **Creates file if missing**: Will create the file if it doesn't exist
2. **Idempotency with markers**: Won't append if marker already exists
3. **Newline handling**: Automatically adds newlines appropriately
4. **Parent directory creation**: Creates parent directories if needed

### Examples

#### Basic Append

```toml
[[step]]
op = "append"
text = """
# Custom settings
export EDITOR=vim
export PAGER=less
"""
dst = "~/.bashrc"
description = "Add environment variables"
```

#### With Idempotency Marker

```toml
[[step]]
op = "append"
text = """
# Custom aliases
alias ll='ls -la'
alias gs='git status'
alias dc='docker-compose'
"""
dst = "~/.zshrc"
marker = "CUSTOM_ALIASES_BLOCK"
description = "Add custom aliases (only once)"
```

#### Creating New File

```toml
[[step]]
op = "append"
text = """
#!/bin/bash
# Custom script
echo "Hello from dotfiles!"
"""
dst = "~/.local/bin/hello"
mode = "0755"  # Make executable
description = "Create custom script"
```

### When to Use

- ✅ Adding to existing configuration files
- ✅ Injecting custom settings
- ✅ Creating new files with content
- ❌ Modifying the middle of files
- ❌ Complex file manipulations

## Prepend Verb

Prepends text to the beginning of files.

### Syntax

```toml
[[step]]
op = "prepend"
text = "Text to prepend"
dst = "~/target/file"
marker = "UNIQUE_MARKER"
```

### Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | ✅ Yes | Text to prepend to file |
| `dst` | string | ✅ Yes | Target file path |
| `marker` | string | No | Marker for idempotency |
| `mode` | string | No | File permissions if creating new file |
| `platforms` | array | No | OS-specific execution |
| `variants` | array | No | Variant-specific execution |

### Behavior

Similar to append but adds text at the beginning of the file.

### Examples

#### Adding File Headers

```toml
[[step]]
op = "prepend"
text = """
#!/usr/bin/env bash
# Managed by dotfiles system
# Last updated: 2025-08-10

"""
dst = "~/.bashrc"
marker = "DOTFILES_HEADER"
description = "Add managed header"
```

#### Priority Settings

```toml
[[step]]
op = "prepend"
text = """
# Load these settings first
export PATH="/usr/local/bin:$PATH"
"""
dst = "~/.zshrc"
marker = "PRIORITY_PATH"
description = "Ensure custom PATH loads first"
```

### When to Use

- ✅ Adding important settings that must load first
- ✅ File headers and warnings
- ✅ Path modifications that need priority
- ❌ Middle-of-file modifications

## Run Verb

Executes shell commands.

### Syntax

```toml
[[step]]
op = "run"
command = "shell command to execute"
sudo = false                     # Optional: Run with sudo
```

### Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | string | ✅ Yes | Shell command to execute |
| `sudo` | boolean | No | Run with sudo privileges |
| `dst` | string | No | Working directory for command |
| `vars` | object | No | Environment variables |
| `platforms` | array | No | OS-specific execution |
| `variants` | array | No | Variant-specific execution |

### Behavior

1. **Shell execution**: Runs in shell with timeout (5 minutes default)
2. **Error handling**: Captures stdout/stderr
3. **Working directory**: Can set specific directory
4. **No rollback**: Cannot undo arbitrary commands

### Examples

#### Basic Command

```toml
[[step]]
op = "run"
command = "mkdir -p ~/.config/custom"
description = "Create custom config directory"
```

#### With Sudo

```toml
[[step]]
op = "run"
command = "apt-get update"
sudo = true
platforms = ["linux"]
description = "Update package lists (Linux)"
```

#### With Environment Variables

```toml
[[step]]
op = "run"
command = "./install.sh"
dst = "scripts"  # Run in scripts directory
vars = { INSTALL_PATH = "~/.local", VERSION = "latest" }
description = "Run installation script"
```

### Security Note

⚠️ **Commands are subject to whitelisting** if enabled in security settings:

```toml
[security]
allowed_commands = [
    "mkdir *",
    "chmod *",
    "git config *"
]
enable_command_whitelist = true
```

### When to Use

- ✅ System configuration commands
- ✅ Permission changes
- ✅ Installation scripts
- ❌ Commands that should only run once (use run_once)
- ❌ Dangerous system modifications

## Run_Once Verb

Executes commands only once per machine/variant.

### Syntax

```toml
[[step]]
op = "run_once"
command = "shell command"
checksum = "v1"                 # Optional: Version tracking
```

### Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | string | ✅ Yes | Shell command to execute |
| `checksum` | string | No | Version identifier for the command |
| `sudo` | boolean | No | Run with sudo privileges |
| `dst` | string | No | Working directory |
| `vars` | object | No | Environment variables |
| `platforms` | array | No | OS-specific execution |
| `variants` | array | No | Variant-specific execution |

### Behavior

1. **Database tracking**: Records execution in state database
2. **Idempotency**: Won't run again if already executed
3. **Checksum versioning**: Re-runs if checksum changes
4. **Per-variant tracking**: Separate tracking for each variant

### Examples

#### One-Time Setup

```toml
[[step]]
op = "run_once"
command = "git config --global init.defaultBranch main"
checksum = "v1"
description = "Set default Git branch name"
```

#### Versioned Command

```toml
[[step]]
op = "run_once"
command = "defaults write com.apple.dock autohide -bool true && killall Dock"
checksum = "v2"  # Increment to re-run after changes
platforms = ["darwin"]
description = "Auto-hide Dock (macOS)"
```

#### Installation Commands

```toml
[[step]]
op = "run_once"
command = "curl -fsSL https://starship.rs/install.sh | sh -s -- -y"
checksum = "starship-v1"
description = "Install Starship prompt"
```

### When to Use

- ✅ Initial setup commands
- ✅ Installation scripts
- ✅ System preferences
- ✅ One-time configurations
- ❌ Regular maintenance commands
- ❌ Commands that need frequent updates

## Common Options

These options are available for all verbs:

### Platform Filtering

Limit operations to specific operating systems:

```toml
platforms = ["darwin"]        # macOS only
platforms = ["linux"]         # Linux only
platforms = ["windows"]       # Windows only
platforms = ["darwin", "linux"]  # macOS and Linux
```

Platform values:
- `darwin` - macOS
- `linux` - Linux distributions
- `windows` - Windows (including WSL)

### Variant Filtering

Limit operations to specific variants:

```toml
variants = ["personal"]       # Personal machines only
variants = ["work"]          # Work machines only
variants = ["laptop", "desktop"]  # Multiple variants
```

### Description

Human-readable description for clarity:

```toml
description = "What this operation does and why"
```

### Parent Directory Creation

For file operations that may need parent directories:

```toml
create_parent_dirs = true     # Create missing directories
parent_dir_mode = "0755"      # Permissions for created directories
```

### Complete Example

```toml
[[step]]
op = "link"
src = "config/special-app"
dst = "~/.config/special-app/config"
platforms = ["linux", "darwin"]
variants = ["personal"]
create_parent_dirs = true
parent_dir_mode = "0755"
description = "Link special app config for personal Unix machines"
```

## Best Practices

### 1. Use Descriptive Names

```toml
# Good
description = "Link Vim configuration with custom plugins"

# Bad
description = "vim stuff"
```

### 2. Group Related Operations

```toml
# Shell configuration group
[[step]]
op = "link"
src = "shell/zshrc"
dst = "~/.zshrc"
description = "Zsh configuration"

[[step]]
op = "link"
src = "shell/aliases"
dst = "~/.aliases"
description = "Shell aliases"

# Git configuration group
[[step]]
op = "copy"
src = "git/gitconfig"
dst = "~/.gitconfig"
description = "Git configuration"
```

### 3. Use Appropriate Verbs

- **Link** for configs you edit often
- **Copy** for templates or files needing permissions
- **SyncDir** for plugin directories
- **Append/Prepend** for modifying existing files
- **Run** for setup commands
- **Run_Once** for one-time setup

### 4. Platform-Specific Paths

```toml
# VS Code on different platforms
[[step]]
op = "syncdir"
src = "vscode"
dst = "~/Library/Application Support/Code/User"
platforms = ["darwin"]

[[step]]
op = "syncdir"
src = "vscode"
dst = "~/.config/Code/User"
platforms = ["linux"]

[[step]]
op = "syncdir"
src = "vscode"
dst = "%APPDATA%/Code/User"
platforms = ["windows"]
```

### 5. Security Considerations

- Never use `run` for untrusted commands
- Use `run_once` for installation scripts
- Set appropriate file permissions with `mode`
- Use markers for idempotency in append/prepend

## Troubleshooting

### Link Not Working

```bash
# Check if source exists
ls -la /path/to/dotfiles/source/file

# Check destination
ls -la ~/.config/target

# Try with force
dotfiles-sync --apply --force sync
```

### Copy Not Updating

```bash
# Check checksums
sha256sum source/file ~/.target

# Force update
dotfiles-sync --apply --force sync
```

### Run_Once Executing Again

```bash
# Check database
sqlite3 ~/.local/state/dotfiles/state.db \
  "SELECT * FROM run_once_tracker"

# Different checksum will re-run
checksum = "v2"  # Increment version
```

### Append Adding Duplicates

```toml
# Always use markers for idempotency
marker = "MY_UNIQUE_MARKER"
```

---

For more information, see the [main README](../README.md) or [FAQ](./FAQ.md).