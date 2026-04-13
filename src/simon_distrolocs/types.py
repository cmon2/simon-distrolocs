"""Type definitions for Simon DistroLocs."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class AuthType(Enum):
    """Authentication type for git sources.

    Attributes:
        TOKEN: Use a personal access token for authentication
        SSH: Use SSH key authentication
        NONE: No authentication (public repos only)
    """

    TOKEN = "token"
    SSH = "ssh"
    NONE = "none"


class LinkMethod(Enum):
    """Defines how a managed config is linked to its destination.

    Attributes:
        SYMLINK: Creates symbolic links (default). Changes in source reflect immediately.
        ANCHOR: Creates a fixed hard copy without further sync. A stable snapshot
            of the source at the time of linking — like a moor point you can
            always return to.
    """

    SYMLINK = "symlink"
    ANCHOR = "anchor"


class SyncStatus(Enum):
    """Represents the synchronization state of a managed configuration."""

    LINKED = "linked"
    SYNCED = "synced"
    UNSYNCED = "unsynced"


@dataclass(frozen=True)
class DistroType:
    """Defines a distribution type with visualization parameters.

    Attributes:
        name: The unique name of this distro type.
        visualization_depth: How deep to render target folder structure in tree.
            0 = files only, 1+ = expand N levels of directories.
    """

    name: str
    visualization_depth: int


@dataclass(frozen=True)
class ConfigMapping:
    """Maps a managed source path to a target destination on the system.

    Attributes:
        name: Human-readable name for this configuration.
        source: Relative path to the managed config within the parent directory.
        target: Destination path on the system (absolute or ~-prefixed).
        distro_type: Optional reference to a DistroType name.
        hosts: Tuple of hostnames where this mapping applies. Empty = all hosts.
        method: How to link source to target (symlink or anchor hard copy).
    """

    name: str
    source: Path
    target: Path
    distro_type: Optional[str] = None
    excluded_on_hosts: tuple[str, ...] = field(default_factory=tuple)
    method: Optional[LinkMethod] = None


@dataclass(frozen=True)
class SyncState:
    """The computed synchronization state for a single configuration mapping.

    Attributes:
        mapping: The original configuration mapping.
        status: The computed sync status (Linked, Synced, or Unsynced).
        source_exists: Whether the source managed file/folder exists.
        target_exists: Whether the target destination exists.
        is_symlink: Whether the target is a symlink.
        method: The link method used for this mapping (symlink or anchor).
    """

    mapping: ConfigMapping
    status: SyncStatus
    source_exists: bool
    target_exists: bool
    is_symlink: bool
    method: LinkMethod


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


@dataclass(frozen=True)
class AppConfig:
    """The parsed and validated application configuration.

    Attributes:
        distro_types: Dictionary of DistroType definitions by name.
        mappings: List of configuration mappings relevant to the current host.
        all_mappings: All mappings (including filtered out by host) for reference.
        duplications: List of RepoDuplication configurations.
    """

    distro_types: dict[str, DistroType]
    mappings: list[ConfigMapping]
    all_mappings: list[ConfigMapping]
    duplications: tuple[RepoDuplication, ...] = field(default_factory=tuple)


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
    auth_type: AuthType
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
