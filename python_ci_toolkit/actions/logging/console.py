"""
This file configures the global Rich Console instance for CI Toolkit.
"""
from pathlib import Path

import rich
from rich.console import Console
from rich.theme import Theme

from ...environment import ci_platform, platforms

_CI_TOOLKIT_RICH_THEME_FILE_PATH = Path(__file__).parent / "styles.cfg"
CI_TOOLKIT_RICH_THEME = Theme.read(path=str(_CI_TOOLKIT_RICH_THEME_FILE_PATH))


def _patch_rich_console() -> Console:
    """
    Patches the global Rich Console instance for the use on the current CI platform.

    Returns:
        Patched Rich Console instance.
    """
    # patch global Rich Console instance
    console = Console(theme=CI_TOOLKIT_RICH_THEME)
    console = ci_platform.on_patch_rich_console(console, CI_TOOLKIT_RICH_THEME)
    assert console is not None, f"CI platform's {ci_platform.on_patch_rich_console.__name__}() callback must return the Rich Console instance."
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
