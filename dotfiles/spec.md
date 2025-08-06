Below is a **design blueprint** that turns the one-off `manifest.yaml` into a **fully declarative meta-configuration layer**.
You can extend it to cover *anything* you might want a new machine to inherit: dotfiles, Oh-My-Zsh add-ons, Homebrew/apt packages, VS Code extensions, one-time shell hooks, secrets, OS-specific tweaks, \&c.

The goal is that **no path or behaviour is hard-coded in the Python synchroniser**; everything lives in a human-readable file that ships inside (or alongside) your dotfiles repo.

---

## 1 Key design principles

| Principle                        | Why it matters                                                                                                     |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Everything lives in the repo** | Re-cloning any branch is a perfect snapshot; nothing relies on state that isn’t version-controlled.                |
| **Declarative, not imperative**  | Describe end-state (“`~/.zshrc` is a symlink to `zsh/zshrc`”) rather than an ordered shell script.                 |
| **Variants + selectors**         | Let the *config* decide whether an item applies to `personal`, `work`, `linux`, `darwin-intel`, `darwin-arm`, etc. |
| **Composable operations**        | “symlink”, “copy”, “append”, “mergeYAML”, “run shell once”, “brew install” – each is a first-class verb.           |
| **Extensible schema**            | New verbs or selectors can be dropped in without changing old entries or the sync engine.                          |

---

## 2 Meta-configuration schema (YAML; call it **`meta.yaml`**)

```yaml
# ----------------- GLOBAL METADATA -----------------
meta:
  repo_version: 1          # bump if you introduce breaking changes
  default_variant: auto    # 'auto' = pick from hostname map below

# Map substrings of hostname ➜ variant name
hostname_map:
  work-mbp: work
  mac-personal: personal

# -------------- DECLARATIVE INSTRUCTIONS -----------
steps:
  #
  # 2.1 Dotfiles (anywhere ➜ anywhere)
  #
  - op: link                # verbs: link | copy | append | template
    src: zsh/zshrc          # path *inside* repo
    dst: ~/.zshrc           # may use ~ or $HOME
    variants: [all]         # explicit list or omit to mean 'all'

  - op: link
    src: zsh/zshrc.work
    dst: ~/.zshrc           # same target; later entries override earlier ones
    variants: [work]

  - op: link
    src: ssh/config.work
    dst: ~/.ssh/config
    variants: [work]

  - op: link
    src: git/gitconfig
    dst: ~/.gitconfig
    platforms: [darwin, linux]  # optional extra selector

  #
  # 2.2 Oh-My-Zsh custom plugins (sync whole dirs)
  #
  - op: syncdir             # mirror a directory recursing, rm extraneous
    src: zsh_custom_plugins
    dst: ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins
    variants: [all]

  #
  # 2.3 Package managers
  #
  - op: brew_install
    list:
      - git
      - neovim
      - jq
    variants: [darwin]

  - op: apt_install
    list:
      - build-essential
      - ripgrep
    variants: [linux]

  #
  # 2.4 VS Code extensions
  #
  - op: vscode_extensions
    list:
      - ms-vscode.vscode-typescript-next
      - eamodio.gitlens
    variants: [all]

  #
  # 2.5 One-time shell hook per machine
  #
  - op: run
    cmd: "./scripts/macos_defaults.sh"
    variants: [personal]
    run_once: true          # via a stamp file under ~/.local/state/dotfiles

  #
  # 2.6 Secrets (pulled from 1Password, SOPS, etc.)
  #
  - op: decrypt_sops
    src: secrets/github_token.enc.yaml
    dst: ~/.config/github_token.yaml
    variants: [all]
```

### Selector fields

* `variants` – e.g. `personal`, `work`, `gaming-rig`.
* `platforms` – `linux`, `darwin`, `windows` (auto-filled from `sys.platform`).
* You can easily add more (e.g. `arch: [arm64, x86_64]`, `env: [CI]`) – the engine only needs to **ignore** unknown keys that don’t match.

### Supported verbs (baseline)

