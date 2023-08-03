"""
Provides functions to retrieve and run CI actions based on Python scripts.
"""

import sys
from dataclasses import dataclass
from types import ModuleType
from typing import List

from .retrieval import retrieve_ci_action_script
from .retrieval.sources.git.caching import reset_action_cache_timestamp
from .utils import Stopwatch
from .utils.logging import loading_animation, print_action_header, get_action_display_name
from ..logging import get_logger
from ..pip import ensure_requirements_installed
from ..python import import_module_from_file

logger = get_logger(__name__)


@dataclass
class ActionRunResult:
    """
    Represents the result of a CI action run.
    """
    exception: BaseException = None

    @property
    def is_successful(self) -> bool:
        """
        Returns whether the action run was successful.
        """
        no_exceptions = self.exception is None
        clean_exit = isinstance(self.exception, SystemExit) and self.exception.code == 0

        return no_exceptions or clean_exit


def execute_action_module(action_module: ModuleType,
                          action_name: str,
                          action_version: str) -> ActionRunResult:
    action_display_name = get_action_display_name(action_name, action_version)

    # check if the action module has a cli() method
    if not hasattr(action_module, "cli"):
        logger.critical(f"Action '{action_display_name}' does not have a 'cli()' method, so it won't be executed.\n"
                        f"Please make sure that the action module has a 'cli()' method which serves as an entry point for the action logic.")
        sys.exit(1)

    # run the action
    action_exception = None
    try:
        action_module.cli()
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

    logger.debug("Cleaned sys.argv before action run:\n "
                 f"  - Original: [blue]{original_argv}[/]\n"
                 f"  - Cleaned:  [blue]{sys.argv}[/]", extra={"markup": True})


def run_ci_action(action_name: str, action_version: str = None, argv: List[str] = None) -> None:
    """
    Executes CI action by the given action name and version.
    """
    # if no version is provided, use the one from the 'main' branch
    if action_version is None:
        action_version = "main"

    # craft action name for logs
    action_display_name = get_action_display_name(action_name, action_version)

    # locate action script
    logger.debug(f"Locating action '{action_display_name}'...")
    action_script_path, action_source = retrieve_ci_action_script(action_name, action_version)

    # install action's requirements if present
    action_requirements_path = action_script_path.parent / "requirements.txt"
    if action_requirements_path.exists():
        logger.debug(f"Action '{action_name}' has requirements file supplied with it. Installing requirements...")

        with loading_animation("Installing action's dependencies"):
            ensure_requirements_installed(action_requirements_path, silence_pip_stdout=False)

        logger.debug("Requirements installation complete.")

    # prepare action's CLI arguments
    rearrange_argv_before_action_run(action_name)

    # import action's Python module
    logger.info(f"Importing Python module of the action '{action_name}'...")
    with loading_animation("Importing action's Python module..."), Stopwatch() as import_stopwatch:
        try:
            action_module = import_module_from_file(f"{action_name}", action_script_path)
        except Exception:
            logger.error(f"Error when importing Python module from action script '{action_script_path}' (action '{action_display_name}' from {action_source}).")
            raise
    logger.info(f"Import completed in {import_stopwatch.elapsed_time_pretty}.")

    # run CI action using its cli() method with the given arguments
    print_action_header(action_name, action_version, action_source)

    with loading_animation(f"[rgb(146,202,85)]Running CI action '{action_display_name}'"), Stopwatch() as run_stopwatch:
        run_result = execute_action_module(action_module, action_name, action_version)

    if not run_result.is_successful:
        # action failed, raise the exception
        try:
            raise run_result.exception
        finally:
            logger.critical(f"[red]Action run failed in {run_stopwatch.elapsed_time_pretty} ({type(run_result.exception).__name__}, '{action_display_name}').[/]",
                            extra={"markup": True, "highlighter": None})

    # action completed successfully
    logger.info(f"[rgb(146,202,85)]Action run completed in {run_stopwatch.elapsed_time_pretty} ('{action_display_name}').[/]",
                extra={"markup": True})

    # reset cache timestamps after each successful action run
    # to allow chaining actions from the same repo without re-downloading them
    reset_action_cache_timestamp(action_name, action_version)
