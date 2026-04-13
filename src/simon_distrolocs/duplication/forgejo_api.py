"""Forgejo API client for repository operations."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..git_helpers import get_ssl_context
from ..parsing import DuplicateError


def get_forgejo_username(forgejo_api: str, token: str) -> str:
    """Get the authenticated username from Forgejo.

    Args:
        forgejo_api: The Forgejo API base URL.
        token: Forgejo authentication token.

    Returns:
        The username of the authenticated user.
    """
    url = f"{forgejo_api}/user"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, context=get_ssl_context()) as response:
        data = json.loads(response.read().decode())
        return data["login"]


def check_repo_exists(forgejo_api: str, repo_name: str, token: str) -> bool:
    """Check if repository exists on Forgejo.

    Args:
        forgejo_api: The Forgejo API base URL.
        repo_name: Full repo name (e.g., "simon_ide/pgxperts-prim-develop").
        token: Forgejo authentication token.

    Returns:
        True if repo exists, False otherwise.
    """
    url = f"{forgejo_api}/repos/{repo_name}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, context=get_ssl_context()) as response:
            return response.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise DuplicateError(f"Failed to check repo existence: {e}")


def create_repo(forgejo_api: str, repo_name: str, token: str) -> None:
    """Create a repository on Forgejo.

    Args:
        forgejo_api: The Forgejo API base URL.
        repo_name: Full repo name (e.g., "simon_ide/pgxperts-prim-develop").
        token: Forgejo authentication token.

    Raises:
        DuplicateError: If creation fails.
    """
    # Split namespace and repo name
    parts = repo_name.split("/")
    if len(parts) != 2:
        raise DuplicateError(f"Invalid repo name format: {repo_name}")
    repo = parts[1]  # Only need repo name for creation under authenticated user

    # Forgejo uses POST /api/v1/user/repos to create a repo under the authenticated user
    url = f"{forgejo_api}/user/repos"

    payload = json.dumps(
        {
            "name": repo,
            "private": True,
        }
    ).encode()

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, context=get_ssl_context()) as response:
            if response.status not in (201, 200):
                raise DuplicateError(f"Failed to create repo: HTTP {response.status}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        raise DuplicateError(f"Failed to create repo: {e}\n{error_body}")


def delete_repo(forgejo_api: str, repo_name: str, token: str) -> None:
    """Delete a repository on Forgejo.

    Args:
        forgejo_api: The Forgejo API base URL.
        repo_name: Full repo name (e.g., "simon_ide/pgxperts-prim-develop").
        token: Forgejo authentication token.

    Raises:
        DuplicateError: If deletion fails.
    """
    url = f"{forgejo_api}/repos/{repo_name}"

    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, context=get_ssl_context()) as response:
            if response.status not in (204, 200):
                raise DuplicateError(f"Failed to delete repo: HTTP {response.status}")
    except urllib.error.HTTPError as e:
        raise DuplicateError(f"Failed to delete repo: {e}")
