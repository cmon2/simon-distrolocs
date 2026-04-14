"""Git environment helpers."""

from __future__ import annotations

import os
from pathlib import Path


def get_git_env() -> dict:
    """Get environment dict for Git operations.

    Configures SSH for hosts that need it (from ~/.ssh/config) and
    SSL verification bypass for self-signed certificates.

    Returns:
        Environment dict with GIT_SSH_COMMAND and SSL settings configured.
    """
    ssh_config_path = Path.home() / ".ssh" / "config"
    return {
        **os.environ,
        "GIT_SSH_COMMAND": f"ssh -F {ssh_config_path} -o PreferredAuthentications=publickey",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSL_NO_VERIFY": "1",
        "GIT_SSL_CAINFO": "",
    }
