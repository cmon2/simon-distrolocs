"""Configuration assembly and loading for Simon DistroLocs."""

from __future__ import annotations

import os
import socket
import warnings
from pathlib import Path
from typing import Any

from .parsing import (
    ConfigError,
    parse_distro_types,
    parse_duplications,
    parse_git_sources,
    parse_mappings,
    parse_toml_config,
)
from .types import AppConfig, ConfigMapping


# Cache for file contents to avoid repeated reads
_file_content_cache: dict[Path, tuple[bytes, float]] = {}


def _get_file_info(file_path: Path) -> tuple[bytes, float]:
    """Get file content and last access time (cached).

    Args:
        file_path: Path to the file.

    Returns:
        Tuple of (file_content, last_access_time).
    """
    if file_path not in _file_content_cache:
        try:
            stat = os.stat(file_path)
            with open(file_path, "rb") as fh:
                content = fh.read()
            _file_content_cache[file_path] = (content, stat.st_atime)
        except OSError:
            _file_content_cache[file_path] = (b"", 0.0)
    return _file_content_cache[file_path]


def _get_relative_depth(path: Path, wd: Path) -> int:
    """Get the depth of a path relative to working directory.

    Args:
        path: The path to measure.
        wd: The working directory.

    Returns:
        Number of path components from wd to path.
    """
    try:
        rel_path = path.relative_to(wd)
        return len(rel_path.parts)
    except ValueError:
        # Not relative to wd, use absolute path depth
        return len(path.parts)


def _sort_configs_by_preference(
    configs: list[tuple[Path, dict[str, Any]]], wd: Path
) -> list[tuple[Path, dict[str, Any]]]:
    """Sort configs by preference: closer to wd first, then more recently accessed.

    Args:
        configs: List of (config_path, toml_dict) tuples.
        wd: Working directory for distance calculation.

    Returns:
        Sorted list with preferred configs first.
    """
    config_infos: list[tuple[Path, dict[str, Any], int, float]] = []
    for config_path, toml_dict in configs:
        depth = _get_relative_depth(config_path.parent, wd)
        _, atime = _get_file_info(config_path)
        config_infos.append((config_path, toml_dict, depth, atime))

    # Sort by: depth (ascending), then atime (descending - most recent first)
    config_infos.sort(key=lambda x: (x[2], -x[3]))
    return [(c[0], c[1]) for c in config_infos]


def _deduplicate_distro_types(
    all_configs: list[tuple[Path, dict[str, Any]]], wd: Path
) -> dict[str, Any]:
    """Merge distro_types from multiple configs, deduplicating and logging conflicts.

    Args:
        all_configs: List of (config_path, toml_dict) sorted by preference.
        wd: Working directory for logging.

    Returns:
        Merged distro_types dictionary.
    """
    merged: dict[str, Any] = {}

    for config_path, toml_dict in all_configs:
        raw_types = toml_dict.get("distro_types", {})
        for name, config in raw_types.items():
            if name in merged:
                if merged[name] != config:
                    warnings.warn(
                        f"Conflicting distro_types entry '{name}' in {config_path}: "
                        f"using version from {config_path} (closer to wd). "
                        f"Conflicting value: {merged[name]}"
                    )
                    merged[name] = config
            else:
                merged[name] = config

    return merged


def _deduplicate_entries_by_key(
    all_configs: list[tuple[Path, dict[str, Any]]],
    key: str,
    entry_type: str,
    wd: Path,
) -> list[dict[str, Any]]:
    """Merge entries from multiple configs by key, deduplicating and logging conflicts.

    Args:
        all_configs: List of (config_path, toml_dict) sorted by preference.
        key: The field name to use as unique key (e.g., 'name').
        entry_type: Human-readable name for logging (e.g., 'mapping', 'git_source').
        wd: Working directory for logging.

    Returns:
        List of deduplicated entry dictionaries.
    """
    seen: dict[str, tuple[dict[str, Any], Path]] = {}  # key -> (entry, source_path)

    for config_path, toml_dict in all_configs:
        raw_entries = toml_dict.get(key, [])
        if isinstance(raw_entries, dict):
            raw_entries = [raw_entries]

        for entry in raw_entries:
            entry_key = entry.get("name", "")
            if not entry_key:
                continue

            if entry_key in seen:
                existing_entry, existing_path = seen[entry_key]
                if existing_entry != entry:
                    existing_depth = _get_relative_depth(existing_path.parent, wd)
                    new_depth = _get_relative_depth(config_path.parent, wd)
                    if new_depth < existing_depth:
                        # New one is closer, use it
                        warnings.warn(
                            f"Conflicting {entry_type} '{entry_key}' in {config_path}: "
                            f"using version from {config_path} (closer to wd). "
                            f"Conflicting entry from: {existing_path}"
                        )
                        seen[entry_key] = (entry, config_path)
                    elif new_depth == existing_depth:
                        # Same distance, use most recently accessed
                        _, existing_atime = _get_file_info(existing_path)
                        _, new_atime = _get_file_info(config_path)
                        if new_atime > existing_atime:
                            warnings.warn(
                                f"Conflicting {entry_type} '{entry_key}' at same depth: "
                                f"using more recent version from {config_path}"
                            )
                            seen[entry_key] = (entry, config_path)
                    # else: keep existing (new one is farther)
            else:
                seen[entry_key] = (entry, config_path)

    return [entry for entry, _ in seen.values()]


