# Dotfiles Management System

> A **safety-first**, declarative dotfiles management system that makes managing your configuration files easy, safe, and reproducible across all your machines.

<div align="center">

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-151_passing-green.svg)](./tests/)
[![Coverage](https://img.shields.io/badge/coverage-65%25-yellow.svg)](./tests/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](./LICENSE)

[**Getting Started**](#getting-started) | [**Quick Tutorial**](#quick-tutorial) | [**Documentation**](#documentation) | [**Examples**](#real-world-examples)

</div>

---

## What Are Dotfiles?

If you're new to dotfiles, don't worry! **Dotfiles** are configuration files that start with a dot (`.`) like `.bashrc`, `.gitconfig`, or `.vimrc`. They control how your programs behave and look. Managing dotfiles means:

- **Keeping settings synchronized** across multiple computers
- **Backing up** your configurations safely
- **Quickly setting up** new machines with your preferences
- **Sharing** configurations with teammates or the community

### Why Use This System?

Unlike manual copying or basic scripts, this system provides:

- **Safety First**: Automatic backups before any changes
- **Preview Mode**: See what will happen before it does (dry-run by default)
- **Rollback**: Undo any operation if something goes wrong
- **Declarative**: Describe what you want, not how to do it
- **Security**: Path validation and command whitelisting

## Getting Started

### Prerequisites

- **Python 3.12 or higher** ([Download Python](https://www.python.org/downloads/))
- **uv** (recommended) or pip for package management
- **Git** for version control

### Installation

#### Option 1: Using uv (Recommended)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone this repository
git clone https://github.com/yourusername/dotfiles.git
cd dotfiles

# Install dependencies
uv sync

# Verify installation
uv run dotfiles-sync --version
```

#### Option 2: Using pip

```bash
# Clone this repository
git clone https://github.com/yourusername/dotfiles.git
cd dotfiles

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .

# Verify installation
dotfiles-sync --version
```

## Quick Tutorial

Let's start with a simple example - managing your Git configuration.

### Step 1: Create Your Configuration File

Create a file named `dotfiles.toml` in your dotfiles directory:

```toml
# Basic information about your dotfiles
[package]
name = "my-dotfiles"
version = "1.0.0"
author = "Your Name <you@example.com>"
description = "My personal dotfiles"

# Safety settings (these are the defaults)
[safety]
dry_run_default = true         # Always preview changes first
backup_before_modify = true    # Create backups automatically
require_confirmation = false   # Ask before making changes

# Security settings
[security]
whitelist_paths = ["~/**"]     # Only allow changes in home directory
blacklist_paths = ["/etc/**"]  # Never modify system files

# Your first operation: Link your gitconfig
[[step]]
op = "link"                    # Create a symbolic link
src = "git/gitconfig"          # Source file in your dotfiles repo
dst = "~/.gitconfig"           # Destination in your home directory
description = "Link Git configuration"
```

### Step 2: Add Your Git Configuration

Create the source file `git/gitconfig`:

```ini
[user]
    name = Your Name
    email = you@example.com

[core]
    editor = vim

[alias]
    st = status
    co = checkout
    br = branch
```

### Step 3: Preview Changes (Dry Run)

Always preview what will happen first:

```bash
# This shows what WOULD happen without making changes
uv run dotfiles-sync sync

# Output:
# DRY RUN MODE - No changes will be made
# Would create link: ~/.gitconfig -> /path/to/dotfiles/git/gitconfig
```

### Step 4: Apply Changes

When you're ready, apply the changes:

```bash
# Actually create the symlink
uv run dotfiles-sync --apply sync

# Output:
# Created link: ~/.gitconfig -> /path/to/dotfiles/git/gitconfig
# Backup saved to: ~/.local/state/dotfiles/backups/...
```

### Step 5: Check Status

See what's currently managed:

```bash
uv run dotfiles-sync status

# Output:
# Dotfiles Status
# Managed files: 1
# Last sync: 2025-08-10 10:30:00
# ~/.gitconfig -> /path/to/dotfiles/git/gitconfig
```

## Documentation

### Available Operations (Verbs)

The system supports 7 core operations, called "verbs":

#### 1. **link** - Create Symbolic Links

Creates a symbolic link from destination to source. Perfect for config files that need to stay in sync.

```toml
[[step]]
op = "link"
src = "config/vimrc"
dst = "~/.vimrc"
description = "Link Vim configuration"
```

**Use when**: You want changes to immediately reflect in both places.

#### 2. **copy** - Copy Files

Creates a physical copy of the file. Good for files that need to be independent.

```toml
[[step]]
op = "copy"
src = "ssh/config"
dst = "~/.ssh/config"
mode = "0600"  # Set permissions (read/write for owner only)
description = "Copy SSH configuration"
```

**Use when**: Files need different permissions or shouldn't be linked.

#### 3. **syncdir** - Synchronize Directories

Copies all files from a source directory to destination.

```toml
[[step]]
op = "syncdir"
src = "vscode"
dst = "~/.config/Code/User"
exclude = ["*.log", "*.tmp"]  # Skip these files
description = "Sync VS Code settings"
```

**Use when**: Managing multiple configuration files in a directory.

#### 4. **append** - Append Text to Files

Adds text to the end of a file (with idempotency using markers).

```toml
[[step]]
op = "append"
text = """
# Custom aliases
alias ll='ls -la'
alias gs='git status'
"""
dst = "~/.bashrc"
marker = "CUSTOM_ALIASES"  # Won't append if this marker exists
description = "Add custom aliases"
```

**Use when**: Adding to existing configuration files.

#### 5. **prepend** - Prepend Text to Files

Adds text to the beginning of a file.

```toml
[[step]]
op = "prepend"
text = "# Managed by dotfiles system\n"
dst = "~/.zshrc"
marker = "DOTFILES_HEADER"
description = "Add header to zshrc"
```

**Use when**: Adding important settings that need to load first.

#### 6. **run** - Execute Commands

Runs shell commands (with safety checks).

```toml
[[step]]
op = "run"
command = "chmod 700 ~/.ssh"
description = "Secure SSH directory"
```

**Use when**: System setup or configuration commands.

#### 7. **run_once** - Execute Commands Once

Runs commands only once per machine (tracked in database).

```toml
[[step]]
op = "run_once"
command = "git config --global init.defaultBranch main"
checksum = "abc123"  # Optional: tracks command version
description = "Set default Git branch"
```

**Use when**: One-time setup commands.

### Configuration File Structure

Your `dotfiles.toml` file uses TOML format with four main sections. **For complete technical reference, see [docs/DOTFILES_TOML_REFERENCE.md](./docs/DOTFILES_TOML_REFERENCE.md).**

```toml
# 1. Package metadata (required)
[package]
name = "my-dotfiles"                    # Required: package name
version = "1.0.0"                       # Required: semantic version (X.Y.Z)
author = "Your Name <email@example.com>" # Optional: author information
description = "My personal dotfiles"    # Optional: description

# 2. Safety settings (optional, these are sensible defaults)
[safety]
dry_run_default = true          # Default: true - always preview first
backup_before_modify = true     # Default: true - create backups
backup_retention_days = 30      # Default: 30 - days to keep backups
verify_checksums = true         # Default: true - verify file integrity
fail_on_error = true           # Default: true - stop on first error
max_operations = 1000          # Default: 1000 - safety limit
require_confirmation = true    # Default: true - ask before destructive ops

# 3. Security settings (optional but recommended)
[security]
whitelist_paths = [             # Default: ["~/.config", "~/.local"]
    "~/.config/**",             # Allow home config directory
    "~/.local/**",              # Allow home local directory
    "~/.bashrc",                # Specific files
    "~/.gitconfig"
]
blacklist_paths = [             # Default: ["/etc", "/usr", "/System"]
    "/etc/**",                  # System configuration files
    "/usr/**",                  # System binaries
    "/System/**",               # macOS system files
    "~/.ssh/id_*",             # SSH private keys
]
secret_provider = "environment"  # Options: environment, keychain, onepassword
enable_command_whitelist = false # Default: false
allowed_commands = [            # Commands allowed when whitelisting enabled
    "chmod *",
    "git config *"
]

# 4. Steps - your operations (at least one required)
[[step]]
op = "link"                     # Operation type (see all types below)
src = "config/file"            # Source path (relative to dotfiles.toml)
dst = "~/.config/file"         # Destination path
description = "Link config file" # Human-readable description

# Common optional fields for all operations:
variants = ["all"]              # Default: ["all"] - which variants apply
platforms = ["macos", "linux"] # Default: all - target platforms
create_parent_dirs = true      # Default: false - auto-create directories
mode = "0644"                  # File permissions (for copy operations)
overwrite = true               # Default: false - overwrite existing files
backup = true                  # Default: true - backup before overwrite
sudo = false                   # Default: false - require sudo (security risk)
```

### All Operation Types

The system supports **12 operation types**. Here are the most common ones:

#### File Operations
```toml
# Link files (real-time sync)
[[step]]
op = "link"
src = "vim/vimrc"
dst = "~/.vimrc"
description = "Link Vim config"

# Copy files (independent copies)
[[step]]
op = "copy"
src = "ssh/config"
dst = "~/.ssh/config"
mode = "0600"                  # Secure permissions
description = "Copy SSH config"

# Synchronize entire directories
[[step]]
op = "syncdir"
src = "vscode"
dst = "~/Library/Application Support/Code/User"
exclude = ["*.log", "workspaceStorage"]  # Skip patterns
description = "Sync VS Code settings"
```

#### Text Operations
```toml
# Append text to files (with idempotency)
[[step]]
op = "append"
text = """
# Custom aliases
alias ll='ls -la'
alias gs='git status'
"""
dst = "~/.bashrc"
marker = "# DOTFILES_ALIASES"   # Prevents duplicates
description = "Add custom aliases"

# Prepend text to files
[[step]]
op = "prepend"
text = "# Managed by dotfiles-sync\n"
dst = "~/.zshrc"
marker = "# DOTFILES_HEADER"
description = "Add header"
```

#### Package Management
```toml
# Homebrew (macOS/Linux)
[[step]]
op = "brew_install"
packages = ["git", "ripgrep", "fd", "bat"]
platforms = ["macos"]
description = "Install development tools"

# APT (Debian/Ubuntu)
[[step]]
op = "apt_install"
packages = ["git", "ripgrep", "fd-find"]
platforms = ["linux"]
sudo = true
description = "Install packages"

# DNF (Fedora/RHEL)
[[step]]
op = "dnf_install"
packages = ["git", "ripgrep", "fd-find"]
platforms = ["linux"]
sudo = true
description = "Install Fedora packages"
```

#### Advanced Operations
```toml
# Template processing with Jinja2
[[step]]
op = "template"
src = "git/gitconfig.j2"
dst = "~/.gitconfig"
vars = { 
    email = "${WORK_EMAIL}", 
    name = "John Doe" 
}
description = "Generate work git config"

# Secret management
[[step]]
op = "secret_ref"
key = "work/api-token"
dst = "~/.config/app/token"
mode = "0600"
description = "Install API token"

# Run commands
[[step]]
op = "run"
command = "chmod 700 ~/.ssh"
description = "Secure SSH directory"

# Run commands once (tracked by checksum)
[[step]]
op = "run_once"
command = "git config --global init.defaultBranch main"
checksum = "git_default_branch_v1"
description = "Set git default branch"
```

### Platform and Variant Support

#### Platforms

Target specific operating systems:

```toml
# macOS only
platforms = ["macos"]

# Linux only  
platforms = ["linux"]

# Cross-platform
platforms = ["macos", "linux", "windows"]

# All platforms (default)
# platforms = ["all"]  # or omit entirely
```

**Valid platforms:** `macos`, `linux`, `windows`, `all`

#### Variants

Use variants for different machine configurations:

```toml
# Personal configuration
[[step]]
op = "copy"
src = "git/gitconfig-personal"
dst = "~/.gitconfig"
variants = ["personal"]
description = "Personal Git config"

# Work configuration
[[step]]
op = "template"
src = "git/gitconfig-work.j2" 
dst = "~/.gitconfig"
variants = ["work"]
vars = { email = "${WORK_EMAIL}" }
description = "Work Git config"

# Multiple variants
[[step]]
op = "link"
src = "shell/aliases"
dst = "~/.aliases"
variants = ["personal", "work"]  # Apply to both
description = "Common aliases"
```

**Run with variants:**
```bash
# Use work configuration
uv run dotfiles-sync --variant work sync

# Use personal configuration  
uv run dotfiles-sync --variant personal sync

# Use default variant (applies "all" and "default")
uv run dotfiles-sync sync
```

### Path Handling and Security

#### Path Types
- **Relative paths**: `config/file` (relative to dotfiles.toml)
- **Home paths**: `~/.config/file` (recommended)
- **Absolute paths**: `/home/user/.config/file`

#### Security Features
- **Whitelisting**: Only allowed paths can be modified
- **Blacklisting**: Forbidden paths are blocked (takes precedence)  
- **Command filtering**: Restrict which commands can run
- **Permission control**: Set specific file permissions
- **Glob patterns**: Use `*`, `**`, `?` in paths

#### Best Practices
1. **Use whitelist paths** to restrict where operations can write
2. **Blacklist sensitive areas** like `/etc`, `/usr`, `/System`  
3. **Set secure permissions** for sensitive files (`mode = "0600"`)
4. **Avoid sudo** unless absolutely necessary
5. **Test with dry-run** before applying changes

### Configuration Validation

The system validates your configuration and shows helpful error messages:

```bash
# Check configuration for errors
uv run dotfiles-sync validate

# Common validation errors:
# - Missing required fields (src, dst for file operations)
# - Invalid version format (must be X.Y.Z)
# - Invalid platform names
# - Path conflicts (whitelist/blacklist overlap)
# - Invalid file permissions
```

### Command-Line Interface

#### Basic Commands

```bash
# Show help
dotfiles-sync --help

# Check version
dotfiles-sync --version

# Validate configuration (checks for errors)
dotfiles-sync validate

# Show current status
dotfiles-sync status

# Preview changes (dry run)
dotfiles-sync sync

# Apply changes
dotfiles-sync --apply sync

# Force operations (skip safety checks)
dotfiles-sync --apply --force sync
```

#### Backup Management

```bash
# List all backups
dotfiles-sync backup list

# Restore a specific backup
dotfiles-sync backup restore <backup-id>

# Show backup details
dotfiles-sync backup show <backup-id>
```

#### Rollback Operations

```bash
# Show recent operations
dotfiles-sync status --transactions

# Rollback last operation
dotfiles-sync rollback

# Rollback specific transaction
dotfiles-sync rollback --transaction <id>
```

#### Drift Detection

```bash
# Check if files have changed
dotfiles-sync diff

# Show detailed differences
dotfiles-sync diff --detailed
```

## Real-World Examples

### Example 1: Complete Developer Setup

```toml
[package]
name = "dev-setup"
version = "2.0.0"
author = "Dev <dev@example.com>"
description = "Full stack developer configuration"

[safety]
dry_run_default = true
backup_before_modify = true

[security]
whitelist_paths = ["~/**", "/usr/local/bin/*"]
blacklist_paths = ["/etc/**", "/System/**"]

# Shell configuration
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

# Git configuration
[[step]]
op = "copy"
src = "git/gitconfig"
dst = "~/.gitconfig"
description = "Git configuration"

[[step]]
op = "copy"
src = "git/gitignore_global"
dst = "~/.gitignore_global"
description = "Global gitignore"

# Vim setup
[[step]]
op = "link"
src = "vim/vimrc"
dst = "~/.vimrc"
description = "Vim configuration"

[[step]]
op = "syncdir"
src = "vim/colors"
dst = "~/.vim/colors"
description = "Vim color schemes"

# VS Code settings (platform-specific)
[[step]]
op = "syncdir"
src = "vscode"
dst = "~/Library/Application Support/Code/User"
platforms = ["darwin"]
exclude = ["*.log"]
description = "VS Code settings (macOS)"

[[step]]
op = "syncdir"
src = "vscode"
dst = "~/.config/Code/User"
platforms = ["linux"]
exclude = ["*.log"]
description = "VS Code settings (Linux)"

# SSH configuration (with secure permissions)
[[step]]
op = "copy"
src = "ssh/config"
dst = "~/.ssh/config"
mode = "0600"
create_parent_dirs = true
description = "SSH client configuration"

# One-time setup commands
[[step]]
op = "run_once"
command = "git config --global core.excludesfile ~/.gitignore_global"
checksum = "v1"
description = "Configure global gitignore"

[[step]]
op = "run_once"
command = "chmod 700 ~/.ssh"
checksum = "v1"
description = "Secure SSH directory"
```

### Example 2: Multi-Machine Setup with Variants

```toml
[package]
name = "multi-machine"
version = "1.0.0"
author = "User <user@example.com>"
description = "Configuration for multiple machines"

# Define hostname to variant mapping
[variants]
"macbook.local" = "laptop"
"desktop.home" = "desktop"
"work-machine" = "work"

# Laptop-specific settings
[[step]]
op = "copy"
src = "power/laptop-power-settings"
dst = "~/.config/power/settings"
variants = ["laptop"]
platforms = ["darwin"]
description = "Laptop power management"

# Desktop-specific settings
[[step]]
op = "link"
src = "monitors/triple-monitor.conf"
dst = "~/.config/monitors.conf"
variants = ["desktop"]
description = "Multi-monitor configuration"

# Work machine settings
[[step]]
op = "copy"
src = "work/vpn-config"
dst = "~/.config/vpn/work.conf"
variants = ["work"]
mode = "0600"
description = "Work VPN configuration"

# Common to all machines
[[step]]
op = "link"
src = "common/tmux.conf"
dst = "~/.tmux.conf"
description = "Tmux configuration (all machines)"
```

## Advanced Usage

### Custom Safety Settings

```toml
[safety]
dry_run_default = true         # Always preview first
backup_before_modify = true    # Backup before changes
backup_retention_days = 60     # Keep backups for 2 months
verify_checksums = true        # Verify file integrity
fail_on_error = false          # Continue on errors
require_confirmation = true    # Ask before each operation
max_file_size = 10485760      # 10MB max file size
```

### Environment Variables

You can use environment variables in paths:

```toml
[[step]]
op = "link"
src = "config/app.conf"
dst = "${XDG_CONFIG_HOME:-~/.config}/app/config"
description = "App configuration with XDG support"
```

### Conditional Operations

```toml
# Only on macOS for personal use
[[step]]
op = "link"
src = "mac/personal/settings"
dst = "~/Library/Preferences/settings.plist"
platforms = ["darwin"]
variants = ["personal"]
description = "Personal macOS settings"

# Only on Linux work machines
[[step]]
op = "copy"
src = "linux/work/bashrc"
dst = "~/.bashrc"
platforms = ["linux"]
variants = ["work"]
description = "Work Linux bash configuration"
```

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Permission denied" errors

**Solution**: Check file permissions and use appropriate `mode`:

```toml
[[step]]
op = "copy"
src = "private/key"
dst = "~/.ssh/id_rsa"
mode = "0600"  # Read/write for owner only
```

#### Issue: Symlinks not working on Windows

**Solution**: Use `copy` instead of `link` on Windows, or run as Administrator:

```toml
[[step]]
op = "copy"  # Use copy on Windows
src = "config/gitconfig"
dst = "~/.gitconfig"
platforms = ["windows"]
```

#### Issue: "File already exists" errors

**Solution**: Use `--force` flag or remove existing file:

```bash
# Force overwrite
dotfiles-sync --apply --force sync

# Or manually remove first
rm ~/.gitconfig
dotfiles-sync --apply sync
```

#### Issue: Changes not appearing after sync

**Solution**: For linked files, changes are immediate. For copied files, re-run sync:

```bash
# Re-sync to update copied files
dotfiles-sync --apply sync
```

#### Issue: Accidentally modified system files

**Solution**: Use the rollback feature:

```bash
# Rollback last operation
dotfiles-sync rollback

# Or restore from backup
dotfiles-sync backup list
dotfiles-sync backup restore <backup-id>
```

### Debugging

Enable verbose output for troubleshooting:

```bash
# Verbose output
dotfiles-sync -v sync

# Very verbose (debug level)
dotfiles-sync -vv sync

# With specific configuration file
dotfiles-sync --config ./test-config.toml sync
```

### Safety Features

The system includes multiple safety layers:

1. **Dry-run by default** - Preview before applying
2. **Automatic backups** - Restore if needed
3. **Path validation** - Prevent system damage
4. **Rollback support** - Undo operations
5. **Checksum verification** - Ensure file integrity
6. **Transaction tracking** - Full audit trail

## FAQ

### Q: Is this safe to use?

**A:** Yes! The system is designed with safety first:
- Dry-run mode by default (preview changes)
- Automatic backups before modifications
- Path validation to prevent system damage
- Complete rollback capability

### Q: Can I use this on multiple operating systems?

**A:** Yes! Use the `platforms` field to specify OS-specific operations:
```toml
platforms = ["darwin", "linux", "windows"]
```

### Q: How do I sync across multiple machines?

**A:** 
1. Store your dotfiles in a Git repository
2. Clone the repo on each machine
3. Use variants for machine-specific settings
4. Run `dotfiles-sync --variant <name> sync`

### Q: Can I test without affecting my system?

**A:** Yes! Use Docker for safe testing:
```bash
make docker-test
```

### Q: What's the difference between link and copy?

**A:** 
- **link**: Creates a symbolic link. Changes to either file affect both.
- **copy**: Creates an independent copy. Changes don't sync automatically.

### Q: How do I handle secrets?

**A:** Never commit secrets! Instead:
1. Use environment variables
2. Store secrets separately
3. Use `.gitignore` for sensitive files
4. Future: Use the planned `secret_ref` verb

### Q: Can I migrate from other dotfile managers?

**A:** Yes! The system uses standard operations:
- From symlink farms: Use `link` operations
- From Stow: Convert folder structure to `link` operations
- From Chezmoi: Convert templates to `copy` operations
- Manual: Start with your most important configs


## Adding Files to Dotfiles Management

### Step-by-Step Guide for Adding New Files

#### 1. Choose Your Management Strategy

Decide whether to use `link` or `copy`:

| Use **link** when: | Use **copy** when: |
|-------------------|-------------------|
| You actively edit the file | File is stable/rarely changes |
| Want instant synchronization | Want explicit version control |
| Testing configurations | Need different permissions |
| | Want independent copies |

#### 2. Add File to Dotfiles Repository

```bash
# Create appropriate directory structure
cd ~/dotfiles
mkdir -p category  # e.g., shell, git, vim, etc.

# For COPY: Copy the original file to your dotfiles
cp ~/.config/app/config.yml category/app-config.yml

# For LINK: Move the original file to your dotfiles
mv ~/.config/app/config.yml category/app-config.yml
```

#### 3. Update dotfiles.toml

Add a new `[[step]]` section:

```toml
# For COPY operation (recommended for most cases)
[[step]]
op = "copy"
src = "category/app-config.yml"
dst = "~/.config/app/config.yml"
description = "App configuration"
create_parent_dirs = true

# For LINK operation (real-time sync)
[[step]]
op = "link"
src = "category/app-config.yml"
dst = "~/.config/app/config.yml"
description = "App configuration"
create_parent_dirs = true
```

#### 4. Test Your Configuration

```bash
# Preview what will happen (dry run - always safe)
uv run dotfiles-sync sync

# If everything looks good, apply the changes
uv run dotfiles-sync --apply sync
```

#### 5. Commit Your Changes

```bash
git add category/app-config.yml dotfiles.toml
git commit -m "Add app configuration to dotfiles"
git push
```

### Real Example: Adding SSH Config

```bash
# 1. Create directory
mkdir -p ssh

# 2. Copy SSH config to dotfiles
cp ~/.ssh/config ssh/config

# 3. Add to dotfiles.toml
cat >> dotfiles.toml << 'EOF'

[[step]]
op = "copy"
src = "ssh/config"
dst = "~/.ssh/config"
mode = "0600"  # Important: SSH requires strict permissions
description = "SSH client configuration"
create_parent_dirs = true
EOF

# 4. Test
uv run dotfiles-sync sync

# 5. Apply
uv run dotfiles-sync --apply sync

# 6. Commit
git add ssh/config dotfiles.toml
git commit -m "Add SSH configuration"
```

### Tips for Common File Types

#### Shell Configuration Files
```toml
[[step]]
op = "copy"  # Use copy to avoid breaking active shells
src = "shell/zshrc"
dst = "~/.zshrc"
```

#### Git Configuration
```toml
[[step]]
op = "copy"  # Copy allows local overrides
src = "git/gitconfig"
dst = "~/.gitconfig"
```

#### Editor Configurations
```toml
[[step]]
op = "link"  # Link for active development
src = "vim/vimrc"
dst = "~/.vimrc"
```

#### SSH Files (Require Permissions)
```toml
[[step]]
op = "copy"
src = "ssh/config"
dst = "~/.ssh/config"
mode = "0600"  # Required for SSH files
```

#### Application Configs
```toml
[[step]]
op = "copy"
src = "apps/vscode-settings.json"
dst = "~/Library/Application Support/Code/User/settings.json"
platforms = ["darwin"]  # Mac only
```

### Updating Existing Managed Files

#### For Copy-Managed Files:
```bash
# Edit your local file as needed
vim ~/.config/app/config.yml

# When ready to save to dotfiles:
cp ~/.config/app/config.yml ~/dotfiles/category/app-config.yml
git add category/app-config.yml
git commit -m "Update app configuration"
```

#### For Link-Managed Files:
```bash
# Edit either location - they're the same file!
vim ~/.config/app/config.yml
# OR
vim ~/dotfiles/category/app-config.yml

# Changes are immediate, just commit when ready
git add category/app-config.yml
git commit -m "Update app configuration"
```

### Removing Files from Management

```bash
# 1. Remove from dotfiles.toml (delete the [[step]] section)

# 2. For linked files, replace with regular file:
rm ~/.config/app/config.yml  # Remove symlink
cp ~/dotfiles/category/app-config.yml ~/.config/app/config.yml

# 3. Optionally remove from repository:
git rm category/app-config.yml
git commit -m "Remove app config from dotfiles management"
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass: `make test`
5. Submit a pull request

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

## License

This project is licensed under the MIT License - see [LICENSE](./LICENSE) for details.

## Acknowledgments

- Inspired by GNU Stow, Chezmoi, and Dotbot
- Built with Python, Click, and Pydantic
- Safety patterns from production deployment tools

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/dotfiles/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/dotfiles/discussions)
- **Documentation**: [Full Documentation](./docs/)

---

<div align="center">

**Happy Dotfiles Management!**

Made with love by the Dotfiles Community

</div>
