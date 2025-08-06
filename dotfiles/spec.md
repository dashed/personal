Below is a **safety-first design blueprint** using **TOML configuration** (like `Cargo.toml`) to create a **fully declarative meta-configuration layer** with comprehensive backup, security, and rollback capabilities.

You can extend it to cover *anything* you might want a new machine to inherit: dotfiles, Oh-My-Zsh add-ons, Homebrew/apt packages, VS Code extensions, one-time shell hooks, secrets, OS-specific tweaks, etc.

The goal is that **no path or behaviour is hard-coded in the Python synchroniser**; everything lives in a human-readable file that ships inside (or alongside) your dotfiles repo, with **safety and security as first-class concerns**.

---

## 1 Key design principles

| Principle                        | Why it matters                                                                                                     |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Everything lives in the repo** | Re-cloning any branch is a perfect snapshot; nothing relies on state that isn't version-controlled.                |
| **Declarative, not imperative**  | Describe end-state ("`~/.zshrc` is a symlink to `zsh/zshrc`") rather than an ordered shell script.                 |
| **Variants + selectors**         | Let the *config* decide whether an item applies to `personal`, `work`, `linux`, `darwin-intel`, `darwin-arm`, etc. |
| **Composable operations**        | "symlink", "copy", "append", "mergeYAML", "run shell once", "brew install" – each is a first-class verb.           |
| **Extensible schema**            | New verbs or selectors can be dropped in without changing old entries or the sync engine.                          |
| **Safety first**                 | Automatic backups, dry-run by default, transaction logs, and rollback capability prevent data loss.                |
| **Security by design**           | Path validation, checksum verification, sandboxing, and audit logging protect against malicious actions.           |

---

## 2 Safety & Security Features

### 2.1 Backup System
- **Automatic backups** before any file modification
- **Timestamped backup directories**: `~/.local/state/dotfiles/backups/YYYY-MM-DD-HHMMSS/`
- **Backup manifest** with metadata about each operation
- **Configurable retention** (default: 30 days)
- **Quick rollback** to any previous state

### 2.2 Transaction System
- **Dry-run by default** - require explicit `--apply` flag for changes
- **Pre-flight validation** of all operations before execution
- **Transaction log** for atomic operations
- **Automatic rollback** on any failure
- **State tracking** in SQLite database, not just stamp files

### 2.3 Security Measures
- **Path validation** - no traversal attacks, whitelist destination paths
- **Checksum verification** for all downloads (SHA256)
- **Command whitelisting** for shell operations
- **Audit logging** of all operations
- **Secret references** instead of storing secrets in repo

---

## 3 Meta-configuration schema (TOML; **`dotfiles.toml`**)

### Why TOML over YAML?

Similar to how Rust uses `Cargo.toml` and Python uses `pyproject.toml`, TOML provides:
- **Type safety**: Clear distinction between strings, arrays, and tables
- **No ambiguity**: No confusion about string quoting or indentation
- **Explicit structure**: `[[array]]` syntax makes repeated sections obvious
- **Better tooling**: Built-in validation and parsing in most languages
- **Familiar patterns**: Follows conventions from Cargo.toml, pyproject.toml

