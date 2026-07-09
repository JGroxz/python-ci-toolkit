"""
Functions for locating and retrieving local and remote action files.
"""
import logging
import time
from pathlib import Path

from .sources.git.caching import is_action_cache_fresh, retrieve_ci_action_script_from_cache
from .sources.git.cloning import require_remote_action_repo, retrieve_ci_action_script_from_git
from .sources.local import retrieve_ci_action_script_local
from ..constants import ACTION_VERSION_DEFAULT_REMOTE_STRING, ACTION_VERSION_LOCAL_STRING
from ..logging.logging import LOG_WITH_MARKUP
from ..utils import log_execution_time, Stopwatch
from ..utils.logging import loading_animation, get_action_display_name

logger = logging.getLogger(__name__)


@log_execution_time
def retrieve_ci_action_script(action_name: str, action_version: str = None) -> tuple[Path, str]:
    """
    Retrieves the given CI action script from the local '.ci/actions' folder or from a remote Git repository.

    Args:
        action_name: Name of the action to retrieve.
        action_version: Version of the action to retrieve. Can be either a Git branch or a Git tag in the source repository, or "local" for local actions.

    Returns:
        Tuple containing:
            - Full path to the retrieved action script file.
            - A string explaining from where the action script was retrieved.
    """
    if action_version == ACTION_VERSION_LOCAL_STRING:
        # local directory
        action_script_path = retrieve_ci_action_script_local(action_name)
        action_source = f"'{action_script_path}'"
        logger.debug(f"Retrieved local action [pyci.action]'{action_name}'[/].", **LOG_WITH_MARKUP)
    else:
        action_version = action_version or ACTION_VERSION_DEFAULT_REMOTE_STRING
        action_display_name = get_action_display_name(action_name, action_version)

        # get remote actions repo configuration
        action_repo_url = require_remote_action_repo()

        if is_action_cache_fresh(action_repo_url, action_name, action_version):
            # from cache
            with Stopwatch() as sw, loading_animation(f"Retrieving action from cache..."):
                action_script_path = retrieve_ci_action_script_from_cache(
                    git_repo_url=action_repo_url,
                    action_name=action_name,
                    action_version=action_version
                )

                action_source = f"'{action_version}' at '{action_repo_url}' (cached)"

            logger.debug(f"Retrieved action '{action_display_name}' from cache in {sw.elapsed_time_ms:.0f} ms.")
        else:
            # from remote Git repo
            start_time = time.perf_counter()

            with loading_animation(f"Retrieving action from Git..."):

                action_script_path = retrieve_ci_action_script_from_git(
                    git_repo_url=action_repo_url,
                    action_name=action_name,
                    action_version=action_version,
                )

                action_source = f"'{action_version}' at '{action_repo_url}'"

            duration = time.perf_counter() - start_time
            logger.debug(f"Retrieved action '{action_display_name}' from Git in {duration:.3f} seconds.")

    return action_script_path, action_source
