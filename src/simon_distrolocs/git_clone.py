"""Git repository cloning for Simon DistroLocs.

This module handles discovering and cloning repositories from configured
git sources (Forgejo, GitHub, GitLab).
"""

from __future__ import annotations

import json
import socket
import ssl
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .types import AuthType, GitSource, RepoInfo

# Verification script paths relative to distrolocs root
VERIFY_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts" / "verify"

VERIFICATION_SCRIPTS = {
    "github": {
        "ssh": "verify_github_ssh_auth.sh",
        "token": "verify_github_token_auth.sh",  # future
    },
    "forgejo": {
        "token": "verify_forgejo_token_auth.sh",
        "ssh": "verify_forgejo_ssh_auth.sh",  # future
    },
    "gitlab": {
        "token": "verify_gitlab_token_auth.sh",
        "ssh": "verify_gitlab_ssh_auth.sh",  # future
    },
}


class CloneError(Exception):
    """Raised when repository cloning fails."""

    pass


def check_auth_verification(source: GitSource) -> tuple[bool, str]:
    """Check if a verification script exists for a git source.

    Args:
        source: The GitSource to check.

    Returns:
        Tuple of (has_verification, message).
    """
    # Determine the source type from URL
    url_lower = source.list_repos_url.lower()

    if "github.com" in url_lower:
        source_type = "github"
    elif "gitlab" in url_lower or "git.hmg" in url_lower:
        source_type = "gitlab"
    else:
        source_type = "forgejo"

    # Determine auth method
    auth_method = source.auth_type.value if source.auth_type else "token"

    # Get the expected verification script
    scripts_for_source = VERIFICATION_SCRIPTS.get(source_type, {})
    script_name = scripts_for_source.get(auth_method)

    if not script_name:
        return False, f"No verification script defined for {source_type}/{auth_method}"

    script_path = VERIFY_SCRIPTS_DIR / script_name

    if script_path.exists():
        return True, f"Verification script found: {script_path}"
    else:
        return False, f"Verification script not found: {script_path}"


def warn_missing_auth_verification(sources: list[GitSource]) -> None:
    """Print warnings for git sources without verification scripts.

    Args:
        sources: List of GitSources to check.
    """
    print("\n[yellow]Checking auth verification for git sources...[/yellow]")

    has_warnings = False
    for source in sources:
        if not source.enabled:
            continue

        has_verification, message = check_auth_verification(source)

        if has_verification:
            print(f"  [green]✓[/green] {source.name}: {message}")
        else:
            print(f"  [yellow]![/yellow] {source.name}: {message}")
            has_warnings = True

    if has_warnings:
        print(
            "\n[yellow]Warning: Some git sources don't have auth verification scripts.[/yellow]\n"
            "This means authentication can't be automatically verified before cloning.\n"
            "Consider adding verification scripts to scripts/verify/"
        )


@dataclass
class CloneResult:
    """Result of a clone operation."""

    repo: RepoInfo
    success: bool
    message: str


def _fetch_repos_forgejo(source: GitSource) -> list[RepoInfo]:
    """Fetch repository list from Forgejo API."""
    repos: list[RepoInfo] = []

    req = urllib.request.Request(source.list_repos_url)
    token = source.get_auth_token()
    if token:
        req.add_header("Authorization", f"token {token}")

    context = None
    if not source.ssl_verify:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(req, context=context) as response:
        data = json.loads(response.read().decode())

    for repo in data:
        clone_url = repo.get("clone_url", "") or repo.get("ssh_url", "")
        repos.append(
            RepoInfo(
                name=repo["name"],
                clone_url=clone_url,
                full_name=repo.get("full_name", repo["name"]),
            )
        )

    return repos


def _fetch_repos_github(source: GitSource) -> list[RepoInfo]:
    """Fetch repository list from GitHub API."""
    repos: list[RepoInfo] = []

    req = urllib.request.Request(source.list_repos_url)
    token = source.get_auth_token()
    if token:
        req.add_header("Authorization", f"token {token}")

    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())

    for repo in data:
        repos.append(
            RepoInfo(
                name=repo["name"],
                clone_url=repo.get("clone_url", ""),
                full_name=repo.get("full_name", repo["name"]),
            )
        )

    return repos


