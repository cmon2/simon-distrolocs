"""Define AuthType enum."""

from __future__ import annotations

from enum import Enum


class AuthType(Enum):
    """Authentication type for git sources.

    Attributes:
        TOKEN: Use a personal access token for authentication
        SSH: Use SSH key authentication
        NONE: No authentication (public repos only)
    """

    TOKEN = "token"
    SSH = "ssh"
    NONE = "none"
