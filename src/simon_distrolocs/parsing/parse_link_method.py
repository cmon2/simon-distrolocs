"""Link method parsing."""

from __future__ import annotations

from ..types import LinkMethod
from .parse_toml import ConfigError


def parse_link_method(method_str: str | None) -> LinkMethod:
    """Parse a method string into a LinkMethod enum value.

    Args:
        method_str: The method string from TOML (e.g., "symlink", "anchor").

    Returns:
        The corresponding LinkMethod enum value (defaults to SYMLINK if None).

    Raises:
        ConfigError: If the method string is not a valid LinkMethod value.
    """
    if method_str is None:
        return LinkMethod.SYMLINK

    try:
        return LinkMethod(method_str)
    except ValueError:
        valid_values = [m.value for m in LinkMethod]
        raise ConfigError(
            f"Invalid method '{method_str}'. Valid values are: {valid_values}"
        )
