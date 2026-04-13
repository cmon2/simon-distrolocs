"""Git repository cloning for Simon DistroLocs.

This module handles discovering and cloning repositories from configured
git sources (Forgejo, GitHub, GitLab).
"""

from __future__ import annotations

import json
import socket
import ssl
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cmon2lib import cprint, clog

from .types import AuthType, GitSource, RepoInfo

# Verification script paths relative to distrolocs root
VERIFY_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts" / "verify"

VERIFICATION_SCRIPTS = {
    "github": {
        "ssh": "verify_github_ssh.sh",
        "token": "verify_github_token.sh",  # future
    },
    "forgejo": {
        "token": "verify_forgejo_token.sh",
        "ssh": "verify_forgejo_ssh.sh",  # future
    },
    "gitlab": {
        "token": "verify_gitlab_token.sh",
        "ssh": "verify_gitlab_ssh.sh",  # future
    },
}


class CloneError(Exception):
    """Raised when repository cloning fails."""

    pass


def _detect_source_type(url: str) -> str:
    """Detect the source type (github, gitlab, or forgejo) from a URL.

    Args:
        url: The URL to analyze.

    Returns:
        The source type: "github", "gitlab", or "forgejo".
    """
    url_lower = url.lower()

    if "github.com" in url_lower:
        return "github"
    elif "gitlab" in url_lower or "git.hmg" in url_lower:
        return "gitlab"
    else:
        return "forgejo"


def check_auth_verification(source: GitSource) -> tuple[bool, str]:
    """Check if a verification script exists for a git source.

    Args:
        source: The GitSource to check.

    Returns:
        Tuple of (has_verification, message).
    """
    # Determine the source type from URL
    source_type = _detect_source_type(source.list_repos_url)

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
    cprint("info", "\n[yellow]Checking auth verification for git sources...[/yellow]")

    has_warnings = False
    for source in sources:
        if not source.enabled:
            continue

        has_verification, message = check_auth_verification(source)

        if has_verification:
            cprint("success", f"  [green]✓[/green] {source.name}: {message}")
        else:
            cprint("warning", f"  [yellow]![/yellow] {source.name}: {message}")
            has_warnings = True

    if has_warnings:
        cprint(
            "warning",
            "\n[yellow]Warning: Some git sources don't have auth verification scripts.[/yellow]\n"
            "This means authentication can't be automatically verified before cloning.\n"
            "Consider adding verification scripts to scripts/verify/",
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

    # Extract the correct hostname from the source URL to fix Forgejo's
    # tendency to return localhost-based clone URLs when queried externally
    parsed_source = urllib.parse.urlparse(source.list_repos_url)
    source_host = parsed_source.netloc

    for repo in data:
        clone_url = repo.get("clone_url", "") or repo.get("ssh_url", "")

        # Fix Forgejo returning localhost URLs when queried via network hostname
        if clone_url:
            parsed_clone = urllib.parse.urlparse(clone_url)
            if parsed_clone.hostname in ("localhost", "127.0.0.1"):
                # Substitute localhost with the actual source host
                clone_url = f"{parsed_clone.scheme}://{source_host}{parsed_clone.path}"
                if parsed_clone.query:
                    clone_url += f"?{parsed_clone.query}"

        repos.append(
            RepoInfo(
                name=repo["name"],
                clone_url=clone_url,
                full_name=repo.get("full_name", repo["name"]),
                updated_at=repo.get("updated_at"),
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
                name=repo["name"],
                clone_url=repo.get("clone_url", ""),
                full_name=repo.get("full_name", repo["name"]),
                updated_at=repo.get("updated_at"),
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
                updated_at=repo.get("updated_at"),
            )
        )

    return repos


def fetch_repos(source: GitSource) -> list[RepoInfo]:
    """Fetch repository list from a git source."""
    source_type = _detect_source_type(source.list_repos_url)

    if source_type == "github":
        return _fetch_repos_github(source)
    elif source_type == "gitlab":
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
                cprint(
                    "info",
                    f"\n[dim]⊘[/dim] [cyan]Source:[/cyan] {source.name} (excluded on {current_host})",
                )
            continue

        if not quiet:
            cprint("info", f"\n[cyan]Source:[/cyan] {source.name}")
            cprint("info", f"  Destination: {source.cloning_destination}")
            cprint("info", f"  API: {source.list_repos_url}")

        try:
            repos = fetch_repos(source)

            # Sort by updated_at descending and apply limit if set
            if source.limit_to_recent_repos > 0:
                # Filter out repos without updated_at, then sort
                repos_with_time = [r for r in repos if r.updated_at]
                repos_with_time.sort(key=lambda r: r.updated_at, reverse=True)
                repos = repos_with_time[: source.limit_to_recent_repos]
                if not quiet:
                    cprint(
                        "info",
                        f"  Found {len(repos)} most recently updated repo(s) "
                        f"(limit: {source.limit_to_recent_repos})",
                    )
            else:
                if not quiet:
                    cprint("info", f"  Found {len(repos)} repository(ies)")
        except Exception as e:
            cprint("error", f"  [red]Failed to fetch repos:[/red] {e}")
            total_failed += 1
            continue

        for repo in repos:
            if repo.name in source.exclude_repos:
                if not quiet:
                    cprint("debug", f"  [dim]⊘[/dim] {repo.name}: excluded")
                continue

            result = clone_repo(repo, source, dry_run=dry_run)
            if result.success:
                total_cloned += 1
                if not quiet:
                    cprint(
                        "success", f"  [green]✓[/green] {repo.name}: {result.message}"
                    )
                clog("info", f"Cloned {repo.name} from {source.name}")
            else:
                total_failed += 1
                cprint("error", f"  [red]✗[/red] {repo.name}: {result.message}")
                clog(
                    "error",
                    f"Failed to clone {repo.name} from {source.name}: {result.message}",
                )

    return total_cloned, total_failed
