"""
Functions to help with logging in the actions package.
"""
import time
from contextlib import contextmanager
from logging import Logger
from threading import Thread
from typing import Iterable

from rich import get_console
from rich.console import RenderableType
from rich.progress import Progress, Task, TimeRemainingColumn, TaskProgressColumn, BarColumn, TextColumn
from rich.text import Text

from . import Stopwatch
from ..constants import ACTION_VERSION_SEPARATOR
from ..logging import get_logger
from ...environment import Local, ci_paths, ci_platform

logger = get_logger(__name__)

_ACTION_VISUAL_THREAD_OFFSET = 10
"""

"""


def _print_system_message(message: str) -> None:
    get_console().print(message, highlight=False)


def _print_top_level_action_message(
    message: str,
    *,
    bend: str | None = None,
    connector_style: str = "pyci.lifecycle",
) -> None:
    console = get_console()
    prefix_width = 3 if bend is not None else 2
    message_lines = Text.from_markup(message).wrap(
        console,
        max(console.width - prefix_width, 1),
        overflow="fold",
        no_wrap=False,
    )
    if not message_lines:
        message_lines.append(Text())

    bend_line_index = 0 if bend == "╭─" else len(message_lines) - 1
    for line_index, line in enumerate(message_lines):
        connector = bend if bend is not None and line_index == bend_line_index else "│"
        rendered_line = Text()
        rendered_line.append(connector, style=connector_style)
        rendered_line.append(" ")
        rendered_line.append_text(line)
        console.print(
            rendered_line,
            overflow="crop",
            no_wrap=True,
            highlight=False,
        )


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


def get_ci_toolkit_version() -> str:
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        return distribution("python-ci-toolkit").version
    except PackageNotFoundError:
        from ...versions import read_project_version

        return str(read_project_version(ci_paths.project_root))


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
    if ci_platform is not Local:
        # cloud environments normally don't support erasing terminal output,
        # so progress bars get messed up; in this case we don't display them
        yield
        return

    # in a local environment, display animated progress bar for visual feedback
    global _progress
    if _progress.live.is_started:
        with _task_in_progress(_progress, description):
            yield
        return

    # if no Live display is active, create a new one
    _progress = _get_new_progress_instance()
    with (
        _task_progress_updater(_progress),
        _task_in_progress(_progress, description)
    ):
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

    return f"[pyci.metadata]{description} {time_string}[/]"


