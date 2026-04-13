"""Forgejo API client for repository duplication."""

from __future__ import annotations

import json
import logging
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from cmon2lib import cprint, clog

from .parsing import DuplicateError

logger = logging.getLogger(__name__)


def _get_git_env() -> dict:
    """Get environment dict with SSH command for Git operations.

    Uses ~/.ssh/config to resolve hostnames like 'git.hmg' which are
    defined in SSH config, not DNS.
    """
    ssh_config_path = Path.home() / ".ssh" / "config"
    return {
        **os.environ,
        "GIT_SSH_COMMAND": f"ssh -F {ssh_config_path} -o PreferredAuthentications=publickey",
    }


def _get_simon_ide_dir() -> Path:
    """Get the simon_ide directory path.

    The simon-distrolocs project is located at:
    simon_ide/06_agents_working_directory/simon-distrolocs/

    So we go up 3 levels from this file (src/simon_distrolocs/forgejo_client.py).

    Returns:
        Path to the simon_ide directory.
    """
    # This file is at src/simon_distrolocs/forgejo_client.py
    # Go up: forgejo_client.py -> simon_distrolocs/ -> src/ -> project root
    return Path(__file__).resolve().parent.parent.parent.parent


def _get_ssl_context() -> ssl.SSLContext:
    """Get SSL context that doesn't verify certificates (for self-signed Forgejo)."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def get_forgejo_config(config_dir: Path) -> tuple[str, str]:
    """Get Forgejo base URL and auth token from git_sources in TOML config.

    Args:
        config_dir: Directory containing the TOML config file.

    Returns:
        Tuple of (forgejo_base_url, auth_token).

    Raises:
        DuplicateError: If no Forgejo source found or can't read token.
    """
    from .config import find_config_file, parse_toml_config

    config_path = find_config_file(config_dir)
    toml_dict = parse_toml_config(config_path)

    git_sources = toml_dict.get("git_sources", [])
    if isinstance(git_sources, dict):
        git_sources = [git_sources]

    for source in git_sources:
        source_name = source.get("name", "")
        source_url = source.get("list_repos_url", "")
        # Match by name containing "forgejo" (case insensitive)
        is_forgejo = "forgejo" in source_name.lower()

        if is_forgejo:
            # Extract base URL from API URL (e.g., http://172.30.32.1:3000)
            # list_repos_url is like http://172.30.32.1:3000/api/v1/users/simon/repos
            if "/api/v1/" in source_url:
                base_url = source_url.split("/api/v1/")[0]
            else:
                base_url = source_url

            auth_token_path = source.get("auth_token_path", "")
            if auth_token_path:
                token_file = Path(auth_token_path)
                if not token_file.is_absolute():
                    # Resolve relative to cwd (repo root)
                    token_file = Path.cwd() / token_file
                if token_file.exists():
                    with open(token_file) as f:
                        token = f.read().strip()
                    # Handle URL format tokens
                    if "@" in token and "://" in token:
                        parts = token.split("@")[0]
                        if ":" in parts:
                            token = parts.rsplit(":", 1)[1]
                    return base_url, token

    raise DuplicateError("No Forgejo source found in git_sources config")


def get_forgejo_username(forgejo_api: str, token: str) -> str:
    """Get the authenticated username from Forgejo.

    Args:
        forgejo_api: The Forgejo API base URL.
        token: Forgejo authentication token.

    Returns:
        The username of the authenticated user.
    """
    url = f"{forgejo_api}/user"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, context=_get_ssl_context()) as response:
        data = json.loads(response.read().decode())
        return data["login"]


def check_repo_exists_on_forgejo(forgejo_api: str, repo_name: str, token: str) -> bool:
    """Check if repository exists on Forgejo.

    Args:
        forgejo_api: The Forgejo API base URL.
        repo_name: Full repo name (e.g., "simon_ide/pgxperts-prim-develop").
        token: Forgejo authentication token.

    Returns:
        True if repo exists, False otherwise.
    """
    url = f"{forgejo_api}/repos/{repo_name}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, context=_get_ssl_context()) as response:
            return response.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise DuplicateError(f"Failed to check repo existence: {e}")


def create_repo_on_forgejo(forgejo_api: str, repo_name: str, token: str) -> None:
    """Create a repository on Forgejo.

    Args:
        forgejo_api: The Forgejo API base URL.
        repo_name: Full repo name (e.g., "simon_ide/pgxperts-prim-develop").
        token: Forgejo authentication token.

    Raises:
        DuplicateError: If creation fails.
    """
    # Split namespace and repo name
    parts = repo_name.split("/")
    if len(parts) != 2:
        raise DuplicateError(f"Invalid repo name format: {repo_name}")
    repo = parts[1]  # Only need repo name for creation under authenticated user

    # Forgejo uses POST /api/v1/user/repos to create a repo under the authenticated user
    url = f"{forgejo_api}/user/repos"

    payload = json.dumps(
        {
            "name": repo,
            "private": True,
        }
    ).encode()

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, context=_get_ssl_context()) as response:
            if response.status not in (201, 200):
                raise DuplicateError(f"Failed to create repo: HTTP {response.status}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        raise DuplicateError(f"Failed to create repo: {e}\n{error_body}")


def delete_repo_on_forgejo(forgejo_api: str, repo_name: str, token: str) -> None:
    """Delete a repository on Forgejo.

    Args:
        forgejo_api: The Forgejo API base URL.
        repo_name: Full repo name (e.g., "simon_ide/pgxperts-prim-develop").
        token: Forgejo authentication token.

    Raises:
        DuplicateError: If deletion fails.
    """
    url = f"{forgejo_api}/repos/{repo_name}"

    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, context=_get_ssl_context()) as response:
            if response.status not in (204, 200):
                raise DuplicateError(f"Failed to delete repo: HTTP {response.status}")
    except urllib.error.HTTPError as e:
        raise DuplicateError(f"Failed to delete repo: {e}")


def _build_source_clone_url(source_url: str, source_type: str) -> str:
    """Build clone URL with credentials embedded if needed.

    Args:
        source_url: The source git URL.
        source_type: Type of source (gitlab, github, forgejo).

    Returns:
        Clone URL with credentials if needed.
    """
    from .config import find_config_file, parse_toml_config

    # For GitLab sources, we need to embed the token
    if source_type.lower() == "gitlab":
        # Try to find config in current directory
        try:
            config_path = find_config_file(Path.cwd())
            config_dir = config_path.parent
        except Exception:
            return source_url

        try:
            toml_dict = parse_toml_config(config_path)
        except Exception:
            return source_url

        git_sources = toml_dict.get("git_sources", [])
        if isinstance(git_sources, dict):
            git_sources = [git_sources]

        for source in git_sources:
            source_name = source.get("name", "").lower()
            if "gitlab" in source_name or "git.hmg" in source_name:
                auth_token_path = source.get("auth_token_path", "")
                if auth_token_path:
                    token_file = Path(auth_token_path)
                    if not token_file.is_absolute():
                        token_file = Path.cwd() / token_file
                    if token_file.exists():
                        with open(token_file) as f:
                            token = f.read().strip()
                        # Handle URL format tokens
                        if "@" in token and "://" in token:
                            parts = token.split("@")[0]
                            if ":" in parts:
                                token = parts.rsplit(":", 1)[1]

                        if source_url.startswith("https://"):
                            parts = source_url.split("://", 1)
                            return f"{parts[0]}://oauth2:{token}@{parts[1]}"

        return source_url

    return source_url


def duplicate_repository(
    source_url: str,
    source_type: str,
    forgejo_target: str,
    branch: str,
    clone_locations: tuple[str, ...],
    config_dir: Path,
    post_clone_scripts: tuple[str, ...] = (),
) -> None:
    """Duplicate a repository to Forgejo and clone to target locations.

    Args:
        source_url: Git URL of source repository.
        source_type: Type of source (gitlab, github, forgejo) for auth lookup.
        forgejo_target: Base name for Forgejo repo (e.g., "pgxperts-prim").
        branch: Branch to duplicate.
        clone_locations: Tuple of paths to clone the Forgejo repo to.
        config_dir: Directory containing the TOML config file.
        post_clone_scripts: Tuple of script paths to execute after cloning.

    Raises:
        DuplicateError: If duplication fails.
    """
    # Get Forgejo config from TOML
    forgejo_base, token = get_forgejo_config(config_dir)
    forgejo_api = f"{forgejo_base}/api/v1"

    # Get authenticated username for namespace
    username = get_forgejo_username(forgejo_api, token)

    # Build full Forgejo repo name
    forgejo_repo_name = f"{username}/{forgejo_target}-{branch}"

    # Extract host from forgejo_base for HTTP URL (HTTPS doesn't work for git operations)
    forgejo_host = forgejo_base.split("://")[-1].split(":")[0]
    # Forgejo uses token auth via HTTP, not SSH
    forgejo_clone_url = (
        f"http://simon:{token}@{forgejo_host}/simon/{forgejo_target}-{branch}.git"
    )

    logger.info("=== Duplicating Repository ===")
    logger.info(f"  Source: {source_url}")
    logger.info(f"  Branch: {branch}")
    logger.info(f"  Forgejo target: {forgejo_repo_name}")
    logger.info(f"  Forgejo API: {forgejo_api}")

    # Verify branch exists in source repo before proceeding
    logger.info(f"Checking if branch '{branch}' exists in source repo...")
    source_clone_url = _build_source_clone_url(source_url, source_type)
    logger.debug(f"Source clone URL: {source_clone_url}")
    temp_check_dir = Path(tempfile.mkdtemp(prefix="dup_check_"))
    try:
        result = subprocess.run(
            [
                "git",
                "clone",
                "--branch",
                branch,
                "--single-branch",
                "--depth",
                "1",
                source_clone_url,
                str(temp_check_dir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env=_get_git_env(),
        )
        logger.debug(f"Clone stdout: {result.stdout}")
        logger.debug(f"Clone stderr: {result.stderr}")
        logger.debug(f"Clone return code: {result.returncode}")
        if not (temp_check_dir / ".git").exists():
            raise DuplicateError(
                f"Branch '{branch}' does not exist in source repository."
            )
        logger.info(f"  ✓ Branch '{branch}' exists")
    except subprocess.CalledProcessError as e:
        raise DuplicateError(
            f"Branch '{branch}' does not exist in source repository."
        ) from e
    finally:
        shutil.rmtree(temp_check_dir, ignore_errors=True)

    # Check if repo exists on Forgejo
    exists = check_repo_exists_on_forgejo(forgejo_api, forgejo_repo_name, token)

    if exists:
        logger.warning(f"Repository already exists on Forgejo: {forgejo_repo_name}")
        raise DuplicateError(
            f"Repository already exists on Forgejo: {forgejo_repo_name}. "
            "Please delete it manually and try again."
        )
    else:
        logger.info(f"Creating repository {forgejo_repo_name} on Forgejo...")
        create_repo_on_forgejo(forgejo_api, forgejo_repo_name, token)

    # Clone source repo to temp directory
    logger.info("Cloning source repository...")
    temp_dir = Path(tempfile.mkdtemp(prefix="dup_"))
    source_clone_url = _build_source_clone_url(source_url, source_type)

    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--branch",
                branch,
                "--single-branch",
                source_clone_url,
                str(temp_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
            env=_get_git_env(),
        )
        logger.info(f"  Cloned to {temp_dir}")

        # Configure git user if not set
        subprocess.run(
            ["git", "config", "user.email", "simon@hmg.local"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Simon"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )

        # Add Forgejo as remote and push
        logger.info("Pushing to Forgejo...")
        subprocess.run(
            ["git", "remote", "add", "forgejo", forgejo_clone_url],
            cwd=temp_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "push", "-u", "forgejo", "HEAD:master"],
            cwd=temp_dir,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes - push can be slow for large repos
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        logger.info(f"  Pushed to {forgejo_clone_url}")

        # Now clone from Forgejo to target locations
        logger.info("Cloning to target locations...")
        for location in clone_locations:
            dest_path = Path(location).expanduser() / f"{forgejo_target}-{branch}"

            if dest_path.exists():
                raise DuplicateError(
                    f"Local clone already exists at {dest_path}. "
                    "Please clean up and delete the local clone first."
                )

            logger.info(f"  Cloning to {dest_path}...")
            subprocess.run(
                ["git", "clone", forgejo_clone_url, str(dest_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
                env=_get_git_env(),
            )
            logger.info(f"  ✓ Cloned successfully")

            # Run post-clone scripts if configured
            if post_clone_scripts:
                cprint(
                    "info",
                    f"\n[cyan]Running post-clone scripts for {dest_path}...[/cyan]",
                )
                for script_path_str in post_clone_scripts:
                    script_path = _get_simon_ide_dir() / script_path_str
                    if not script_path.exists():
                        cprint(
                            "warning",
                            f"  [yellow]![/yellow] Script not found: {script_path}",
                        )
                        continue

                    cprint("info", f"  [cyan]Running {script_path.name}...[/cyan]")
                    try:
                        result = subprocess.run(
                            [str(script_path), str(dest_path)],
                            check=True,
                            capture_output=True,
                            text=True,
                            timeout=300,
                        )
                        if result.stdout:
                            clog("debug", result.stdout)
                        cprint(
                            "success",
                            f"  [green]✓[/green] {script_path.name} completed",
                        )
                    except subprocess.CalledProcessError as e:
                        cprint(
                            "error",
                            f"  [red]✗[/red] {script_path.name} failed: {e.stderr}",
                        )
                        clog(
                            "error",
                            f"Post-clone script failed: {script_path} - {e.stderr}",
                        )

        logger.info("✓ Duplication complete!")
        logger.info(f"  Forgejo repo: {forgejo_clone_url}")

    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
