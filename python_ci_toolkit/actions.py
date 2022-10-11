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


def download_ci_action_script(action_name: str) -> Path:
    """
    Downloads the CI script file from the default location based on the given action name.

    Notes:
        Action scripts must be located in a folder which URL is specified in 'PYTHON_CI_ACTIONS_DIRECTORY_URL'
        environment variable (it can be an online resource). Inside the folder, each action script must be located
        inside an individual folder of the same name, e.g.:
        'build_dockers.py' must be located in 'ACTIONS_FOLDER/build_dockers/build_dockers.py'.

        Downloaded scripts will be placed in the folder named '.ci' at the root of the CI project.

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

    # params = {
    #     "client_id": actions_oauth_key,
    #     "client_secret": actions_oauth_secret,
    #     "grant_type": "authorization_code",
    #     "code": actions_oauth_code,
    # }
    # endpoint = "https://bitbucket.org/site/oauth2/access_token"
    # response = requests.post(endpoint,  data=params, params=params, headers={"Accept": "application/json"}).json()
    # print(f"Got token: {token}")
    # access_token = response['access_token']

    # download
    print(f"Downloading action '{action_name}' from '{action_script_url}'...")
    # request.urlretrieve(action_script_url, action_script_local_path)
    print(f"Action '{action_name}' is downloaded to '{action_script_local_path}'.")

    return action_script_local_path


def run_ci_action(action_name: str, args: Dict) -> None:
    """
    Executes CI action by the given action name.
    """
    os.environ["PYTHON_CI_ACTIONS_DIRECTORY_URL"] = "https://bitbucket.org/pyci/python-ci-actions/raw/main/actions/"  # TODO: remove
    # os.environ["PYTHON_CI_ACTIONS_USER"] = "jgroxz"  # TODO: remove
    # os.environ["PYTHON_CI_ACTIONS_PASS"] = "ATBB5pA3Y5bGS382Xp7KB7f4wEdmC862B71A"  # TODO: remove
    # os.environ["PYTHON_CI_ACTIONS_OAUTH_ID"] = "sHE43VpSaGEcYG2Xgz"  # TODO: remove
    # os.environ["PYTHON_CI_ACTIONS_OAUTH_SECRET"] = "5NNWCezkdFSsgx4DxdaKXeLMsqgqkEFV"  # TODO: remove
    # os.environ["PYTHON_CI_ACTIONS_OAUTH_CODE"] = "A8xEdkMGDzzyupV5sz"  # TODO: remove
    os.environ["PYTHON_CI_ACTIONS_GIT_REPO_URL"] = "git@bitbucket.org:pyci/python-ci-actions.git"  # TODO: remove
    os.environ["PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY"] = """***REMOVED PRIVATE KEY***
"""
    # TODO: remove
    action_script_path = download_ci_action_script(action_name)
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
