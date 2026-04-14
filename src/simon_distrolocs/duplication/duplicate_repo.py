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


def _run_post_clone_scripts(scripts: tuple[str, ...], clone_path: Path) -> None:
    """Execute post-clone scripts in order.

    Args:
        scripts: Tuple of script paths (relative to repo root).
        clone_path: Path to the cloned repository.
    """
    for script in scripts:
        script_path = Path(script)
        if not script_path.is_absolute():
            # Resolve relative to current working directory (repo root)
            script_path = Path.cwd() / script_path

        if not script_path.exists():
            logger.warning(f"  Post-clone script not found: {script_path}")
            continue

        logger.info(f"  Running post-clone script: {script}...")
        result = subprocess.run(
            [str(script_path), str(clone_path)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            logger.warning(f"  Script '{script}' failed: {result.stderr.strip()}")
        else:
            logger.info(f"  ✓ Script '{script}' completed")


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

    # Extract host from forgejo_base for HTTP URL (including port)
    # forgejo_base is like http://192.168.56.1:3000
    forgejo_host = forgejo_base.split("://")[-1]  # Get "192.168.56.1:3000"
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
    source_clone_url = build_source_clone_url(source_url, source_type, config_dir)
    logger.debug(f"Source clone URL: {source_clone_url}")
    temp_check_dir = Path(tempfile.mkdtemp(prefix="dup_check_"))
    try:
        # Use clean environment for HTTPS GitLab URLs (token auth, no SSH needed)
        check_env = {k: v for k, v in get_git_env().items() if k != "GIT_SSH_COMMAND"}
        check_env["GIT_TERMINAL_PROMPT"] = "0"
        check_env["GIT_SSL_NO_VERIFY"] = "1"
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
            env=check_env,
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
    source_clone_url = build_source_clone_url(source_url, source_type, config_dir)

    try:
        # Use clean environment for HTTPS GitLab URLs (token auth, no SSH needed)
        clone_env = {k: v for k, v in get_git_env().items() if k != "GIT_SSH_COMMAND"}
        clone_env["GIT_TERMINAL_PROMPT"] = "0"
        clone_env["GIT_SSL_NO_VERIFY"] = "1"
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
            env=clone_env,
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
        # Get current branch name and push that
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=temp_dir,
            capture_output=True,
            text=True,
        )
        current_branch = result.stdout.strip()
        logger.info(f"  Pushing branch: {current_branch}")

        push_result = subprocess.run(
            ["git", "push", "-u", "forgejo", f"HEAD:{current_branch}"],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes - push can be slow for large repos
            env=clone_env,
        )
        if push_result.returncode != 0:
            logger.error(f"  Push failed: {push_result.stderr}")
            raise DuplicateError(f"Failed to push to Forgejo: {push_result.stderr}")
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
            # Use clean environment for local clone - no SSH override needed for HTTP
            clone_env = {
                k: v for k, v in get_git_env().items() if k != "GIT_SSH_COMMAND"
            }
            clone_env["GIT_TERMINAL_PROMPT"] = "0"
            clone_env["GIT_SSL_NO_VERIFY"] = "1"
            clone_env["GIT_SSL_CAINFO"] = ""
            logger.debug(
                f"  Clone env: GIT_SSL_NO_VERIFY={clone_env.get('GIT_SSL_NO_VERIFY')}, GIT_SSL_CAINFO={repr(clone_env.get('GIT_SSL_CAINFO'))}"
            )
            result = subprocess.run(
                ["git", "clone", "--branch", branch, forgejo_clone_url, str(dest_path)],
                capture_output=True,
                text=True,
                timeout=300,
                env=clone_env,
            )
            logger.debug(f"  Clone output: {result.stdout}")
            logger.debug(f"  Clone stderr: {result.stderr}")
            logger.debug(f"  Clone return code: {result.returncode}")

            # Execute post-clone scripts
            if post_clone_scripts:
                _run_post_clone_scripts(post_clone_scripts, dest_path)

        logger.info("✓ Duplication complete!")
        logger.info(f"  Forgejo repo: {forgejo_clone_url}")

    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
