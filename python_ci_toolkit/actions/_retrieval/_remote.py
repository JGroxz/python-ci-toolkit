"""
Functions for retrieving actions from remote sources.
"""

import hashlib
import logging
import sys
from pathlib import Path

from .._constants import DOWNLOADED_ACTION_REPOS_DIRECTORY
from .._logging import get_action_display_name
from .._utils import timeit
from ...git import git_ssh_credentials
from ...shell import run_shell_command

logger = logging.getLogger(__name__)


def get_clone_directory_from_action_repo_url(git_repo_url: str) -> Path:
    """
    Generates a deterministic local path to clone the given Git repository based on its URL.

    Args:
        git_repo_url: URL of the Git repository to generate path for.

    Returns:
        Local path generated based on the provided Git repo URL.
    """
    git_repo_hash = hashlib.md5(git_repo_url.encode()).hexdigest()
    cloned_repo_path = DOWNLOADED_ACTION_REPOS_DIRECTORY / git_repo_hash
    return cloned_repo_path


@timeit
def retrieve_action_repo(git_repo_url: str, ssh_private_key: str = None) -> Path:
    """
    Retrieves the given Git repository into the standard actions cache location.

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
    DOWNLOADED_ACTION_REPOS_DIRECTORY.mkdir(exist_ok=True, parents=True)

    # generate local repo path based on remote
    cloned_repo_path = get_clone_directory_from_action_repo_url(git_repo_url)

    # default kwargs for run_shell_command() calls
    RUN_KWARGS = dict(cwd=cloned_repo_path, silence_output=True, use_wsl_on_windows=False)

    with git_ssh_credentials(ssh_private_key):
        if not cloned_repo_path.exists():
            logger.debug(f"Cloning action repo from '{git_repo_url}' to '{cloned_repo_path}'.")

            # execute a fresh pull
            run_shell_command(f'git clone "{git_repo_url}" "{cloned_repo_path}"', **RUN_KWARGS)
        else:
            logger.debug(f"Using cached action repo of '{git_repo_url}' from '{cloned_repo_path}'.")

        # fetch all available remote branches and tags
        run_shell_command("git fetch --tags", **RUN_KWARGS)

        # switch existing clone to main branch
        run_shell_command("git checkout main", **RUN_KWARGS)

    # check if actions directory is present before returning it
    actions_directory = cloned_repo_path / "actions"
    if not actions_directory.exists():
        logger.error(f"Repository '{git_repo_url}' does not have 'actions' directory in it.")
        sys.exit(1)

    return actions_directory


@timeit
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

    # settings for running CLI commands
    run_shell_command_kwargs = {
        "cwd": cloned_actions_directory,
        "silence_output": (logger.getEffectiveLevel() > logging.DEBUG),
        "use_wsl_on_windows": False
    }

    with git_ssh_credentials(ssh_private_key):
        # clone the repo
        if action_version is None:
            # if no version specified, use the main branch (it's checked out by default)
            run_shell_command("git merge origin/main", **run_shell_command_kwargs)
        else:
            # find branches or tags matching the given version
            result = run_shell_command(f'git show-ref', **run_shell_command_kwargs)
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
            run_shell_command(f'git checkout "{action_version}"', **run_shell_command_kwargs)

            # if on a branch, pull updates
            result = run_shell_command(f'git status', **run_shell_command_kwargs)
            is_on_a_branch = ("On branch" in result.output)
            if is_on_a_branch:
                run_shell_command(f'git merge "origin/{action_version}"', **run_shell_command_kwargs)

    # check if the repo had the requested action script
    if not action_script_path.exists():
        logger.error(f"Cloned repository '{git_repo_url}' does not include action '{action_name}' (expected script path is '{action_script_path}').\n"
                     f"Please make sure that the remote repository has the required action script.")
        sys.exit(4)

    return action_script_path
