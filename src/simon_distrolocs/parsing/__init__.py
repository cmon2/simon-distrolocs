"""Parsing utilities for TOML configuration.

This package contains individual parsing functions.
For backwards compatibility, all functions are re-exported here.
"""

from .parse_toml import ConfigError, parse_toml_config
from .parse_distro_types import parse_distro_types
from .parse_link_method import parse_link_method
from .parse_mappings import parse_mappings
from .parse_auth_type import parse_auth_type
from .parse_git_sources import parse_git_sources
from .parse_duplications import find_duplication_by_name, parse_duplications


class DuplicateError(Exception):
    """Raised when repository duplication fails."""

    pass


__all__ = [
    "ConfigError",
    "DuplicateError",
    "parse_toml_config",
    "parse_distro_types",
    "parse_link_method",
    "parse_mappings",
    "parse_auth_type",
    "parse_git_sources",
    "parse_duplications",
    "find_duplication_by_name",
]
