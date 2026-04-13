"""Define GitSource dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .define_auth_type import AuthType


@dataclass
class GitSource:
    """Configuration for a git source (GitHub, Forgejo, GitLab).

    Attributes:
        name: Human-readable name for this source.
        list_repos_url: API URL to list repositories.
        auth_type: How to authenticate with this source.
        auth_token: Path to a file containing the authentication token.
        cloning_destination: Directory where cloned repos will be placed.
        enabled: Whether this source is active.
        ssl_verify: Whether to verify SSL certificates.
        exclude_repos: List of repo names to skip.
        excluded_on_hosts: Tuple of hostnames where this source should NOT be used.
        limit_to_recent_repos: If > 0, only clone this many most recently updated repos.
    """

    name: str
    list_repos_url: str
    auth_type: "AuthType"
    auth_token_path: Path
    cloning_destination: Path
    enabled: bool = True
    ssl_verify: bool = True
    exclude_repos: tuple[str, ...] = field(default_factory=tuple)
    excluded_on_hosts: tuple[str, ...] = field(default_factory=tuple)
    limit_to_recent_repos: int = 0

    def get_auth_token(self) -> str:
        """Read the authentication token from the token file.

        Handles two formats:
        1. Raw token: "tokenstring"
        2. URL format: "http://user:token@host"

        Returns:
            The token string, or empty string if file doesn't exist.
        """
        try:
            with open(self.auth_token_path) as f:
                token = f.read().strip()

            # Handle URL-formatted tokens (e.g., "http://simon:TOKEN@host")
            if "@" in token and "://" in token:
                # Extract token from URL format: scheme://user:token@host
                # The token is the password part (between : and @)
                parts = token.split("@")[0]
                if ":" in parts:
                    token = parts.rsplit(":", 1)[1]

            return token
        except OSError:
            return ""
