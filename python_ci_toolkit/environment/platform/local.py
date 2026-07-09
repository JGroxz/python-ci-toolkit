import logging
import os
from pathlib import Path

from rich.console import Console
from rich.theme import Theme

from .base import CiPlatform
from ...shell import probe_shell_command_runner

logger = logging.getLogger(__name__)


class Local(CiPlatform):
    """
    Integration for local environment.
    """

    @classmethod
    def is_current(cls) -> bool:
        return True  # <- local environment is always local

    @classmethod
    def name(cls) -> str:
        return "Local / Unknown"

    @classmethod
    def supports_multiline_envvars(cls) -> bool:
        return True

    @classmethod
    def get_ci_project_root(cls) -> Path:
        # general case: find the root of the enclosing Git repository
        result = probe_shell_command_runner(
            "git rev-parse --show-toplevel",
            cwd=os.getcwd(),
        )

        if result.is_successful:
            git_repo_root = result.output_stripped
            return Path(git_repo_root)

        # other case: we are not inside a Git repo, so the root cannot be reliably determined
        logger.debug(f"Could not determine project's root directory: not a Git repo.\n"
                     f"  CI environment: '{cls.name()}'\n"
                     f"  CWD: '{os.getcwd()}'\n"
                     f"Assuming current working directory as the current CI project's root.")
        return Path(os.getcwd())

    @classmethod
    def on_patch_rich_console(cls, console: Console, default_theme: Theme) -> Console:
        # for local console output we respect the user's terminal width, if any
        terminal_width = int(os.getenv("TERMINAL_WIDTH")) if os.getenv("TERMINAL_WIDTH") else None

        return Console(
            theme=default_theme,
            width=terminal_width
        )
