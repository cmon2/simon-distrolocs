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
        post_clone_scripts_raw = item.get("post_clone_scripts", [])

        if isinstance(clone_locations_raw, str):
            clone_locations_raw = [clone_locations_raw]
        if isinstance(post_clone_scripts_raw, str):
            post_clone_scripts_raw = [post_clone_scripts_raw]

        duplications.append(
            RepoDuplication(
                name=name,
                source_type=source_type,
                source_url=source_url,
                forgejo_target=forgejo_target,
                target_clone_locations=tuple(clone_locations_raw),
                enabled=enabled,
                post_clone_scripts=tuple(post_clone_scripts_raw),
            )
        )

    return tuple(duplications)


def find_duplication_by_name(
    duplications: tuple[RepoDuplication, ...], name: str
) -> RepoDuplication | None:
    """Find a duplication by name.

    Args:
        duplications: Tuple of RepoDuplication objects.
        name: Name of the duplication to find.

    Returns:
        RepoDuplication if found, None otherwise.
    """
    for dup in duplications:
        if dup.name == name:
            return dup
    return None
