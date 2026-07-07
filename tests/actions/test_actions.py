from __future__ import annotations

import logging
from pathlib import Path

from python_ci_toolkit.shell import run_shell_command


def test_retrieve_action_repo(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_action_repo, get_remote_action_repo
    from python_ci_toolkit.actions.retrieval.sources.local import _LOCAL_ACTIONS_DIRECTORY_RELATIVE

    action_repo_url, action_repo_ssh_private_key = get_remote_action_repo()
    cloned_actions_directory: Path = retrieve_action_repo(action_repo_url, action_repo_ssh_private_key)

    print(cloned_actions_directory)

    cloned_repo_root = cloned_actions_directory
    for _ in _LOCAL_ACTIONS_DIRECTORY_RELATIVE.parts:
        cloned_repo_root = cloned_repo_root.parent

    print(f"Cloned repo root: '{cloned_repo_root}'")

    assert action_repo_url == str(remote_actions_git_repo)
    assert action_repo_ssh_private_key is None
    assert (cloned_repo_root / ".git").exists(), \
        "There is no '.git' file in the action repo directory. It means the repo was not cloned."


def test_retrieve_ci_action_script_from_git(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_ci_action_script_from_git, get_remote_action_repo

    TEST_ACTION_NAME = "hello_world"
    TEST_ACTION_VERSION = "main"

    action_repo_url, action_repo_ssh_private_key = get_remote_action_repo()
    action_script_path = retrieve_ci_action_script_from_git(
        git_repo_url=action_repo_url,
        action_name=TEST_ACTION_NAME,
        action_version=TEST_ACTION_VERSION,
        ssh_private_key=action_repo_ssh_private_key
    )

    action_script_directory = action_script_path.parent

    assert action_repo_url == str(remote_actions_git_repo)
    assert action_repo_ssh_private_key is None
    result = run_shell_command(f'git status',
                               cwd=action_script_directory, silence_output=True, use_wsl_on_windows=False)
    assert TEST_ACTION_VERSION in result.output, \
        f"Action repo must be checked out at branch/tag '{TEST_ACTION_VERSION}', but it's not:\n{result.output}"


def test_remote_action_caching(remote_actions_git_repo: Path, caplog):
    caplog.set_level(logging.DEBUG)

    from python_ci_toolkit.environment.paths import purge_temporary_files
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import DOWNLOADED_ACTION_REPOS_DIRECTORY
    from python_ci_toolkit.actions.retrieval.sources.git.caching import DOWNLOADED_ACTION_CACHE_TIMESTAMPS_DIRECTORY

    def run_test_action_twice():
        # make sure that cached files are not present
        purge_temporary_files()

        assert not DOWNLOADED_ACTION_REPOS_DIRECTORY.exists(), \
            f"Purging the caches must delete the downloaded action repos directory: '{DOWNLOADED_ACTION_REPOS_DIRECTORY}', but it still exists."
        assert not DOWNLOADED_ACTION_CACHE_TIMESTAMPS_DIRECTORY.exists(), \
            f"Purging the caches must delete the downloaded action repos timestamps directory: '{DOWNLOADED_ACTION_CACHE_TIMESTAMPS_DIRECTORY}', but it still exists."

        # define the test action
        TEST_ACTION_NAME = "hello_world"
        TEST_ACTION_VERSION = "main"

        # retrieve the action
        from python_ci_toolkit.actions.retrieval import retrieve_ci_action_script

        action_script_path, action_source = retrieve_ci_action_script(TEST_ACTION_NAME, TEST_ACTION_VERSION)

        assert action_script_path.exists(), \
            f"On the first run, action script must be retrieved from the remote repo, but it's not: '{action_script_path}'"
        assert action_source == f"'{TEST_ACTION_VERSION}' at '{remote_actions_git_repo}'", \
            f"On the first run, action script must be retrieved from Git, but source was: {action_source}"

        # retrieve the action repo again
        action_script_path, action_source = retrieve_ci_action_script(TEST_ACTION_NAME, TEST_ACTION_VERSION)

        assert action_script_path.exists(), \
            f"On the second run, action script must be retrieved from the remote repo, but it's not: '{action_script_path}'"
        assert action_source == f"'{TEST_ACTION_VERSION}' at '{remote_actions_git_repo}' (cached)", \
            f"On the second run, action script must be retrieved from cache, but source was: {action_source}"

    # run the test to verify that caching works
    run_test_action_twice()
    run_test_action_twice()


def test_list_actions_in_directory():
    from python_ci_toolkit.actions.retrieval.sources.local import list_actions_in_directory, LOCAL_ACTIONS_DIRECTORY

    local_actions = list_actions_in_directory(LOCAL_ACTIONS_DIRECTORY)

    EXPECTED_LOCAL_ACTION_NAMES = [
        "complex_test_action"
    ]

    # verify the number
    assert len(local_actions) == len(EXPECTED_LOCAL_ACTION_NAMES), \
        f"Expected to find {len(EXPECTED_LOCAL_ACTION_NAMES)} local actions in '{LOCAL_ACTIONS_DIRECTORY}', but found {len(local_actions)}:\n{local_actions}"

    # verify the names
    local_action_names = [p.stem for p in local_actions]
    for name in EXPECTED_LOCAL_ACTION_NAMES:
        assert name in local_action_names, \
            f"Expected to find action '{name}' in '{LOCAL_ACTIONS_DIRECTORY}', but found only {local_action_names}."
