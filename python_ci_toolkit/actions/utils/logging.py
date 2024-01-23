"""
Functions to help with logging in the actions package.
"""
import time
from contextlib import contextmanager
from logging import Logger
from threading import Thread
from typing import Iterable

from rich import print
from rich.console import RenderableType
from rich.progress import Progress, Task, TimeRemainingColumn, TaskProgressColumn, BarColumn, TextColumn

from . import Stopwatch
from ..constants import ACTION_VERSION_SEPARATOR
from ...environment import ci_project_root, ci_platform, platforms
from ...logging import get_logger

logger = get_logger(__name__)

_ACTION_VISUAL_THREAD_OFFSET = 27
"""

"""


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


def _get_new_progress_instance() -> Progress:
    """
    Returns a new instance of the Rich Progress class.
    """
    progress_renderables = (
        " ",
        BarColumn(_ACTION_VISUAL_THREAD_OFFSET - 3, pulse_style="pyci.progress"),
        " [pyci.flair_dark]│[/]",
        TextColumn("[progress.description]{task.description}"),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    )
    progress = Progress(*progress_renderables, transient=True, refresh_per_second=60)

    # patch this Progress's get_renderables method to sort tasks by their start time when rendering
    def get_renderables(self: Progress) -> Iterable[RenderableType]:
        """Get a number of renderables for the progress display."""
        sorted_tasks = sorted(self.tasks, key=lambda task: task.start_time, reverse=True)
        table = self.make_tasks_table(sorted_tasks)
        yield table

    progress.get_renderables = get_renderables.__get__(progress)

    return progress


_progress = _get_new_progress_instance()
"""
Global Rich Progress instance used to display loading animations in the console.
"""


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
    if ci_platform != platforms.Local:
        # cloud environments normally don't support erasing terminal output,
        # so progress bars get messed up; in this case we don't display them
        yield

    # in a local environment, display animated progress bar for visual feedback
    global _progress
    if not _progress.live.is_started:
        _progress = _get_new_progress_instance()
        with (
            _task_progress_updater(_progress),
            _task_in_progress(_progress, description)
        ):
            yield
    else:
        with _task_in_progress(_progress, description):
            yield


def _get_task_description_for_display(task: Task) -> str:
    """
    Crafts a message to be displayed in the progress bar while the task is running.

    Args:
        task: Task to get the description for.

    Returns:
        Message to be displayed in the progress bar.
    """
    # extract original description
    description = task.fields["original_description"]

    # craft elapsed time string
    elapsed_time = task.elapsed
    elapsed_time_pretty = Stopwatch.format_time_pretty(elapsed_time)
    time_string = "" if (elapsed_time < 1) else f"[dim]({elapsed_time_pretty})[/]"

    return f"[pyci.info]{description} {time_string}[/]"


@contextmanager
def _task_in_progress(progress: Progress, description: str) -> None:
    """
    Adds a task to the stack of tasks that are currently displayed in the progress bar.

    Args:
        progress: Progress instance to add the task to.
        description: Description of the task.
    """
    task_id = progress.add_task(
        f"[pyci.info]{description}",
        total=None,
        original_description=description,
    )

    try:
        yield
    finally:
        progress.update(task_id, completed=True)


@contextmanager
def _task_progress_updater(progress: Progress) -> None:
    """
    Updates the descriptions of all tasks in the progress bar in a background thread while the context is active.

    Args:
        progress: Progress bar object to use.
    """
    is_done = False

    def update_tasks():
        while not is_done:
            time.sleep(0.1)

            # remove completed tasks
            completed_task_id = [task.id for task in progress.tasks if task.completed]
            for task in completed_task_id:
                progress.remove_task(task)

            # update descriptions of running tasks
            for task in progress.tasks:
                progress.update(task.id, description=_get_task_description_for_display(task), refresh=True)

    Thread(target=update_tasks, daemon=True).start()

    try:
        yield  # <- within this context, do the task
    finally:
        is_done = True


def _get_action_run_border_tip_element(top: bool = True) -> str:
    width = _ACTION_VISUAL_THREAD_OFFSET
    if top:
        return f"╰{'─' * width}╮"
        # f"\n{' ' * (width + 1)}┴")
    else:
        # (f"{' ' * (width + 1)}┬\n"
        return f"╭{'─' * width}╯"


