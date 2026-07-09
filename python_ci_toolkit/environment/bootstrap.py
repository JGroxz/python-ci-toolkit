"""
Explicit runtime preparation for the current CI project.

This module applies provider-specific compatibility steps before toolkit code
starts touching project Git state or action repositories. Platform adapters
report environment facts; this bootstrap decides which preparation steps are
needed for the current project runtime.
"""

from pathlib import Path

from .paths import ci_paths
from .platform import GitHubActions, ci_platform
from ..git.repo import add_git_safe_directory

_prepared_project_roots: set[tuple[type, Path]] = set()


def prepare_ci_project_runtime() -> None:
    project_root = ci_paths.project_root
    preparation_key = (ci_platform, project_root)
    if preparation_key in _prepared_project_roots:
        return

    if ci_platform is GitHubActions:
        # GitHub Actions can mount the workspace with ownership Git considers
        # unsafe, so mark it before any project Git operation runs.
        add_git_safe_directory(project_root)

    _prepared_project_roots.add(preparation_key)
