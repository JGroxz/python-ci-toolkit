import os
from pathlib import Path

from .base import CiPlatform


class GitHubActions(CiPlatform):
    """
    Integration for GitHub Actions.
    """

    @classmethod
    def is_current(cls) -> bool:
        return bool(os.environ.get("GITHUB_WORKSPACE"))

    @classmethod
    def name(cls) -> str:
        return "GitHub Actions"

    @classmethod
    def supports_multiline_envvars(cls) -> bool:
        return False

    @classmethod
    def get_ci_project_root(cls) -> Path:
        return Path(os.environ.get("GITHUB_WORKSPACE"))
