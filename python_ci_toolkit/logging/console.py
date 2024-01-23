"""
This file configures the global Rich Console instance for CI Toolkit.
"""
from os import getenv
from pathlib import Path

import rich
from rich.console import Console
from rich.theme import Theme

from ..environment import ci_platform
from ..environment.platforms import Local

_CI_TOOLKIT_RICH_THEME_FILE_PATH = Path(__file__).parent / "styles.cfg"
CI_TOOLKIT_RICH_THEME = Theme.read(path=str(_CI_TOOLKIT_RICH_THEME_FILE_PATH))
MAX_WIDTH = int(getenv("TERMINAL_WIDTH")) if getenv("TERMINAL_WIDTH") else None  # type: ignore


def _patch_rich_console() -> Console:
    """
    Patches the global Rich Console instance for the use in the current CI environment.

    Returns:
        Patched Rich Console instance.
    """

    # force terminal in cloud CI environments
    force_terminal = True if (ci_platform != Local) else None

    # patch global Rich Console instance
    console = Console(
        theme=CI_TOOLKIT_RICH_THEME,
        width=MAX_WIDTH,
        force_terminal=force_terminal
    )
    rich._console = console

    return console


_logging_console = _patch_rich_console()
"""
Rich Console instance used for CI Toolkit's logging output.

Notes:
    This is a global instance of Rich Console, which is patched for the current CI environment.
"""


def _patch_rich_click_console() -> None:
    """
    Patches rich_click library to use the global Rich Console instance for logging.
    """
    from rich_click import rich_click

    def get_rich_console_for_click() -> Console:
        _logging_console.highlighter = rich_click.highlighter
        _logging_console.width = 80
        return _logging_console

    rich_click._get_rich_console = get_rich_console_for_click


_patch_rich_click_console()
