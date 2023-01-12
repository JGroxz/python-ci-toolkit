"""
Provides functions to retrieve and run CI actions based on Python scripts.
"""
import logging
import os
import shutil
import stat
import sys
import time
from pathlib import Path
from typing import List

from python_ci_toolkit import pip
from ..environment import assert_environment_variable_set, assert_multiline_environment_variable_set, \
    ci_files_directory, ci_temp_files_directory, get_ci_environment_name, ci_project_root
from ..git import git_ssh_credentials, get_default_ssh_private_key
from ..python import import_module_from_file
from ..shell import run_shell_command

# Constants
ACTION_VERSION_SEPARATOR = "@"
DOWNLOADED_ACTIONS_DIRECTORY_PATH: Path = ci_temp_files_directory.joinpath("downloaded_actions")


def delete_git_repo(repo_path: Path) -> None:
    """
    Deletes Git repository in the given folder.

    Notes:
        Deleting Git directory requires special treatment, because a normal shutil.rmtree() call can fail
        because of certain files in .git folder which get marked as read-only when cloning.

    Args:
        repo_path: Path to the Git repository's folder.
    """

    def on_rm_error(func, path, exc_info):
        # from: https://stackoverflow.com/a/4829285
        os.chmod(path, stat.S_IWRITE)
        os.unlink(path)

    shutil.rmtree(repo_path, onerror=on_rm_error)


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
    action_display_name = f"{action_name}{ACTION_VERSION_SEPARATOR}{action_version}"

    # prepare paths
    action_script_name = f"{action_name}.py"
    cloned_repo_path = ci_temp_files_directory.joinpath("actions_repo_clone")
    action_script_cloned_path = Path(cloned_repo_path, "actions", f"{action_name}", f"{action_name}.py")
    action_local_directory = DOWNLOADED_ACTIONS_DIRECTORY_PATH.joinpath(action_name)
    action_script_local_path = action_local_directory.joinpath(action_script_name)
    action_requirements_local_path = action_local_directory.joinpath("requirements.txt")

    # prepare directories
    os.makedirs(action_local_directory, exist_ok=True)
    os.makedirs(ci_temp_files_directory, exist_ok=True)

    with git_ssh_credentials(ssh_private_key):
        # clone the repo
        if action_version is None:
            # if no version specified, just clone the main branch
            run_shell_command(f'git clone --depth 1 "{git_repo_url}" "{cloned_repo_path}"', silence_output=True,
                              use_wsl_on_windows=False)
        else:
            # find branches or tags matching the given version
            _, output = run_shell_command(f'git ls-remote "{git_repo_url}"', silence_output=True,
                                          use_wsl_on_windows=False)
            output_lines = output.split("\n")
            branch_exists = False
            tag_exists = False
            for line in output_lines:
                if f"refs/heads/{action_version}" in line:
                    branch_exists = True
                if f"refs/tags/{action_version}" in line:
                    tag_exists = True

            # if both a branch and a tag exist with the same name, do not pull to avoid ambiguity
            if tag_exists and branch_exists:
                logging.error(
                    f"Both a branch and a tag named '{action_version}' exist in remote repository '{git_repo_url}'.\n"
                    f"The action '{action_display_name}' wil not be pulled to avoid ambiguity.\n"
                    f"Please remove the redundant branch or tag ('{action_version}') from the repo before pulling this version again.")
                sys.exit(2)

            # if nothing matches the version, there is nothing we can do
            if (not tag_exists) and (not branch_exists):
                logging.error(f"Cannot pull action '{action_display_name}' from Git: "
                              f"remote repository '{git_repo_url}' has neither a branch nor a tag named '{action_version}'.\n"
                              f"Please make sure that the corresponding branch or tag ('{action_version}') exists before pulling this version again.")
                sys.exit(3)

            # clear the way for the new clone
            if cloned_repo_path.exists():
                delete_git_repo(cloned_repo_path)

            # pull whatever is available
            run_shell_command(f'git clone --depth 1 --branch "{action_version}" "{git_repo_url}" "{cloned_repo_path}"',
                              silence_output=True, use_wsl_on_windows=False)

        # check if the repo had the requested action script
        if not action_script_cloned_path.exists():
            logging.error(
                f"Cloned repository '{git_repo_url}' does include action '{action_name}' (expected script path is '{action_script_cloned_path}').\n"
                f"Please make sure that the remote repository has the required action script.")
            sys.exit(4)

        # copy the action script over to the downloaded actions directory
        shutil.copyfile(action_script_cloned_path, action_script_local_path)

        # copy requirements if those are present
        action_requirements_cloned_path = action_script_cloned_path.parent.joinpath("requirements.txt")
        if action_requirements_cloned_path.exists():
            shutil.copyfile(action_requirements_cloned_path, action_requirements_local_path)

        # clean up
        delete_git_repo(cloned_repo_path)

    return action_script_local_path


