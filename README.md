# Simon DistroLocs

**Configuration Distribution Tool for Linux**

A CLI application to manage and distribute centralized configuration files/folders to system-specific destinations, with integrated git repository cloning capabilities.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

Simon DistroLocs solves the problem of keeping multiple machines in sync with the same configuration files. Instead of manually copying configs or using version control solely on each machine, you maintain a centralized configuration directory with a TOML manifest that describes where each config should go.

**Key Features:**
- **Host-specific mappings**: Deploy configs only to intended machines
- **Multiple link methods**: Symlink (live updates) or anchor (fixed snapshot)
- **Rich visualization**: See sync status at a glance with colored tree output
- **Git repository cloning**: Clone repos from GitHub, Forgejo, or GitLab via `--repos-only`

---

## Installation

### Using uv (Required)

All Python package operations must use `uv`. Never use `pip` directly.

```bash
cd simon-distrolocs
uv sync
uv pip install -e .
```

For a virtual environment:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

---

## Quick Start

### 1. Create a Configuration Directory

```bash
mkdir -p ~/my-configs
cd ~/my-configs
```

### 2. Create a Config File

Create `simon-distrolocs.toml`:

```toml
[distro_types.workstation]
visualizationDepth = 2

[[mapping]]
name = "Bash RC"
source = "configs/bashrc"
target = "~/.bashrc"
distro_type = "workstation"

[[mapping]]
name = "Vim Config"
source = "configs/vim"
target = "~/.vim"
distro_type = "workstation"
```

### 3. Add Your Configs

```bash
mkdir -p configs
cp ~/.bashrc configs/bashrc
cp -r ~/.vim configs/vim
```

### 4. Run the Tool

```bash
simon-distrolocs ~/my-configs
```

**Output:**
```
Managed Configurations on workstation (3 configs)

└── Workstation Configs (3 configs)
    ├── Bash RC → ~/.bashrc [unsynced]
    └── Vim Config → ~/.vim [unsynced]
```

### 5. Sync Your Configs

```bash
# Preview what would be synced
simon-distrolocs ~/my-configs --dry-run --overwrite

# Actually sync
simon-distrolocs ~/my-configs --overwrite
```

---

## Configuration Reference

### TOML Structure

```toml
# Define visualization depth for different machine types
[distro_types.workstation]
visualizationDepth = 2

[distro_types.server]
visualizationDepth = 1

# Map configs to destinations
[[mapping]]
name = "Bash RC"
source = "configs/bashrc"
target = "~/.bashrc"
distro_type = "workstation"
method = "symlink"  # or "anchor"

# Host-specific config (excluded on certain hosts)
[[mapping]]
name = "Work Laptop Theme"
source = "laptop/theme"
target = "~/.theme"
excluded_on_hosts = ["other-host"]
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable config name |
| `source` | Yes | Path relative to config directory |
| `target` | Yes | Destination path (supports `~`) |
| `distro_type` | No | References `[distro_types.*]` for visualization depth |
| `method` | No | `symlink` (default) or `anchor` |
| `excluded_on_hosts` | No | List of hostnames where this should NOT apply |

---

## Link Methods

### Symlink (Default)

Creates a symbolic link from target → source. Changes to source reflect immediately.

```toml
method = "symlink"
```

**Best for:** Configs you edit frequently and want changes to propagate live.

### Anchor

Creates a hard copy (snapshot) at the destination. Source changes do NOT propagate.

```toml
method = "anchor"
```

**Best for:** Stable configs you want to "pin" to a known-good state.

---

## CLI Options

```bash
simon-distrolocs <dir> [options]

Options:
  --overwrite       Overwrite destination files with managed versions
  --sync            Alias for --overwrite
  --dry-run         Preview changes without applying them
  --hide-linked     Hide linked items from output
  --hide-synced     Hide synced items from output
  --only-unsynced   Show only unsynced items
  --repos-only      Clone repositories from git sources and exit
  -v, --verbose     Increase verbosity (can be repeated)
  -q, --quiet       Suppress informational messages
  --version         Show version
  --help            Show help
```

---

## Git Repository Cloning

Simon DistroLocs can clone repositories from configured git sources using the `--repos-only` flag.

### Configure Git Sources

Add `[[git_sources]]` to your TOML:

**Note:** `auth_token_path` and `cloning_destination` are resolved relative to the current working directory (repo root), not the TOML file location.

```toml
[[git_sources]]
name = "GitLab"
list_repos_url = "https://git.hmg/api/v4/projects?membership=true&per_page=100"
auth_type = "token"
auth_token_path = "02_configs/git/Gitlab/token"
cloning_destination = "git-repos/"
enabled = true
ssl_verify = false
exclude_repos = []
excluded_on_hosts = []
```

### Supported Sources

| Source | API Pattern | Auth Method |
|--------|-------------|-------------|
| GitHub | `api.github.com` or `/orgs/` | Token in URL |
| GitLab | `gitlab` or `git.hmg` | `oauth2:{token}` in URL |
| Forgejo | Default fallback | Token in URL |

### Clone Repos

```bash
# Clone all repos from configured sources
simon-distrolocs ~/my-configs --repos-only

# Preview what would be cloned
simon-distrolocs ~/my-configs --repos-only --dry-run
```

---

## Sync States

| State | Color | Meaning |
|-------|-------|---------|
| `linked` | Cyan | Valid symlink to source |
| `synced` | Green | Files match exactly |
| `unsynced` | Red | Files differ or missing |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Configuration error or git clone failure |
| 2 | File system error (permission denied, path not found) |

---

## Requirements

- Python 3.10+
- `rich>=13.0.0`
- `tomli>=2.0.0` (Python 3.10 only; 3.11+ uses built-in `tomllib`)

---

## Project Structure

```
simon-distrolocs/
├── src/
│   └── simon_distrolocs/
│       ├── __init__.py           # Package init
│       ├── __main__.py           # CLI entry point
│       ├── config.py             # TOML parsing
│       ├── evaluate_sync.py      # Sync status evaluation
│       ├── execute_sync.py       # Execute sync operations
│       ├── compare_paths.py      # Path comparison utilities
│       ├── compute_hashes.py     # File/directory hashing
│       ├── manage_files.py       # File operations (copy, remove, symlink)
│       ├── render_tree_view.py   # Rich tree rendering
│       ├── types/                # Type definitions
│       │   ├── __init__.py       # Re-exports all types
│       │   ├── define_auth_type.py
│       │   ├── define_link_method.py
│       │   ├── define_sync_status.py
│       │   ├── define_distro_type.py
│       │   ├── define_config_mapping.py
│       │   ├── define_sync_state.py
│       │   ├── define_repo_duplication.py
│       │   ├── define_app_config.py
│       │   ├── define_repo_info.py
│       │   └── define_git_source.py
│       └── clone_repos.py        # Git repository cloning
├── requirements.md               # Requirements specification
├── pyproject.toml               # Package configuration
└── README.md                    # This file
```

---

## License

MIT License - See LICENSE file for details.