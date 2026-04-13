"""Hash computation for files and directories."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Generator


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
