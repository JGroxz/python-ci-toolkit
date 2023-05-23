"""
Provides functions to retrieve and run CI actions based on Python scripts.
"""

import sys
from typing import List

from ._constants import ACTION_VERSION_SEPARATOR
from ._logging import loading_animation, print_action_header, get_action_display_name
from ._retrieval import retrieve_ci_action_script
from ..logging import get_logger
from ..pip import ensure_requirements_installed
from ..python import import_module_from_file

logger = get_logger(__name__)


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
    sys.argv = sys.argv[:1]
    if argv is not None:
        sys.argv.extend(argv)

    # run CI action using its cli() method with the given arguments
    logger.debug(f"Importing Python module of the action '{action_name}'...")
    with loading_animation("Importing action's Python module..."):
        try:
            action_module = import_module_from_file(f"{action_name}", action_script_path)
        except Exception:
            logger.error(f"Error when importing Python module from action script '{action_script_path}' (action '{action_display_name}' from {action_source}).")
            raise
    logger.debug("Import completed.")

    print_action_header(action_name, action_version, action_source)

    with loading_animation(f"[rgb(146,202,85)]Running CI action '{action_display_name}'"):
        action_module.cli()
