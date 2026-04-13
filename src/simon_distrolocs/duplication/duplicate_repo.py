"""Repository duplication orchestration."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..auth_verification import verify_forgejo_token
from ..git_helpers import build_source_clone_url, get_git_env
from ..parsing import DuplicateError
from .forgejo_api import check_repo_exists, create_repo, get_forgejo_username

logger = logging.getLogger(__name__)


def duplicate_repository(
    source_url: str,
    source_type: str,
    forgejo_target: str,
    branch: str,
    clone_locations: tuple[str, ...],
    config_dir: Path,
) -> None:
    """Duplicate a repository to Forgejo and clone to target locations.

    Args:
        source_url: Git URL of source repository.
        source_type: Type of source (gitlab, github, forgejo) for auth lookup.
        forgejo_target: Base name for Forgejo repo (e.g., "pgxperts-prim").
        branch: Branch to duplicate.
        clone_locations: Tuple of paths to clone the Forgejo repo to.
        config_dir: Directory containing the TOML config file.

    Raises:
        DuplicateError: If duplication fails.
    """
    # Import here to avoid circular dependency
    from .get_forgejo_config import get_forgejo_config

    # Get Forgejo config from TOML
    forgejo_base, token = get_forgejo_config(config_dir)
    forgejo_api = f"{forgejo_base}/api/v1"

    # Verify Forgejo authentication before proceeding
    logger.info("Verifying Forgejo authentication...")
    success, message = verify_forgejo_token(forgejo_base)
    if success:
        logger.info(f"  ✓ {message}")
    else:
        raise DuplicateError(f"Forgejo authentication failed: {message}")

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
    source_clone_url = build_source_clone_url(source_url, source_type)
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
            env=get_git_env(),
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
    exists = check_repo_exists(forgejo_api, forgejo_repo_name, token)

    if exists:
        logger.warning(f"Repository already exists on Forgejo: {forgejo_repo_name}")
        raise DuplicateError(
            f"Repository already exists on Forgejo: {forgejo_repo_name}. "
            "Please delete it manually and try again."
        )
    else:
        logger.info(f"Creating repository {forgejo_repo_name} on Forgejo...")
        create_repo(forgejo_api, forgejo_repo_name, token)

    # Clone source repo to temp directory
    logger.info("Cloning source repository...")
    temp_dir = Path(tempfile.mkdtemp(prefix="dup_"))
    source_clone_url = build_source_clone_url(source_url, source_type)

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
            env=get_git_env(),
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
                env=get_git_env(),
            )
            logger.info(f"  ✓ Cloned successfully")

        logger.info("✓ Duplication complete!")
        logger.info(f"  Forgejo repo: {forgejo_clone_url}")

    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
