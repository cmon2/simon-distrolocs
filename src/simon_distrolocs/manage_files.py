"""File management operations (copy, remove, symlink)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def copy_file(source: Path, target: Path) -> None:
    """Copy a file to a target location.

    This function will create parent directories as needed and
    will overwrite an existing file.

    Args:
        source: Source file path.
        target: Target destination path.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_directory(source: Path, target: Path) -> None:
    """Copy a directory tree to a target location.

    This function will remove an existing target directory if present
    and create a fresh copy.

    Args:
        source: Source directory path.
        target: Target destination path.
    """
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def remove_path(path: Path) -> None:
    """Remove a file, directory, or symlink.

    Args:
        path: Path to remove.
    """
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def ensure_parent_dir(path: Path) -> None:
    """Ensure the parent directory of a path exists.

    Args:
        path: Path whose parent should exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)


def safe_execute_copy(source: Path, target: Path) -> bool:
    """Safely execute a copy operation with error handling.

    Args:
        source: Source path.
        target: Target destination.

    Returns:
        True if copy succeeded, False otherwise.
    """
    try:
        if source.is_dir():
            copy_directory(source, target)
        else:
            copy_file(source, target)
        return True
    except OSError:
        return False


def create_symlink(source: Path, target: Path) -> bool:
    """Create a symlink from target to source.

    Creates parent directories if they don't exist, removes existing
    target (file, dir, or symlink), and creates the symlink.

    Args:
        source: The path the symlink should point to.
        target: The path where the symlink will be created.

    Returns:
        True if symlink was created successfully, False otherwise.
    """
    try:
        # Create parent directories if needed
        target.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing target (file, dir, or symlink)
        if target.exists() or target.is_symlink():
            remove_path(target)

        # Create symlink from target pointing to source
        target.symlink_to(source)
        return True
    except OSError as e:
        logger.error("Failed to create symlink from %s to %s: %s", target, source, e)
        return False
