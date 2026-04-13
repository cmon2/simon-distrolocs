#!/usr/bin/env python3
"""duplicate_repo.py - Duplicate a repository to Forgejo and clone to target locations.

This script handles the repo duplication workflow:
1. Find duplication config by name from TOML
2. Check if repo exists on Forgejo
3. Create repo on Forgejo if needed
4. Clone source repo and push to Forgejo
5. Clone the Forgejo repo to target locations

Usage:
    scripts/duplicate_repo.py <config_dir> <duplication_name> <branch>

Behaviors:
- If Forgejo repo already exists: prompts user to delete/recreate OR cancel
- If local clone already exists at target location: aborts with instruction to clean up
- Branch existence is verified before creating Forgejo repo
- Idempotent: safe to re-run after failures by cleaning up first

The script is idempotent:
- If Forgejo repo exists: offers to delete/recreate or cancel
- If local clone exists: aborts with instruction to clean up
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)

# Handle Python version compatibility
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

# Base directory for simon-distrolocs (resolved relative to this script)
SCRIPT_DIR = Path(__file__).parent.resolve()
# simon_ide/ is 3 levels up from scripts/
# scripts/ -> simon-distrolocs/ -> 06_agents_working_directory/ -> simon_ide/
SIMON_IDE_DIR = SCRIPT_DIR.parent.parent.parent


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


class DuplicateError(Exception):
    """Raised when repository duplication fails."""

    pass


def load_duplication_config(config_dir: Path, name: str):
    """Load duplication config by name from TOML.

    Args:
        config_dir: Directory containing the TOML config file.
        name: Name of the duplication to find.

    Returns:
        Tuple of (duplication dict, config_path).

    Raises:
        DuplicateError: If config or duplication not found.
    """
    # Find TOML file
    matching_files = list(config_dir.rglob("*simon-distrolocs.toml"))
    if not matching_files:
        raise DuplicateError(f"No config file found in {config_dir}")
    if len(matching_files) > 1:
        raise DuplicateError(f"Multiple config files found: {matching_files}")

    config_path = matching_files[0]

    with open(config_path, "rb") as f:
        toml_dict = tomllib.load(f)

    duplications = toml_dict.get("duplication", [])
    if isinstance(duplications, dict):
        duplications = [duplications]

    for dup in duplications:
        if dup.get("name") == name:
            return dup, config_path

    raise DuplicateError(f"Duplication '{name}' not found in config")


def get_forgejo_config(config_dir: Path | str) -> tuple[str, str, str]:
    """Get Forgejo base URL, auth token, and username from git_sources in TOML config.

    Args:
        config_dir: Directory containing the TOML config file.

    Returns:
        Tuple of (forgejo_base_url, auth_token, username).

    Raises:
        DuplicateError: If no Forgejo source found or can't get user info.
    """
    # Ensure config_dir is a Path
    if isinstance(config_dir, str):
        config_dir = Path(config_dir)

    matching_files = list(config_dir.rglob("*simon-distrolocs.toml"))
    if not matching_files:
        raise DuplicateError(f"No config file found in {config_dir}")

    config_path = matching_files[0]

    with open(config_path, "rb") as f:
        toml_dict = tomllib.load(f)

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
                    # Resolve relative to simon_ide root, not cwd
                    token_file = SIMON_IDE_DIR / token_file
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

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(req, context=context) as response:
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

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=context) as response:
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

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=context) as response:
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

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=context) as response:
            if response.status not in (204, 200):
                raise DuplicateError(f"Failed to delete repo: HTTP {response.status}")
    except urllib.error.HTTPError as e:
        raise DuplicateError(f"Failed to delete repo: {e}")


def duplicate_repository(
    source_url: str,
    source_type: str,
    forgejo_target: str,
    branch: str,
    clone_locations: list[str],
    config_dir: Path,
) -> None:
    """Duplicate a repository to Forgejo and clone to target locations.

    Args:
        source_url: Git URL of source repository.
        source_type: Type of source (gitlab, github, forgejo) for auth lookup.
        forgejo_target: Base name for Forgejo repo (e.g., "pgxperts-prim").
        branch: Branch to duplicate.
        clone_locations: List of paths to clone the Forgejo repo to.
        config_dir: Directory containing the TOML config file.
    """
    # Get Forgejo config from TOML (don't filter by excluded_on_hosts)
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

    print(f"\n=== Duplicating Repository ===")
    print(f"  Source: {source_url}")
    print(f"  Branch: {branch}")
    print(f"  Forgejo target: {forgejo_repo_name}")
    print(f"  Forgejo API: {forgejo_api}")
    print()

    # Verify branch exists in source repo before proceeding
    print(f"Checking if branch '{branch}' exists in source repo...")
    source_clone_url = _build_source_clone_url(source_url, source_type, config_dir)
    logging.debug(f"Source clone URL: {source_clone_url}")
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
        logging.debug(f"Clone stdout: {result.stdout}")
        logging.debug(f"Clone stderr: {result.stderr}")
        logging.debug(f"Clone return code: {result.returncode}")
        if not (temp_check_dir / ".git").exists():
            print(f"[RED]Branch '{branch}' does not exist in source repository.[/RED]")
            print("Please verify the branch name and try again.")
            shutil.rmtree(temp_check_dir, ignore_errors=True)
            sys.exit(1)
        print(f"  ✓ Branch '{branch}' exists")
    except subprocess.CalledProcessError:
        print(f"[RED]Branch '{branch}' does not exist in source repository.[/RED]")
        print("Please verify the branch name and try again.")
        shutil.rmtree(temp_check_dir, ignore_errors=True)
        sys.exit(1)
    finally:
        shutil.rmtree(temp_check_dir, ignore_errors=True)

    # Check if repo exists on Forgejo
    exists = check_repo_exists_on_forgejo(forgejo_api, forgejo_repo_name, token)

    if exists:
        print(
            f"[YELLOW]Repository already exists on Forgejo: {forgejo_repo_name}[/YELLOW]"
        )
        print()
        print("Options:")
        print(
            "  1. Delete and recreate (WARNING: this will delete ALL data in the repo)"
        )
        print("  2. Cancel duplication")
        print()
        choice = input("Enter choice (1 or 2): ").strip()

        if choice == "1":
            print(f"\nDeleting existing repository {forgejo_repo_name}...")
            delete_repo_on_forgejo(forgejo_api, forgejo_repo_name, token)
            print("Creating new repository...")
            create_repo_on_forgejo(forgejo_api, forgejo_repo_name, token)
        else:
            print("Cancelled.")
            sys.exit(0)
    else:
        print(f"Creating repository {forgejo_repo_name} on Forgejo...")
        create_repo_on_forgejo(forgejo_api, forgejo_repo_name, token)

    # Clone source repo to temp directory
    print(f"\nCloning source repository...")
    temp_dir = Path(tempfile.mkdtemp(prefix="dup_"))
    source_clone_url = _build_source_clone_url(source_url, source_type, config_dir)

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
        print(f"  Cloned to {temp_dir}")

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
        print(f"\nPushing to Forgejo...")
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
        print(f"  Pushed to {forgejo_clone_url}")

        # Now clone from Forgejo to target locations
        print(f"\nCloning to target locations...")
        for location in clone_locations:
            dest_path = Path(location).expanduser() / f"{forgejo_target}-{branch}"

            if dest_path.exists():
                print(f"[RED]Local clone already exists at {dest_path}[/RED]")
                print("Please clean up and delete the local clone first, then retry.")
                print()
                print("Aborting.")
                sys.exit(1)

            print(f"  Cloning to {dest_path}...")
            subprocess.run(
                ["git", "clone", forgejo_clone_url, str(dest_path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
                env=_get_git_env(),
            )
            print(f"  ✓ Cloned successfully")

        print(f"\n[GREEN]✓ Duplication complete![/GREEN]")
        print(f"  Forgejo repo: {forgejo_clone_url}")

    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def _build_source_clone_url(source_url: str, source_type: str, config_dir: Path) -> str:
    """Build clone URL with credentials embedded if needed.

    Args:
        source_url: The source git URL.
        source_type: Type of source (gitlab, github, forgejo) for auth lookup.
        config_dir: Directory containing the TOML config file.

    Returns:
        Clone URL with credentials if needed.
    """
    # For GitLab sources, we need to embed the token
    if source_type.lower() == "gitlab":
        # Get GitLab token
        matching_files = list(config_dir.rglob("*simon-distrolocs.toml"))
        if matching_files:
            with open(matching_files[0], "rb") as f:
                toml_dict = tomllib.load(f)

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
                            token_file = SIMON_IDE_DIR / token_file
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


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 = success, non-zero = error).
    """
    parser = argparse.ArgumentParser(
        description="Duplicate a repository to Forgejo and clone to target locations.",
    )
    parser.add_argument(
        "config_dir",
        type=Path,
        help="Directory containing simon-distrolocs.toml config",
    )
    parser.add_argument(
        "name",
        help="Name of the duplication from TOML config",
    )
    parser.add_argument(
        "branch",
        help="Branch to duplicate",
    )

    args = parser.parse_args()

    try:
        dup_config, config_path = load_duplication_config(args.config_dir, args.name)
        config_dir = config_path.parent

        source_type = dup_config.get("source_type")
        source_url = dup_config.get("source_url")
        forgejo_target = dup_config.get("forgejo_target")
        clone_locations = dup_config.get("target_clone_locations", [])

        if not source_type:
            raise DuplicateError("source_type not specified in duplication config")
        if not source_url:
            raise DuplicateError("source_url not specified in duplication config")
        if not forgejo_target:
            raise DuplicateError("forgejo_target not specified in duplication config")
        if not clone_locations:
            raise DuplicateError(
                "target_clone_locations not specified in duplication config"
            )

        duplicate_repository(
            source_url=source_url,
            source_type=source_type,
            forgejo_target=forgejo_target,
            branch=args.branch,
            clone_locations=clone_locations,
            config_dir=config_dir,
        )
        return 0

    except DuplicateError as e:
        print(f"[RED]Error: {e}[/RED]", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[RED]Unexpected error: {e}[/RED]", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
