# 🚀 Quick Reference Guide

> Cheat sheet for the Dotfiles Management System

## Installation

```bash
# Using uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone <your-dotfiles-repo>
cd dotfiles
uv sync
uv run dotfiles-sync --version

# Using pip
python -m venv venv
source venv/bin/activate
pip install -e .
dotfiles-sync --version
```

## Command Line Usage

### Essential Commands

```bash
# Preview changes (dry run - safe)
dotfiles-sync sync

# Apply changes
dotfiles-sync --apply sync

# Force changes (skip checks)
dotfiles-sync --apply --force sync

# Check configuration
dotfiles-sync validate

# Show status
dotfiles-sync status
```

### Backup & Recovery

```bash
# List backups
dotfiles-sync backup list

# Restore backup
dotfiles-sync backup restore <backup-id>

# Rollback last operation
dotfiles-sync rollback

# Rollback specific transaction
dotfiles-sync rollback --transaction <id>
```

### Variants & Options

```bash
# Use specific variant
dotfiles-sync --variant work sync

# Use different config file
dotfiles-sync --config custom.toml sync

# Verbose output
dotfiles-sync -v sync          # Verbose
dotfiles-sync -vv sync         # Very verbose (debug)

# Check for drift
dotfiles-sync diff
```

## Configuration File Structure

### Minimal Config

```toml
[package]
name = "my-dotfiles"
version = "1.0.0"
author = "Name <email>"
description = "My dotfiles"

[[step]]
op = "link"
src = "gitconfig"
dst = "~/.gitconfig"
```

### Full Config Template

```toml
[package]
name = "my-dotfiles"
version = "1.0.0"
author = "Name <email@example.com>"
description = "Description"

[safety]
dry_run_default = true
backup_before_modify = true
backup_retention_days = 30
verify_checksums = true
fail_on_error = false
require_confirmation = false

[security]
whitelist_paths = ["~/**"]
blacklist_paths = ["/etc/**", "/System/**"]
allowed_commands = ["chmod *", "git config *"]
enable_command_whitelist = true

[variants]
"hostname1" = "personal"
"hostname2" = "work"

[[step]]
op = "link|copy|syncdir|append|prepend|run|run_once"
# ... verb-specific fields
```

## Verb Quick Reference

### link - Create Symlinks

```toml
[[step]]
op = "link"
src = "source/file"           # Required
dst = "~/destination"         # Required
create_parent_dirs = true     # Optional
platforms = ["darwin"]        # Optional
variants = ["personal"]       # Optional
```

**Use for**: Config files, frequently edited files

### copy - Copy Files

```toml
[[step]]
op = "copy"
src = "source/file"           # Required
dst = "~/destination"         # Required
mode = "0600"                 # Optional (permissions)
create_parent_dirs = true     # Optional
```

**Use for**: Templates, files needing specific permissions

### syncdir - Sync Directories

```toml
[[step]]
op = "syncdir"
src = "source/dir"            # Required
dst = "~/dest/dir"            # Required
exclude = ["*.log", "*.tmp"]  # Optional
```

**Use for**: Plugin directories, theme collections

### append - Add to End of File

```toml
[[step]]
op = "append"
text = "text to add"          # Required
dst = "~/file"                # Required
marker = "UNIQUE_ID"          # Optional (idempotency)
mode = "0644"                 # Optional
```

**Use for**: Adding aliases, environment variables

### prepend - Add to Start of File

```toml
[[step]]
op = "prepend"
text = "text to add"          # Required
dst = "~/file"                # Required
marker = "UNIQUE_ID"          # Optional
```

**Use for**: Priority settings, file headers

### run - Execute Commands

```toml
[[step]]
op = "run"
command = "shell command"     # Required
sudo = true                   # Optional
dst = "working/dir"           # Optional
vars = { KEY = "value" }      # Optional
```

**Use for**: Setup commands, permission changes

### run_once - Execute Once

```toml
[[step]]
op = "run_once"
command = "shell command"     # Required
checksum = "v1"               # Optional (version)
sudo = true                   # Optional
```

**Use for**: One-time setup, installations

## Common Patterns

### Platform-Specific Operations

```toml
# macOS only
[[step]]
op = "link"
src = "mac/config"
dst = "~/Library/Preferences/config"
platforms = ["darwin"]

# Linux only
[[step]]
op = "copy"
src = "linux/config"
dst = "~/.config/app"
platforms = ["linux"]

# Multiple platforms
platforms = ["darwin", "linux"]
```

### Variant-Specific Operations

```toml
# Personal machines
[[step]]
op = "link"
src = "personal/ssh"
dst = "~/.ssh/config"
variants = ["personal"]

# Work machines
[[step]]
op = "copy"
src = "work/gitconfig"
dst = "~/.gitconfig"
variants = ["work"]
```

### Creating Parent Directories

```toml
[[step]]
op = "link"
src = "config/deep/file"
dst = "~/.config/app/deep/config"
create_parent_dirs = true
parent_dir_mode = "0755"
```

### Setting File Permissions

```toml
[[step]]
op = "copy"
src = "ssh/id_rsa"
dst = "~/.ssh/id_rsa"
mode = "0600"  # Read/write owner only
```

### Using Environment Variables

