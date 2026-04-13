"""CLI entry point for Simon DistroLocs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from cmon2lib import cprint, clog

from .config import AppConfig, ConfigError, find_config_file, load_config
from .forgejo_client import duplicate_repository
from .parsing import (
    DuplicateError,
    find_duplication_by_name,
    parse_duplications,
    parse_git_sources,
    parse_toml_config,
)
from .manage_files import remove_path
from .clone_repos import clone_all_repos
from .evaluate_sync import (
    count_by_status,
    evaluate_all_sync_status,
    filter_sync_states,
)
from .execute_sync import execute_sync
from .types import SyncStatus
from .render_tree_view import build_config_tree, print_legend


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
        cprint("error", f"[bold red]Configuration Error:[/bold red] {e}")
        clog("error", f"Configuration error: {e}")
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
    unsynced_states = [
        s for s in sync_states if s.status == SyncStatus.UNSYNCED and s.source_exists
    ]

    if not unsynced_states:
        if not dry_run:
            cprint("success", "[green]All configs are already in sync.[/green]")
        return 0

    synced_count = 0

    for state in unsynced_states:
        mapping = state.mapping
        source = mapping.source
        target = mapping.target

        if dry_run:
            cprint(
                "info",
                f"[yellow]Would sync:[/yellow] {mapping.name} "
                f"({source} → {target}) [dim]({state.method.value})[/dim]",
            )
        else:
            cprint(
                "info",
                f"[cyan]Syncing:[/cyan] {mapping.name} "
                f"({source} → {target}) [dim]({state.method.value})[/dim]",
            )

            # Use execute_sync which respects the method (symlink vs anchor)
            new_state = execute_sync(state)
            if new_state.status in (SyncStatus.SYNCED, SyncStatus.LINKED):
                cprint(
                    "success",
                    f"  [green]✓ Synced successfully ({new_state.status.value})[/green]",
                )
                clog("success", f"Synced config: {mapping.name}")
                synced_count += 1
            else:
                cprint("error", f"  [red]✗ Failed to sync[/red]")
                clog("error", f"Failed to sync: {mapping.name}")

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

    overwrite = args.overwrite or args.sync

    if args.verbose > 0 and not args.quiet:
        cprint("info", f"[dim]Scanning: {args.managed_configs_directory}[/dim]")

    config = load_config(args.managed_configs_directory)

    # Handle --repos-only mode (clone repos from git sources)
    if args.repos_only:
        try:
            config_file = find_config_file(args.managed_configs_directory)
            toml_dict = parse_toml_config(config_file)
            git_sources = parse_git_sources(toml_dict)

            if not git_sources:
                cprint("warning", "[yellow]No git sources configured.[/yellow]")
                return 0

            total_cloned, total_failed = clone_all_repos(
                git_sources, dry_run=args.dry_run, quiet=args.quiet
            )

            cprint(
                "info",
                f"\n[bold]Cloned {total_cloned} repository(ies), {total_failed} failed[/bold]",
            )
            clog("info", f"Clone result: {total_cloned} cloned, {total_failed} failed")
            return 0 if total_failed == 0 else 1

        except ConfigError as e:
            cprint("error", f"[bold red]Configuration Error:[/bold red] {e}")
            clog("error", f"Configuration error: {e}")
            return 1

    # Handle --duplicate mode (duplicate repo to Forgejo)
    if args.duplicate:
        if not args.branch:
            cprint(
                "error",
                "[bold red]Error: --branch is required when using --duplicate[/bold red]",
            )
            return 1

        try:
            config_path = find_config_file(args.managed_configs_directory)
            toml_dict = parse_toml_config(config_path)
            duplications = parse_duplications(toml_dict)

            duplication = find_duplication_by_name(duplications, args.duplicate)
            if duplication is None:
                cprint(
                    "error",
                    f"[bold red]Duplication '{args.duplicate}' not found in config[/bold red]",
                )
                clog("error", f"Duplication not found: {args.duplicate}")
                return 1

            duplicate_repository(
                source_url=duplication.source_url,
                source_type=duplication.source_type,
                forgejo_target=duplication.forgejo_target,
                branch=args.branch,
                clone_locations=duplication.target_clone_locations,
                config_dir=args.managed_configs_directory,
            )
            cprint("success", "[green]✓ Duplication complete![/green]")
            return 0

        except DuplicateError as e:
            cprint("error", f"[bold red]Duplicate Error:[/bold red] {e}")
            clog("error", f"Duplicate error: {e}")
            return 1
        except ConfigError as e:
            cprint("error", f"[bold red]Configuration Error:[/bold red] {e}")
            clog("error", f"Configuration error: {e}")
            return 1

    if not config.mappings:
        cprint("warning", "[yellow]No configurations found for this host.[/yellow]")
        return 0

    sync_states = evaluate_all_sync_status(config)

    counts = count_by_status(sync_states)

    if not args.quiet:
        cprint("info", "")

        print_tree_output(
            config,
            sync_states,
            hide_linked=args.hide_linked,
            hide_synced=args.hide_synced,
            only_unsynced=args.only_unsynced,
        )

        cprint("info", "")
        print_legend(Console())

    if overwrite:
        cprint("info", "")

        if args.dry_run:
            cprint("info", "[bold]Dry run mode - no changes will be made[/bold]")
            cprint("info", "")

        synced = execute_overwrite(config, sync_states, dry_run=args.dry_run)

        if args.dry_run:
            cprint("info", f"\n[bold]Would sync {synced} configuration(s)[/bold]")
        else:
            cprint("success", f"\n[bold]Synced {synced} configuration(s)[/bold]")
            clog("success", f"Sync completed: {synced} config(s) synced")

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

        cprint("info", f"\n[bold]Summary:[/bold] {', '.join(summary_parts)}")

        if counts[SyncStatus.UNSYNCED] > 0:
            cprint("info", "\n[dim]Use --overwrite to sync unsynced configs[/dim]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
