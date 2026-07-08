"""
Provides functions to retrieve and run CI actions based on Python scripts.
"""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import List

from .datatypes import ActionRunResult, ActionOutput
from .constants import ACTION_VERSION_DEFAULT_REMOTE_STRING, ACTION_VERSION_LOCAL_STRING
from .retrieval import retrieve_ci_action_script
from .retrieval.sources.git.cloning import get_remote_action_repo
from .retrieval.sources.git.caching import reset_action_cache_timestamp
from .utils import Stopwatch
from .utils.logging import (loading_animation, print_action_run_start, get_action_display_name,
                            print_action_run_end_success, print_action_run_end_failure, get_action_progress_message)
from .logging import get_logger
from .logging.logging import LOG_WITH_MARKUP
from ..pip import ensure_requirements_installed
from ..python import import_module_from_file

logger = get_logger(__name__)

_ACTION_ENTRY_POINT_FUNCTION_NAME = "action"
"""Name of the Python method used as an entry point for the action logic."""


def execute_action_module(action_module: ModuleType,
                          action_name: str,
                          action_version: str) -> ActionRunResult:
    action_display_name = get_action_display_name(action_name, action_version)

    # check if the action module has the required entry point function
    if not hasattr(action_module, _ACTION_ENTRY_POINT_FUNCTION_NAME):
        logger.critical(f"Action '{action_display_name}' does not have a '{_ACTION_ENTRY_POINT_FUNCTION_NAME}()' function, so it won't be executed.\n"
                        f"Please make sure that the action module has a '{_ACTION_ENTRY_POINT_FUNCTION_NAME}()' "
                        f"function which serves as an entry point for the action logic.")
        sys.exit(1)

    # run the action
    action_exception = None
    try:
        action_function: callable = getattr(action_module, _ACTION_ENTRY_POINT_FUNCTION_NAME)

        extra_kwargs = {}
        is_click_command = hasattr(action_function, "no_args_is_help")
        if is_click_command:
            # if the action entry point is wrapped by Click, use 'standalone_mode=False' to get the return value
            # (https://stackoverflow.com/a/66156654)
            extra_kwargs.setdefault("standalone_mode", False)

        logger.debug(f"Calling action entry point function: {action_function}")
        return_value = action_function(**extra_kwargs)
        logger.debug(f"Action function return value: {return_value}")
    except BaseException as e:
        action_exception = e
        return_value = None

    return ActionRunResult(
        exception=action_exception,
        output=ActionOutput(value=return_value)
    )


def rearrange_argv_before_action_run(action_name: str) -> None:
    """
    Combines all args up to and including action name and puts them in the first argument of the argv.

    Notes:
        This is to make any CLI implementations in the actions themselves work as expected.
    """
    original_argv = sys.argv.copy()

    # remove all arguments which come before action name
    while not sys.argv[0].startswith(action_name):
        sys.argv.pop(0)

    # popped args
    removed_args_count = len(original_argv) - len(sys.argv)
    popped_args = original_argv[:removed_args_count]
    sys.argv[0] = " ".join(popped_args) + " " + action_name

    logger.debug("Cleaned sys.argv before action run:\n"
                 f"  - Original: [pyci.info]{original_argv}[/]\n"
                 f"  - Cleaned:  [pyci.info]{sys.argv}[/]", extra={"markup": True})


_running_actions_stack: list[tuple[str, str]] = [
    # (action_name, action_version)
]


def _is_action_running(action_name: str) -> bool:
    return any(running_action_name == action_name for running_action_name, _ in _running_actions_stack)


@dataclass(frozen=True)
class _ActionRuntimeContext:
    action_name: str
    action_version: str
    action_display_name: str
    is_nested: bool


@contextmanager
def _action_runtime_context(action_name: str, action_version: str | None = None) -> Iterator[_ActionRuntimeContext]:
    action_version = action_version or ACTION_VERSION_DEFAULT_REMOTE_STRING

    action_stack_identifier = (action_name, action_version)
    if _is_action_running(action_name):
        raise RuntimeError(f"Action '{action_name}' is already running. Recursive action calls are not allowed.")

    original_argv = sys.argv.copy()
    _running_actions_stack.append(action_stack_identifier)

    try:
        yield _ActionRuntimeContext(
            action_name=action_name,
            action_version=action_version,
            action_display_name=get_action_display_name(action_name, action_version),
            is_nested=(len(_running_actions_stack) > 1),
        )
    finally:
        sys.argv = original_argv
        logger.debug(f"Restored sys.argv after action run: {sys.argv}")

        if action_stack_identifier in _running_actions_stack:
            _running_actions_stack.remove(action_stack_identifier)


