"""Configuration parsing and validation for Simon DistroLocs.

This module provides backwards-compatible imports.
All implementation is in assemble_config.py and parsing/ subdirectory.
"""

from __future__ import annotations

# Re-export ConfigError from parsing for backwards compatibility
from .parsing import ConfigError

# Re-export parsing functions for backwards compatibility
from .parsing import (
    parse_distro_types,
    parse_duplications,
    parse_git_sources,
    parse_link_method,
    parse_mappings,
    parse_toml_config,
)

# Re-export assembly functions for backwards compatibility
from .assemble_config import find_config_file, get_visualization_depth, load_config

# Re-export AppConfig from types for backwards compatibility
from .types import AppConfig

__all__ = [
    "ConfigError",
    "find_config_file",
    "parse_toml_config",
    "parse_distro_types",
    "parse_link_method",
    "parse_mappings",
    "parse_git_sources",
    "parse_duplications",
    "load_config",
    "get_visualization_depth",
]

# Import find_config_file from assemble_config for backwards compatibility
from .assemble_config import find_config_file
