import logging
import os
from pathlib import Path

from .base import CiPlatform
from ...shell import run_shell_command

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
        result = run_shell_command("git rev-parse --show-toplevel", use_wsl_on_windows=False,
                                   raise_on_error=False, silence_output=True,
                                   cwd=os.getcwd())

        if result.is_successful:
            git_repo_root = result.output_stripped
            return Path(git_repo_root)

        # other case: we are not inside a Git repo, so the root cannot be reliably determined
        logger.debug(f"Could not determine project's root directory: not a Git repo.\n"
                     f"  CI environment: '{cls.name()}'\n"
                     f"  CWD: '{os.getcwd()}'\n"
                     f"Assuming current working directory as the current CI project's root.")
        return Path(os.getcwd())
