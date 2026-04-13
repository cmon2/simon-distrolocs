"""Build clone URL with embedded credentials."""

from __future__ import annotations

from pathlib import Path


def build_source_clone_url(source_url: str, source_type: str) -> str:
    """Build clone URL with credentials embedded if needed.

    For GitLab sources, this embeds the OAuth token so git clone works
    without interactive authentication.

    Args:
        source_url: The source git URL.
        source_type: Type of source (gitlab, github, forgejo).

    Returns:
        Clone URL with credentials if needed.
    """
    # For GitLab sources, we need to embed the token
    if source_type.lower() == "gitlab":
        # Try to find config in current directory
        try:
            from ..assemble_config import find_config_file
            from ..parsing import parse_git_sources
            from ..parsing.parse_toml import parse_toml_config

            config_path = find_config_file(Path.cwd())
            toml_dict = parse_toml_config(config_path)
        except Exception:
            return source_url

        try:
            git_sources = parse_git_sources(toml_dict)
        except Exception:
            return source_url

        # Find GitLab source
        gitlab_source = None
        for source in git_sources:
            if "gitlab" in source.name.lower() or "git.hmg" in source.name.lower():
                gitlab_source = source
                break

        if gitlab_source is None:
            return source_url

        token = gitlab_source.get_auth_token()
        if not token:
            return source_url

        if source_url.startswith("https://"):
            # GitLab uses oauth2 prefix for tokens
            parts = source_url.split("://", 1)
            return f"{parts[0]}://oauth2:{token}@{parts[1]}"

    return source_url
