"""Define ConfigMapping dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .define_link_method import LinkMethod


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
    distro_type: str | None = None
    excluded_on_hosts: tuple[str, ...] = field(default_factory=tuple)
    method: "LinkMethod | None" = None
