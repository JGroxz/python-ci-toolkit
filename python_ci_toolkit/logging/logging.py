"""
Functions for managing logging in CI environments.
"""
from __future__ import annotations

import logging
from pathlib import Path

import click
import rich
import rich.traceback
import rich_click
from rich.console import Console
from rich.logging import RichHandler

from ..environment import ci_environment_type, CiEnvironmentType

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

    # patch rich_click console
    rich_click._console = global_console

    return global_console


_logging_console = _patch_rich_console()
"""
Rich Console instance used for CI Toolkit's logging output.

Notes:
    This is a global instance of Rich Console, which is patched for the current CI environment.
"""


def configure_ci_logging(level: str | int = None) -> None:
    """
    Configures the root logger with Rich handler using the CI console.

    Notes:
        This call configures rich and logging module for the current CI environment and terminal type, be it Bitbucket pipelines or a local machine.
        This enables nicely formatted logs and detailed, well-readable tracebacks.

        After running this function, you can use logging.*() methods to get nicely formatted log messages in the output.

    Args:
        level: Level to set the root logger to.
    """
    # if no level provided, preserve root logger's level
    if level is None:
        level = logging.root.getEffectiveLevel()

    # configure tracebacks
    rich.traceback.install(console=_logging_console,
                           show_locals=False,
                           suppress=[click, rich_click, rich])

    # basicConfig in case logging has not been set up yet
    FORMAT = "%(message)s"
    logging.basicConfig(
        level=level,
        format=FORMAT,
        handlers=[
            RichHandler(console=_logging_console,
                        show_path=False,
                        tracebacks_show_locals=False,
                        # disable Rich markup by default to avoid character clashes when printing logs;
                        # markup can still be processed on demand by explicitly adding 'extra={"markup": True}' to the log call
                        markup=False)
        ],
    )

    # override root logger's level on every call
    logging.getLogger().setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger with the specified name.
    Ensures that the logging module is configured with the default handlers for the current CI environment.
    """
    configure_ci_logging()
    return logging.getLogger(name)
