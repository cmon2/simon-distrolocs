"""Define DistroType dataclass."""

from __future__ import annotations

from dataclasses import dataclass


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
