# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-04-12

### Added

- **Initial Release**: Core configuration distribution functionality
  - TOML configuration parsing with `*simon-distrolocs.toml` discovery
  - Host-specific mapping filtering via `socket.gethostname()`
  - Sync status evaluation: Linked, Synced, Unsynced
  - Rich tree visualization with color-coded status
  - Symlink and Anchor link methods
  - `--overwrite` and `--sync` flags for applying configurations
  - `--dry-run` preview mode
  - Filtering options: `--hide-linked`, `--hide-synced`, `--only-unsynced`

- **Git Repository Cloning** (via `--repos-only`)
  - `git_clone.py` module for discovering and cloning repositories
  - Support for GitHub, Forgejo, and GitLab APIs
  - `[[git_sources]]` TOML configuration section
  - Token-based authentication with proper URL embedding
  - `exclude_repos` option to skip certain repositories
  - `excluded_on_hosts` option to disable sources on certain hosts
  - `ssl_verify` option to disable SSL for local instances

- **New Types** in `types.py`
  - `AuthType` enum: TOKEN, SSH, NONE
  - `RepoInfo` dataclass: name, clone_url, full_name
  - `GitSource` dataclass: name, list_repos_url, auth_type, auth_token_path, cloning_destination, enabled, ssl_verify, exclude_repos, excluded_on_hosts

- **New Configuration Parsing** in `config.py`
  - `_parse_auth_type()` function
  - `_parse_git_sources()` function for parsing `[[git_sources]]` TOML section

### Documentation

- `requirements.md`: Combined requirements specification (replaces requirements.txt)
- `README.md`: User-facing documentation with quick start guide
- `AGENTS.md`: AI agent instructions for working on the project

### Changes

- Removed `requirements.txt` (merged into `requirements.md`)
- Updated `__init__.py` version to 1.0.0 (display) while keeping actual version at 0.0.1

---

## [Unreleased]

### Added

- **Multi-config file merging**: When multiple `*simon-distrolocs.toml` files are found, they are now merged instead of causing an error. Conflicts are resolved by preferring entries closer to the working directory.

### Fixed

- **Path resolution bug**: When multiple configs exist, token paths now resolve correctly using the actual config file's directory, not the originally passed directory

- **Git source path resolution**: `auth_token_path` and `cloning_destination` now correctly resolved relative to cwd (repo root), not the TOML config directory
- **GitLab SSL verification**: Updated example to use `ssl_verify = false` for self-signed certs

### Documentation

- **Path resolution docs**: Added note that git source paths are resolved relative to cwd
- **GitLab ssl_verify example**: Changed from `true` to `false` in requirements.md

---

## [0.0.1] - 2026-04-12