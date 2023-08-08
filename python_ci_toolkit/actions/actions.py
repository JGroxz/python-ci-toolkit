"""
Provides functions to retrieve and run CI actions based on Python scripts.
"""

import sys
import time
from types import ModuleType
from typing import List

from .datatypes import ActionRunResult
from .retrieval import retrieve_ci_action_script
from .retrieval.sources.git.caching import reset_action_cache_timestamp
from .utils import Stopwatch
from .utils.logging import (loading_animation, print_action_run_start, get_action_display_name,
                            print_action_run_end_success, print_action_run_end_failure, get_action_progress_message)
from ..logging import get_logger
from ..logging.logging import LOG_WITH_MARKUP
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
        action_function = getattr(action_module, _ACTION_ENTRY_POINT_FUNCTION_NAME)
        action_output = action_function()
    except BaseException as e:
        action_exception = e

    return ActionRunResult(exception=action_exception)


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


def run_ci_action(action_name: str, action_version: str = None, argv: List[str] = None) -> None:
    """
    Executes CI action by the given action name and version.
    """
    # if no version is provided, use the one from the 'main' branch
    if action_version is None:
        action_version = "main"

    # add action to the stack
    action_stack_identifier = (action_name, action_version)
    if action_stack_identifier in _running_actions_stack:
        raise RuntimeError(f"Action '{action_name}' is already running. Recursive action calls are not allowed.")
    _running_actions_stack.append(action_stack_identifier)

    is_nested_action = len(_running_actions_stack) > 1

    # craft action name for logs
    action_display_name = get_action_display_name(action_name, action_version)

    # locate action script
    logger.debug(f"Locating action '{action_display_name}'...")
    action_script_path, action_source = retrieve_ci_action_script(action_name, action_version)
    logger.debug(f"Located action '{action_display_name}' at {action_source}.")

    # announce action run start
    if not is_nested_action:
        print_action_run_start(action_name, action_version, action_source)

    # install action's requirements if present
    action_requirements_path = action_script_path.parent / "requirements.txt"
    if action_requirements_path.exists():
        logger.debug(f"Action [pyci.action]'{action_name}'[/] has requirements file supplied with it. Installing requirements...", **LOG_WITH_MARKUP)

        with (
            loading_animation(get_action_progress_message(action_display_name, "Installing action's dependencies")),
            Stopwatch() as requirements_installation_stopwatch
        ):
            time.sleep(1)
            ensure_requirements_installed(action_requirements_path, silence_pip_stdout=False)

        logger.debug(f"Requirements installation complete in {requirements_installation_stopwatch.elapsed_time_pretty}.")

    # prepare action's CLI arguments
    if not is_nested_action:
        rearrange_argv_before_action_run(action_name)

    # import action's Python module
    logger.debug(f"Importing Python module of the action [pyci.action]'{action_name}'[/]...", **LOG_WITH_MARKUP)
    with (
        loading_animation(get_action_progress_message(action_display_name, "Importing action's Python module")),
        Stopwatch() as import_stopwatch
    ):
        time.sleep(1)
        try:
            action_module = import_module_from_file(f"{action_name}", action_script_path, True)
        except Exception:
            logger.error(f"Error when importing Python module from action script '{action_script_path}' (action '{action_display_name}' from {action_source}).")
            raise
    logger.debug(f"Import completed in {import_stopwatch.elapsed_time_pretty}.")

    # run CI action module with the given arguments
    with(
        loading_animation(get_action_progress_message(action_display_name, "Running")),
        Stopwatch() as run_stopwatch
    ):
        time.sleep(1)
        run_result = execute_action_module(action_module, action_name, action_version)

    if not run_result.is_successful:
        # action failed, raise the exception
        try:
            raise run_result.exception
        finally:
            print_action_run_end_failure(action_display_name, run_stopwatch, run_result.exception)

    # action completed successfully
    if not is_nested_action:
        print_action_run_end_success(action_display_name, run_stopwatch)

    # reset cache timestamps after each successful action run
    # to allow chaining actions from the same repo without re-downloading them
    reset_action_cache_timestamp(action_name, action_version)

    # remove action from the stack
    _running_actions_stack.remove(action_stack_identifier)
