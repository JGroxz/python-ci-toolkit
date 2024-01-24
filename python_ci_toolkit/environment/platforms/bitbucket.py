import os
from pathlib import Path

from rich.console import Console
from rich.theme import Theme

from .base import CiPlatform


class BitbucketPipelines(CiPlatform):
    """
    Integration for Bitbucket Pipelines.
    """

    @classmethod
    def is_current(cls) -> bool:
        return bool(os.environ.get("BITBUCKET_PIPELINE_UUID"))

    @classmethod
    def name(cls) -> str:
        return "Bitbucket Pipelines"

    @classmethod
    def supports_multiline_envvars(cls) -> bool:
        return False

    @classmethod
    def get_ci_project_root(cls) -> Path:
        return Path(os.environ.get("BITBUCKET_CLONE_DIR"))

    @classmethod
    def on_patch_rich_console(cls, console: Console, default_theme: Theme) -> Console:
        return Console(
            theme=default_theme,

            # Bitbucket Pipelines console does not wrap long lines, so we limit the width here to make output more readable
            width=80,

            # Bitbucket Pipelines console supports colors, but we have to force terminal for Rich to output them there
            force_terminal=True
        )
