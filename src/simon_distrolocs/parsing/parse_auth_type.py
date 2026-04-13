"""Auth type parsing."""

from __future__ import annotations

from ..types import AuthType
from .parse_toml import ConfigError


def parse_auth_type(auth_str: str | None) -> AuthType:
    """Parse an auth type string into an AuthType enum value.

    Args:
        auth_str: The auth type string from TOML (e.g., "token", "ssh", "none").

    Returns:
        The corresponding AuthType enum value (defaults to NONE if None).

    Raises:
        ConfigError: If the auth type string is not a valid AuthType value.
    """
    if auth_str is None:
        return AuthType.NONE

    try:
        return AuthType(auth_str.lower())
    except ValueError:
        valid_values = [a.value for a in AuthType]
        raise ConfigError(
            f"Invalid auth_type '{auth_str}'. Valid values are: {valid_values}"
        )
