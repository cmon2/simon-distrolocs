# Simon DistroLocs - Requirements Specification

**Version**: 1.2.0  
**Target OS**: Linux  
**Python Version**: 3.10+ (uses `tomllib` for 3.11+, `tomli` fallback for 3.10)

---

## 1. Overview

### Purpose
A CLI tool to manage and distribute centralized configuration files/folders to system-specific destinations, with integrated git repository cloning and duplication capabilities.

### Core Functionality
1. **Configuration Distribution**: Scans a parent directory for `*simon-distrolocs.toml`, parses host-specific mappings, evaluates sync status, and visualizes the configuration hierarchy using Rich terminal formatting.
2. **Git Repository Cloning**: Discovers and clones repositories from configured git sources (GitHub, Forgejo, GitLab) based on `git_sources` TOML configuration.
3. **Repository Duplication**: Duplicates repositories from external sources (GitHub, GitLab, Forgejo) to local Forgejo instance, with optional cloning to target locations.

---

## 2. Configuration Schema (TOML)

### 2.1 File Discovery

- Recursively search parent directory for files matching `*simon-distrolocs.toml`
- **Constraint**: If multiple matches found, abort with error (unless identical content, then use first)
- Use `tomllib` (Python 3.11+) or `tomli` (Python 3.10)

### 2.2 Configuration Mappings

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
# Excluded on these hosts (empty = apply to all)
excluded_on_hosts = []
```

### 2.3 Git Sources Configuration

```toml
[[git_sources]]
name = "GitHub Public"
list_repos_url = "https://api.github.com/users/cmon2/repos"
auth_type = "token"
auth_token_path = "02_configs/git/GitHub/token"
cloning_destination = "git-repos/"
enabled = true
ssl_verify = true
exclude_repos = []

[[git_sources]]
name = "Forgejo Private"
list_repos_url = "http://localhost:3000/api/v1/users/simon/repos"
auth_type = "token"
auth_token_path = "02_configs/git/Forgejo/token"
cloning_destination = "git-repos/"
enabled = true
ssl_verify = false
exclude_repos = []

[[git_sources]]
name = "GitLab"
list_repos_url = "https://git.hmg/api/v4/projects"
auth_type = "token"
auth_token_path = "02_configs/git/Gitlab/token"
cloning_destination = "git-repos/"
enabled = true
ssl_verify = false
exclude_repos = []
excluded_on_hosts = []
limit_to_recent_repos = 0  # Optional: clone only N most recently updated repos
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
| `ssl_verify` | boolean | **Yes** | Must be explicitly true or false |
| `exclude_repos` | array | No | List of repo names to skip |
| `excluded_on_hosts` | array | No | List of hostnames where this source should NOT be used |
| `limit_to_recent_repos` | integer | No | If > 0, clone only this many most recently updated repos |

### 2.4 Repository Duplication Configuration

```toml
[[duplication]]
name = "pgxperts-prim-dev"           # Name referenced by --duplicate CLI flag
source_type = "gitlab"               # For auth lookup (gitlab, github, forgejo)
source_url = "https://git.hmg/simon/pgxperts-prim.git"
forgejo_target = "pgxperts-prim"     # Base name for Forgejo repo
target_clone_locations = ["~/git-repos/", "/var/dev/repos/"]
enabled = true
```

#### Duplication Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique name referenced by `--duplicate` CLI flag |
| `source_type` | string | Yes | Type of source for auth lookup (`gitlab`, `github`, `forgejo`) |
| `source_url` | string | Yes | Git URL of the source repository |
| `forgejo_target` | string | Yes | Base name for Forgejo repo (without namespace) |
| `target_clone_locations` | array | Yes | Directories where duplicated repo should be cloned |
| `enabled` | boolean | No | Whether this duplication is active (default: true) |

---

## 3. Sync Status Engine

### 3.1 Status States

| Status | Condition | Display |
|--------|-----------|---------|
| **Linked** | Valid symlink exists at target, pointing to source | `[linked]` (cyan) |
| **Synced** | File exists at both locations, contents match exactly | `[synced]` (green) |
| **Unsynced** | File missing, or contents differ | `[unsynced]` (red) |

### 3.2 LinkMethod Variants

| Method | Behavior | Sync Status | Use Case |
|--------|----------|-------------|----------|
| **symlink** (default) | Creates symbolic link from target → source | Linked | Configs that change frequently |
| **anchor** | Hard copy of source to target (snapshot) | Synced | Stable configs; fixed point |

### 3.3 Status Evaluation Logic

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

## 4. CLI Interface

### 4.1 Command Structure

```bash
simon-distrolocs <managed_configs_directory> [OPTIONS]

# Or using module syntax:
python -m simon_distrolocs <managed_configs_directory> [OPTIONS]
```

### 4.2 Options