def retrieve_ci_action_script_local(action_name: str) -> Path:
    """
    Tries to locate the given Python CI action in the current CI project's '.ci/actions' directory.

    Args:
        action_name: Name of the action to locate.

    Returns:
        Full path to the given action's Python file.
    """
    local_ci_actions_folder = ci_files_directory.joinpath("actions")
    action_file_path = Path(local_ci_actions_folder, f"{action_name}.py")

    if not action_file_path.exists():
        raise FileNotFoundError(
            f"Cannot run action '{action_name}' from local file '{action_file_path}': file does not exist.\n"
            f"When you run actions in local mode, make sure that the corresponding action file exists in '.ci/actions' folder in your CI project's root.")

    return action_file_path


def _print_action_header(action_name: str, action_version: str, action_source: str) -> None:
    ci_environment_name = get_ci_environment_name()

    # noinspection PyBroadException
    try:
        import pkg_resources
        version = pkg_resources.get_distribution('python-ci-toolkit').version
    except Exception:
        from ..versions import read_project_version
        version = read_project_version(ci_project_root)

    action_display_name = f"{action_name}{ACTION_VERSION_SEPARATOR}{action_version}";

    logging.info(f"[green]>_[/][rgb(146,202,85)] Running CI action '{action_display_name}'[/]...\n"
                 f"     CI toolkit version: [blue]{version}[/]\n"
                 f"     CI environment: [blue]{ci_environment_name}[/]\n"
                 f"     Action version: [blue]{action_version}[/]\n"
                 f"     Action source: {action_source}", extra={"markup": True, "highlighter": None})


def run_ci_action(action_name: str, action_version: str = None, argv: List[str] = None) -> None:
    """
    Executes CI action by the given action name.
    """
    action_display_name = (action_name
                           if (action_version is None)
                           else f"{action_name}{ACTION_VERSION_SEPARATOR}{action_version}")

    # locate action script
    logging.debug(f"Locating action '{action_display_name}'...")
    if action_version == "local":
        # local folder
        action_script_path = retrieve_ci_action_script_local(action_name)
        action_source = f"'{action_script_path}'"
        logging.debug(f"Retrieved local action '{action_name}'. Running...")
    else:
        # Git repo
        start_time = time.perf_counter()

        actions_git_repo_url = assert_environment_variable_set(
            "PYTHON_CI_ACTIONS_GIT_REPO_URL",
            f"URL address of the Git repository is required to pull the code for action '{action_display_name}'.",
            fallback_value_getter=lambda: "git@bitbucket.org:pyci/python-ci-actions.git")
        actions_ssh_private_key = assert_multiline_environment_variable_set(
            "PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY",
            "SSH private key is required to pull actions from the private remote Git repositories.",
            fallback_value_getter=get_default_ssh_private_key)

        action_script_path = retrieve_ci_action_script_from_git(
            git_repo_url=actions_git_repo_url,
            action_name=action_name,
            action_version=action_version,
            ssh_private_key=actions_ssh_private_key
        )

        branch_or_tag_name = "main" if (action_version is None) else action_version
        action_source = f"'{branch_or_tag_name}' at '{actions_git_repo_url}'"

        duration = time.perf_counter() - start_time
        logging.info(f"Retrieved action '{action_display_name}' from Git in {duration:.3f} seconds.")

    # install action's requirements if present
    action_requirements_path = action_script_path.parent.joinpath("requirements.txt")
    if action_requirements_path.exists():
        logging.debug(f"Action '{action_name}' has requirements file supplied with it. Installing requirements...")
        pip.ensure_requirements_installed(action_requirements_path)
        logging.debug("Requirements installation complete.")

    # prepare action's CLI arguments
    sys.argv = sys.argv[:1]
    if argv is not None:
        sys.argv.extend(argv)

    # run CI action using its cli() method with the given arguments
    try:
        logging.debug(f"Importing Python module of the action '{action_name}'...")
        action_module = import_module_from_file(f"{action_name}", f"{action_script_path}")
        logging.debug("Import completed.")
    except Exception:
        logging.error(
            f"Error when importing Python module from action script '{action_script_path}' (action '{action_display_name}' from {action_source}).")
        raise

    _print_action_header(action_name, action_version, action_source)

    action_module.cli()
