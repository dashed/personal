# Configs Directory Structure

This directory contains the actual dotfiles and configuration files managed by the dotfiles-sync system.

## Directory Organization

```
configs/
├── shell/      # Shell configurations (zshrc, bashrc, aliases)
├── git/        # Git configuration (gitconfig, gitignore)
├── ssh/        # SSH configuration files
├── editor/     # Editor configs (vim, neovim, vscode)
├── terminal/   # Terminal emulator configs (tmux, alacritty, kitty)
├── macos/      # macOS-specific configurations
├── apps/       # Application-specific configs
└── claude/     # Claude AI configuration
    └── CLAUDE.md
```

## Adding New Configuration Files

1. **Choose the appropriate category directory** (or create a new one)
2. **Place your configuration file** in that directory
3. **Update dotfiles.toml** in the root directory to include the new file
4. **Test with dry-run**: `uv run dotfiles-sync sync`
5. **Apply when ready**: `uv run dotfiles-sync --apply sync`

## Current Files

### claude/
- `CLAUDE.md` - Claude AI instructions and critical thinking guidelines

## Directory Guidelines

- **shell/** - Shell configuration files like `.zshrc`, `.bashrc`, `.aliases`
- **git/** - Git configuration like `.gitconfig`, `.gitignore_global`
- **ssh/** - SSH configuration files (remember to set proper permissions)
- **editor/** - Text editor configurations for vim, neovim, VS Code, etc.
- **terminal/** - Terminal emulator settings for tmux, alacritty, kitty, etc.
- **macos/** - macOS-specific settings and preferences
- **apps/** - Configuration for specific applications

## Example Usage

To add a new zsh configuration:

```bash
# 1. Copy your zshrc to the shell directory
cp ~/.zshrc configs/shell/zshrc

# 2. Add to dotfiles.toml
cat >> dotfiles.toml << 'EOF'

[[step]]
op = "copy"
src = "configs/shell/zshrc"
dst = "~/.zshrc"
description = "Zsh configuration"
EOF

# 3. Test the configuration
uv run dotfiles-sync sync

# 4. Apply when ready
uv run dotfiles-sync --apply sync
```

## Best Practices

1. **Use descriptive filenames** without the leading dot (e.g., `gitconfig` not `.gitconfig`)
2. **Group related configs** in the same directory
3. **Document special requirements** (like file permissions) in comments
4. **Test changes** with dry-run before applying
5. **Commit frequently** to track configuration evolution