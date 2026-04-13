"""TOML parsing utilities."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Handle Python version compatibility
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]


class ConfigError(Exception):
    """Raised when configuration parsing or validation fails."""

    pass


def parse_toml_config(config_path: Path) -> dict[str, Any]:
    """Parse a TOML configuration file.

    Args:
        config_path: Path to the TOML file.

    Returns:
        Parsed TOML as a dictionary.

    Raises:
        ConfigError: If TOML parsing fails.
    """
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Failed to parse TOML: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read config file: {e}") from e
