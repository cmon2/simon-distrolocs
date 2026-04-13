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
            from ..config import find_config_file, parse_toml_config

            config_path = find_config_file(Path.cwd())
        except Exception:
            return source_url

        try:
            toml_dict = parse_toml_config(config_path)
        except Exception:
            return source_url

        git_sources = toml_dict.get("git_sources", [])
        if isinstance(git_sources, dict):
            git_sources = [git_sources]

        for source in git_sources:
            source_name = source.get("name", "").lower()
            if "gitlab" in source_name or "git.hmg" in source_name:
                auth_token_path = source.get("auth_token_path", "")
                if auth_token_path:
                    token_file = Path(auth_token_path)
                    if not token_file.is_absolute():
                        token_file = Path.cwd() / token_file
                    if token_file.exists():
                        with open(token_file) as f:
                            token = f.read().strip()
                        # Handle URL format tokens
                        if "@" in token and "://" in token:
                            parts = token.split("@")[0]
                            if ":" in parts:
                                token = parts.rsplit(":", 1)[1]

                        if source_url.startswith("https://"):
                            parts = source_url.split("://", 1)
                            return f"{parts[0]}://oauth2:{token}@{parts[1]}"

    return source_url