def get_action_progress_message(action_name: str, status: str) -> str:
    """
    Crafts a message to be displayed in the progress bar while the action is running.

    Args:
        action_name: Name of the action.
        status: Status of the action (e.g. "Importing", "Running" etc.).

    Returns:
        Message to be displayed in the progress bar.
    """
    return f"[pyci.flair]>_ '{action_name}': {status}..."


def print_action_run_start(action_name: str,
                           action_version: str,
                           action_source: str,
                           is_nested: bool) -> None:
    """
    Prints a message to the console to indicate that the action run has started.

    Args:
        action_name: Name of the action.
        action_version: Version of the action.
        action_source: Source of the action (local directory, Git repo etc.).
        is_nested: Whether the action was called from another action.
    """
    # noinspection PyBroadException
    try:
        import pkg_resources
        version = pkg_resources.get_distribution('python-ci-toolkit').version
    except Exception:
        from ...versions import read_project_version
        version = read_project_version(ci_project_root)

    action_display_name = get_action_display_name(action_name, action_version)

    if not is_nested:
        title = f"[pyci.flair] Running CI action [pyci.action]'{action_display_name}'[/]...[/]"
        info_lines = [
            f"CI toolkit version: [pyci.info]{version}[/]",
            f"CI environment: [pyci.info]{ci_platform.name()}[/]",
            f"Action version: [pyci.info]{action_version}[/]",
            f"Action source: [pyci.info]{action_source}[/]",
        ]
        print(f"[pyci.flair_dark]╭─{title}[/]")
        for line in info_lines:
            print(f"[pyci.flair_dark]│[/]   {line}")
        print(f"[pyci.flair_dark]{_get_action_run_border_tip_element(True)}[/]")
    else:
        title = f"[pyci.flair]Running nested action [pyci.action]'{action_display_name}'[/]...[/]"
        print(f"{' ' * (_ACTION_VISUAL_THREAD_OFFSET + 1)}[pyci.flair_dark]├─▶[/] {title}")


def print_action_run_end_success(action_name: str, stopwatch: Stopwatch, is_nested: bool) -> None:
    """
    Prints a message to the console to indicate that the action run has completed successfully.

    Args:
        action_name: Name of the action.
        stopwatch: Stopwatch used to measure the action run time.
        is_nested: Whether the action was called from another action.
    """
    if not is_nested:
        message = f"Action run completed in {stopwatch.elapsed_time_pretty} ('{action_name}')."
        print(f"[pyci.flair_dark]{_get_action_run_border_tip_element(False)}[/]")
        print(f"[pyci.flair_dark]╰─[/] [pyci.success]{message}[/]")
    else:
        message = f"Nested action '{action_name}' completed in {stopwatch.elapsed_time_pretty}."
        print(f"{' ' * (_ACTION_VISUAL_THREAD_OFFSET + 1)}[pyci.flair_dark]├─◀[/] [pyci.success]{message}[/]")


def print_action_run_end_failure(action_name: str,
                                 stopwatch: Stopwatch,
                                 exception: BaseException,
                                 is_nested: bool) -> None:
    """
    Prints a message to the console to indicate that the action run has failed.

    Args:
        action_name: Name of the action.
        stopwatch: Stopwatch used to measure the action run time.
        exception: Exception that caused the action run to fail.
        is_nested: Whether the action was called from another action.
    """
    exception_type = type(exception)
    exception_string = exception_type.__name__
    if isinstance(exception, SystemExit):
        exception_string += f' with code "{exception.code}"'

    if not is_nested:
        message = f"Action run failed in {stopwatch.elapsed_time_pretty} ({exception_string}, '{action_name}')."
        print(f"[pyci.error]{_get_action_run_border_tip_element(False)}[/]")
        print(f"[pyci.error]╰─[/][pyci.critical] {message} [/]")
    else:
        message = f"Nested action '{action_name}' failed in {stopwatch.elapsed_time_pretty}."
        print(f"{' ' * (_ACTION_VISUAL_THREAD_OFFSET + 1)}[pyci.error]├─◀[/][pyci.critical] {message} [/]\n"
              f"{' ' * (_ACTION_VISUAL_THREAD_OFFSET + 1)}[pyci.error]│  [/][pyci.critical] ({exception_string}) [/]")
