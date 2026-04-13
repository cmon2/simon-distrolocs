"""Define RepoDuplication dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RepoDuplication:
    """Configuration for duplicating a repository to Forgejo.

    Attributes:
        name: Unique name to reference this duplication (used by CLI).
        source_type: Type of source (gitlab, github, forgejo) for auth lookup.
        source_url: The git URL of the source repository to duplicate.
        forgejo_target: The base name for the repo on Forgejo (without namespace).
        target_clone_locations: Tuple of directory paths where the duplicated
            repo should be cloned after creation.
        enabled: Whether this duplication is active.
    """

    name: str
    source_type: str
    source_url: str
    forgejo_target: str
    target_clone_locations: tuple[str, ...]
    enabled: bool = True
