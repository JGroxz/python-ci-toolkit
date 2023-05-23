"""
Functions to help with logging in the actions package.
"""

from contextlib import contextmanager
from logging import Logger

from rich.progress import Progress

from ..constants import ACTION_VERSION_SEPARATOR
from ...environment import ci_project_root, ci_environment_name, CiEnvironmentType, ci_environment_type
from ...logging import get_logger, ci_output_console

logger = get_logger(__name__)


def get_action_logger(name: str = None) -> Logger:
    """
    Returns a logger for use in CI actions.
    Automatically adds handlers to log into the console of the current CI environment.

    Args:
        name: Name of the CI action this logger is intended for.
    """
    if name is None:
        name = "default"

    # the naming ensures that the returned action logger inherits logging settings from the CI toolkit
    return get_logger(f"python_ci_toolkit.actions.external.{name}")


def get_action_display_name(action_name: str, action_version: str) -> str:
    """
    Returns a display name of the action for use in logs.
    """
    return f"{action_name}{ACTION_VERSION_SEPARATOR}{action_version}"


def print_action_header(action_name: str, action_version: str, action_source: str) -> None:
    # noinspection PyBroadException
    try:
        import pkg_resources
        version = pkg_resources.get_distribution('python-ci-toolkit').version
    except Exception:
        from ...versions import read_project_version
        version = read_project_version(ci_project_root)

    action_display_name = get_action_display_name(action_name, action_version)

    logger.info(f"[green]>_[/][rgb(146,202,85)] Running CI action '{action_display_name}'[/]...\n"
                f"     CI toolkit version: [blue]{version}[/]\n"
                f"     CI environment: [blue]{ci_environment_name}[/]\n"
                f"     Action version: [blue]{action_version}[/]\n"
                f"     Action source: [blue]{action_source}[/]", extra={"markup": True, "highlighter": None})


@contextmanager
def loading_animation(description: str) -> None:
    """
    Context manager that displays a loading animation in the console.
    To be displayed to the user while doing prolonged tasks like cloning action Git repo.

    Notes:
        Animation is disabled in cloud CI environments, as their consoles normally don't support this level of rendering.

    Args:
        description: Info message describing what's happening. Will be displayed next to the animation.
    """
    if ci_environment_type == CiEnvironmentType.Unknown:
        # in a local environment, display animated progress bar for visual feedback
        with Progress(console=ci_output_console, transient=True, refresh_per_second=60) as progress:
            progress.add_task(f"[blue]{description}...", total=None)

            # TODO: add thread which will update description of the task with a timer if it takes longer than 10 s

            try:
                yield  # <- within this context, clone repos, install requirements etc.
            except Exception:
                raise
    else:
        # cloud environments normally don't support erasing terminal output,
        # so progress bars get messed up; in this case we don't display them
        yield
