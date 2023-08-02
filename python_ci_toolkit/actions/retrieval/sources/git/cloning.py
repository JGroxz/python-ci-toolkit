"""
Functions for retrieving action repositories from Git.
"""

import logging
import sys
from pathlib import Path

from .caching import create_action_cache_timestamp
from ....retrieval.sources.local import list_actions_in_directory, LOCAL_ACTIONS_DIRECTORY_RELATIVE
from ....utils import log_execution_time, hash_string
from ....utils.logging import get_action_display_name
from .....environment.paths.internal import ci_temp_files_shared_directory
from .....environment.variables import retrieve_environment_variable
from .....git import git_ssh_credentials, get_default_ssh_private_key
from .....shell import run_shell_command

logger = logging.getLogger(__name__)

DEFAULT_ACTION_REPO_URL = "git@github.com:pyci/python-ci-actions.git"
DOWNLOADED_ACTION_REPOS_DIRECTORY = ci_temp_files_shared_directory / "downloaded_action_repos"


def get_remote_action_repo() -> tuple[str, str]:
    """
    Returns:
        A tuple with:
            - URL of the remote Git repository that contains actions.
            - Secret SSH key to access the remote Git repository.
    """
    actions_git_repo_url = retrieve_environment_variable(
        "PYTHON_CI_ACTIONS_GIT_REPO_URL",
        f"URL address of the Git repository is required to pull the action code.",
        fallback_value=DEFAULT_ACTION_REPO_URL
    )
    actions_ssh_private_key = retrieve_environment_variable(
        "PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY",
        "SSH private key is required to pull actions from the private remote Git repositories.",
        fallback_value=get_default_ssh_private_key
    )

    return actions_git_repo_url, actions_ssh_private_key


def get_clone_directory_from_action_repo_url(git_repo_url: str) -> Path:
    """
    Generates a deterministic local path to clone the given Git repository based on its URL.

    Args:
        git_repo_url: URL of the Git repository to generate path for.

    Returns:
        Local path generated based on the provided Git repo URL.
    """
    cloned_repo_path = DOWNLOADED_ACTION_REPOS_DIRECTORY / hash_string(git_repo_url)
    return cloned_repo_path


@log_execution_time
def retrieve_action_repo(git_repo_url: str, ssh_private_key: str = None) -> Path:
    """
    Retrieves the given Git repository into the standard actions download location.

    Notes:
        This action will return the existing local repo if it was cloned before.
        The repo is guaranteed to have all updates fetched and the main branch checked out.

    Args:
        git_repo_url: URL of the Git repository to pull.
        ssh_private_key: Private SSH key to be used when accessing the specified Git repository (string value).

    Returns:
        Path to the directory in the cloned repository that contains actions.
    """

    # prepare downloads directory
    DOWNLOADED_ACTION_REPOS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    # generate local repo path based on remote
    cloned_repo_path = get_clone_directory_from_action_repo_url(git_repo_url)

    with git_ssh_credentials(ssh_private_key):
        if not cloned_repo_path.exists():
            logger.debug(f"Cloning action repo from '{git_repo_url}' to '{cloned_repo_path}'.")

            # execute a fresh pull
            run_shell_command(f'git clone "{git_repo_url}" "{cloned_repo_path}"', silence_output=True, use_wsl_on_windows=False)
        else:
            logger.debug(f"Using local clone of action repo '{git_repo_url}' at '{cloned_repo_path}'.")

        # default settings for running shell commands inside the cloned repo
        def run_repo_command(c: str):
            return run_shell_command(c, cwd=cloned_repo_path, silence_output=True, use_wsl_on_windows=False)

        # fetch all available remote branches and tags
        run_repo_command("git fetch --tags")

        # switch existing clone to main branch
        run_repo_command("git checkout main")

    # check if actions directory is present before returning it
    actions_directory = cloned_repo_path / LOCAL_ACTIONS_DIRECTORY_RELATIVE
    if not actions_directory.exists():
        logger.error(f"Repository '{git_repo_url}' does not have 'actions' directory in it.")
        sys.exit(1)

    return actions_directory


