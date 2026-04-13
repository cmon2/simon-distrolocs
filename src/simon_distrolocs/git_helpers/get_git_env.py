"""Git environment helpers."""

from __future__ import annotations

import os
from pathlib import Path


def get_git_env() -> dict:
    """Get environment dict with SSH command for Git operations.

    Uses ~/.ssh/config to resolve hostnames like 'git.hmg' which are
    defined in SSH config, not DNS.

    Returns:
        Environment dict with GIT_SSH_COMMAND configured.
    """
    ssh_config_path = Path.home() / ".ssh" / "config"
    return {
        **os.environ,
        "GIT_SSH_COMMAND": f"ssh -F {ssh_config_path} -o PreferredAuthentications=publickey",
    }
