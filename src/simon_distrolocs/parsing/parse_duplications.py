"""Duplications parsing."""

from __future__ import annotations

from typing import Any

from ..types import RepoDuplication


def parse_duplications(toml_dict: dict[str, Any]) -> tuple[RepoDuplication, ...]:
    """Parse [[duplication]] sections from TOML.

    Args:
        toml_dict: Parsed TOML dictionary.

    Returns:
        Tuple of RepoDuplication objects.
    """
    duplications: list[RepoDuplication] = []
    raw_duplications = toml_dict.get("duplication", [])

    if isinstance(raw_duplications, dict):
        raw_duplications = [raw_duplications]

    for item in raw_duplications:
        name = item.get("name", "")
        source_type = item.get("source_type", "")
        source_url = item.get("source_url", "")
        forgejo_target = item.get("forgejo_target", "")
        clone_locations_raw = item.get("target_clone_locations", [])
        enabled = item.get("enabled", True)

        if isinstance(clone_locations_raw, str):
            clone_locations_raw = [clone_locations_raw]

        duplications.append(
            RepoDuplication(
                name=name,
                source_type=source_type,
                source_url=source_url,
                forgejo_target=forgejo_target,
                target_clone_locations=tuple(clone_locations_raw),
                enabled=enabled,
            )
        )

    return tuple(duplications)
