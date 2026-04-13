"""Sync status evaluation for Simon DistroLocs."""

from __future__ import annotations

from .types import AppConfig, ConfigMapping, LinkMethod, SyncState, SyncStatus
from .compare_paths import is_symlink_to, paths_match


def _is_copy_method(method: LinkMethod | None) -> bool:
    """Determine if a link method resolves to a copy operation.

    Args:
        method: The link method to check.

    Returns:
        True if the method is a copy/anchor variant, False for symlink.
    """
    # ANCHOR is the copy variant; None/SYMLINK are symlink variants.
    # Treat mirror, fossilize, crystallize as anchor (copy) by method resolution.
    if method is None:
        return False
    return method != LinkMethod.SYMLINK


def evaluate_sync_status(mapping: ConfigMapping) -> SyncState:
    """Evaluate the synchronization status of a configuration mapping.

    Args:
        mapping: The configuration mapping to evaluate.

    Returns:
        SyncState representing the current status.
    """
    source = mapping.source
    target = mapping.target

    source_exists = source.exists()
    target_exists = target.exists()

    if not source_exists:
        return SyncState(
            mapping=mapping,
            status=SyncStatus.UNSYNCED,
            source_exists=False,
            target_exists=target_exists,
            is_symlink=target.is_symlink() if target_exists else False,
            method=mapping.method or LinkMethod.SYMLINK,
        )

    if target.is_symlink():
        if is_symlink_to(target, source):
            return SyncState(
                mapping=mapping,
                status=SyncStatus.LINKED,
                source_exists=True,
                target_exists=True,
                is_symlink=True,
                method=mapping.method or LinkMethod.SYMLINK,
            )
        else:
            return SyncState(
                mapping=mapping,
                status=SyncStatus.UNSYNCED,
                source_exists=True,
                target_exists=True,
                is_symlink=True,
                method=mapping.method or LinkMethod.SYMLINK,
            )

    if not target_exists:
        return SyncState(
            mapping=mapping,
            status=SyncStatus.UNSYNCED,
            source_exists=True,
            target_exists=False,
            is_symlink=False,
            method=mapping.method or LinkMethod.SYMLINK,
        )

    if paths_match(source, target):
        return SyncState(
            mapping=mapping,
            status=SyncStatus.SYNCED,
            source_exists=True,
            target_exists=True,
            is_symlink=False,
            method=mapping.method or LinkMethod.SYMLINK,
        )

    return SyncState(
        mapping=mapping,
        status=SyncStatus.UNSYNCED,
        source_exists=True,
        target_exists=True,
        is_symlink=False,
        method=mapping.method or LinkMethod.SYMLINK,
    )


def evaluate_all_sync_status(config: AppConfig) -> list[SyncState]:
    """Evaluate sync status for all configurations in the app config.

    Args:
        config: The application configuration.

    Returns:
        List of SyncState objects for all host-relevant mappings.
    """
    return [evaluate_sync_status(mapping) for mapping in config.mappings]


def filter_sync_states(
    states: list[SyncState],
    show_linked: bool = True,
    show_synced: bool = True,
    show_unsynced: bool = True,
) -> list[SyncState]:
    """Filter sync states by status.

    Args:
        states: List of sync states to filter.
        show_linked: Include LINKED states.
        show_synced: Include SYNCED states.
        show_unsynced: Include UNSYNCED states.

    Returns:
        Filtered list of sync states.
    """
    result: list[SyncState] = []

    for state in states:
        if state.status == SyncStatus.LINKED and show_linked:
            result.append(state)
        elif state.status == SyncStatus.SYNCED and show_synced:
            result.append(state)
        elif state.status == SyncStatus.UNSYNCED and show_unsynced:
            result.append(state)

    return result


def count_by_status(states: list[SyncState]) -> dict[SyncStatus, int]:
    """Count sync states by their status.

    Args:
        states: List of sync states.

    Returns:
        Dictionary mapping status to count.
    """
    counts: dict[SyncStatus, int] = {
        SyncStatus.LINKED: 0,
        SyncStatus.SYNCED: 0,
        SyncStatus.UNSYNCED: 0,
    }

    for state in states:
        counts[state.status] += 1

    return counts
