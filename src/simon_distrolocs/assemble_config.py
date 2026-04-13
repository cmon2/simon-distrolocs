"""Configuration assembly and loading for Simon DistroLocs."""

from __future__ import annotations

import socket
import warnings
from pathlib import Path

from .parsing import (
    ConfigError,
    parse_distro_types,
    parse_duplications,
    parse_git_sources,
    parse_mappings,
    parse_toml_config,
)
from .types import AppConfig, ConfigMapping


def find_config_file(parent_dir: Path) -> Path:
    """Find the single simon-distrolocs.toml file in the directory tree.

    Args:
        parent_dir: The parent directory to search within.

    Returns:
        Path to the discovered TOML file.

    Raises:
        ConfigError: If zero or multiple config files are found.
    """
    matching_files = list(parent_dir.rglob("*simon-distrolocs.toml"))

    if not matching_files:
        raise ConfigError(
            f"No configuration file found in {parent_dir}. "
            "Expected a file matching *simon-distrolocs.toml"
        )

    if len(matching_files) > 1:
        # Check if all files are identical
        file_contents = []
        for f in matching_files:
            try:
                with open(f, "rb") as fh:
                    file_contents.append(fh.read())
            except OSError:
                pass

        # If all files have the same content, use the first one
        if len(file_contents) > 1 and all(c == file_contents[0] for c in file_contents):
            warnings.warn(
                f"Multiple identical config files found. Using: {matching_files[0]}\n"
                f"Ignoring duplicates: {[str(f) for f in matching_files[1:]]}"
            )
            return matching_files[0]

        # Files differ - this is a real error
        file_list = "\n".join(f"  - {f}" for f in matching_files)
        raise ConfigError(
            f"Multiple configuration files found with different content.\n{file_list}"
        )

    return matching_files[0]


def load_config(parent_dir: Path) -> AppConfig:
    """Load and validate the configuration from the parent directory.

    Args:
        parent_dir: The parent directory containing managed configs and TOML.

    Returns:
        Validated AppConfig object.

    Raises:
        ConfigError: If configuration is missing, invalid, or ambiguous.
    """
    config_path = find_config_file(parent_dir)
    toml_dict = parse_toml_config(config_path)

    distro_types = parse_distro_types(toml_dict)
    all_mappings = parse_mappings(toml_dict, parent_dir)
    duplications = parse_duplications(toml_dict)

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
