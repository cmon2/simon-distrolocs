"""Define AppConfig dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .define_config_mapping import ConfigMapping
    from .define_distro_type import DistroType
    from .define_repo_duplication import RepoDuplication


@dataclass(frozen=True)
class AppConfig:
    """The parsed and validated application configuration.

    Attributes:
        distro_types: Dictionary of DistroType definitions by name.
        mappings: List of configuration mappings relevant to the current host.
        all_mappings: All mappings (including filtered out by host) for reference.
        duplications: List of RepoDuplication configurations.
    """

    distro_types: dict[str, "DistroType"]
    mappings: list["ConfigMapping"]
    all_mappings: list["ConfigMapping"]
    duplications: tuple["RepoDuplication", ...] = field(default_factory=tuple)
