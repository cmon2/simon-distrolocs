"""Authentication verification scripts for git sources.

This module provides functions to verify authentication credentials
for GitHub, GitLab, and Forgejo sources before attempting operations.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Directory containing verification scripts (bash scripts)
AUTH_VERIFICATION_DIR = Path(__file__).parent


def verify_github_ssh(key_path: str | None = None) -> tuple[bool, str]:
    """Verify GitHub SSH authentication.

    Args:
        key_path: Optional path to SSH private key. If not provided,
            auto-detects from standard locations.

    Returns:
        Tuple of (success, message).
    """
    script = AUTH_VERIFICATION_DIR / "verify_github_ssh.sh"
    if not script.exists():
        return False, f"Verification script not found: {script}"

    cmd = [str(script)]
    if key_path:
        cmd.append(key_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True, result.stdout.strip()
    else:
        return False, result.stdout.strip() or result.stderr.strip()


def verify_gitlab_token(
    gitlab_api: str | None = None, token_path: str | None = None
) -> tuple[bool, str]:
    """Verify GitLab token authentication.

    Args:
        gitlab_api: GitLab API URL (e.g., https://gitlab.com).
            If not provided, uses default.
        token_path: Optional path to token file. If not provided,
            auto-detects from standard locations.

    Returns:
        Tuple of (success, message).
    """
    script = AUTH_VERIFICATION_DIR / "verify_gitlab_token.sh"
    if not script.exists():
        return False, f"Verification script not found: {script}"

    cmd = [str(script)]
    if gitlab_api:
        cmd.append(gitlab_api)
    if token_path:
        cmd.append(token_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True, result.stdout.strip()
    else:
        return False, result.stdout.strip() or result.stderr.strip()


def verify_forgejo_token(
    forgejo_base: str | None = None, token_path: str | None = None
) -> tuple[bool, str]:
    """Verify Forgejo token authentication.

    Args:
        forgejo_base: Forgejo base URL (e.g., http://localhost:3000).
            If not provided, tries to auto-detect from git remotes.
        token_path: Optional path to token file. If not provided,
            auto-detects from standard locations.

    Returns:
        Tuple of (success, message).
    """
    script = AUTH_VERIFICATION_DIR / "verify_forgejo_token.sh"
    if not script.exists():
        return False, f"Verification script not found: {script}"

    cmd = [str(script)]
    if forgejo_base:
        cmd.append(forgejo_base)
    if token_path:
        cmd.append(token_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return True, result.stdout.strip()
    else:
        return False, result.stdout.strip() or result.stderr.strip()