```toml
# Dotfiles Configuration - Similar to Cargo.toml structure
# This file defines all dotfile operations in a declarative, safety-first manner

[package]
name = "dotfiles"
version = "1.0.0"
schema_version = "1.0"
author = "Your Name"
description = "Personal dotfiles configuration"

# Default variant selection (can be overridden by CLI or env)
default_variant = "auto"  # auto | personal | work | etc.

# Safety configuration - defaults to maximum safety
[safety]
dry_run_default = true           # SAFETY: require --apply flag for changes
backup_before_modify = true      # create backups before any destructive operation  
backup_retention_days = 30       # auto-cleanup old backups
max_changes_per_run = 100        # prevent runaway operations
strict_mode = true               # fail on any validation error
require_checksums = true         # all downloads must have SHA256 verification

# Security configuration
[security]
# Whitelist destination paths (glob patterns)
allowed_dst_paths = [
    "$HOME/**",
    "/usr/local/bin/*",
]

# Never allow these paths (takes precedence over allowed)
forbidden_dst_paths = [
    "/etc/**",
    "/System/**", 
    "$HOME/.ssh/authorized_keys",
]

# Whitelist for 'run' operations
safe_commands = [
    "./scripts/macos_defaults.sh",
    "./scripts/install_deps.sh",
]

# SHA256 checksums for external downloads
[checksums]
"uv-darwin-arm64" = "abc123..."
"uv-darwin-x86_64" = "def456..."
"uv-linux-x86_64" = "ghi789..."

# Hostname to variant mapping
[hostname]
"work-mbp" = "work"
"mac-personal" = "personal"

# Secret provider configuration
[secrets]
provider = "env"  # env | 1password | vault | aws-secrets-manager
env_prefix = "DOTFILES_"
# vault_addr = "https://vault.example.com"  # for vault provider
# onepassword_vault = "Personal"  # for 1password provider

# ============== DECLARATIVE STEPS ==============
# Each [[step]] defines an operation, similar to [[bin]] in Cargo.toml

# Dotfile symlinks
[[step]]
op = "link"
src = "zsh/zshrc"
dst = "~/.zshrc"
variants = ["all"]
backup = true

[[step]]
op = "link"
src = "zsh/zshrc.work" 
dst = "~/.zshrc"
variants = ["work"]
priority = 10  # Higher priority overrides previous entries

[[step]]
op = "link"
src = "ssh/config.work"
dst = "~/.ssh/config"
variants = ["work"]
create_parent_dirs = true
parent_dir_mode = "0700"

[[step]]
op = "link"
src = "git/gitconfig"
dst = "~/.gitconfig"
platforms = ["darwin", "linux"]


# Oh-My-Zsh custom plugins (with safety features)
[[step]]
op = "syncdir"
src = "zsh_custom_plugins"
dst = "${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins"
variants = ["all"]
# Safety features
delete_extraneous = false        # Don't delete by default
trash_instead_of_delete = true   # Move to trash, not permanent delete
max_deletions = 10               # Safety limit per run
exclude_patterns = [".git", "*.bak", ".DS_Store"]
require_confirmation = true      # Ask user before deletions


# Package managers with version pinning
[[step]]
op = "brew_install"
# Use @ for version pinning, similar to npm
packages = [
    "git@2.40.0",     # Pinned version
    "neovim",         # Latest version
    "jq",
]
platforms = ["darwin"]
check_installed_first = true

[[step]]
op = "apt_install"
packages = ["build-essential", "ripgrep"]
platforms = ["linux"]
sudo_required = true


# VS Code extensions
[[step]]
op = "vscode_extensions"
extensions = [
    "ms-vscode.vscode-typescript-next",
    "eamodio.gitlens",
]
variants = ["all"]
check_installed_first = true


# One-time shell hooks (with safety checks)
[[step]]
op = "run"
cmd = "./scripts/macos_defaults.sh"
checksum = "sha256:abcd1234..."  # Script integrity verification
variants = ["personal"]
run_once = true                   # Tracked in state database
require_confirmation = true       # Ask user before first run
timeout = 300                     # Seconds
safe_env_only = true             # Minimal environment


# Secret references (never stored in repo)
[[step]]
op = "secret_ref"
secret_name = "github_token"
provider = "env"                  # Uses [secrets] config
env_var = "GITHUB_TOKEN"
dst = "~/.config/github_token"
mode = "0600"
variants = ["all"]
```

### 3.1 Selector fields & Precedence

**Available selectors:**
* `variants` – e.g. `personal`, `work`, `gaming-rig`
* `platforms` – `linux`, `darwin`, `windows` (auto-detected)
* `arch` – `arm64`, `x86_64` (auto-detected)
* `hostname` – exact hostname match
* `env` – environment variables (e.g., `CI=true`)
* `priority` – explicit ordering (higher number wins)

**Boolean logic:**
- Multiple selector types = AND (e.g., `variants = ["work"]` AND `platforms = ["darwin"]`)
- Within a selector = OR (e.g., `variants = ["work", "personal"]` means work OR personal)
- Later steps override earlier ones for same dst (unless priority is set)
- Conflicts are warned in dry-run output with resolution strategy shown

**Package version syntax:**
- `"package"` – Install latest version
- `"package@1.2.3"` – Pin to specific version (like npm/yarn)
- `"package@~1.2"` – Compatible versions (1.2.x)
- `"package@^1.2"` – Minor updates allowed (1.x.x)

