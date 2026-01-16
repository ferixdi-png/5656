"""
Git integration for auto-commit functionality (Batch 48).

Used by FileStorage to persist balance changes to GitHub.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


async def git_add_commit_push(file_path: Union[str, Path], commit_message: str) -> bool:
    """
    Add, commit, and push a file to GitHub.
    
    Args:
        file_path: Path to file to commit
        commit_message: Commit message
    
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path = Path(file_path)
        
        # Check if git is available
        git_check = await asyncio.create_subprocess_exec(
            "git", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await git_check.communicate()
        
        if git_check.returncode != 0:
            logger.warning("[GIT] Git not available - skipping auto-commit")
            return False
        
        # Add file
        add_proc = await asyncio.create_subprocess_exec(
            "git", "add", str(file_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await add_proc.communicate()
        
        if add_proc.returncode != 0:
            logger.warning(f"[GIT] Failed to add {file_path}")
            return False
        
        # Commit
        commit_proc = await asyncio.create_subprocess_exec(
            "git", "commit", "-m", commit_message,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await commit_proc.communicate()
        
        if commit_proc.returncode != 0:
            stderr_str = stderr.decode() if stderr else ""
            # "nothing to commit" is not an error
            if "nothing to commit" in stderr_str or "nothing added to commit" in stderr_str:
                logger.debug(f"[GIT] Nothing to commit for {file_path}")
                return True
            logger.warning(f"[GIT] Failed to commit {file_path}: {stderr_str}")
            return False
        
        # Push (fire and forget - don't wait)
        push_proc = await asyncio.create_subprocess_exec(
            "git", "push", "origin", "main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Don't wait for push to complete (async background push)
        asyncio.create_task(_wait_push(push_proc, file_path))
        
        logger.info(f"[GIT] ✅ Committed and pushing: {file_path.name}")
        return True
    
    except Exception as e:
        logger.error(f"[GIT] Error in git_add_commit_push: {e}")
        return False


async def _wait_push(proc, file_path):
    """Wait for push to complete in background."""
    try:
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            logger.info(f"[GIT] ✅ Pushed: {file_path.name}")
        else:
            stderr_str = stderr.decode() if stderr else ""
            logger.warning(f"[GIT] Push failed for {file_path.name}: {stderr_str}")
    except Exception as e:
        logger.error(f"[GIT] Error waiting for push: {e}")


async def git_pull() -> bool:
    """
    Pull latest changes from GitHub.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        pull_proc = await asyncio.create_subprocess_exec(
            "git", "pull", "origin", "main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await pull_proc.communicate()
        
        if pull_proc.returncode != 0:
            stderr_str = stderr.decode() if stderr else ""
            logger.warning(f"[GIT] Pull failed: {stderr_str}")
            return False
        
        logger.info("[GIT] ✅ Pulled latest changes from GitHub")
        return True
    
    except Exception as e:
        # BATCH 48.31: Git not available - log as DEBUG, not ERROR
        logger.debug(f"[GIT] Git pull not available (expected in Docker): {e}")
        return False


def is_git_configured() -> bool:
    """
    Check if git is configured (name, email set).
    
    Returns:
        True if configured, False otherwise
    """
    try:
        import subprocess
        
        # Check user.name
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            return False
        
        # Check user.email
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            return False
        
        return True
    
    except Exception:
        return False


def configure_git_for_render():
    """
    Configure git for Render environment (auto-commit bot).
    
    Sets user.name and user.email if not already set.
    """
    try:
        import subprocess
        
        if is_git_configured():
            logger.info("[GIT] Git already configured")
            return
        
        # Set user.name
        subprocess.run(
            ["git", "config", "user.name", "Render Bot"],
            check=False,
            timeout=5
        )
        
        # Set user.email
        subprocess.run(
            ["git", "config", "user.email", "bot@render.com"],
            check=False,
            timeout=5
        )
        
        logger.info("[GIT] ✅ Git configured for Render auto-commit")
    
    except Exception as e:
        # BATCH 48.31: Git not available in Docker - log as DEBUG, not ERROR
        logger.debug(f"[GIT] Git not available (expected in Docker): {e}")

