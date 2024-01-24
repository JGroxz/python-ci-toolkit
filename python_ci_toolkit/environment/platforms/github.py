import os
from pathlib import Path

from rich.console import Console
from rich.theme import Theme

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

    @classmethod
    def on_patch_rich_console(cls, console: Console, default_theme: Theme) -> Console:
        return Console(
            theme=default_theme,

            # GitHub Actions console nicely wraps long lines, so we don't need to limit the width here
            width=None,

            # GitHub Actions console supports colors, but we have to force terminal for Rich to output them there
            force_terminal=True
        )
