# Simon DistroLocs - Requirements Specification

**Version**: 1.1.0  
**Target OS**: Linux  
**Python Version**: 3.10+ (uses `tomllib` for 3.11+, `tomli` fallback for 3.10)

---

## 1. Overview

### Purpose
A CLI tool to manage and distribute centralized configuration files/folders to system-specific destinations, with integrated git repository cloning capabilities.

### Core Functionality
1. **Configuration Distribution**: Scans a parent directory for `*simon-distrolocs.toml`, parses host-specific mappings, evaluates sync status, and visualizes the configuration hierarchy using Rich terminal formatting.
2. **Git Repository Cloning**: Discovers and clones repositories from configured git sources (GitHub, Forgejo, GitLab) based on `git_sources` TOML configuration.

---

## 2. Architecture

### Directory Structure

```
simon-distrolocs/
├── src/
│   └── simon_distrolocs/
│       ├── __init__.py
│       ├── __main__.py          # CLI entry point
│       ├── config.py            # TOML parsing and validation
│       ├── sync_engine.py       # Sync status evaluation
│       ├── filesystem.py        # File operations (copy, compare)
│       ├── visualization.py     # Rich tree rendering
│       ├── types.py             # Type definitions
│       └── git_clone.py         # Git repository cloning
├── requirements.txt
├── requirements.md              # This document
└── pyproject.toml
```

### Data Flow (Configuration)

```
CLI Input → Find TOML → Parse Config → Filter by Hostname → Evaluate Sync Status → Render Tree
    │           │            │               │                    │                    │
    ▼           ▼            ▼               ▼                    ▼                    ▼
 [Path]    [0-1 Files]   [TOML Dict]    [Host Configs]      [Sync States]        [Rich Tree]
```

### Data Flow (Git Clone)

```
CLI --repos-only → Find TOML → Parse git_sources → Fetch repos from APIs → Clone each repo
```

---

## 3. Configuration Schema (TOML)

### 3.1 File Discovery

- Recursively search parent directory for files matching `*simon-distrolocs.toml`
- **Constraint**: If multiple matches found, abort with error (unless identical content, then use first)
- Use `tomllib` (Python 3.11+) or `tomli` (Python 3.10)

### 3.2 Configuration Mappings

```toml
[distro_types.workstation]
# visualizationDepth: How deep to render target folder structure in tree (0 = files only)
visualizationDepth = 2

[distro_types.server]
visualizationDepth = 1

[[mapping]]
# Human-readable name for the managed config
name = "Bash RC"
# Source path relative to parent directory (where the managed config lives)
source = "configs/bashrc"
# Target path on the system (where it should go)
target = "~/.bashrc"
# Optional: Reference to a distro_type (defaults to 0 depth if omitted)
distro_type = "workstation"
# Optional: Link method - "symlink" (default) or "anchor"
method = "symlink"

[[mapping]]
name = "Work Laptop Config"
source = "laptop/config"
target = "~/.config/laptop"
# Only apply this mapping on these hosts
hosts = ["work-laptop", "work-laptop.local"]
```

### 3.3 Git Sources Configuration

```toml
[[git_sources]]
name = "GitHub Public"
list_repos_url = "https://api.github.com/users/cmon2/repos"
auth_type = "token"
auth_token_path = "02_configs/git/GitHub/token"
cloning_destination = "git-repos/"
enabled = true
ssl_verify = true
exclude = ["simon_ide"]

[[git_sources]]
name = "Forgejo Private"
list_repos_url = "http://localhost:3000/api/v1/users/simon/repos"
auth_type = "token"
auth_token_path = "02_configs/git/Forgejo/token"
cloning_destination = "git-repos/"
enabled = true
ssl_verify = false
exclude = []

[[git_sources]]
name = "GitLab"
list_repos_url = "https://git.hmg/api/v4/projects"
auth_type = "token"
auth_token_path = "02_configs/git/Gitlab/token"
cloning_destination = "git-repos/"
enabled = true
ssl_verify = false
exclude = []
```

**Note:** `auth_token_path` and `cloning_destination` are resolved relative to the current working directory (repo root), not the TOML file location.

#### Git Source Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable name for the source |
| `list_repos_url` | string | Yes | API URL to list repositories |
| `auth_type` | string | Yes | `token`, `ssh`, or `none` |
| `auth_token_path` | string | Yes (if auth_type=token) | Path to file containing the token |
| `cloning_destination` | string | Yes | Directory where cloned repos will be placed |
| `enabled` | boolean | No | Whether this source is active (default: true) |
| `ssl_verify` | boolean | No | Whether to verify SSL certificates (default: true) |
| `exclude` | array | No | List of repo names to skip |

---

## 4. Sync Status Engine

### 4.1 Status States

| Status | Condition | Display |
|--------|-----------|---------|
| **Linked** | Valid symlink exists at target, pointing to source | `[linked]` (cyan) |
| **Synced** | File exists at both locations, contents match exactly | `[synced]` (green) |
| **Unsynced** | File missing, or contents differ | `[unsynced]` (red) |

### 4.2 LinkMethod Variants

| Method | Behavior | Sync Status | Use Case |
|--------|----------|-------------|----------|
| **symlink** (default) | Creates symbolic link from target → source | Linked | Configs that change frequently |
| **anchor** | Hard copy of source to target (snapshot) | Synced | Stable configs; fixed point |

### 4.3 Status Evaluation Logic

