"""Path comparison utilities."""

from __future__ import annotations

from pathlib import Path

from .compute_hashes import compute_directory_hash, compute_file_hash


def paths_match(source: Path, target: Path) -> bool:
    """Check if a source file/directory matches a target.

    Args:
        source: The source managed path.
        target: The target system path.

    Returns:
        True if contents match exactly, False otherwise.
    """
    source_exists = source.exists()
    target_exists = target.exists()

    if source_exists != target_exists:
        return False

    if not source_exists:
        return True

    if source.is_file():
        return compute_file_hash(source) == compute_file_hash(target)

    if source.is_dir():
        return compute_directory_hash(source) == compute_directory_hash(target)

    return False


def is_symlink_to(path: Path, expected_target: Path) -> bool:
    """Check if a path is a symlink pointing to a specific target.

    Args:
        path: The path to check.
        expected_target: The expected symlink target.

    Returns:
        True if path is a symlink to expected_target, False otherwise.
    """
    if not path.is_symlink():
        return False

    try:
        link_target = path.resolve()
        expected_resolved = expected_target.resolve()
        return link_target == expected_resolved
    except OSError:
        return False
