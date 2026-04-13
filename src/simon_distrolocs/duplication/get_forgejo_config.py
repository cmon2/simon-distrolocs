"""Parse Forgejo source configuration from TOML."""

from __future__ import annotations

from pathlib import Path

from ..assemble_config import find_config_file
from .parse_duplications import DuplicateError
from .parse_toml import parse_toml_config


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

    git_sources = toml_dict.get("git_sources", [])
    if isinstance(git_sources, dict):
        git_sources = [git_sources]

    for source in git_sources:
        source_name = source.get("name", "")
        source_url = source.get("list_repos_url", "")
        # Match by name containing "forgejo" (case insensitive)
        is_forgejo = "forgejo" in source_name.lower()

        if is_forgejo:
            # Extract base URL from API URL (e.g., http://172.30.32.1:3000)
            # list_repos_url is like http://172.30.32.1:3000/api/v1/users/simon/repos
            if "/api/v1/" in source_url:
                base_url = source_url.split("/api/v1/")[0]
            else:
                base_url = source_url

            auth_token_path = source.get("auth_token_path", "")
            if auth_token_path:
                token_file = Path(auth_token_path)
                if not token_file.is_absolute():
                    # Resolve relative to cwd (repo root)
                    token_file = Path.cwd() / token_file
                if token_file.exists():
                    with open(token_file) as f:
                        token = f.read().strip()
                    # Handle URL format tokens
                    if "@" in token and "://" in token:
                        parts = token.split("@")[0]
                        if ":" in parts:
                            token = parts.rsplit(":", 1)[1]
                    return base_url, token

    raise DuplicateError("No Forgejo source found in git_sources config")
