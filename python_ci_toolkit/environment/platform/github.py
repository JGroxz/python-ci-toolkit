import os
from pathlib import Path

from rich.console import Console
from rich.theme import Theme

from .base import CiPlatform
from ...shell import run_shell_command


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
        ci_project_root = Path(os.getenv("GITHUB_WORKSPACE"))

        # GitHub Actions workspace directory belongs to a different user out-of-the-box,
        # so we have to mark it as safe to be able to run all git commands without errors.
        # See for more info: https://github.com/python-semantic-release/python-semantic-release/issues/560
        run_shell_command(f'git config --global --add safe.directory "{ci_project_root}"', silence_output=True, use_wsl_on_windows=False)

        return ci_project_root

    @classmethod
    def on_patch_rich_console(cls, console: Console, default_theme: Theme) -> Console:
        return Console(
            theme=default_theme,

            # GitHub Actions console nicely wraps long lines, so we don't need to limit the width here
            width=None,

            # GitHub Actions console supports colors, but we have to force terminal for Rich to output them there
            force_terminal=True
        )
