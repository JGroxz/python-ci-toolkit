import time

import pytest

from python_ci_toolkit.logging import configure_ci_logging
from python_ci_toolkit.shell import run_shell_command


def test_retrieve_action_repo():
    from python_ci_toolkit.actions.actions import retrieve_action_repo, DEFAULT_ACTION_REPO_URL
    from python_ci_toolkit.git import get_default_ssh_private_key

    start = time.perf_counter()

    ssh_private_key = get_default_ssh_private_key()
    repo_directory = retrieve_action_repo(git_repo_url=DEFAULT_ACTION_REPO_URL, ssh_private_key=ssh_private_key)

    print(f"Retrieved action repo in {(time.perf_counter() - start) * 1000} ms")
    print(repo_directory)

    assert (repo_directory / "../.git").exists(), \
        "There is no '.git' file in the action repo directory. It means the repo was not cloned."


def test_retrieve_ci_action_script_from_git():
    from python_ci_toolkit.actions.actions import retrieve_ci_action_script_from_git, DEFAULT_ACTION_REPO_URL
    from python_ci_toolkit.git import get_default_ssh_private_key, git_ssh_credentials

    ssh_private_key = get_default_ssh_private_key()
    action_name = "build_dockers"
    action_version = "main"

    action_script_path = retrieve_ci_action_script_from_git(
        git_repo_url=DEFAULT_ACTION_REPO_URL,
        action_name=action_name,
        action_version=action_version,
        ssh_private_key=ssh_private_key
    )

    action_script_directory = action_script_path.parent

    with git_ssh_credentials(ssh_private_key):
        result = run_shell_command(f'git status',
                                      cwd=action_script_directory, silence_output=True, use_wsl_on_windows=False)
        assert action_version in result.output, \
            f"Action repo must be checked out at branch/tag '{action_version}', but it's not:\n{result.output}"


def test_list_actions_in_directory():
    from python_ci_toolkit.actions.actions import list_actions_in_directory, DOWNLOADED_ACTION_REPOS_DIRECTORY

    # local_actions = list_actions_in_directory(LOCAL_ACTIONS_DIRECTORY)
    # print(local_actions)

    downloaded_actions = list_actions_in_directory(DOWNLOADED_ACTION_REPOS_DIRECTORY / "4388b54d60d7fececf2a578d7963a098" / "actions")
    print([x.stem for x in downloaded_actions])


if __name__ == '__main__':
    configure_ci_logging("DEBUG")
    # test_retrieve_action_repo()
    # test_retrieve_ci_action_script_from_git()
    test_list_actions_in_directory()
