"""Type definitions for Simon DistroLocs."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


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
    hosts: tuple[str, ...] = field(default_factory=tuple)
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
class AppConfig:
    """The parsed and validated application configuration.

    Attributes:
        distro_types: Dictionary of DistroType definitions by name.
        mappings: List of configuration mappings relevant to the current host.
        all_mappings: All mappings (including filtered out by host) for reference.
    """

    distro_types: dict[str, DistroType]
    mappings: list[ConfigMapping]
    all_mappings: list[ConfigMapping]
