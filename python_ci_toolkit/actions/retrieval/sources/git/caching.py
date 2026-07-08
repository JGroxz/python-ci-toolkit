"""
Functions for managing the cache of action files retrieved from remote sources.
"""

import logging
import sys
from pathlib import Path

from ..local import get_complex_action_path_in_directory, _LOCAL_ACTIONS_DIRECTORY_RELATIVE
from ....utils import hash_string
from ....utils.file_timestamps import time_since_file_timestamp, reset_file_timestamp
from ....utils.logging import get_action_display_name
from ....logging.logging import LOG_WITH_MARKUP
from .....environment.paths.internal import ci_temp_files_shared_directory
logger = logging.getLogger(__name__)

DOWNLOADED_ACTION_CACHE_TIMESTAMPS_DIRECTORY = ci_temp_files_shared_directory / "downloaded_action_cache_timestamps"

# Defaults
DEFAULT_REMOTE_ACTIONS_CACHE_INVALIDATION_TIMEOUT = 60
"""
Time during which the action cache is considered fresh, in seconds.
"""


def _get_action_cache_timestamp_path(git_repo_url: str,
                                     action_name: str,
                                     action_version: str) -> Path:
    """
    Returns the path to the file that stores the timestamp of the last cache update for the given remote Git repository.

    Args:
        git_repo_url: The URL of the remote Git repository from which the action files were retrieved.
        action_name: The name of the action that was retrieved.
        action_version: The version of the action files that were retrieved.

    Returns:
        The path to the file that stores the timestamp of the last cache update for the given remote Git repository.
        The file is not guaranteed to exist.
    """
    repo_hash = hash_string(git_repo_url)
    cache_directory = DOWNLOADED_ACTION_CACHE_TIMESTAMPS_DIRECTORY / repo_hash / action_version

    return cache_directory / f"{action_name}.timestamp"


def _resolve_action_cache_timestamp_path(action_name: str,
                                         action_version: str) -> Path | None:
    """
    Retrieves the path to the file that acts as a timestamp of the last cache update for the given action (if one exists).

    Notes:
        As there is no way to know which Git repository the action came from, this function will scan the existing caches
        to find the first one that matches the given action name and version.

    Args:
        action_name: The name of the action.
        action_version: The version of the action.

    Returns:
        The path to the file that acts as a timestamp of the last cache update for the given action.
        If no such file exists, returns None.
    """
    if not DOWNLOADED_ACTION_CACHE_TIMESTAMPS_DIRECTORY.exists():
        # we don't have any caches yet
        logger.debug(f"Did not find cache timestamp for action '{get_action_display_name(action_name, action_version)}': no cache directory exists yet.")
        return None

    for repo_directory in DOWNLOADED_ACTION_CACHE_TIMESTAMPS_DIRECTORY.iterdir():
        if not repo_directory.is_dir():
            # we only care about directories
            continue

        expected_version_directory = repo_directory / action_version
        if not expected_version_directory.exists():
            # we don't have cache for this version in this repo
            continue

        expected_action_cache_path = expected_version_directory / f"{action_name}.timestamp"
        if not expected_action_cache_path.exists():
            # we don't have cache for this action in this repo
            continue

        # we found the action
        return expected_action_cache_path

    # we don't have cache for this action
    logger.debug(f"No cache timestamp available for action '{get_action_display_name(action_name, action_version)}'.")
    return None


def create_action_cache_timestamp(git_repo_url: str,
                                  action_name: str,
                                  action_version: str) -> None:
    """
    Creates a new cache timestamp for the given action version from the given Git repository.

    Args:
        git_repo_url: The URL of the remote Git repository from which the action files were retrieved.
        action_name: The name of the action.
        action_version: The version of the action.
    """
    cache_timestamp_file_path = _get_action_cache_timestamp_path(git_repo_url, action_name, action_version)
    reset_file_timestamp(cache_timestamp_file_path)

    logger.debug(f"Created cache timestamp for action '{get_action_display_name(action_name, action_version)}' from '{git_repo_url}'.")


def reset_action_cache_timestamp(action_name: str, action_version: str):
    """
    Resets the cache freshness timer for the Git repository the given action comes from.

    Args:
        action_name: Name of the action.
        action_version: Version of the action.
    """
    timestamp_file_path = _resolve_action_cache_timestamp_path(action_name, action_version)
    if timestamp_file_path is None:
        # we don't have cache for this action
        return

    # we have the repo cache dir and version – update timestamps of all action caches here
    action_repo_timestamps_directory = timestamp_file_path.parent
    for action_timestamp_file in action_repo_timestamps_directory.iterdir():
        reset_file_timestamp(action_timestamp_file)
        logger.debug(f"Successfully reset cache timestamp for action '{get_action_display_name(action_timestamp_file.stem, action_version)}'.")


def is_action_cache_fresh(action_name: str, action_version: str) -> bool:
    """
    Checks whether the locally cached files of the given action exist and are up-to-date.

    Args:
        action_name: The name of the action.
        action_version: The version of the action.

    Returns:
        True if the cached action files are up-to-date, False otherwise.
    """
    timestamp_file_path = _resolve_action_cache_timestamp_path(action_name, action_version)
    if timestamp_file_path is None:
        # we don't have cache for this action
        return False

    # check if the cache is fresh enough
    cache_age = time_since_file_timestamp(timestamp_file_path)
    is_fresh = cache_age < DEFAULT_REMOTE_ACTIONS_CACHE_INVALIDATION_TIMEOUT

    # log
    state_name = "fresh" if is_fresh else "stale"
    logger.debug(f"Action cache for '{get_action_display_name(action_name, action_version)}' is {state_name} "
                 f"(age {cache_age:.3f} s, limit {DEFAULT_REMOTE_ACTIONS_CACHE_INVALIDATION_TIMEOUT} s).")

    return is_fresh


def retrieve_ci_action_script_from_cache(git_repo_url: str, action_name: str, action_version: str) -> Path:
    """
    Retrieves the given CI action script from the local cache path.
    """
    from .cloning import checkout_git_action_ref, get_clone_directory_from_action_repo_url

    # prepare paths
    repo_directory = get_clone_directory_from_action_repo_url(git_repo_url)
    action_script_path = get_complex_action_path_in_directory(repo_directory / _LOCAL_ACTIONS_DIRECTORY_RELATIVE, action_name)

    # switch to the desired version in the repo (it's assumed to exist because we have the cached timestamp for this version)
    checkout_git_action_ref(repo_directory, git_repo_url, action_name, action_version)

    # check if the repo had the requested action script
    if not action_script_path.exists():
        logger.error(f"Cloned repository '{git_repo_url}' does not include action [pyci.action]'{action_name}'[/] (expected script path is '{action_script_path}').\n"
                     f"Please make sure that the remote repository has the required action script.\n"
                     f"If you are sure the action script exists, remove the action cache files and try again.", **LOG_WITH_MARKUP)
        sys.exit(5)

    return action_script_path
