"""
Functions for managing logging in CI environments.
"""
from __future__ import annotations

import logging

import click
import rich
import rich_click
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install

from ..environment import ci_environment_type, CiEnvironmentType


def _get_ci_output_console() -> Console:
    """
    Returns a Rich Console configured for the use in CI environment.
    """
    if ci_environment_type == CiEnvironmentType.BitbucketPipelines:
        return Console(force_terminal=True)

    return Console()


ci_output_console = _get_ci_output_console()
"""
Rich console used by the CI toolkit's loggers.
"""


def configure_ci_logging(level: str | int = logging.INFO) -> None:
    """
    Configures the root logger with Rich handler using the CI console.

    Notes:
        This call configures rich and logging module for the current CI environment and terminal type, be it Bitbucket pipelines or a local machine.
        This enables nicely formatted logs and detailed, well-readable tracebacks.

        After running this function, you can use logging.*() methods to get nicely formatted log messages in the output.

    Args:
        level: Level to set the root logger to.
    """

    install(console=ci_output_console,
            show_locals=False,
            suppress=[click, rich_click, rich])

    # basicConfig in case logging has not been set up yet
    FORMAT = "%(message)s"
    logging.basicConfig(
        level=level,
        format=FORMAT,
        handlers=[
            RichHandler(console=ci_output_console,
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
