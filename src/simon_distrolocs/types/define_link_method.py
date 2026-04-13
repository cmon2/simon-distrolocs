"""Define LinkMethod enum."""

from __future__ import annotations

from enum import Enum


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