@log_execution_time
def retrieve_ci_action_script_from_git(git_repo_url: str, action_name: str, action_version: str = None,
                                       ssh_private_key: str = None) -> Path:
    """
    Retrieves Python CI script file with the given name from Git repository specified in 'PYTHON_CI_ACTIONS_GIT_REPO_URL' environment variable.
    If the repository is private, a private SSH key can be supplied in 'PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY' environment variable.

    Notes:
        Action scripts must be located in a Git repository which URL is specified in 'PYTHON_CI_ACTIONS_GIT_REPO_URL' environment variable.
        Repository must contain a folder named 'actions', where each action script must be located inside an individual folder of the same name, e.g.:
        'build_dockers.py' must be located in 'GIT_REPO_ROOT/actions/build_dockers/build_dockers.py'.

        Downloaded scripts will be placed in the folder named '.ci' at the root of the current CI project.

    Args:
        git_repo_url: URL of the Git repository to pull the action from.
        action_name: Name of the action to download.
        action_version: Version of the action to pull. Can be either a Git branch or a Git tag in the source repository.
        ssh_private_key: Private SSH key to be used when accessing the specified Git repository (string value).

    Returns:
        Local path to the downloaded action file.
    """

    # retrieve repo
    cloned_actions_directory = retrieve_action_repo(git_repo_url, ssh_private_key)

    # prepare paths
    action_display_name = get_action_display_name(action_name, action_version)
    action_script_directory = cloned_actions_directory / f"{action_name}"
    action_script_path = action_script_directory / f"{action_name}.py"

    # default settings for running shell commands
    def run_repo_command(c: str):
        return run_shell_command(c, cwd=cloned_actions_directory, silence_output=True, use_wsl_on_windows=False)

    # clone the repo
    with git_ssh_credentials(ssh_private_key):
        if action_version is None:
            # if no version specified, use the main branch (it's checked out by default)
            run_repo_command('git merge origin/main')
        else:
            # find branches or tags matching the given version
            result = run_repo_command(f'git show-ref')
            output = result.output
            branch_exists = (f"refs/heads/{action_version}" in output) or (f"refs/remotes/origin/{action_version}" in output)
            tag_exists = (f"refs/tags/{action_version}" in output)

            if branch_exists:
                logger.debug(f"'{action_version}' is a branch in '{git_repo_url}'.")
            if tag_exists:
                logger.debug(f"'{action_version}' is a tag in '{git_repo_url}'.")

            # if both a branch and a tag exist with the same name, do not pull to avoid ambiguity
            if tag_exists and branch_exists:
                logger.error(f"Both a branch and a tag named '{action_version}' exist in remote repository '{git_repo_url}'.\n"
                             f"The action '{action_display_name}' wil not be pulled to avoid ambiguity.\n"
                             f"Please remove the redundant branch or tag ('{action_version}') from the repo before pulling this version again.")
                sys.exit(2)

            # if nothing matches the version, there is nothing we can do
            if (not tag_exists) and (not branch_exists):
                logger.error(f"Cannot pull action '{action_display_name}' from Git:\n"
                             f"  Repository '{git_repo_url}' has neither a branch nor a tag named '{action_version}'.\n"
                             f"  Please make sure that the corresponding branch or tag ('{action_version}') exists before pulling this version again.")
                sys.exit(3)

            # checkout required branch/tag
            run_repo_command(f'git checkout "{action_version}"')

            # if on a branch, pull updates
            result = run_repo_command(f'git status')
            is_on_a_branch = ("On branch" in result.output)
            if is_on_a_branch:
                run_repo_command(f'git merge "origin/{action_version}"')

    # create cache entries for each complex action script in the cloned repo
    for action_path in list_actions_in_directory(cloned_actions_directory, include_simple_actions=False):
        create_action_cache_timestamp(
            git_repo_url=git_repo_url,
            action_name=action_path.stem,  # <- name of the action is the name of the script
            action_version=action_version
        )

    # check if the repo had the requested action script
    if not action_script_path.exists():
        logger.error(f"Cloned repository '{git_repo_url}' does not include action '{action_name}' (expected script path is '{action_script_path}').\n"
                     f"Please make sure that the remote repository has the required action script.")
        sys.exit(4)

    return action_script_path
