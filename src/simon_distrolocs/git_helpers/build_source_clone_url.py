"""Build clone URL with embedded credentials."""

from __future__ import annotations

from pathlib import Path


def build_source_clone_url(
    source_url: str, source_type: str, config_dir: Path | None = None
) -> str:
    """Build clone URL with credentials embedded if needed.

    For GitLab sources, this embeds the OAuth token so git clone works
    without interactive authentication.

    Args:
        source_url: The source git URL.
        source_type: Type of source (gitlab, github, forgejo).
        config_dir: Optional directory containing TOML config.
            If not provided, uses current working directory.

    Returns:
        Clone URL with credentials if needed.
    """
    # For GitLab sources, we need to embed the token
    if source_type.lower() == "gitlab":
        # Use config_dir if provided, otherwise fall back to cwd
        search_dir = config_dir if config_dir else Path.cwd()
        # Try to find config in specified directory
        try:
            from ..assemble_config import find_config_file
            from ..parsing import parse_git_sources
            from ..parsing.parse_toml import parse_toml_config

            config_path = find_config_file(search_dir)
            toml_dict = parse_toml_config(config_path)
        except Exception:
            return source_url

        try:
            # Use config_path.parent to ensure paths resolve correctly
            git_sources = parse_git_sources(toml_dict, config_path.parent)
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

        # Handle both HTTPS and SSH GitLab URLs
        # SSH format: git@git.hmg:group/repo.git
        # Convert SSH to HTTPS for token auth: https://git.hmg/group/repo
        source_url_https = source_url
        if source_url.startswith("git@"):
            # Convert SSH to HTTPS: git@git.hmg:group/repo.git -> https://git.hmg/group/repo
            ssh_part = source_url[4:]  # Remove "git@"
            if ":" in ssh_part:
                # git.hmg:group/repo.git -> git.hmg/group/repo
                host_part = ssh_part.replace(":", "/")
                # Remove .git suffix
                if host_part.endswith(".git"):
                    host_part = host_part[:-4]
                source_url_https = f"https://{host_part}"
        elif source_url.startswith("https://"):
            source_url_https = source_url

        if source_url_https.startswith("https://"):
            # GitLab uses oauth2 prefix for tokens
            parts = source_url_https.split("://", 1)
            return f"{parts[0]}://oauth2:{token}@{parts[1]}"

    return source_url
