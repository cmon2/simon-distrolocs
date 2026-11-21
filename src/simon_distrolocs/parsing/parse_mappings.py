"""Mappings parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..types import ConfigMapping
from .parse_link_method import parse_link_method


def parse_mappings(toml_dict: dict[str, Any], parent_dir: Path) -> list[ConfigMapping]:
    """Parse [[mapping]] sections from TOML.

    Args:
        toml_dict: Parsed TOML dictionary.
        parent_dir: The parent managed configs directory.

    Returns:
        List of ConfigMapping objects.
    """
    mappings: list[ConfigMapping] = []
    raw_mappings = toml_dict.get("mapping", [])

    if isinstance(raw_mappings, dict):
        raw_mappings = [raw_mappings]

    for item in raw_mappings:
        name = item.get("name", "")
        source_str = item.get("source", "")
        target_str = item.get("target", "")
        excluded_on_hosts_raw = item.get("excluded_on_hosts", [])
        method_str = item.get("method")

        if isinstance(excluded_on_hosts_raw, str):
            excluded_on_hosts_raw = [excluded_on_hosts_raw]

        # A mapping carries absolute paths: a symlink whose target is relative resolves
        # against its own directory, not against the working directory of the tool, so a
        # relative source would write a link that points nowhere.
        source = (parent_dir / source_str).absolute()
        target = Path(target_str.replace("~", str(Path.home()))).absolute()
        method = parse_link_method(method_str)

        mapping = ConfigMapping(
            name=name,
            source=source,
            target=target,
            excluded_on_hosts=tuple(excluded_on_hosts_raw),
            method=method,
        )
        mappings.append(mapping)

    return mappings
