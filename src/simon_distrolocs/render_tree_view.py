"""Rich-based visualization for Simon DistroLocs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.style import Style
from rich.syntax import Syntax
from rich.tree import Tree

if TYPE_CHECKING:
    from .types import AppConfig, SyncState

from .types import SyncStatus


SYNC_COLORS: dict[str, str] = {
    "linked": "green",
    "synced": "green",
    "unsynced": "red",
}

STATUS_SYMBOLS: dict[str, str] = {
    "linked": "✓",
    "synced": "✓",
    "unsynced": "✗",
}


def get_status_style(status: "SyncStatus") -> Style:
    """Get the Rich style for a sync status.

    Args:
        status: The sync status.

    Returns:
        Rich Style object.
    """
    color = SYNC_COLORS.get(status.value, "white")
    return Style(color=color, bold=True)


def get_status_symbol(status: "SyncStatus") -> str:
    """Get the status symbol for display.

    Args:
        status: The sync status.

    Returns:
        Formatted symbol with color tags.
    """
    color = SYNC_COLORS.get(status.value, "white")
    symbol = STATUS_SYMBOLS.get(status.value, "?")
    return f"[{color}]{symbol}[/{color}]"


def expand_path_for_display(target: Path, depth: int) -> list[tuple[Path, int]]:
    """Expand a path into components for tree display.

    Args:
        target: The target path to expand.
        depth: Maximum depth to expand (0 = just the root).

    Returns:
        List of (path_component, level) tuples for tree rendering.
    """
    parts: list[tuple[Path, int]] = []

    if depth == 0:
        return [(target, 0)]

    try:
        resolved = target.expanduser().resolve()
    except OSError:
        resolved = target

    current = Path("/")
    parts.append((current, 0))

    if resolved.is_dir():
        for i, part in enumerate(resolved.parts[1:], start=1):
            if i >= depth:
                parts.append((Path("..."), i))
                break
            current = current / part
            parts.append((current, i))

    return parts


def render_target_tree(target: Path, depth: int) -> str:
    """Render a target path as a tree string.

    Args:
        target: The target path.
        depth: Visualization depth.

    Returns:
        String representation of the expanded path.
    """
    if depth == 0:
        return str(target)

    parts = expand_path_for_display(target, depth)
    lines: list[str] = []

    for path_part, level in parts:
        if level == 0:
            lines.append(str(path_part))
        else:
            prefix = "│   " * (level - 1) + "├── "
            lines.append(f"{prefix}{path_part.name}")

    return "\n".join(lines)


def build_config_tree(
    config: "AppConfig",
    sync_states: list["SyncState"],
    console: Console,
) -> Tree:
    """Build a Rich tree representation of the managed configurations.

    Args:
        config: The application configuration.
        sync_states: List of evaluated sync states.
        console: Rich console for styling context.

    Returns:
        Tree object ready for rendering.
    """
    from .config import get_visualization_depth
    from .evaluate_sync import count_by_status

    hostname = config.mappings[0].source.parts[0] if config.mappings else "unknown"

    status_counts = count_by_status(sync_states)
    summary_parts: list[str] = []

    if status_counts[SyncStatus.SYNCED] > 0:
        summary_parts.append(
            f"[green]{status_counts[SyncStatus.SYNCED]} synced[/green]"
        )
    if status_counts[SyncStatus.UNSYNCED] > 0:
        summary_parts.append(
            f"[yellow]{status_counts[SyncStatus.UNSYNCED]} unsynced[/yellow]"
        )
    if status_counts[SyncStatus.LINKED] > 0:
        summary_parts.append(f"[cyan]{status_counts[SyncStatus.LINKED]} linked[/cyan]")

    summary = ", ".join(summary_parts) if summary_parts else "no configs"

    header = f"Managed Configurations on [yellow]{hostname}[/yellow] ([bold]{summary}[/bold])"
    tree = Tree(header, guide_style="dim")

    for sync_state in sync_states:
        mapping = sync_state.mapping
        status = sync_state.status
        status_symbol = get_status_symbol(status)

        source_str = f"[dim]→ {mapping.source}[/dim]"

        label = f"[bold]{mapping.name}[/bold] → [blue]{mapping.target}[/blue] {status_symbol}"
        target_depth = get_visualization_depth(config, mapping)

        subtree = tree.add(label)

        if target_depth > 0:
            path_lines = expand_path_for_display(mapping.target, target_depth + 1)
            for path_part, level in path_lines[1:]:
                if level > target_depth:
                    break
                indent = "│   " * (level - 1) + "├── " if level > 0 else ""
                subtree.add(f"[dim]{indent}{path_part}[/dim]")

        subtree.add(source_str)

    return tree


def print_config_tree(
    config: "AppConfig",
    sync_states: list["SyncState"],
    console: Console | None = None,
) -> None:
    """Print the configuration tree to the console.

    Args:
        config: The application configuration.
        sync_states: List of evaluated sync states.
        console: Rich console (creates one if not provided).
    """
    if console is None:
        console = Console()

    tree = build_config_tree(config, sync_states, console)
    console.print(tree)


def print_legend(console: Console | None = None) -> None:
    """Print the sync status legend.

    Args:
        console: Rich console (creates one if not provided).
    """
    if console is None:
        console = Console()

    legend_items = [
        ("[green]✓[/green]", "Synced or linked"),
        ("[red]✗[/red]", "Unsynced"),
    ]

    console.print("[bold]Legend:[/bold]")
    for symbol, description in legend_items:
        console.print(f"  {symbol}    {description}")
