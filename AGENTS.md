# AGENTS.md - Simon DistroLocs

Instructions for AI agents working on the Simon DistroLocs project.

---

## Project Overview

Simon DistroLocs is a CLI tool for managing and distributing centralized configuration files to system-specific destinations, with git repository cloning capabilities.

**Repository**: `git-repos/simon-public-git/simon-distrolocs/` (GitHub public repo)
**Location in simon_ide**: `git-repos/simon-public-git/simon-distrolocs/`

---

## Key Conventions

### Naming Convention
- **Functions**: `<<verb>>_<<substantive>>` (e.g., `get_input`, `check_tools`)
- **Dataclasses**: PascalCase (e.g., `ConfigMapping`, `GitSource`)
- **Enums**: PascalCase with UPPER_SNAKE values (e.g., `LinkMethod.SYMLINK`)

### Python Standards
- Use `pathlib.Path` for all file paths (no `os.path` or string paths)
- Use type hints on all functions and classes
- Use dataclasses with `frozen=True` for immutable types
- Import ordering: stdlib → third-party → local (enforced by isort)

### DRY Principle
- Configuration values exist in exactly one place (TOML config)
- Script logic reads from config, never duplicates values
- Constants defined once, referenced everywhere

---

## Architecture

### Core Modules

| Module | Responsibility |
|--------|----------------|
| `__main__.py` | CLI entry point, argument parsing |
| `config.py` | TOML file discovery, parsing, validation |
| `types/` | Type definitions (individual define_*.py files) |
| `evaluate_sync.py` | Sync status evaluation |
| `execute_sync.py` | Execute sync operations |
| `compare_paths.py` | Path comparison utilities |
| `compute_hashes.py` | File/directory hash computation |
| `manage_files.py` | File operations (copy, remove, symlink) |
| `render_tree_view.py` | Rich tree rendering |
| `clone_repos.py` | Git repository cloning from API sources |

### Data Flow

```
CLI Input → Find TOML → Parse Config → Filter by Hostname → Evaluate Sync Status → Render Tree
```

---

## Configuration Schema

### Mapping Structure

```toml
[[mapping]]
name = "Config Name"
source = "relative/path"      # Source relative to config directory
target = "~/.config"          # Destination (supports ~)
distro_type = "workstation"   # Optional: references [distro_types.*]
method = "symlink"           # Optional: "symlink" (default) or "anchor"
excluded_on_hosts = []       # Optional: hosts where this should NOT apply
```

### Git Sources Structure

**Note:** `auth_token_path` and `cloning_destination` are resolved relative to the current working directory (repo root), not the TOML file location.

```toml
[[git_sources]]
name = "Source Name"
list_repos_url = "https://api.example.com/repos"
auth_type = "token"           # "token", "ssh", or "none"
auth_token_path = "path/to/tokenfile"
cloning_destination = "destinationDir/"
enabled = true
ssl_verify = true             # REQUIRED - must be explicitly true or false
exclude_repos = ["repo1", "repo2"]
excluded_on_hosts = []       # Optional: hosts where this source should NOT be used
limit_to_recent_repos = 0    # Optional: if > 0, clone only N most recently updated repos
```

---

## Testing

**IMPORTANT**: Always use `uv` for Python operations. Never use `pip` directly.

### Manual Testing

```bash
# Test basic import (using uv venv)
uv venv
source .venv/bin/activate
uv pip install -e .
python -c "from simon_distrolocs import __main__"

# Test help
python -m simon_distrolocs --help

# Test with a real config directory
mkdir -p /tmp/test-configs
echo '[distro_types.test]' > /tmp/test-configs/test.toml
echo 'visualizationDepth = 1' >> /tmp/test-configs/test.toml
python -m simon_distrolocs /tmp/test-configs
```

### Verify clone_repos Module

```bash
# Test imports (using uv venv)
uv venv
source .venv/bin/activate
uv pip install -e .
python -c "from simon_distrolocs.clone_repos import clone_all_repos, RepoInfo, GitSource"

# Verify types exist
python -c "from simon_distrolocs.types import AuthType, GitSource, RepoInfo"
```

---

## Adding New Features

### New Link Method

1. Add value to `LinkMethod` enum in `types.py`
2. Update `_is_copy_method()` in `sync_engine.py`
3. Add handling in `execute_sync()` in `sync_engine.py`
4. Update documentation in `requirements.md`

### New Git Source

1. Add detection logic in `fetch_repos()` in `clone_repos.py`
2. Add fetch function (e.g., `_fetch_repos_newsource()`)
3. Update URL detection patterns
4. Add tests for API response parsing

---

## Error Handling

### Configuration Errors
- `ConfigError` in `config.py` for TOML parsing issues
- Exit code 1 for configuration errors

### File System Errors
- Exit code 2 for permission denied, path not found
- Use `safe_execute_copy()` for graceful failures

### Git Clone Errors
- `CloneError` exception for cloning failures
- Return `(cloned, failed)` tuple from `clone_all_repos()`

---

## Dependencies

### Runtime
- `rich>=13.0.0` - Terminal formatting

### Python Version
- 3.11+: Uses built-in `tomllib`
- 3.10: Uses `tomli>=2.0.0` as fallback

---

## Security

- **Never commit tokens/keys**: Auth tokens are stored in separate files, not in TOML
- **No sensitive data in public repos**: The GitHub repo is public; tokens go in gitignored paths
- **Token file format**: Plain text, one token per file

---

## File Structure

```
simon-distrolocs/
├── src/simon_distrolocs/
│   ├── __init__.py
│   ├── __main__.py         # CLI entry (DO NOT import from here for functionality)
│   ├── config.py           # Config loading
│   ├── filesystem.py       # File ops
│   ├── clone_repos.py      # Git cloning
│   ├── sync_engine.py      # Sync logic
│   ├── types.py            # Type defs
│   └── visualization.py    # Rich output
├── requirements.md          # Full requirements spec
├── pyproject.toml          # Package config
└── README.md               # User-facing docs
```

---

## Common Tasks

### Update Version
1. Edit `__init__.py` `__version__`
2. Edit `pyproject.toml` version
3. Add entry to `CHANGELOG.md`
4. Create git tag

### Add New CLI Option
1. Add argument in `create_parser()` in `__main__.py`
2. Handle in `main()` function
3. Update `--help` output
4. Document in README.md

---

## Notes

- This is a **public repository** on GitHub (`simon-public-git/simon-distrolocs`)
- The **main development repo** is `simon_ide` on Forgejo (private)
- Changes should be committed to the GitHub clone first, then pulled into simon_ide
- The `git-repos/simon-public-git/simon-distrolocs/` path is gitignored in simon_ide