| Option | Description |
|--------|-------------|
| `--overwrite` | Overwrite destination files with managed versions |
| `--sync` | Sync all unsynced configs (alias for --overwrite) |
| `--dry-run` | Show what would be done without making changes |
| `--hide-linked` | Hide Linked items from output |
| `--hide-synced` | Hide Synced items from output |
| `--only-unsynced` | Show only Unsynced items |
| `--repos-only` | Clone repositories from configured git sources and exit |
| `--duplicate <name>` | Duplicate a repository to Forgejo (requires `--branch`) |
| `--branch <branch>` | Branch to duplicate (required with `--duplicate`) |
| `-v, --verbose` | Increase verbosity (can be repeated) |
| `-q, --quiet` | Suppress informational messages |
| `--version` | Show version number |

### 4.3 Exit Codes

- `0`: Success
- `1`: Configuration error, git clone failure, or duplication failure
- `2`: File system error (permission denied, path not found)

---

## 5. Git Repository Cloning

### 5.1 Source Types

| Source | Detection Pattern | Auth Header |
|--------|-------------------|-------------|
| **GitHub** | `github.com` in URL | `Authorization: token {token}` |
| **GitLab** | `gitlab` or `git.hmg` in URL | `PRIVATE-TOKEN: {token}` with `oauth2:` prefix |
| **Forgejo** | Default (fallback) | `Authorization: token {token}` |

### 5.2 Clone URL Building

- GitHub: Uses token directly in URL
- GitLab: Prefixes token with `oauth2:` before embedding in URL
- Forgejo: Uses token directly in URL

### 5.3 Clone Behavior

- Skips repos that already exist locally
- Respects `exclude_repos` list to skip certain repositories
- Sorts by `updated_at` descending when `limit_to_recent_repos` is set
- Supports `--dry-run` to preview what would be cloned
- Disables SSL verification when `ssl_verify = false`
- Warns if no auth verification script exists for a source

### 5.4 Auth Verification

Before cloning, the system verifies authentication for each git source by running verification scripts at `auth_verification/`:
- `verify_github_ssh.sh`
- `verify_forgejo_token.sh`
- `verify_gitlab_token.sh`

If authentication fails, cloning aborts with an error. This ensures credentials work before attempting operations.

---

## 6. Repository Duplication

### 6.1 Workflow

1. Find duplication config by name from TOML
2. Verify branch exists in source repository
3. Check if repo exists on Forgejo (offer delete/recreate if so)
4. Create repo on Forgejo if needed
5. Clone source repo and push to Forgejo
6. Clone from Forgejo to all `target_clone_locations`

### 6.2 Behavior

- **Idempotent**: Safe to re-run after failures by cleaning up first
- **Branch verification**: Aborts if branch doesn't exist in source
- **Local clone check**: Aborts if target location already has a clone
- **SSH for source**: Uses `GIT_SSH_COMMAND` with `~/.ssh/config` for source clones

### 6.3 Forgejo URL Format

Tokens can be stored in two formats:
1. Raw token: `tokenstring`
2. URL format: `http://user:token@host` (token extracted from password portion)

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
    excluded_on_hosts: tuple[str, ...] = field(default_factory=tuple)
    method: Optional[LinkMethod] = None

@dataclass
class RepoInfo:
    name: str
    clone_url: str
    full_name: str
    updated_at: Optional[str] = None  # For sorting by recency

@dataclass
class GitSource:
    name: str
    list_repos_url: str
    auth_type: AuthType
    auth_token_path: Path
    cloning_destination: Path
    enabled: bool = True
    ssl_verify: bool = True
    exclude_repos: tuple[str, ...] = field(default_factory=tuple)
    excluded_on_hosts: tuple[str, ...] = field(default_factory=tuple)
    limit_to_recent_repos: int = 0

    def get_auth_token(self) -> str:
        """Read authentication token from token file.
        
        Handles two formats:
        1. Raw token: "tokenstring"
        2. URL format: "http://user:token@host"
        """
        try:
            with open(self.auth_token_path) as f:
                token = f.read().strip()
            
            # Handle URL-formatted tokens
            if "@" in token and "://" in token:
                parts = token.split("@")[0]
                if ":" in parts:
                    token = parts.rsplit(":", 1)[1]
            
            return token
        except OSError:
            return ""

@dataclass
class RepoDuplication:
    name: str
    source_type: str
    source_url: str
    forgejo_target: str
    target_clone_locations: tuple[str, ...]
    enabled: bool = True

@dataclass
class CloneResult:
    """Result of a clone operation."""
    repo: RepoInfo
    success: bool
    message: str
```

---

## 9. Dependencies

### Runtime
```
rich>=13.0.0
cmon2lib>=0.1.0
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
7. **Explicit SSL verification**: `ssl_verify` must be explicitly set (no default)

---

## 11. Future Considerations

- Multiple TOML file merging
- Bidirectional sync
- Configuration templating
- Exclude patterns for file discovery
- SSH key authentication for git sources
- Additional auth verification scripts (SSH)