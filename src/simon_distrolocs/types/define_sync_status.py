"""Define SyncStatus enum."""

from __future__ import annotations

from enum import Enum


class SyncStatus(Enum):
    """Represents the synchronization state of a managed configuration."""

    LINKED = "linked"
    SYNCED = "synced"
    UNSYNCED = "unsynced"