def _fetch_repos_gitlab(source: GitSource) -> list[RepoInfo]:
    """Fetch repository list from GitLab API."""
    repos: list[RepoInfo] = []

    req = urllib.request.Request(source.list_repos_url)
    token = source.get_auth_token()
    if token:
        req.add_header("PRIVATE-TOKEN", token)

    context = None
    if not source.ssl_verify:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(req, context=context) as response:
        data = json.loads(response.read().decode())

    for repo in data:
        repos.append(
            RepoInfo(
                name=repo["path_with_namespace"],
                clone_url=repo.get("http_url_to_repo", ""),
                full_name=repo.get("path_with_namespace", repo["path"]),
            )
        )

    return repos


def fetch_repos(source: GitSource) -> list[RepoInfo]:
    """Fetch repository list from a git source."""
    url = source.list_repos_url.lower()

    if "github.com" in url or "/orgs/" in url:
        return _fetch_repos_github(source)
    elif "gitlab" in url or "git.hmg" in url:
        return _fetch_repos_gitlab(source)
    else:
        return _fetch_repos_forgejo(source)


def _build_clone_url(repo: RepoInfo, source: GitSource) -> str:
    """Build the clone URL with embedded credentials if needed."""
    clone_url = repo.clone_url

    if source.auth_type == AuthType.TOKEN:
        token = source.get_auth_token()
        if token and token not in clone_url:
            if clone_url.startswith("https://"):
                # GitLab uses oauth2 prefix for tokens
                if (
                    "gitlab" in source.list_repos_url.lower()
                    or "git.hmg" in source.list_repos_url.lower()
                ):
                    token = f"oauth2:{token}"
                parts = clone_url.split("://", 1)
                clone_url = f"{parts[0]}://{token}@{parts[1]}"

    return clone_url


def clone_repo(repo: RepoInfo, source: GitSource, dry_run: bool = False) -> CloneResult:
    """Clone a single repository."""
    dest_dir = source.cloning_destination / repo.name
    clone_url = _build_clone_url(repo, source)

    if dest_dir.exists():
        return CloneResult(repo=repo, success=True, message="Already exists, skipping")

    if dry_run:
        return CloneResult(
            repo=repo, success=True, message=f"Would clone to {dest_dir}"
        )

    source.cloning_destination.mkdir(parents=True, exist_ok=True)
    dest_dir.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone"]
    if not source.ssl_verify:
        cmd.extend(["-c", "http.sslverify=false"])
    cmd.extend([clone_url, str(dest_dir)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            return CloneResult(repo=repo, success=True, message=f"Cloned to {dest_dir}")
        else:
            return CloneResult(
                repo=repo, success=False, message=f"Failed: {result.stderr[:200]}"
            )
    except subprocess.TimeoutExpired:
        return CloneResult(repo=repo, success=False, message="Timeout after 5 minutes")
    except Exception as e:
        return CloneResult(repo=repo, success=False, message=f"Error: {str(e)}")


def clone_all_repos(
    sources: list[GitSource], dry_run: bool = False, quiet: bool = False
) -> tuple[int, int]:
    """Clone repositories from all enabled sources."""
    # Warn about missing auth verification
    warn_missing_auth_verification(sources)

    current_host = socket.gethostname()
    total_cloned = 0
    total_failed = 0

    for source in sources:
        if not source.enabled:
            continue

        if current_host in source.excluded_on_hosts:
            if not quiet:
                print(
                    f"\n[dim]⊘[/dim] [cyan]Source:[/cyan] {source.name} (excluded on {current_host})"
                )
            continue

        if not quiet:
            print(f"\n[cyan]Source:[/cyan] {source.name}")
            print(f"  Destination: {source.cloning_destination}")
            print(f"  API: {source.list_repos_url}")

        try:
            repos = fetch_repos(source)
            if not quiet:
                print(f"  Found {len(repos)} repository(ies)")
        except Exception as e:
            print(f"  [red]Failed to fetch repos:[/red] {e}")
            total_failed += 1
            continue

        for repo in repos:
            if repo.name in source.exclude_repos:
                if not quiet:
                    print(f"  [dim]⊘[/dim] {repo.name}: excluded")
                continue

            result = clone_repo(repo, source, dry_run=dry_run)
            if result.success:
                total_cloned += 1
                if not quiet:
                    print(f"  [green]✓[/green] {repo.name}: {result.message}")
            else:
                total_failed += 1
                print(f"  [red]✗[/red] {repo.name}: {result.message}")

    return total_cloned, total_failed
