"""Sync execution for Simon DistroLocs."""

from __future__ import annotations

from .evaluate_sync import _is_copy_method
from .manage_files import create_symlink, safe_execute_copy
from .types import SyncState, SyncStatus


def execute_sync(state: SyncState) -> SyncState:
    """Execute the synchronization action for a mapping based on its method.

    Args:
        state: The sync state describing what needs to be synced.

    Returns:
        A new SyncState with status updated to LINKED (symlink) or SYNCED (copy),
        or the original state if the operation failed.
    """
    source = state.mapping.source
    target = state.mapping.target

    success: bool
    if _is_copy_method(state.method):
        success = safe_execute_copy(source, target)
        new_status = SyncStatus.SYNCED if success else state.status
    else:
        success = create_symlink(source, target)
        new_status = SyncStatus.LINKED if success else state.status

    if success:
        return SyncState(
            mapping=state.mapping,
            status=new_status,
            source_exists=state.source_exists,
            target_exists=True,
            is_symlink=not _is_copy_method(state.method),
            method=state.method,
        )

    return state
