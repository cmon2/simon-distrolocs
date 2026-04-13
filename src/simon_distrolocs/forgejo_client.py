"""Forgejo API client for repository duplication.

This module provides backwards-compatible re-exports.
All implementation has been moved to:
- git_helpers/ - Git environment and URL helpers
- duplication/ - Forgejo API and duplication orchestration
"""

from __future__ import annotations

# Re-export from new locations for backwards compatibility
from .duplication import (
    check_repo_exists,
    create_repo,
    delete_repo,
    duplicate_repository,
    get_forgejo_username,
)
from .duplication.duplicate_repo import DuplicateError

__all__ = [
    "DuplicateError",
    "check_repo_exists",
    "create_repo",
    "delete_repo",
    "duplicate_repository",
    "get_forgejo_username",
]
