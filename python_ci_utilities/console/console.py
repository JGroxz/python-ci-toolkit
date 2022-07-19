"""
Functions for setting up a CI console.
"""

import logging

from ..pip import ensure_package_installed

try:
    ensure_package_installed("rich")
except RuntimeError:
    raise ImportError("'python_ci_utilities.console' requires 'rich' package in order to work, but it could not be located.")

from rich.console import Console

from ..environment import is_running_in_bitbucket_ci


def get_ci_console() -> Console:
    """
    Returns:
        Rich Console configured for the use in CI environment.
    """
    if is_running_in_bitbucket_ci():
        return Console(force_terminal=True)

    return Console()


ci_console = get_ci_console()
"""
A main entrypoint for printing CI logs.
"""


def setup_ci_logging() -> None:
    """
    Sets up logging module with rich handler for the use in Bitbucket CI environment.
    """
    from rich.logging import RichHandler
    from rich.traceback import install

    install(console=ci_console, show_locals=False)

    FORMAT = "%(message)s"
    logging.basicConfig(
        level="INFO",
        format=FORMAT,
        handlers=[
            RichHandler(
                console=ci_console,
                show_path=False,
                tracebacks_show_locals=False,
                markup=True,
            )
        ]
    )


def initialize_ci_environment() -> Console:
    setup_ci_logging()

    initialized_notification = "[green_yellow]>_[/][rgb(146,202,85)] Python CI console initialized[/] " \
                               "[grey50](triggered by the import of [i]python_ci_utilities.console[/])[/]"
    logging.info(initialized_notification)

    return ci_console


initialize_ci_environment()
