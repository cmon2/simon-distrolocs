"""Git repository cloning for Simon DistroLocs.

This module handles discovering and cloning repositories from configured
git sources (Forgejo, GitHub, GitLab).
"""

from __future__ import annotations

import json
import ssl
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .types import AuthType, GitSource, RepoInfo


class CloneError(Exception):
    """Raised when repository cloning fails."""

    pass


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
                name=repo["path"],
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
    total_cloned = 0
    total_failed = 0

    for source in sources:
        if not source.enabled:
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
            if repo.name in source.exclude:
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
