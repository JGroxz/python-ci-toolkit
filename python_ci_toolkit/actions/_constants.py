"""
Constants used throughout the actions package.
"""

from ..environment.paths import _ci_temp_files_shared_directory, ci_files_directory

# Constants
ACTION_VERSION_SEPARATOR = "@"
DOWNLOADED_ACTION_REPOS_DIRECTORY = _ci_temp_files_shared_directory / "downloaded_action_repos"
LOCAL_ACTIONS_DIRECTORY = ci_files_directory / "actions"
DEFAULT_ACTION_REPO_URL = "git@github.com:pyci/python-ci-actions.git"
