"""CLI entry point for Simon DistroLocs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from .config import (
    AppConfig,
    ConfigError,
    load_config,
    _parse_git_sources,
    find_config_file,
    parse_toml_config,
)
from .filesystem import remove_path
from .git_clone import clone_all_repos
from .sync_engine import (
    count_by_status,
    evaluate_all_sync_status,
    execute_sync,
    filter_sync_states,
)
from .types import SyncStatus
from .visualization import build_config_tree, print_legend


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="simon-distrolocs",
        description="Manage and distribute centralized configuration files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  simon-distrolocs ./my-configs
  simon-distrolocs ./my-configs --overwrite
  simon-distrolocs ./my-configs --only-unsynced
        """,
    )

    parser.add_argument(
        "managed_configs_directory",
        type=Path,
        help="Parent directory containing managed configs and TOML file",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite destination files with managed versions",
    )

    parser.add_argument(
        "--sync",
        action="store_true",
        help="Sync all unsynced configs (alias for --overwrite)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    parser.add_argument(
        "--hide-linked",
        action="store_true",
        help="Hide Linked items from output",
    )

    parser.add_argument(
        "--hide-synced",
        action="store_true",
        help="Hide Synced items from output",
    )

    parser.add_argument(
        "--only-unsynced",
        action="store_true",
        help="Show only Unsynced items",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (can be repeated)",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress informational messages",
    )

    parser.add_argument(
        "--repos-only",
        action="store_true",
        help="Clone repositories from configured git sources and exit",
    )

    parser.add_argument(
        "--duplicate",
        metavar="NAME",
        help="Duplicate a repository to Forgejo (requires --branch)",
    )

    parser.add_argument(
        "--branch",
        metavar="BRANCH",
        help="Branch to duplicate (required with --duplicate)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    return parser


def load_configuration(managed_dir: Path) -> AppConfig:
    """Load and validate configuration from the managed directory.

    Args:
        managed_dir: Path to the managed configs directory.

    Returns:
        Validated AppConfig.

    Raises:
        SystemExit: If configuration loading fails.
    """
    try:
        return load_config(managed_dir)
    except ConfigError as e:
        console = Console(stderr=True)
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(1)


def execute_overwrite(
    config: AppConfig, sync_states: list, dry_run: bool = False
) -> int:
    """Execute the overwrite operation for unsynced configs.

    Args:
        config: Application configuration.
        sync_states: List of sync states.
        dry_run: If True, only show what would be done.

    Returns:
        Number of configs that would be/were synced.
    """
    console = Console()
    error_console = Console(stderr=True)
    unsynced_states = [
        s for s in sync_states if s.status == SyncStatus.UNSYNCED and s.source_exists
    ]

    if not unsynced_states:
        if not dry_run:
            console.print("[green]All configs are already in sync.[/green]")
        return 0

    synced_count = 0

    for state in unsynced_states:
        mapping = state.mapping
        source = mapping.source
        target = mapping.target

        if dry_run:
            console.print(
                f"[yellow]Would sync:[/yellow] {mapping.name} "
                f"({source} → {target}) [dim]({state.method.value})[/dim]"
            )
        else:
            console.print(
                f"[cyan]Syncing:[/cyan] {mapping.name} "
                f"({source} → {target}) [dim]({state.method.value})[/dim]"
            )

            # Use execute_sync which respects the method (symlink vs anchor)
            new_state = execute_sync(state)
            if new_state.status in (SyncStatus.SYNCED, SyncStatus.LINKED):
                console.print(
                    f"  [green]✓ Synced successfully ({new_state.status.value})[/green]"
                )
                synced_count += 1
            else:
                error_console.print(f"  [red]✗ Failed to sync[/red]")

    return synced_count


def print_tree_output(
    config: AppConfig,
    sync_states: list,
    hide_linked: bool = False,
    hide_synced: bool = False,
    only_unsynced: bool = False,
) -> None:
    """Print the configuration tree output.

    Args:
        config: Application configuration.
        sync_states: List of sync states.
        hide_linked: Hide linked items.
        hide_synced: Hide synced items.
        only_unsynced: Show only unsynced items.
    """
    console = Console()

    show_linked = not hide_linked and not only_unsynced
    show_synced = not hide_synced and not only_unsynced
    show_unsynced = True

    if only_unsynced:
        show_linked = False
        show_synced = False

    filtered_states = filter_sync_states(
        sync_states,
        show_linked=show_linked,
        show_synced=show_synced,
        show_unsynced=show_unsynced,
    )

    tree = build_config_tree(config, filtered_states, console)
    console.print(tree)


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code (0 = success, non-zero = error).
    """
    parser = create_parser()
    args = parser.parse_args()

    console = Console()

    overwrite = args.overwrite or args.sync

    if args.verbose > 0 and not args.quiet:
        console.print(f"[dim]Scanning: {args.managed_configs_directory}[/dim]")

    config = load_config(args.managed_configs_directory)

    # Handle --repos-only mode (clone repos from git sources)
    if args.repos_only:
        try:
            config_file = find_config_file(args.managed_configs_directory)
            toml_dict = parse_toml_config(config_file)
            git_sources = _parse_git_sources(toml_dict, config_file.parent)

            if not git_sources:
                console.print("[yellow]No git sources configured.[/yellow]")
                return 0

            total_cloned, total_failed = clone_all_repos(
                git_sources, dry_run=args.dry_run, quiet=args.quiet
            )

            console.print(
                f"\n[bold]Cloned {total_cloned} repository(ies), {total_failed} failed[/bold]"
            )
            return 0 if total_failed == 0 else 1

        except ConfigError as e:
            console.print(f"[bold red]Configuration Error:[/bold red] {e}")
            return 1

    # Handle --duplicate mode (duplicate repo to Forgejo)
    if args.duplicate:
        if not args.branch:
            console.print(
                "[bold red]Error: --branch is required when using --duplicate[/bold red]"
            )
            return 1

        script_path = (
            Path(__file__).parent.parent.parent / "scripts" / "duplicate_repo.py"
        )

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    str(args.managed_configs_directory),
                    args.duplicate,
                    args.branch,
                ],
                cwd=args.managed_configs_directory,
            )
            return result.returncode
        except Exception as e:
            console.print(f"[bold red]Error running duplicate script:[/bold red] {e}")
            return 1

    if not config.mappings:
        console.print("[yellow]No configurations found for this host.[/yellow]")
        return 0

    sync_states = evaluate_all_sync_status(config)

    counts = count_by_status(sync_states)

    if not args.quiet:
        console.print()

        print_tree_output(
            config,
            sync_states,
            hide_linked=args.hide_linked,
            hide_synced=args.hide_synced,
            only_unsynced=args.only_unsynced,
        )

        console.print()
        print_legend(console)

    if overwrite:
        console.print()

        if args.dry_run:
            console.print("[bold]Dry run mode - no changes will be made[/bold]")
            console.print()

        synced = execute_overwrite(config, sync_states, dry_run=args.dry_run)

        if args.dry_run:
            console.print(f"\n[bold]Would sync {synced} configuration(s)[/bold]")
        else:
            console.print(f"\n[bold]Synced {synced} configuration(s)[/bold]")

    elif not args.quiet:
        summary_parts: list[str] = []
        if counts[SyncStatus.SYNCED] > 0:
            summary_parts.append(f"[green]{counts[SyncStatus.SYNCED]} synced[/green]")
        if counts[SyncStatus.UNSYNCED] > 0:
            summary_parts.append(
                f"[yellow]{counts[SyncStatus.UNSYNCED]} unsynced[/yellow]"
            )
        if counts[SyncStatus.LINKED] > 0:
            summary_parts.append(f"[cyan]{counts[SyncStatus.LINKED]} linked[/cyan]")

        console.print(f"\n[bold]Summary:[/bold] {', '.join(summary_parts)}")

        if counts[SyncStatus.UNSYNCED] > 0:
            console.print("\n[dim]Use --overwrite to sync unsynced configs[/dim]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