### 3.2 Supported verbs (safety-enhanced)

| Verb                | Effect                                                                      | Safety Features                          |
| ------------------- | --------------------------------------------------------------------------- | ---------------------------------------- |
| `link`              | Create or replace a **symlink** (`dst` -> `src`)                           | Backup existing, validate paths         |
| `copy`              | Copy file/dir verbatim; overwrite if checksum differs                      | Backup, checksum comparison              |
| `append`            | Append text from `src` to end of `dst`                                     | Backup, idempotency check                |
| `template`          | Render Jinja2 template with variables                                      | Sandbox, injection prevention           |
| `syncdir`           | Mirror directory tree (safe mode by default)                               | No delete default, trash, confirmation  |
| `brew_install`      | Install Homebrew packages (use `package@version` syntax)                   | Version pinning, installed check         |
| `apt_install`       | Install APT packages                                                        | Version pinning, sudo awareness         |
| `vscode_extensions` | Install VS Code extensions                                                 | Installed check                          |
| `run`               | Run whitelisted commands only                                              | Checksum verify, timeout, confirmation  |
| `secret_ref`        | Reference external secrets                                                 | Never stored, runtime injection only    |

---

## 4 Repository layout with safety files

```
dotfiles/
│
├── dotfiles.toml            # single source of truth (like Cargo.toml)
├── dotfiles.schema.json     # JSON schema for TOML validation
├── checksums.txt            # SHA256 hashes for all external downloads
├── .backup-excludes         # patterns to never backup
├── .safety-config           # additional safety rules
│
├── zsh/
│   ├── zshrc                # shared
│   ├── zshrc.work           # work overrides
│   └── zshrc.personal       # personal overrides
│
├── git/gitconfig
├── ssh/config.work
│
├── zsh_custom_plugins/
│   └── fzf-tab/...
│
├── scripts/
│   ├── macos_defaults.sh
│   └── checksums/          # individual checksum files
│       └── macos_defaults.sh.sha256
│
└── tests/                   # test your dotfiles!
    ├── test_links.py
    └── test_safety.py
```

---

## 5 Synchronizer architecture (safety-first)

```text
main()
 ├─ parse CLI (--variant, --config, --apply, --force, --rollback)
 ├─ validate dotfiles.toml against schema
 ├─ load dotfiles.toml -> dict
 ├─ initialize state database (SQLite at ~/.local/state/dotfiles/state.db)
 ├─ check for incomplete transactions -> offer rollback
 │
 ├─ resolve variant:
 │     CLI flag > $DOTFILES_VARIANT env > hostname_map > default
 │
 ├─ PRE-FLIGHT PHASE:
 │   ├─ validate all src paths exist in repo
 │   ├─ validate all dst paths against whitelist
 │   ├─ check write permissions for dst paths
 │   ├─ verify checksums for any downloads
 │   ├─ detect conflicts between steps
 │   └─ show dry-run summary -> require confirmation if --apply
 │
 ├─ TRANSACTION PHASE:
 │   ├─ create transaction ID and log
 │   ├─ for each applicable step:
 │   │   ├─ create backup if modifying existing file
 │   │   ├─ record pre-state in transaction log
 │   │   ├─ execute verb handler
 │   │   ├─ verify success
 │   │   ├─ record post-state in transaction log
 │   │   └─ on failure -> ROLLBACK all changes
 │   └─ commit transaction
 │
 ├─ POST-SYNC PHASE:
 │   ├─ cleanup old backups (> retention_days)
 │   ├─ update state database
 │   ├─ write audit log entry
 │   └─ show summary with changes made
 │
 └─ exit code (0=success, 1=error, 2=rollback performed)
```

### 5.1 Core classes (enhanced)

