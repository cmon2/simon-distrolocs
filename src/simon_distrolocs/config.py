"""Configuration parsing and validation for Simon DistroLocs."""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from typing import Any

# Handle Python version compatibility
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

from .types import AppConfig, AuthType, ConfigMapping, DistroType, GitSource, LinkMethod


class ConfigError(Exception):
    """Raised when configuration parsing or validation fails."""

    pass


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
            import warnings

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


def parse_toml_config(config_path: Path) -> dict[str, Any]:
    """Parse a TOML configuration file.

    Args:
        config_path: Path to the TOML file.

    Returns:
        Parsed TOML as a dictionary.

    Raises:
        ConfigError: If TOML parsing fails.
    """
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Failed to parse TOML: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read config file: {e}") from e


def _parse_distro_types(toml_dict: dict[str, Any]) -> dict[str, DistroType]:
    """Parse distro_types section from TOML.

    Args:
        toml_dict: Parsed TOML dictionary.

    Returns:
        Dictionary of DistroType objects keyed by name.
    """
    distro_types: dict[str, DistroType] = {}
    raw_types = toml_dict.get("distro_types", {})

    for name, config in raw_types.items():
        if isinstance(config, dict):
            depth = config.get("visualizationDepth", 0)
        else:
            depth = 0
        distro_types[name] = DistroType(name=name, visualization_depth=depth)

    return distro_types


def _parse_link_method(method_str: str | None) -> LinkMethod:
    """Parse a method string into a LinkMethod enum value.

    Args:
        method_str: The method string from TOML (e.g., "symlink", "anchor").

    Returns:
        The corresponding LinkMethod enum value (defaults to SYMLINK if None).

    Raises:
        ConfigError: If the method string is not a valid LinkMethod value.
    """
    if method_str is None:
        return LinkMethod.SYMLINK

    try:
        return LinkMethod(method_str)
    except ValueError:
        valid_values = [m.value for m in LinkMethod]
        raise ConfigError(
            f"Invalid method '{method_str}'. Valid values are: {valid_values}"
        )


def _parse_mappings(toml_dict: dict[str, Any], parent_dir: Path) -> list[ConfigMapping]:
    """Parse [[mapping]] sections from TOML.

    Args:
        toml_dict: Parsed TOML dictionary.
        parent_dir: The parent managed configs directory.

    Returns:
        List of ConfigMapping objects.
    """
    mappings: list[ConfigMapping] = []
    raw_mappings = toml_dict.get("mapping", [])

    if isinstance(raw_mappings, dict):
        raw_mappings = [raw_mappings]

    for item in raw_mappings:
        name = item.get("name", "")
        source_str = item.get("source", "")
        target_str = item.get("target", "")
        distro_type = item.get("distro_type")
        hosts_raw = item.get("hosts", [])
        method_str = item.get("method")

        if isinstance(hosts_raw, str):
            hosts_raw = [hosts_raw]

        source = parent_dir / source_str
        target = Path(target_str.replace("~", str(Path.home())))
        method = _parse_link_method(method_str)

        mapping = ConfigMapping(
            name=name,
            source=source,
            target=target,
            distro_type=distro_type,
            hosts=tuple(hosts_raw),
            method=method,
        )
        mappings.append(mapping)

    return mappings


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

    distro_types = _parse_distro_types(toml_dict)
    all_mappings = _parse_mappings(toml_dict, parent_dir)

    current_host = socket.gethostname()

    filtered_mappings: list[ConfigMapping] = []
    for mapping in all_mappings:
        if not mapping.hosts or current_host in mapping.hosts:
            filtered_mappings.append(mapping)

    return AppConfig(
        distro_types=distro_types,
        mappings=filtered_mappings,
        all_mappings=all_mappings,
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


def _parse_auth_type(auth_str: str | None) -> AuthType:
    """Parse an auth type string into an AuthType enum value.

    Args:
        auth_str: The auth type string from TOML (e.g., "token", "ssh", "none").

    Returns:
        The corresponding AuthType enum value (defaults to NONE if None).

    Raises:
        ConfigError: If the auth type string is not a valid AuthType value.
    """
    if auth_str is None:
        return AuthType.NONE

    try:
        return AuthType(auth_str.lower())
    except ValueError:
        valid_values = [a.value for a in AuthType]
        raise ConfigError(
            f"Invalid auth_type '{auth_str}'. Valid values are: {valid_values}"
        )


def _parse_git_sources(toml_dict: dict[str, Any], parent_dir: Path) -> list[GitSource]:
    """Parse [[git_sources]] section from TOML.

    Args:
        toml_dict: Parsed TOML dictionary.
        parent_dir: The parent managed configs directory.

    Returns:
        List of GitSource objects.
    """
    sources: list[GitSource] = []
    raw_sources = toml_dict.get("git_sources", [])

    if isinstance(raw_sources, dict):
        raw_sources = [raw_sources]

    for item in raw_sources:
        name = item.get("name", "")
        list_repos_url = item.get("list_repos_url", "")
        auth_type_str = item.get("auth_type")
        auth_token_path_str = item.get("auth_token_path", "")
        cloning_dest_str = item.get("cloning_destination", "")
        enabled = item.get("enabled", True)
        ssl_verify = item.get("ssl_verify", True)
        exclude_raw = item.get("exclude", [])

        if isinstance(exclude_raw, str):
            exclude_raw = [exclude_raw]

        auth_type = _parse_auth_type(auth_type_str)
        auth_token_path = (
            parent_dir / auth_token_path_str if auth_token_path_str else Path("")
        )
        cloning_destination = Path(cloning_dest_str) if cloning_dest_str else Path("")

        source = GitSource(
            name=name,
            list_repos_url=list_repos_url,
            auth_type=auth_type,
            auth_token_path=auth_token_path,
            cloning_destination=cloning_destination,
            enabled=enabled,
            ssl_verify=ssl_verify,
            exclude=tuple(exclude_raw),
        )
        sources.append(source)

    return sources
