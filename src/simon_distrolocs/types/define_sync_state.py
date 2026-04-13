"""Define SyncState dataclass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .define_config_mapping import ConfigMapping
    from .define_link_method import LinkMethod
    from .define_sync_status import SyncStatus


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

    mapping: "ConfigMapping"
    status: "SyncStatus"
    source_exists: bool
    target_exists: bool
    is_symlink: bool
    method: "LinkMethod"