def find_config_files(parent_dir: Path) -> list[Path]:
    """Find all simon-distrolocs.toml files in the directory tree.

    Args:
        parent_dir: The parent directory to search within.

    Returns:
        List of discovered TOML file paths.

    Raises:
        ConfigError: If no config files are found.
    """
    matching_files = list(parent_dir.rglob("*simon-distrolocs.toml"))

    if not matching_files:
        raise ConfigError(
            f"No configuration file found in {parent_dir}. "
            "Expected a file matching *simon-distrolocs.toml"
        )

    return matching_files


def find_config_file(parent_dir: Path) -> Path:
    """Find the preferred simon-distrolocs.toml file.

    When multiple config files exist, they are merged with:
    - Identical entries: deduplicated (kept once)
    - Conflicting entries: log warning, use closer to wd, or more recently accessed

    Args:
        parent_dir: The parent directory to search within.

    Returns:
        Path to the preferred TOML file.

    Raises:
        ConfigError: If no config files are found.
    """
    matching_files = find_config_files(parent_dir)

    if len(matching_files) == 1:
        return matching_files[0]

    # Multiple files - check if all identical
    contents_and_times = [_get_file_info(f) for f in matching_files]
    first_content = contents_and_times[0][0]

    if all(c == first_content for c, _ in contents_and_times):
        warnings.warn(
            f"Multiple identical config files found. Using: {matching_files[0]}\n"
            f"Ignoring duplicates: {[str(f) for f in matching_files[1:]]}"
        )
        return matching_files[0]

    # Files differ - find preferred one (closest to wd, most recent on tie)
    wd = Path.cwd()
    config_infos: list[tuple[Path, int, float]] = []
    for f in matching_files:
        depth = _get_relative_depth(f.parent, wd)
        _, atime = _get_file_info(f)
        config_infos.append((f, depth, atime))

    # Sort by depth (ascending), then atime (descending)
    config_infos.sort(key=lambda x: (x[1], -x[2]))
    preferred = config_infos[0][0]

    warnings.warn(
        f"Multiple config files found with different content. "
        f"Using preferred (closest to wd): {preferred}\n"
        f"All configs will be merged with conflict resolution."
    )

    return preferred


def load_config(parent_dir: Path) -> AppConfig:
    """Load and merge the configuration from all config files in the directory.

    When multiple config files are found, they are merged:
    - [distro_types.*]: Merged by key, later values override earlier on conflict
    - [[mapping]], [[git_sources]], [[duplication]]: Deduplicated by name,
      with conflict resolution preferring entries closer to working directory

    Args:
        parent_dir: The parent directory containing managed configs and TOML.

    Returns:
        Validated AppConfig object with merged contents.

    Raises:
        ConfigError: If configuration is missing or invalid.
    """
    config_files = find_config_files(parent_dir)
    wd = Path.cwd()

    # Parse all configs
    all_configs: list[tuple[Path, dict[str, Any]]] = []
    for config_path in config_files:
        toml_dict = parse_toml_config(config_path)
        all_configs.append((config_path, toml_dict))

    # Sort by preference (closer to wd first, then more recent)
    all_configs = _sort_configs_by_preference(all_configs, wd)

    # Merge distro_types (dict by key)
    merged_distro_types_raw = _deduplicate_distro_types(all_configs, wd)

    # Build merged toml dict for parsing
    merged_toml: dict[str, Any] = {"distro_types": merged_distro_types_raw}

    # Merge entries by key
    for entry_key, toml_key in [
        ("mapping", "mapping"),
        ("git_source", "git_sources"),
        ("duplication", "duplication"),
    ]:
        deduped = _deduplicate_entries_by_key(all_configs, toml_key, entry_key, wd)
        merged_toml[toml_key] = deduped

    # Parse merged config
    distro_types = parse_distro_types(merged_toml)
    all_mappings = parse_mappings(merged_toml, parent_dir)
    duplications = parse_duplications(merged_toml)

    current_host = socket.gethostname()

    filtered_mappings: list[ConfigMapping] = []
    for mapping in all_mappings:
        if current_host not in mapping.excluded_on_hosts:
            filtered_mappings.append(mapping)

    return AppConfig(
        distro_types=distro_types,
        mappings=filtered_mappings,
        all_mappings=all_mappings,
        duplications=duplications,
    )


def get_visualization_depth(config: AppConfig, mapping: ConfigMapping) -> int:
    """Get the visualization depth for a mapping's distro type.

    Args:
        config: The application configuration.
        mapping: The configuration mapping.

    Returns:
        Visualization depth (0 if no distro_type specified).
    """
    if mapping.distro_type is None:
        return 0

    distro_type = config.distro_types.get(mapping.distro_type)
    if distro_type is None:
        return 0

    return distro_type.visualization_depth
