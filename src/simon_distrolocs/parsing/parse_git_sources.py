"""Git sources parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..types import GitSource
from .parse_auth_type import parse_auth_type
from .parse_toml import ConfigError


def parse_git_sources(
    toml_dict: dict[str, Any], config_dir: Path | None = None
) -> list[GitSource]:
    """Parse [[git_sources]] section from TOML.

    Args:
        toml_dict: Parsed TOML dictionary.
        config_dir: The directory containing the TOML config file (unused for git sources,
            kept for API compatibility - paths are resolved relative to cwd).

    Returns:
        List of GitSource objects.
    """
    sources: list[GitSource] = []
    raw_sources = toml_dict.get("git_sources", [])

    if isinstance(raw_sources, dict):
        raw_sources = [raw_sources]

    # Resolve git source paths relative to cwd (repo root), not config_dir
    repo_root = Path.cwd()

    for item in raw_sources:
        name = item.get("name", "")
        list_repos_url = item.get("list_repos_url", "")
        auth_type_str = item.get("auth_type")
        auth_token_path_str = item.get("auth_token_path", "")
        cloning_dest_str = item.get("cloning_destination", "")
        enabled = item.get("enabled", True)
        ssl_verify = item.get("ssl_verify")
        if ssl_verify is None:
            raise ConfigError(
                f"git_sources entry '{name}' is missing required field: ssl_verify"
            )
        exclude_repos_raw = item.get("exclude_repos", [])
        excluded_on_hosts_raw = item.get("excluded_on_hosts", [])
        limit_to_recent_repos = item.get("limit_to_recent_repos", 0)

        if isinstance(exclude_repos_raw, str):
            exclude_repos_raw = [exclude_repos_raw]
        if isinstance(excluded_on_hosts_raw, str):
            excluded_on_hosts_raw = [excluded_on_hosts_raw]

        auth_type = parse_auth_type(auth_type_str)
        auth_token_path = (
            repo_root / auth_token_path_str if auth_token_path_str else Path("")
        )
        cloning_destination = (
            repo_root / cloning_dest_str if cloning_dest_str else Path("")
        )

        source = GitSource(
            name=name,
            list_repos_url=list_repos_url,
            auth_type=auth_type,
            auth_token_path=auth_token_path,
            cloning_destination=cloning_destination,
            enabled=enabled,
            ssl_verify=ssl_verify,
            exclude_repos=tuple(exclude_repos_raw),
            excluded_on_hosts=tuple(excluded_on_hosts_raw),
            limit_to_recent_repos=limit_to_recent_repos,
        )
        sources.append(source)

    return sources
