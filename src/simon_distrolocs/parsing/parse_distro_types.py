"""Distro types parsing."""

from __future__ import annotations

from typing import Any

from ..types import DistroType


def parse_distro_types(toml_dict: dict[str, Any]) -> dict[str, DistroType]:
    """Parse distro_types section from TOML.

    Args:
        toml_dict: Parsed TOML dictionary.

    Returns:
        Dictionary of DistroType objects keyed by name.
    """
    distro_types: dict[str, DistroType] = {}
    raw_types = toml_dict.get("distro_types", {})

    for name, config in raw_types.items():
        if isinstance(config, dict):
            depth = config.get("visualizationDepth", 0)
        else:
            depth = 0
        distro_types[name] = DistroType(name=name, visualization_depth=depth)

    return distro_types
