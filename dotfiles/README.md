# <à Dotfiles Management System

> A **safety-first**, declarative dotfiles management system that makes managing your configuration files easy, safe, and reproducible across all your machines.

<div align="center">

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-151_passing-green.svg)](./tests/)
[![Coverage](https://img.shields.io/badge/coverage-65%25-yellow.svg)](./tests/)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](./LICENSE)

[**Getting Started**](#-getting-started) " [**Quick Tutorial**](#-quick-tutorial) " [**Documentation**](#-documentation) " [**Examples**](#-real-world-examples)

</div>

---

## =Ö What Are Dotfiles?

If you're new to dotfiles, don't worry! **Dotfiles** are configuration files that start with a dot (`.`) like `.bashrc`, `.gitconfig`, or `.vimrc`. They control how your programs behave and look. Managing dotfiles means:

- = **Keeping settings synchronized** across multiple computers
- =æ **Backing up** your configurations safely
- =€ **Quickly setting up** new machines with your preferences
- =e **Sharing** configurations with teammates or the community

### Why Use This System?

Unlike manual copying or basic scripts, this system provides:

-  **Safety First**: Automatic backups before any changes
- = **Preview Mode**: See what will happen before it does (dry-run by default)
- © **Rollback**: Undo any operation if something goes wrong
- =Ý **Declarative**: Describe what you want, not how to do it
- =á **Security**: Path validation and command whitelisting

## =€ Getting Started

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

## <¯ Quick Tutorial

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
# = DRY RUN MODE - No changes will be made
# Would create link: ~/.gitconfig -> /path/to/dotfiles/git/gitconfig
```

### Step 4: Apply Changes

When you're ready, apply the changes:

```bash
# Actually create the symlink
uv run dotfiles-sync --apply sync

# Output:
#  Created link: ~/.gitconfig -> /path/to/dotfiles/git/gitconfig
# =æ Backup saved to: ~/.local/state/dotfiles/backups/...
```

### Step 5: Check Status

See what's currently managed:

```bash
uv run dotfiles-sync status

# Output:
# =Ê Dotfiles Status
# Managed files: 1
# Last sync: 2025-08-10 10:30:00
#  ~/.gitconfig -> /path/to/dotfiles/git/gitconfig
```

## =Ú Documentation

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

Your `dotfiles.toml` file has four main sections:

```toml
# 1. Package metadata (required)
[package]
name = "my-dotfiles"
version = "1.0.0"
author = "Your Name <email@example.com>"
description = "Description of your dotfiles"

# 2. Safety settings (optional, these are defaults)
[safety]
dry_run_default = true         # Preview by default
backup_before_modify = true    # Always backup
backup_retention_days = 30     # Keep backups for 30 days
verify_checksums = true        # Verify file integrity
fail_on_error = false          # Continue on errors
require_confirmation = false   # Interactive confirmation

# 3. Security settings (optional but recommended)
[security]
whitelist_paths = [
    "~/**",                    # Allow home directory
    "/usr/local/bin/*"         # Allow local binaries
]
blacklist_paths = [
    "/etc/**",                 # Block system configs
    "/System/**",              # Block macOS system
    "~/.ssh/authorized_keys"   # Block sensitive files
]
allowed_commands = [
    "chmod *",                 # Allow permission changes
    "git config *"             # Allow git configuration
]
enable_command_whitelist = true

# 4. Steps - your operations (at least one required)
[[step]]
op = "link"
src = "source/file"
dst = "~/destination"
# Optional fields for all operations:
platforms = ["darwin", "linux"]  # Only run on these OS
variants = ["personal", "work"]  # Only for these variants
create_parent_dirs = true        # Create missing directories
```

### Platform and Variant Support

#### Platforms

Limit operations to specific operating systems:

```toml
[[step]]
op = "link"
src = "mac/sketchybar"
dst = "~/.config/sketchybar"
platforms = ["darwin"]  # Only on macOS
description = "macOS menu bar configuration"

[[step]]
op = "copy"
src = "linux/xinitrc"
dst = "~/.xinitrc"
platforms = ["linux"]  # Only on Linux
description = "X11 initialization"
```

#### Variants

Use variants for different machine configurations:

```toml
# Work-specific Git configuration
[[step]]
op = "copy"
src = "git/gitconfig-work"
dst = "~/.gitconfig"
variants = ["work"]
description = "Work Git configuration"

# Personal Git configuration
[[step]]
op = "copy"
src = "git/gitconfig-personal"
dst = "~/.gitconfig"
variants = ["personal"]
description = "Personal Git configuration"
```

Run with a specific variant:

```bash
# Use work configuration
uv run dotfiles-sync --variant work sync

# Use personal configuration
uv run dotfiles-sync --variant personal sync
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

## < Real-World Examples

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

## =à Advanced Usage

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

## =' Troubleshooting

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

## =Ë FAQ

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

## > Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Ensure all tests pass: `make test`
5. Submit a pull request

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

## =Ä License

This project is licensed under the MIT License - see [LICENSE](./LICENSE) for details.

## =O Acknowledgments

- Inspired by GNU Stow, Chezmoi, and Dotbot
- Built with Python, Click, and Pydantic
- Safety patterns from production deployment tools

## =î Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/dotfiles/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/dotfiles/discussions)
- **Documentation**: [Full Documentation](./docs/)

---

<div align="center">

**Happy Dotfiles Management! <‰**

Made with d by the Dotfiles Community

</div>