def _retrieve_action_script(runtime_context: _ActionRuntimeContext) -> tuple[Path, str]:
    logger.debug(f"Locating action '{runtime_context.action_display_name}'...")
    action_script_path, action_source = retrieve_ci_action_script(
        runtime_context.action_name,
        runtime_context.action_version,
    )
    logger.debug(f"Located action '{runtime_context.action_display_name}' at {action_source}.")
    return action_script_path, action_source


def _install_action_requirements(action_script_path: Path, runtime_context: _ActionRuntimeContext) -> None:
    action_requirements_path = action_script_path.parent / "requirements.txt"
    if not action_requirements_path.exists():
        return

    logger.debug(f"Action [pyci.action]'{runtime_context.action_name}'[/] has requirements file supplied with it. Installing requirements...", **LOG_WITH_MARKUP)

    with (
        loading_animation(get_action_progress_message(runtime_context.action_display_name, "Installing action's dependencies")),
        Stopwatch() as requirements_installation_stopwatch
    ):
        ensure_requirements_installed(action_requirements_path, quiet=True)

    logger.debug(f"Requirements installation complete in {requirements_installation_stopwatch.elapsed_time_pretty}.")


def _prepare_argv_before_action_run(runtime_context: _ActionRuntimeContext, args: List[str] | None = None) -> None:
    if not runtime_context.is_nested:
        rearrange_argv_before_action_run(runtime_context.action_name)
        return

    if args is None:
        args = []
    sys.argv = [runtime_context.action_name, *args]
    logger.debug(f"Updated sys.argv with provided values before nested action run: {sys.argv}")


def _import_action_module(action_script_path: Path, action_source: str, runtime_context: _ActionRuntimeContext) -> ModuleType:
    logger.debug(f"Importing Python module of the action [pyci.action]'{runtime_context.action_name}'[/]...", **LOG_WITH_MARKUP)

    with (
        loading_animation(get_action_progress_message(runtime_context.action_display_name, "Importing action's Python module")),
        Stopwatch() as import_stopwatch
    ):
        try:
            action_module = import_module_from_file(f"{runtime_context.action_name}", action_script_path, True)
        except Exception:
            logger.error(
                f"Error when importing Python module from action script '{action_script_path}' "
                f"(action '{runtime_context.action_display_name}' from {action_source})."
            )
            raise

    logger.debug(f"Import completed in {import_stopwatch.elapsed_time_pretty}.")
    return action_module


def _run_action_module(action_module: ModuleType, runtime_context: _ActionRuntimeContext) -> ActionOutput:
    with(
        loading_animation(get_action_progress_message(runtime_context.action_display_name, "Running")),
        Stopwatch() as run_stopwatch
    ):
        run_result = execute_action_module(
            action_module,
            runtime_context.action_name,
            runtime_context.action_version,
        )

    if not run_result.is_successful:
        try:
            raise run_result.exception
        finally:
            print_action_run_end_failure(
                runtime_context.action_display_name,
                run_stopwatch,
                run_result.exception,
                runtime_context.is_nested,
            )

    print_action_run_end_success(
        runtime_context.action_display_name,
        run_stopwatch,
        runtime_context.is_nested,
    )

    return run_result.output


def _reset_remote_action_cache_timestamp(runtime_context: _ActionRuntimeContext) -> None:
    if runtime_context.action_version == ACTION_VERSION_LOCAL_STRING:
        return

    action_repo = get_remote_action_repo()
    if action_repo is None:
        return

    action_repo_url, _ = action_repo
    reset_action_cache_timestamp(
        action_repo_url,
        runtime_context.action_name,
        runtime_context.action_version,
    )


def run_ci_action(action_name: str, action_version: str = None, args: List[str] = None) -> ActionOutput:
    """
    Executes CI action by the given action name and version.

    Args:
        action_name: Name of the action to run.
        action_version: Version of the action to run.
        args: Vector of command-line arguments to pass to the action.
    """
    with _action_runtime_context(action_name, action_version) as runtime_context:
        action_script_path, action_source = _retrieve_action_script(runtime_context)

        print_action_run_start(
            runtime_context.action_name,
            runtime_context.action_version,
            action_source,
            runtime_context.is_nested,
        )

        _install_action_requirements(action_script_path, runtime_context)
        _prepare_argv_before_action_run(runtime_context, args)

        action_module = _import_action_module(action_script_path, action_source, runtime_context)
        action_output = _run_action_module(action_module, runtime_context)

        _reset_remote_action_cache_timestamp(runtime_context)

        return action_output