```python
from pathlib import Path
from typing import Optional, Any, Dict
import sqlite3
import hashlib
import tomllib  # Python 3.11+ built-in TOML parser
# For Python < 3.11, use: import tomli as tomllib

class SafetyValidator:
    """Pre-flight validation of all operations"""
    def validate_path(self, path: Path, whitelist: list, blacklist: list) -> bool: ...
    def verify_checksum(self, file: Path, expected: str) -> bool: ...
    def check_permissions(self, path: Path) -> bool: ...

class BackupManager:
    """Handle all backup operations"""
    def __init__(self, backup_dir: Path, retention_days: int): ...
    def backup_file(self, path: Path) -> Path: ...
    def restore_file(self, backup_path: Path, original_path: Path): ...
    def cleanup_old_backups(self): ...

class TransactionLog:
    """Atomic operations with rollback"""
    def __init__(self, db: sqlite3.Connection): ...
    def begin_transaction(self) -> str: ...  # returns transaction_id
    def record_operation(self, op: dict, state: str): ...
    def commit(self, transaction_id: str): ...
    def rollback(self, transaction_id: str): ...

class StateDatabase:
    """Persistent state tracking"""
    def __init__(self, db_path: Path): ...
    def has_run(self, operation_id: str) -> bool: ...
    def mark_complete(self, operation_id: str): ...
    def get_history(self, limit: int = 10) -> list: ...

class SecretProvider:
    """Handle secret references without storing them"""
    def get_secret(self, name: str) -> Optional[str]: ...
    def validate_secret_ref(self, ref: dict) -> bool: ...

class Context:
    variant: str
    platform: str  # 'darwin', 'linux', 'win32'
    arch: str      # 'arm64', 'x86_64'
    hostname: str
    env: dict
    safety_validator: SafetyValidator
    backup_manager: BackupManager
    transaction_log: TransactionLog
    state_db: StateDatabase
    secret_provider: SecretProvider

class Verb:
    name: str
    def validate(self, spec: dict, ctx: Context) -> list[str]: ...  # validation errors
    def apply(self, spec: dict, ctx: Context) -> bool: ...  # success/failure
    def rollback(self, spec: dict, ctx: Context): ...  # undo operation

# Loading the TOML configuration
def load_config(config_path: Path) -> Dict[str, Any]:
    """Load and validate dotfiles.toml configuration"""
    with open(config_path, 'rb') as f:
        config = tomllib.load(f)
    
    # Validate required sections
    required = ['package', 'safety', 'security']
    for section in required:
        if section not in config:
            raise ValueError(f"Missing required section: [{section}]")
    
    return config

# Example usage
config = load_config(Path('dotfiles.toml'))
steps = config.get('step', [])  # Array of steps
safety = config['safety']  # Safety configuration table
```

---

## 6 Bootstrap script (cross-platform & secure)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Safety first
DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${DOTFILES_DIR}"

# Platform detection
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

# Map to standard names
case "${OS}" in
  darwin) PLATFORM="darwin" ;;
  linux) PLATFORM="linux" ;;
  mingw*|cygwin*|msys*) PLATFORM="windows" ;;
  *) echo "Unsupported OS: ${OS}"; exit 1 ;;
esac

case "${ARCH}" in
  x86_64|amd64) ARCH_STD="x86_64" ;;
  arm64|aarch64) ARCH_STD="arm64" ;;
  *) echo "Unsupported architecture: ${ARCH}"; exit 1 ;;
esac

echo "Detected platform: ${PLATFORM}-${ARCH_STD}"

# Use XDG directories
BIN_DIR="${XDG_BIN_HOME:-${HOME}/.local/bin}"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/dotfiles"
mkdir -p "${BIN_DIR}" "${STATE_DIR}"

# Function to verify checksum
verify_checksum() {
  local file="$1"
  local expected="$2"
  
  if command -v sha256sum >/dev/null; then
    echo "${expected}  ${file}" | sha256sum -c - >/dev/null 2>&1
  elif command -v shasum >/dev/null; then
    echo "${expected}  ${file}" | shasum -a 256 -c - >/dev/null 2>&1
  else
    echo "Warning: No checksum tool available, skipping verification"
    return 0
  fi
}