@contextmanager
def _task_in_progress(progress: Progress, description: str) -> None:
    """
    Adds a task to the stack of tasks that are currently displayed in the progress bar.

    Args:
        progress: Progress instance to add the task to.
        description: Description of the task.
    """
    task_id = progress.add_task(
        f"[pyci.metadata]{description}",
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


def _print_nested_action_message(
    message: str,
    nesting_depth: int,
    *,
    opening: bool,
    connector_style: str = "pyci.lifecycle",
) -> None:
    console = get_console()
    nesting_depth = max(nesting_depth, 1)
    thread_column = _ACTION_VISUAL_THREAD_OFFSET + 1
    content_column = thread_column + nesting_depth + 2
    message_lines = Text.from_markup(message).wrap(
        console,
        max(console.width - content_column, 1),
        overflow="fold",
        no_wrap=False,
    )
    if not message_lines:
        message_lines.append(Text())

    final_line_index = len(message_lines) - 1
    for line_index, line in enumerate(message_lines):
        is_bend_line = (
            line_index == 0
            if opening
            else line_index == final_line_index
        )
        rendered_line = Text(" " * thread_column)
        if is_bend_line:
            rendered_line.append(
                "│" * (nesting_depth - 1),
                style="pyci.flair_dark_dim",
            )
            rendered_line.append(
                "╰╮" if opening else "╭╯",
                style=connector_style,
            )
        else:
            rendered_line.append(
                "│" * nesting_depth,
                style="pyci.flair_dark_dim",
            )
            rendered_line.append("│", style=connector_style)
        rendered_line.append(" ")
        rendered_line.append_text(line)
        console.print(
            rendered_line,
            overflow="crop",
            no_wrap=True,
            highlight=False,
        )


def print_action_run_start(action_name: str,
                           action_version: str,
                           action_source: str,
                           is_nested: bool,
                           nesting_depth: int = 0,
                           toolkit_version: str | None = None,
                           ci_environment: str | None = None) -> None:
    """
    Prints a message to the console to indicate that the action run has started.

    Args:
        action_name: Name of the action.
        action_version: Version of the action.
        action_source: Source of the action (local directory, Git repo etc.).
        is_nested: Whether the action was called from another action.
    """
    toolkit_version = toolkit_version or get_ci_toolkit_version()

    action_display_name = get_action_display_name(action_name, action_version)

    if not is_nested:
        title = (
            "[pyci.lifecycle]Running[/] action "
            f"[pyci.action]'{action_display_name}'[/]"
            "..."
        )
        if ci_environment is None:
            toolkit_info = (
                f"PyCI [pyci.metadata]v{toolkit_version}[/] "
                "with no CI platform detected"
            )
        else:
            toolkit_info = (
                f"PyCI [pyci.metadata]v{toolkit_version}[/] in "
                f"[pyci.metadata]{ci_environment}[/] environment"
            )
        info_lines = [
            toolkit_info,
            f"Action source: [pyci.metadata]{action_source}[/]",
        ]
        _print_top_level_action_message(title, bend="╭─")
        for line in info_lines:
            _print_top_level_action_message(line)
        _print_system_message(
            f"[pyci.lifecycle]{_get_action_run_border_tip_element(True)}[/]"
        )
    else:
        title = (
            "[pyci.lifecycle]Running[/] nested action "
            f"[pyci.action]'{action_display_name}'[/]"
            "..."
        )
        _print_nested_action_message(
            title,
            nesting_depth,
            opening=True,
        )


def print_action_run_end_success(
    action_name: str,
    stopwatch: Stopwatch | float,
    is_nested: bool,
    nesting_depth: int = 0,
) -> None:
    """
    Prints a message to the console to indicate that the action run has completed successfully.

    Args:
        action_name: Name of the action.
        stopwatch: Stopwatch used to measure the action run time.
        is_nested: Whether the action was called from another action.
    """
    elapsed_time_pretty = (
        Stopwatch.format_time_pretty(stopwatch)
        if isinstance(stopwatch, float)
        else stopwatch.elapsed_time_pretty
    )
    if not is_nested:
        message = (
            "[pyci.status.success]Completed[/] action "
            f"[pyci.action]'{action_name}'[/] in "
            f"[pyci.duration]{elapsed_time_pretty}[/]."
        )
        _print_system_message(
            f"[pyci.lifecycle]{_get_action_run_border_tip_element(False)}[/]"
        )
        _print_top_level_action_message(message, bend="╰─")
    else:
        message = (
            "[pyci.status.success]Completed[/] nested action "
            f"[pyci.action]'{action_name}'[/] in "
            f"[pyci.duration]{elapsed_time_pretty}[/]."
        )
        _print_nested_action_message(
            message,
            nesting_depth,
            opening=False,
        )


def print_action_run_end_failure(action_name: str,
                                 stopwatch: Stopwatch | float,
                                 exception: BaseException | str,
                                 is_nested: bool,
                                 nesting_depth: int = 0) -> None:
    """
    Prints a message to the console to indicate that the action run has failed.

    Args:
        action_name: Name of the action.
        stopwatch: Stopwatch used to measure the action run time.
        exception: Exception that caused the action run to fail.
        is_nested: Whether the action was called from another action.
    """
    elapsed_time_pretty = (
        Stopwatch.format_time_pretty(stopwatch)
        if isinstance(stopwatch, float)
        else stopwatch.elapsed_time_pretty
    )
    if isinstance(exception, str):
        exception_string = exception
    else:
        exception_type = type(exception)
        exception_string = exception_type.__name__
        if isinstance(exception, SystemExit):
            exception_string += f' with code "{exception.code}"'

    if not is_nested:
        message = (
            "[pyci.status.failure]Failed[/] action "
            f"[pyci.action]'{action_name}'[/] in "
            f"[pyci.duration]{elapsed_time_pretty}[/] "
            f"([pyci.status.failure]{exception_string}[/])."
        )
        _print_system_message(
            f"[pyci.status.failure]{_get_action_run_border_tip_element(False)}[/]"
        )
        _print_top_level_action_message(
            message,
            bend="╰─",
            connector_style="pyci.status.failure",
        )
    else:
        message = (
            "[pyci.status.failure]Failed[/] nested action "
            f"[pyci.action]'{action_name}'[/] in "
            f"[pyci.duration]{elapsed_time_pretty}[/] "
            f"([pyci.status.failure]{exception_string}[/])."
        )
        _print_nested_action_message(
            message,
            nesting_depth,
            opening=False,
            connector_style="pyci.status.failure",
        )