```toml
[[step]]
op = "link"
src = "config"
dst = "${XDG_CONFIG_HOME:-~/.config}/app/config"
```

### Idempotent Text Addition

```toml
[[step]]
op = "append"
text = "alias ll='ls -la'"
dst = "~/.bashrc"
marker = "CUSTOM_ALIASES"  # Won't add if marker exists
```

## File Permissions Reference

```
0600  rw-------  Owner read/write only (private keys)
0644  rw-r--r--  Owner write, others read (config files)
0700  rwx------  Owner full access only (private dirs)
0755  rwxr-xr-x  Owner full, others read/exec (directories)
0775  rwxrwxr-x  Owner/group full, others read/exec
```

## Platform Values

- `darwin` - macOS
- `linux` - Linux (all distributions)
- `windows` - Windows (including WSL)

## Directory Paths by Platform

### Configuration Directories

```toml
# macOS
"~/Library/Application Support/"
"~/Library/Preferences/"
"~/Library/LaunchAgents/"

# Linux
"~/.config/"
"~/.local/share/"
"~/.local/bin/"

# Windows
"%APPDATA%/"
"%LOCALAPPDATA%/"
"%USERPROFILE%/"
```

### Common Application Paths

```toml
# VS Code
"~/Library/Application Support/Code/User"  # macOS
"~/.config/Code/User"                      # Linux
"%APPDATA%/Code/User"                      # Windows

# Vim/Neovim
"~/.vim"                                    # Vim
"~/.config/nvim"                           # Neovim
```

## Safety Commands

```bash
# Always safe to run
dotfiles-sync validate         # Check config
dotfiles-sync status           # Show status
dotfiles-sync sync             # Dry run (preview)
dotfiles-sync diff             # Check for changes

# Modifies files (use with care)
dotfiles-sync --apply sync     # Apply changes
dotfiles-sync --apply --force sync  # Force changes

# Recovery
dotfiles-sync rollback         # Undo last operation
dotfiles-sync backup restore <id>  # Restore backup
```

## Troubleshooting Quick Fixes

### Permission Denied

```toml
# Set correct permissions
mode = "0600"  # For private files
mode = "0755"  # For directories/scripts
```

### File Already Exists

```bash
# Force overwrite
dotfiles-sync --apply --force sync

# Or check what's there
ls -la ~/path/to/file
```

### Command Not Running

```toml
# Check whitelist in [security]
allowed_commands = ["your-command *"]
enable_command_whitelist = false  # Or disable
```

### Run_Once Running Again

```toml
# Change checksum to re-run
checksum = "v2"  # Increment version
```

### Symlink Not Working

```bash
# Check source exists
ls -la dotfiles/source/file

# Force recreate
dotfiles-sync --apply --force sync
```

## Testing & Development

```bash
# Safe testing in Docker
make docker-test           # Quick test
make docker-test-all       # All platforms

# Local development (safe)
make test                  # Unit tests
make lint                  # Code style
make typecheck            # Type checking
make validate             # Config validation

# Quick check before commit
make quick-check          # Lint + type + validate
```

## Environment Variables

```bash
# Set default variant
export DOTFILES_VARIANT=work

# Set custom config location
export DOTFILES_CONFIG=~/custom/config.toml

# Enable debug output
export DOTFILES_DEBUG=1
```

## Exit Codes

- `0` - Success
- `1` - General error
- `2` - Configuration error
- `3` - Validation error
- `4` - Operation failed

## Getting Help

```bash
# General help
dotfiles-sync --help

# Command help
dotfiles-sync sync --help
dotfiles-sync backup --help

# Version info
dotfiles-sync --version
```

## Common Workflows

### Initial Setup

```bash
1. git clone <your-repo> ~/dotfiles
2. cd ~/dotfiles
3. uv sync
4. uv run dotfiles-sync validate
5. uv run dotfiles-sync sync        # Preview
6. uv run dotfiles-sync --apply sync  # Apply
```

### Daily Use

```bash
# Check for drift
dotfiles-sync diff

# Update from repo
git pull
dotfiles-sync sync         # Preview
dotfiles-sync --apply sync # Apply
```

### Adding New Configs

```bash
1. Add file to dotfiles repo
2. Add [[step]] to dotfiles.toml
3. dotfiles-sync validate
4. dotfiles-sync sync      # Preview
5. dotfiles-sync --apply sync
6. git add && git commit
```

### Emergency Recovery

```bash
# If something goes wrong
dotfiles-sync rollback

# If that doesn't work
dotfiles-sync backup list
dotfiles-sync backup restore <latest-id>

# Manual recovery
cd ~/.local/state/dotfiles/backups/
```

---

**Pro Tips:**

- 🔍 Always dry-run first: `dotfiles-sync sync`
- 📦 Backups are in: `~/.local/state/dotfiles/backups/`
- 🔧 Use variants for different machines
- 🛡️ Set up path whitelisting for safety
- 📝 Use markers for idempotent text operations
- 🔄 Version your run_once commands with checksums

**Documentation:**
- [Full README](../README.md)
- [Verb Reference](./VERB_REFERENCE.md)
- [Safety Guide](./SAFETY.md)
- [Contributing](../CONTRIBUTING.md)