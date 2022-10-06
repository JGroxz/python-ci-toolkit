"""
Functions for setting up a CI console.
"""

import logging
import os
from pathlib import Path

from rich.console import Console

from ..environment import is_running_in_bitbucket_ci, get_ci_environment_name

_INITIALIZED = False
"""Whether the console was initialized. Used to make initialize_ci_console() logic run only once."""


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
Console for the current CI session.

See initialize_ci_console() for more details.
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


def initialize_ci_console() -> Console:
    """
    Sets up the console for the current CI session. Run this in the beginning of each CI script.

    Notes:
        This call configures rich and logging module for the current CI environment and terminal type, be it Bitbucket pipelines or a local machine.
        This enables nicely formatted logs and detailed, well-readable tracebacks.

        After running this method, you can:
         - use the returned console object to print rich-formatted text and objects
         - use logging.*() methods to get nicely formatted log messages in the output

    Returns:
        An initialized rich Console instance which can be used for formatting output in the console.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return ci_console

    setup_ci_logging()

    ci_environment_name = get_ci_environment_name()

    try:
        import pkg_resources
        version = pkg_resources.get_distribution('python-ci-toolkit').version
    except Exception:
        from ..versions import get_project_version
        version = get_project_version(Path(os.path.dirname(__file__), "../../"))

    initialized_notification = f"[green]>_[/][rgb(146,202,85)] Python CI console initialized[/]\n"
    initialized_notification += f"     CI toolkit version: [blue]{version}[/]\n"
    initialized_notification += f"     CI environment: [blue]{ci_environment_name}[/]\n" \
                                f"     [bright_black](from [i]python_ci_utilities.console[/])[/]"

    logging.info(initialized_notification)

    _INITIALIZED = True

    return ci_console


initialize_ci_console()