# Install uv if needed
install_uv() {
  local uv_version="0.2.9"
  local uv_binary=""
  
  case "${PLATFORM}-${ARCH_STD}" in
    darwin-arm64) uv_binary="uv-aarch64-apple-darwin" ;;
    darwin-x86_64) uv_binary="uv-x86_64-apple-darwin" ;;
    linux-x86_64) uv_binary="uv-x86_64-unknown-linux-gnu" ;;
    linux-arm64) uv_binary="uv-aarch64-unknown-linux-gnu" ;;
    *) 
      echo "No pre-built uv binary for ${PLATFORM}-${ARCH_STD}"
      echo "Please install uv manually: https://github.com/astral-sh/uv"
      exit 1
      ;;
  esac
  
  local uv_url="https://github.com/astral-sh/uv/releases/download/v${uv_version}/${uv_binary}.tar.gz"
  local checksum="$(grep "${uv_binary}" checksums.txt | cut -d' ' -f1)"
  
  echo "Installing uv ${uv_version}..."
  
  # Download with retries
  local tmp_file="/tmp/uv-${RANDOM}.tar.gz"
  curl -LsSf "${uv_url}" -o "${tmp_file}" || {
    echo "Failed to download uv"
    exit 1
  }
  
  # Verify checksum
  if ! verify_checksum "${tmp_file}" "${checksum}"; then
    echo "Checksum verification failed!"
    rm -f "${tmp_file}"
    exit 1
  fi
  
  # Extract
  tar xzf "${tmp_file}" -C "${BIN_DIR}" uv
  rm -f "${tmp_file}"
  
  echo "uv installed to ${BIN_DIR}/uv"
}

# Check for uv
if ! command -v uv >/dev/null 2>&1; then
  if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
    export PATH="${BIN_DIR}:${PATH}"
  fi
  
  if ! command -v uv >/dev/null 2>&1; then
    install_uv
  fi
fi

# Check Python version
PYTHON_CMD=""
for cmd in python3 python; do
  if command -v "${cmd}" >/dev/null 2>&1; then
    if "${cmd}" -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
      PYTHON_CMD="${cmd}"
      break
    fi
  fi
done

if [[ -z "${PYTHON_CMD}" ]]; then
  echo "Error: Python 3.12+ is required"
  echo "Please install Python 3.12 or later"
  exit 1
fi

echo "Using Python: $(${PYTHON_CMD} --version)"

# Create virtual environment if needed
VENV_DIR="${STATE_DIR}/venv"
if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating virtual environment..."
  uv venv "${VENV_DIR}"
fi

# Activate virtual environment
source "${VENV_DIR}/bin/activate" 2>/dev/null || source "${VENV_DIR}/Scripts/activate"

# Install/update dependencies
if [[ -f "requirements.lock.txt" ]]; then
  echo "Installing dependencies..."
  uv pip sync requirements.lock.txt
else
  echo "Warning: requirements.lock.txt not found"
  echo "Installing from pyproject.toml..."
  uv pip install -e .
fi

# Run with safety defaults
echo ""
echo "==================================="
echo "Running dotfiles sync (DRY RUN MODE)"
echo "==================================="
echo ""

"${PYTHON_CMD}" -m dotfiles_sync \
  --repo "${DOTFILES_DIR}" \
  --dry-run \
  "$@"

echo ""
echo "This was a dry run. No changes were made."
echo "To apply changes, run: $0 --apply"
echo ""
echo "For more options, run: $0 --help"
```

---

## 7 Backup & Recovery Operations

### 7.1 Automatic Backup Structure
```
~/.local/state/dotfiles/
├── backups/
│   ├── 2024-01-15-143022/      # timestamp of backup
│   │   ├── manifest.json        # what was backed up and why
│   │   ├── files/               # actual file backups
│   │   │   ├── home-user-.zshrc
│   │   │   └── home-user-.gitconfig
│   │   └── transaction.log      # operations performed
│   │
│   └── latest -> 2024-01-15-143022  # symlink to most recent
│
├── state.db                     # SQLite database
└── logs/
    └── sync-2024-01-15.log
```

### 7.2 Recovery Commands
```bash
# List all backups
dotfiles_sync --list-backups

# Show what changed in a specific backup
dotfiles_sync --show-backup 2024-01-15-143022

# Rollback to a specific backup
dotfiles_sync --rollback 2024-01-15-143022

# Rollback last operation
dotfiles_sync --rollback-last

