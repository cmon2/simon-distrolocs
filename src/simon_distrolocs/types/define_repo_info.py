"""Define RepoInfo dataclass."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepoInfo:
    """Information about a repository from a git source.

    Attributes:
        name: The repository name.
        clone_url: The URL to clone the repository.
        full_name: The full name (owner/repo) of the repository.
        updated_at: Optional timestamp of last update (ISO8601 string).
    """

    name: str
    clone_url: str
    full_name: str
    updated_at: str | None = None
