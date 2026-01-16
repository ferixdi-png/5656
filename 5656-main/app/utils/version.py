"""
Version detection utility - safely gets app version from git or build ID.

CRITICAL: Never expose secrets (tokens, passwords, etc.) in version strings.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_git_sha(project_root: Optional[Path] = None) -> Optional[str]:
    """
    Get current git commit SHA (short, 7 chars).
    
    Returns None if git is not available or not in a git repo.
    Safe: only returns commit hash, no secrets.
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    
    try:
        # Try to get git SHA
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False
        )
        
        if result.returncode == 0 and result.stdout:
            sha = result.stdout.strip()
            # Validate: should be 7 hex chars
            if len(sha) == 7 and all(c in '0123456789abcdef' for c in sha.lower()):
                return sha
        
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
        logger.debug(f"Could not get git SHA: {e}")
    
    return None


def get_build_id() -> Optional[str]:
    """
    Get build ID from environment variable (e.g., Render BUILD_ID).
    
    Returns None if not set.
    Safe: only reads from env, no secrets.
    """
    # Render.com provides BUILD_ID
    build_id = os.getenv("BUILD_ID")
    if build_id:
        return build_id
    
    # GitHub Actions provides GITHUB_SHA
    github_sha = os.getenv("GITHUB_SHA")
    if github_sha:
        # Return short version (7 chars)
        return github_sha[:7] if len(github_sha) >= 7 else github_sha
    
    # Generic CI/CD
    ci_commit_sha = os.getenv("CI_COMMIT_SHA")  # GitLab
    if ci_commit_sha:
        return ci_commit_sha[:7] if len(ci_commit_sha) >= 7 else ci_commit_sha
    
    return None


def get_app_version(project_root: Optional[Path] = None) -> str:
    """
    Get app version string (git SHA or build ID).
    
    Priority:
    1. BUILD_ID from env (Render, etc.)
    2. GITHUB_SHA from env (GitHub Actions)
    3. CI_COMMIT_SHA from env (GitLab, etc.)
    4. Git SHA from local repo
    5. "unknown" if nothing available
    
    Returns:
        Version string (7-char SHA or build ID), never contains secrets.
    """
    # Try build ID first (CI/CD)
    build_id = get_build_id()
    if build_id:
        return build_id
    
    # Try git SHA (local development)
    git_sha = get_git_sha(project_root)
    if git_sha:
        return git_sha
    
    # Fallback
    return "unknown"


def get_version_info() -> dict:
    """
    Get full version info dict (for logging/debugging).
    
    Returns:
        Dict with version, source, and other metadata (no secrets).
    """
    project_root = Path(__file__).parent.parent.parent
    
    version = get_app_version(project_root)
    
    info = {
        "version": version,
        "source": "unknown",
    }
    
    # Determine source
    if os.getenv("BUILD_ID"):
        info["source"] = "BUILD_ID"
    elif os.getenv("GITHUB_SHA"):
        info["source"] = "GITHUB_SHA"
    elif os.getenv("CI_COMMIT_SHA"):
        info["source"] = "CI_COMMIT_SHA"
    elif get_git_sha(project_root):
        info["source"] = "git"
    
    return info

