"""
Functions for locating and retrieving local and remote action files.
"""
import logging
import time
from pathlib import Path

from python_ci_toolkit.actions._constants import DEFAULT_ACTION_REPO_URL
from python_ci_toolkit.actions._logging import loading_animation, get_action_display_name
from python_ci_toolkit.actions._retrieval._local import retrieve_ci_action_script_local
from python_ci_toolkit.actions._retrieval._remote import retrieve_ci_action_script_from_git
from python_ci_toolkit.actions._utils import timeit
from python_ci_toolkit.environment import retrieve_environment_variable
from python_ci_toolkit.git import get_default_ssh_private_key

logger = logging.getLogger(__name__)


@timeit
def retrieve_ci_action_script(action_name: str, action_version: str = None) -> (Path, str):
    """
    Retrieves the given CI action script from the local '.ci/actions' folder or from a remote Git repository.

    Args:
        action_name: Name of the action to retrieve.
        action_version: Version of the action to retrieve. Can be either a Git branch or a Git tag in the source repository, or "local" for local actions.

    Returns:
        Tuple of the action script's full path and the action's source string.
    """
    action_display_name = get_action_display_name(action_name, action_version)

    if action_version == "local":
        # local directory
        action_script_path = retrieve_ci_action_script_local(action_name)
        action_source = f"'{action_script_path}'"
        logger.debug(f"Retrieved local action '{action_name}'.")
    else:
        # TODO: retrieve from cache here if available
        cached = False
        if cached:
            raise NotImplementedError("Retrieving actions from cache is not implemented yet.")
        else:
            with loading_animation(f"Retrieving action from Git"):
                start_time = time.perf_counter()

                # Git repo
                actions_git_repo_url = retrieve_environment_variable(
                    "PYTHON_CI_ACTIONS_GIT_REPO_URL",
                    f"URL address of the Git repository is required to pull the code for action '{action_display_name}'.",
                    fallback_value=DEFAULT_ACTION_REPO_URL
                )
                actions_ssh_private_key = retrieve_environment_variable(
                    "PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY",
                    "SSH private key is required to pull actions from the private remote Git repositories.",
                    fallback_value=get_default_ssh_private_key
                )

                action_script_path = retrieve_ci_action_script_from_git(
                    git_repo_url=actions_git_repo_url,
                    action_name=action_name,
                    action_version=action_version,
                    ssh_private_key=actions_ssh_private_key
                )

                action_source = f"'{action_version}' at '{actions_git_repo_url}'"

                duration = time.perf_counter() - start_time

            logger.info(f"Retrieved action '{action_display_name}' from Git in {duration:.3f} seconds.")

    return action_script_path, action_source
