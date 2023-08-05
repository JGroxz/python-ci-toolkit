"""
Functions to help with logging in the actions package.
"""
import time
from contextlib import contextmanager
from logging import Logger
from threading import Thread

from rich import print
from rich.progress import Progress
from rich.text import Text

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


_ACTION_VISUAL_THREAD_OFFSET = 27


def _get_action_run_border_tip_element(top: bool = True) -> str:
    width = _ACTION_VISUAL_THREAD_OFFSET
    if top:
        return f"╰{'─' * width}╮"
        # f"\n{' ' * (width + 1)}┴")
    else:
        # (f"{' ' * (width + 1)}┬\n"
        return f"╭{'─' * width}╯"


def get_action_run_in_progress_message(action_name: str) -> str:
    """
    Crafts a message to be displayed in the progress bar while the action is running.

    Args:
        action_name: Name of the action.

    Returns:
        Message to be displayed in the progress bar.
    """
    left_part = Text(f">_ '{action_name}'")
    available_width = _ACTION_VISUAL_THREAD_OFFSET
    overflow = len(left_part) - available_width
    if overflow > 0:
        ellipsized_ending = "…'"
        left_part.right_crop(overflow + len(ellipsized_ending) + 1)
        left_part.append(ellipsized_ending)
    left_part.pad_left(available_width - len(left_part) - 1)

    separator = f"[pyci.flair_dark]│[/]"
    right_part = f"[pyci.flair][pyci.action]Running[/]"

    return f" [pyci.flair]{left_part} {separator} {right_part}"


def print_action_run_start(action_name: str, action_version: str, action_source: str) -> None:
    """
    Prints a message to the console to indicate that the action run has started.

    Args:
        action_name: Name of the action.
        action_version: Version of the action.
        action_source: Source of the action (local directory, Git repo etc.).
    """
    # noinspection PyBroadException
    try:
        import pkg_resources
        version = pkg_resources.get_distribution('python-ci-toolkit').version
    except Exception:
        from ...versions import read_project_version
        version = read_project_version(ci_project_root)

    action_display_name = get_action_display_name(action_name, action_version)

    title = f"[pyci.flair] Running CI action [pyci.action]'{action_display_name}'[/]...[/]"

    info_lines = [
        f"CI toolkit version: [pyci.info]{version}[/]",
        f"CI environment: [pyci.info]{ci_environment_name}[/]",
        f"Action version: [pyci.info]{action_version}[/]",
        f"Action source: [pyci.info]{action_source}[/]",
    ]

    print(f"[pyci.flair_dark]╭─{title}[/]")
    for line in info_lines:
        print(f"[pyci.flair_dark]│[/]   {line}")
    print(f"[pyci.flair_dark]{_get_action_run_border_tip_element(True)}[/]")


def print_action_run_end_success(action_name: str, stopwatch: Stopwatch) -> None:
    """
    Prints a message to the console to indicate that the action run has completed successfully.

    Args:
        action_name: Name of the action.
        stopwatch: Stopwatch used to measure the action run time.
    """
    message = f"Action run completed in {stopwatch.elapsed_time_pretty} ('{action_name}')."

    print(f"[pyci.flair_dark]{_get_action_run_border_tip_element(False)}[/]")
    print(f"[pyci.flair_dark]╰─[/] [pyci.success]{message}[/]")


def print_action_run_end_failure(action_name: str, stopwatch: Stopwatch, exception: BaseException) -> None:
    """
    Prints a message to the console to indicate that the action run has failed.

    Args:
        action_name: Name of the action.
        stopwatch: Stopwatch used to measure the action run time.
        exception: Exception that caused the action run to fail.
    """
    exception_type = type(exception)
    exception_string = exception_type.__name__
    if exception_type == SystemExit:
        exception_string += f" with code {exception.code}"

    message = f"Action run failed in {stopwatch.elapsed_time_pretty} ({exception_string}, '{action_name}')."

    print(f"[pyci.error]{_get_action_run_border_tip_element(False)}[/]")
    print(f"[pyci.error]╰─[/][pyci.critical] {message} [/]")
