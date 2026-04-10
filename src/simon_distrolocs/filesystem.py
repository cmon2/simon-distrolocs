"""File system operations for Simon DistroLocs."""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of a file's contents.

    Args:
        file_path: Path to the file.

    Returns:
        Hexadecimal hash string.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_directory_hash(dir_path: Path) -> str:
    """Compute a hash of a directory's contents.

    The hash is computed from the sorted list of relative paths and their
    individual file hashes.

    Args:
        dir_path: Path to the directory.

    Returns:
        Hexadecimal hash string representing the directory contents.
    """
    file_hashes: list[str] = []

    for file_path in sorted(_iterate_files(dir_path)):
        rel_path = file_path.relative_to(dir_path)
        file_hashes.append(f"{rel_path}:{compute_file_hash(file_path)}")

    sha256 = hashlib.sha256()
    sha256.update("|".join(file_hashes).encode())
    return sha256.hexdigest()


def _iterate_files(dir_path: Path) -> Generator[Path, None, None]:
    """Iterate over all files in a directory recursively.

    Args:
        dir_path: Path to the directory.

    Yields:
        Paths to all files within the directory.
    """
    for item in dir_path.rglob("*"):
        if item.is_file():
            yield item


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
