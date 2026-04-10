# Simon DistroLocs - Configuration Distribution Tool

## Specification Document

**Version**: 1.0 (Increment 1)  
**Target OS**: Linux  
**Python Version**: 3.11+ (uses `tomllib`), with fallback to `tomli` for 3.10

---

## 1. Overview

**Purpose**: A CLI tool to manage and distribute centralized configuration files/folders to system-specific destinations.

**Core Functionality**: Scans a parent directory for a single `*simon-distrolocs.toml` configuration file, parses host-specific mappings, evaluates sync status, and visualizes the configuration hierarchy using Rich terminal formatting.

---

## 2. Architecture

### 2.1 Directory Structure

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
│       └── types.py             # Type definitions
├── requirements.txt
├── requirements.md              # This document
└── pyproject.toml
```

### 2.2 Data Flow

```
CLI Input → Find TOML → Parse Config → Filter by Hostname → Evaluate Sync Status → Render Tree
    │           │            │               │                    │                    │
    ▼           ▼            ▼               ▼                    ▼                    ▼
 [Path]    [0-1 Files]   [TOML Dict]    [Host Configs]      [Sync States]        [Rich Tree]
```

---

## 3. Configuration Schema (TOML)

### 3.1 File Discovery

- Recursively search parent directory for files matching `*simon-distrolocs.toml`
- **Constraint**: If multiple matches found, abort immediately with error
- Use `tomllib` (Python 3.11+) or `tomli` (Python 3.10)

### 3.2 TOML Structure

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

[[mapping]]
name = "Vim Config"
source = "configs/vim"
target = "~/.vim"
distro_type = "workstation"

[[mapping]]
name = "System Scripts"
source = "scripts/"
target = "/usr/local/bin/"
distro_type = "server"
```

### 3.3 Host Filtering

- Use `socket.gethostname()` to get current machine name
- Configuration `[[mapping]]` entries may have optional `hosts` array
- If `hosts` is specified, mapping only applies if current hostname matches
- If `hosts` is omitted, mapping applies to all hosts

```toml
[[mapping]]
name = "Work Laptop Config"
source = "laptop/config"
target = "~/.config/laptop"
# Only apply this mapping on these hosts
hosts = ["work-laptop", "work-laptop.local"]
```

---

## 4. Sync Status Engine

### 4.1 Status States

| Status | Condition | Display |
|--------|-----------|---------|
| **Linked** | Valid symlink exists at target, pointing to source | `[link]` (cyan) |
| **Synced** | File exists at both locations, contents match exactly | `[synced]` (green) |
| **Unsynced** | File missing, or contents differ | `[unsynced]` (red) |

### 4.2 Status Evaluation Logic

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

### 4.3 Content Comparison

- **Files**: Compare byte content using `hashlib.sha256()`
- **Directories**: Compare by hashing sorted file list + content recursively

---

## 5. CLI Interface

### 5.1 Command Structure

```bash
python -m simon_distrolocs <managed_configs_directory> [OPTIONS]

Positional Arguments:
  managed_configs_directory    Parent directory containing managed configs and TOML file

Options:
  --overwrite                  Overwrite destination files with managed versions
  --sync                      Sync all unsynced configs (alias for --overwrite)
  --dry-run                   Show what would be done without making changes
  --hide-linked               Hide Linked items from output
  --hide-synced               Hide Synced items from output
  --only-unsynced             Show only Unsynced items
  -v, --verbose               Increase verbosity
  -q, --quiet                 Suppress informational messages
  --help                      Show help message
```

### 5.2 Exit Codes

- `0`: Success
- `1`: Configuration error (no TOML found, multiple TOMLs, parse error)
- `2`: File system error (permission denied, path not found)
- `3`: Overwrite cancelled by user

---

## 6. Visualization

### 6.1 Rich Tree Output

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
  [cyan][link][/cyan]        Valid symlink to managed source
```

### 6.2 Visualization Depth

- `distro_type.visualizationDepth` controls how deep the tree expands target paths
- `0`: Show only the target path (no expansion)
- `1`: Show target path + one level of subdirectories
- `2+`: Show target path + N levels

---

## 7. File Operations

### 7.1 Overwrite Behavior

When `--overwrite` or `--sync` is specified:

1. For each **Unsynced** config:
   - If target is a symlink: Remove symlink first
   - If target is a directory: Remove recursively
   - If target is a file: Remove file
   - Copy source → destination (preserving permissions)

2. **Synced** configs: No action (already matching)

3. **Linked** configs: No action (symlinks are display-only in Increment 1)

### 7.2 Directory Copying

- Use `shutil.copytree()` for directories
- Preserve file permissions and timestamps
- Handle existing files by removing first

---

## 8. Error Handling

### 8.1 TOML Discovery Errors

| Scenario | Behavior |
|----------|----------|
| No `*simon-distrolocs.toml` found | Error: "No configuration file found in {directory}" |
| Multiple TOML files found | Error: "Multiple configuration files found. Merge support coming in Increment 2." |
| TOML parse error | Error: "Failed to parse TOML: {detailed error}" |

### 8.2 File System Errors

| Scenario | Behavior |
|----------|----------|
| Source path missing | Warning: "Source path not found: {path}" (skip config) |
| Permission denied (read) | Error: "Cannot read source: {path}" |
| Permission denied (write) | Error: "Cannot write to destination: {path}" |
| Target is symlink | Skip with warning (symlinks managed separately) |

---

## 9. Type Definitions

```python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

class SyncStatus(Enum):
    LINKED = "linked"
    SYNCED = "synced"
    UNSYNCED = "unsynced"

@dataclass(frozen=True)
class DistroType:
    name: str
    visualization_depth: int

@dataclass(frozen=True)
class ConfigMapping:
    name: str
    source: Path  # Relative to managed configs directory
    target: Path  # Absolute or ~ path on system
    distro_type: Optional[str]
    hosts: tuple[str, ...]  # Empty tuple = all hosts

@dataclass(frozen=True)
class SyncState:
    mapping: ConfigMapping
    status: SyncStatus
    source_exists: bool
    target_exists: bool
    is_symlink: bool
```

---

## 10. Dependencies

```
rich>=13.0.0
```

For Python < 3.11:
```
tomli>=2.0.0
```

---

## 11. Constraints

1. **Linux-only**: Uses Linux path conventions, symlink behaviors
2. **No symlink creation in Increment 1**: Symlinks are display-only
3. **Single TOML**: Multiple TOML merging deferred to Increment 2
4. **Typed Python**: All code uses type hints, dataclasses where appropriate
5. **Pure functions**: Business logic prefers pure functions over mutation
6. **Path handling**: All file paths via `pathlib.Path`

---

## 12. Future Considerations (Increment 2+)

- Multiple TOML file merging
- Symlink creation and management
- Bidirectional sync
- Dry-run mode for overwrite
- Configuration templating
- Exclude patterns for file discovery
