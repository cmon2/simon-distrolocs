"""Parse Forgejo source configuration from TOML."""

from __future__ import annotations

from pathlib import Path

from ..assemble_config import find_config_file
from ..parsing import DuplicateError, parse_git_sources
from ..types import GitSource
from ..parsing.parse_toml import parse_toml_config


def _find_forgejo_source(git_sources: list[GitSource]) -> GitSource | None:
    """Find the Forgejo GitSource by name pattern.

    Args:
        git_sources: List of GitSource objects.

    Returns:
        Forgejo GitSource or None if not found.
    """
    for source in git_sources:
        if "forgejo" in source.name.lower():
            return source
    return None


def get_forgejo_config(config_dir: Path) -> tuple[str, str]:
    """Get Forgejo base URL and auth token from git_sources in TOML config.

    Args:
        config_dir: Directory containing the TOML config file.

    Returns:
        Tuple of (forgejo_base_url, auth_token).

    Raises:
        DuplicateError: If no Forgejo source found or can't read token.
    """
    config_path = find_config_file(config_dir)
    toml_dict = parse_toml_config(config_path)

    # Use the directory of the actual config file, not the original config_dir
    # This ensures paths resolve correctly when multiple configs exist
    git_sources = parse_git_sources(toml_dict, config_path.parent)
    forgejo_source = _find_forgejo_source(git_sources)

    if forgejo_source is None:
        raise DuplicateError("No Forgejo source found in git_sources config")

    # Extract base URL from API URL
    # list_repos_url is like http://172.30.32.1:3000/api/v1/users/simon/repos
    list_repos_url = forgejo_source.list_repos_url
    if "/api/v1/" in list_repos_url:
        base_url = list_repos_url.split("/api/v1/")[0]
    else:
        base_url = list_repos_url

    token = forgejo_source.get_auth_token()
    return base_url, token