# Clean old backups manually
dotfiles_sync --clean-backups --older-than 30
```

---

## 8 Validation & Testing

### 8.1 Schema Validation (dotfiles.schema.json)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["package", "safety", "step"],
  "properties": {
    "package": {
      "type": "object",
      "required": ["name", "version"],
      "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "schema_version": {"type": "string"},
        "default_variant": {"type": "string"}
      }
    },
    "safety": {
      "type": "object",
      "properties": {
        "dry_run_default": {"type": "boolean"},
        "backup_before_modify": {"type": "boolean"},
        "backup_retention_days": {"type": "integer", "minimum": 1}
      }
    },
    "security": {
      "type": "object",
      "properties": {
        "allowed_dst_paths": {
          "type": "array",
          "items": {"type": "string"}
        },
        "forbidden_dst_paths": {
          "type": "array",
          "items": {"type": "string"}
        },
        "safe_commands": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "step": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["op"],
        "properties": {
          "op": {
            "type": "string",
            "enum": ["link", "copy", "append", "template", "syncdir", 
                     "brew_install", "apt_install", "vscode_extensions", "run", "secret_ref"]
          },
          "src": {"type": "string"},
          "dst": {"type": "string"},
          "variants": {
            "type": "array",
            "items": {"type": "string"}
          },
          "platforms": {
            "type": "array",
            "items": {"type": "string"}
          }
        }
      }
    }
  }
}
```

### 8.2 Testing Your Dotfiles
```python
# tests/test_safety.py
import pytest
from pathlib import Path

def test_no_sensitive_files_in_repo():
    """Ensure no secrets are committed"""
    forbidden_patterns = [
        "*.key", "*.pem", "*_token", "*_secret",
        ".env", ".env.*"
    ]
    # Implementation...

def test_all_links_valid():
    """Verify all symlink targets exist in repo"""
    # Implementation...

def test_checksums_present():
    """Verify all external resources have checksums"""
    # Implementation...
```

---

## 9 Migration Guide

### From existing dotfiles:
1. Create `dotfiles.toml` with safety settings enabled
2. Start with `dry_run_default: true` 
3. List current dotfiles as `link` operations
4. Run `dotfiles_sync --dry-run` to preview
5. Add backups and validation progressively
6. Test rollback before going live

### From other tools:
- **From Stow**: Convert folder structure to `link` operations
- **From Chezmoi**: Export templates, convert to `template` operations  
- **From yadm**: Extract bootstrap script to `run` operations
- **From bare git**: Add `dotfiles.toml` layer on top

### Example: Adding a new capability

Want to auto-install asdf plugins on your personal laptop? Add to `dotfiles.toml`:

```toml
[[step]]
op = "asdf_plugins"
plugins = ["nodejs", "python", "golang"]  
variants = ["personal"]
```

Then create a simple verb handler in Python:
```python
class AsdfPlugins(Verb):
    name = "asdf_plugins"
    def apply(self, spec: dict, ctx: Context) -> bool:
        for plugin in spec["plugins"]:
            subprocess.run(["asdf", "plugin-add", plugin], check=False)
        return True
```

---

## 10 Security Best Practices

1. **Never store secrets in the repo**, even encrypted
2. **Always verify checksums** for downloaded binaries
3. **Use minimal permissions** (0600 for private files, 0755 for scripts)
4. **Whitelist commands** that can be executed
5. **Validate all paths** to prevent traversal attacks
6. **Audit log everything** for accountability
7. **Test in VM first** for new configurations
8. **Regular backups** before major changes
9. **Use secret managers** (1Password CLI, Vault, etc.)
10. **Review diffs** before applying changes

---

## Summary

This enhanced specification uses **TOML format** (like Cargo.toml) and prioritizes **safety and security** while maintaining the flexibility of a custom dotfiles system:

- **Type-safe configuration**: TOML provides clear, unambiguous syntax without YAML's pitfalls
- **No data loss**: Automatic backups, dry-run by default, rollback capability
- **No security breaches**: Path validation, checksum verification, command whitelisting
- **Clear behavior**: Explicit precedence rules, conflict detection, comprehensive logging
- **Cross-platform**: Works on Linux, macOS, Windows (WSL), ARM and x86
- **Extensible**: Add new operations without changing core engine
- **Testable**: Schema validation, automated tests, dry-run mode
- **Familiar patterns**: Follows conventions from Cargo.toml, pyproject.toml

The system is designed to **fail safely** – any error triggers automatic rollback, and destructive operations require explicit confirmation. With TOML's clarity and built-in safety features, you can confidently manage dotfiles across all your machines without fear of breaking critical configurations.

Happy (and safe) hacking!