```
1. If target is symlink:
   - If symlink target == absolute(source): Linked
   - Else: Unsynced
2. Else if target exists:
   - If contents match source: Synced
   - Else: Unsynced
3. Else:
   - Unsynced (missing)
```

---

## 5. CLI Interface

### 5.1 Command Structure

```bash
simon-distrolocs <managed_configs_directory> [OPTIONS]

# Or using module syntax:
python -m simon_distrolocs <managed_configs_directory> [OPTIONS]
```

### 5.2 Options

| Option | Description |
|--------|-------------|
| `--overwrite` | Overwrite destination files with managed versions |
| `--sync` | Sync all unsynced configs (alias for --overwrite) |
| `--dry-run` | Show what would be done without making changes |
| `--hide-linked` | Hide Linked items from output |
| `--hide-synced` | Hide Synced items from output |
| `--only-unsynced` | Show only Unsynced items |
| `--repos-only` | Clone repositories from configured git sources and exit |
| `-v, --verbose` | Increase verbosity (can be repeated) |
| `-q, --quiet` | Suppress informational messages |
| `--version` | Show version number |

### 5.3 Exit Codes

- `0`: Success
- `1`: Configuration error or git clone failure
- `2`: File system error (permission denied, path not found)

---

## 6. Git Repository Cloning

### 6.1 Source Types

| Source | API Pattern | Auth Header |
|--------|-------------|-------------|
| **GitHub** | `api.github.com` or `/orgs/` | `Authorization: token {token}` |
| **GitLab** | `gitlab` or `git.hmg` | `PRIVATE-TOKEN: {token}` with `oauth2:` prefix |
| **Forgejo** | Default (fallback) | `Authorization: token {token}` |

### 6.2 Clone URL Building

- GitHub: Uses token directly in URL
- GitLab: Prefixes token with `oauth2:` before embedding in URL
- Forgejo: Uses token directly in URL

### 6.3 Clone Behavior

- Skips repos that already exist locally
- Respects `exclude` list to skip certain repositories
- Supports `--dry-run` to preview what would be cloned
- Disables SSL verification when `ssl_verify = false`

---

## 7. Visualization

### Rich Tree Output

```
simon-distrolocs [cyan]●[/cyan] Managed Configurations on [yellow]workstation[/yellow]

└── [bold]Workstation Configs[/bold] ([green]3 configs[/green])
    ├── [cyan]●[/cyan] [bold]Bash RC[/bold] → ~/.bashrc [green][synced][/green]
    │   └── ~/.bashrc [dim]→ configs/bashrc[/dim]
    ├── [cyan]●[/cyan] [bold]Vim Config[/bold] → ~/.vim [yellow][unsynced][/yellow]
    │   └── ~/.vim [dim]→ configs/vim[/dim]
    └── [cyan]●[/cyan] [bold]Scripts[/bold] → /usr/local/bin/ [green][synced][/green]
        └── /usr/local/bin/ [dim]→ scripts/[/dim]

Legend:
  [green][synced][/green]    Files match exactly
  [yellow][unsynced][/yellow] Files differ or missing
  [cyan][linked][/cyan]      Valid symlink to managed source
```

---

## 8. Type Definitions

```python
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

class LinkMethod(Enum):
    SYMLINK = "symlink"  # Default
    ANCHOR = "anchor"    # Hard copy

class SyncStatus(Enum):
    LINKED = "linked"
    SYNCED = "synced"
    UNSYNCED = "unsynced"

class AuthType(Enum):
    TOKEN = "token"
    SSH = "ssh"
    NONE = "none"

@dataclass(frozen=True)
class DistroType:
    name: str
    visualization_depth: int

@dataclass(frozen=True)
class ConfigMapping:
    name: str
    source: Path
    target: Path
    distro_type: Optional[str] = None
    hosts: tuple[str, ...] = field(default_factory=tuple)
    method: Optional[LinkMethod] = None

@dataclass(frozen=True)
class RepoInfo:
    name: str
    clone_url: str
    full_name: str

@dataclass
class GitSource:
    name: str
    list_repos_url: str
    auth_type: AuthType
    auth_token_path: Path
    cloning_destination: Path
    enabled: bool = True
    ssl_verify: bool = True
    exclude: tuple[str, ...] = field(default_factory=tuple)

    def get_auth_token(self) -> str:
        """Read authentication token from token file."""
        try:
            with open(self.auth_token_path) as f:
                return f.read().strip()
        except OSError:
            return ""
```

---

## 9. Dependencies

### Runtime
```
rich>=13.0.0
```

### Python Version Compatibility
- Python 3.11+: Uses built-in `tomllib`
- Python 3.10: Uses `tomli>=2.0.0` as fallback

### Optional Dependencies
```
tomli>=2.0.0;python_version<'3.11'
```

---

## 10. Constraints

1. **Linux-only**: Uses Linux path conventions, symlink behaviors
2. **Single TOML**: Multiple TOML merging deferred to future
3. **Typed Python**: All code uses type hints, dataclasses where appropriate
4. **Pure functions**: Business logic prefers pure functions over mutation
5. **Path handling**: All file paths via `pathlib.Path`
6. **No sensitive data in public repos**: Tokens/keys must not be committed

---

## 11. Future Considerations

- Multiple TOML file merging
- Bidirectional sync
- Configuration templating
- Exclude patterns for file discovery
- SSH key authentication for git sources