"""
This file configures the global Rich Console instance for CI Toolkit.
"""
from pathlib import Path

import rich
from rich.console import Console

from python_ci_toolkit.environment import ci_environment_type, CiEnvironmentType

_THEME_FILE_PATH = Path(__file__).parent / "rich_theme.cfg"


def _patch_rich_console() -> Console:
    """
    Patches the global Rich Console instance for the use in the current CI environment.

    Returns:
        Patched Rich Console instance.
    """
    global_console = rich.get_console()

    if (ci_environment_type == CiEnvironmentType.BitbucketPipelines
            or ci_environment_type == CiEnvironmentType.GitHubActions):
        global_console._force_terminal = True

    return global_console


_logging_console = _patch_rich_console()
"""
Rich Console instance used for CI Toolkit's logging output.

Notes:
    This is a global instance of Rich Console, which is patched for the current CI environment.
"""
