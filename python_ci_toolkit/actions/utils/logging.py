"""
Functions to help with logging in the actions package.
"""
import time
from contextlib import contextmanager
from logging import Logger
from threading import Thread

from rich.progress import Progress

from . import Stopwatch
from ..constants import ACTION_VERSION_SEPARATOR
from ...environment import ci_project_root, ci_environment_name, CiEnvironmentType, ci_environment_type
from ...logging import get_logger

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

    logger.info(f"[pyci.flair]>_ Running CI action [pyci.action]'{action_display_name}'[/]...[/]\n"
                f"     CI toolkit version: [pyci.info]{version}[/]\n"
                f"     CI environment: [pyci.info]{ci_environment_name}[/]\n"
                f"     Action version: [pyci.info]{action_version}[/]\n"
                f"     Action source: [pyci.info]{action_source}[/]", extra={"markup": True, "highlighter": None})


@contextmanager
def loading_animation(description: str) -> None:  # TODO: rework loading animation to a transient Live display which is accessible from the actions themselves
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
        with (
            Progress(transient=True, refresh_per_second=60) as progress,
            Stopwatch() as sw
        ):
            task_id = progress.add_task(f"[pyci.info]{description}...", total=None)

            is_done = False

            def update_description():
                while not is_done:
                    time.sleep(0.1)
                    if sw.elapsed_time < 1:
                        continue
                    progress.update(task_id, description=f"[pyci.info]{description}... [dim]({sw.elapsed_time_pretty})[/]")

            Thread(target=update_description, daemon=True).start()

            try:
                yield  # <- within this context, clone repos, install requirements etc.
            except BaseException:
                raise
            finally:
                is_done = True
    else:
        # cloud environments normally don't support erasing terminal output,
        # so progress bars get messed up; in this case we don't display them
        yield
