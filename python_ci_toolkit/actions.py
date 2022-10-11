"""
Provides functions to retrieve and run CI actions based on Python scripts.
"""
import io
import os
import shutil
import stat
import time
from pathlib import Path
from typing import Dict

from python_ci_toolkit.environment import assert_environment_variable_set, ci_project_root
from python_ci_toolkit.shell import run_shell_command

CI_SCRIPTS_DIRECTORY_NAME = ".ci"
CI_SCRIPTS_DIRECTORY_PATH: Path = Path(ci_project_root, CI_SCRIPTS_DIRECTORY_NAME)


def retrieve_ci_action_script(action_name: str) -> Path:
    """
    Retrieves Python CI script file with the given name from Git repository specified in 'PYTHON_CI_ACTIONS_GIT_REPO_URL' environment variable.
    If the repository is private, a private SSH key can be supplied in 'PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY' environment variable.

    Notes:
        Action scripts must be located in a Git repository which URL is specified in 'PYTHON_CI_ACTIONS_GIT_REPO_URL' environment variable.
        Repository must contain a folder named 'actions', where each action script must be located inside an individual folder of the same name, e.g.:
        'build_dockers.py' must be located in 'GIT_REPO_ROOT/actions/build_dockers/build_dockers.py'.

        Downloaded scripts will be placed in the folder named '.ci' at the root of the current CI project.

    Args:
        action_name: Name of the action to download.

    Returns:
        Local path to the downloaded action file.
    """
    start_time = time.perf_counter()

    # retrieve configuration from env
    actions_git_repo_url = assert_environment_variable_set("PYTHON_CI_ACTIONS_GIT_REPO_URL")
    actions_ssh_private_key = assert_environment_variable_set("PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY")

    # prepare paths
    action_script_name = f"{action_name}.py"
    action_script_local_path = Path(CI_SCRIPTS_DIRECTORY_PATH, action_script_name)

    print("Setting up SSH...")
    temp_location = Path(CI_SCRIPTS_DIRECTORY_PATH, f"actions_clone")
    os.makedirs(temp_location, exist_ok=True)

    ssh_key_file_location = Path(temp_location, "actions_ssh_key")
    with io.open(ssh_key_file_location, "w", newline="\n") as file:
        file.write(actions_ssh_private_key)

    print("Cloning...")
    clone_location = Path(temp_location, "actions_repo")

    os.environ["GIT_SSH_COMMAND"] = f"ssh -i \"{ssh_key_file_location}\" -o IdentitiesOnly=yes"
    run_shell_command(f'git clone --depth 1 "{actions_git_repo_url}" "{clone_location}"', silence_output=True, use_wsl_on_windows=False)

    cloned_action_script_path = Path(clone_location, "actions", action_name, f"{action_name}.py")
    shutil.copyfile(cloned_action_script_path, action_script_local_path)

    def on_rm_error(func, path, exc_info):
        # from: https://stackoverflow.com/a/4829285
        os.chmod(path, stat.S_IWRITE)
        os.unlink(path)

    shutil.rmtree(temp_location, onerror=on_rm_error)

    duration = time.perf_counter() - start_time
    print(f"Retrieved action '{action_name}' in {duration:.3f} seconds.")

    return action_script_local_path


def run_ci_action(action_name: str, args: Dict) -> None:
    """
    Executes CI action by the given action name.
    """
    os.environ["PYTHON_CI_ACTIONS_GIT_REPO_URL"] = "git@bitbucket.org:pyci/python-ci-actions.git"  # TODO: remove
    os.environ["PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY"] = """***REMOVED PRIVATE KEY***
"""
    # TODO: remove
    action_script_path = retrieve_ci_action_script(action_name)
    # TODO: run CI action


def cli() -> None:
    """
    Executes CI action.
    """
    # TODO: get CI action name from the first cmd arg
    action_name = "build_dockers"
    # TODO: get the remaining cmd args
    args = {}
    run_ci_action(action_name, args)


if __name__ == '__main__':
    cli()