| Verb                                                  | Effect                                                                      |
| ----------------------------------------------------- | --------------------------------------------------------------------------- |
| `link`                                                | Create or replace a **symlink** (`dst` → `src`).                            |
| `copy`                                                | Copy file/dir verbatim; overwrite if checksum differs.                      |
| `append`                                              | Append text from `src` to end of `dst` (create if missing).                 |
| `template`                                            | Render Jinja2 template with variables `{home}`, `{variant}`, env vars, etc. |
| `syncdir`                                             | Mirror directory tree (rsync-style, delete extraneous).                     |
| `brew_install`, `apt_install`, `vscode_extensions`, … | Wrapper verbs that internally call out to system package manager.           |
| `run`                                                 | Run arbitrary shell; if `run_once: true` create a stamp file after success. |
| `decrypt_sops`                                        | Decrypt to destination (requires `sops`).                                   |

You only need **one tiny class per new verb** in the Python engine.

---

## 3 Updated repository layout (flexible)

```
dotfiles/
│
├── meta.yaml                # ← single source of truth
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
├── Brewfile                  # could be referenced by a 'run' verb
└── scripts/
    └── macos_defaults.sh
```

Nothing else is imposed – nest as you wish; only **`src:`** paths in `meta.yaml` matter.

---

## 4 Synchroniser architecture (high-level)

```text
main()
 ├─ parse CLI (--variant, --config, --dry-run, ...)
 ├─ load meta.yaml  ➜  dict
 ├─ resolve variant:
 │     flag  >  $DOTFILES_VARIANT env  > hostname_map  > default
 ├─ evaluate each step:
 │     if selectors match current context → dispatch to verb handler
 │
 └─ summary + exit code (non-zero on any failure)
```

### Core classes

```python
class Context:
    variant: str
    platform: str  # 'darwin', 'linux', 'win32'
    arch: str      # 'arm64', 'x86_64'
    env: dict

class StepRunner:
    def __init__(self, ctx): ...
    def run_step(self, spec): ...   # looks at spec["op"] and dispatches

class Verb:
    name: str
    def apply(self, spec, ctx): ...
```

Adding a new operation is **one file** inheriting `Verb` and registering itself.

---

## 5 Handling *uv* & reproducible Python envs

1. Ship a **`requirements.lock.txt`** generated by `uv pip compile`.
2. Provide a helper script `bootstrap.sh`:

```bash
#!/bin/sh
set -e
if ! command -v uv >/dev/null; then
  curl -Ls https://github.com/astral-sh/uv/releases/download/v0.2.9/uv-x86_64-apple-darwin.tar.gz | tar xz -C /usr/local/bin uv
fi
uv pip sync requirements.lock.txt
python -m dotfiles_sync --repo . "$@"
```

All machines – work or personal – get the *exact* same Python package set.

---

## 6 Migrating from the old `manifest.yaml`

* Rename it to `meta.yaml`.
* For every earlier list item, wrap it in a `steps:` entry with `op: link`.
* Move variant-specific arrays under separate `op` entries with `variants: [...]`.
* Keep extending with new verbs as your needs grow.

---

## 7 Example: adding a new capability in 90 seconds

> **Need:** auto-install *asdf* plugins only on personal laptop.

1. Declare in `meta.yaml`:

```yaml
- op: asdf_plugins
  list: [nodejs, python, golang]
  variants: [personal]
```

2. Drop `asd_plugins.py` in `verbs/`:

```python
class AsdfPlugins(Verb):
    name = "asdf_plugins"
    def apply(self, spec, ctx):
        for plugin in spec["list"]:
            sh(["asdf", "plugin-add", plugin], check=False)
```

3. Commit & push. All future `dotfiles sync` runs on your personal Mac will ensure those plugins exist.

---

## 8 Why not use *X* (Stow, chezmoi, yadm …)?

Those tools are great, but adding more languages & ecosystems can be overkill when you:

* already need Python (for `uv`)
* want package-manager orchestration plus arbitrary hooks, not *just* file placement
* prefer a single config file under version control so teammates can audit PRs.

That said, nothing stops you from **wrapping** Stow/Chezmoi as verbs (`op: stow`).

---

### TL;DR

* Put a single **`meta.yaml`** at the root.
* Describe every desired end-state as a *step* with a simple verb.
* Extend verbs on demand; the sync engine stays tiny and generic.
* Variants, platforms, architectures, hosts – all just selectors in the YAML.
* Result: one `dotfiles sync` command clones/updates the repo and brings any machine (work VM, personal MacBook, CI container) to parity with exactly the configuration slices you choose.

You now have a **fully flexible, meta-configured dotfiles system**—powerful enough to grow indefinitely, yet readable enough to review in a Git diff. Happy hacking!
