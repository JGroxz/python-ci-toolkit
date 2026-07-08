from __future__ import annotations

import logging
from pathlib import Path

import pytest

from python_ci_toolkit.shell import run_shell_command


def _get_cloned_repo_root(cloned_actions_directory: Path) -> Path:
    from python_ci_toolkit.actions.retrieval.sources.local import _LOCAL_ACTIONS_DIRECTORY_RELATIVE

    cloned_repo_root = cloned_actions_directory
    for _ in _LOCAL_ACTIONS_DIRECTORY_RELATIVE.parts:
        cloned_repo_root = cloned_repo_root.parent

    return cloned_repo_root


def _write_remote_hello_world_action(repo_path: Path, description: str) -> None:
    remote_action_file = repo_path / ".ci" / "actions" / "hello_world" / "hello_world.py"
    remote_action_file.write_text(
        '"""\n'
        f'{description}\n'
        '"""\n'
        '\n'
        '\n'
        'def main() -> None:\n'
        '    print("hello world")\n',
        encoding="utf-8"
    )


def _create_remote_actions_git_repo(repo_path: Path, description: str) -> Path:
    action_directory = repo_path / ".ci" / "actions" / "hello_world"
    action_directory.mkdir(parents=True)
    _write_remote_hello_world_action(repo_path, description)

    run_shell_command("git init", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    run_shell_command("git symbolic-ref HEAD refs/heads/main", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    _commit_remote_action_repo(repo_path, "Add hello world action")

    return repo_path


def _create_git_repo_without_actions(repo_path: Path) -> Path:
    repo_path.mkdir(parents=True)
    (repo_path / "README.md").write_text("No CI actions here.\n", encoding="utf-8")

    run_shell_command("git init", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    run_shell_command("git symbolic-ref HEAD refs/heads/main", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    _commit_remote_action_repo(repo_path, "Add readme")

    return repo_path


def _commit_remote_action_repo(repo_path: Path, message: str) -> None:
    run_shell_command("git add .", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    run_shell_command(
        f'git -c user.name="Python CI Toolkit Tests" -c user.email="tests@example.invalid" commit -m "{message}"',
        cwd=repo_path,
        silence_output=True,
        use_wsl_on_windows=False
    )


def _create_remote_action_branch(repo_path: Path, branch_name: str, description: str) -> None:
    run_shell_command(f'git checkout -b "{branch_name}"', cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    _write_remote_hello_world_action(repo_path, description)
    _commit_remote_action_repo(repo_path, f"Update hello world action on {branch_name}")
    run_shell_command("git checkout main", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)


def _create_remote_action_tag(repo_path: Path, tag_name: str, description: str) -> None:
    _write_remote_hello_world_action(repo_path, description)
    _commit_remote_action_repo(repo_path, f"Update hello world action for {tag_name}")
    run_shell_command(f'git tag "{tag_name}"', cwd=repo_path, silence_output=True, use_wsl_on_windows=False)


def test_retrieve_action_repo(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_action_repo, get_remote_action_repo

    action_repo = get_remote_action_repo()
    assert action_repo is not None
    action_repo_url, action_repo_ssh_private_key = action_repo
    cloned_actions_directory: Path = retrieve_action_repo(action_repo_url, action_repo_ssh_private_key)

    print(cloned_actions_directory)

    cloned_repo_root = _get_cloned_repo_root(cloned_actions_directory)

    print(f"Cloned repo root: '{cloned_repo_root}'")

    assert action_repo_url == str(remote_actions_git_repo)
    assert action_repo_ssh_private_key is None
    assert (cloned_repo_root / ".git").exists(), \
        "There is no '.git' file in the action repo directory. It means the repo was not cloned."


def test_retrieve_action_repo_reclones_invalid_cached_path(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import (
        get_clone_directory_from_action_repo_url,
        retrieve_action_repo,
    )

    action_repo_url = str(remote_actions_git_repo)
    cloned_repo_root = get_clone_directory_from_action_repo_url(action_repo_url)
    cloned_repo_root.mkdir(parents=True)
    invalid_cache_file = cloned_repo_root / "not-a-git-repo.txt"
    invalid_cache_file.write_text("invalid cache", encoding="utf-8")

    cloned_actions_directory = retrieve_action_repo(action_repo_url)

    assert (cloned_repo_root / ".git").exists()
    assert not invalid_cache_file.exists()
    assert (cloned_actions_directory / "hello_world" / "hello_world.py").exists()


def test_retrieve_action_repo_reclones_cached_clone_with_wrong_origin(
    tmp_path: Path,
    remote_actions_git_repo: Path,
):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import (
        get_clone_directory_from_action_repo_url,
        retrieve_action_repo,
    )

    repo_a_url = str(remote_actions_git_repo)
    repo_b = _create_remote_actions_git_repo(tmp_path / "other-remote-actions", "Wrong origin hello world action.")
    cloned_repo_root = get_clone_directory_from_action_repo_url(repo_a_url)
    cloned_repo_root.parent.mkdir(parents=True, exist_ok=True)

    run_shell_command(
        f'git clone "{repo_b}" "{cloned_repo_root}"',
        silence_output=True,
        use_wsl_on_windows=False,
    )

    cloned_actions_directory = retrieve_action_repo(repo_a_url)

    origin = run_shell_command(
        "git config --get remote.origin.url",
        cwd=cloned_repo_root,
        silence_output=True,
        use_wsl_on_windows=False,
    )
    cloned_action_file = cloned_actions_directory / "hello_world" / "hello_world.py"

    assert origin.output_stripped == repo_a_url
    assert "Remote hello world action." in cloned_action_file.read_text(encoding="utf-8")


def test_retrieve_action_repo_resets_dirty_cached_clone(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_action_repo

    action_repo_url = str(remote_actions_git_repo)
    cloned_actions_directory = retrieve_action_repo(action_repo_url)
    cloned_repo_root = _get_cloned_repo_root(cloned_actions_directory)
    cloned_action_file = cloned_actions_directory / "hello_world" / "hello_world.py"
    untracked_file = cloned_repo_root / "untracked.tmp"

    cloned_action_file.write_text("dirty local cache change", encoding="utf-8")
    untracked_file.write_text("dirty local cache file", encoding="utf-8")

    retrieve_action_repo(action_repo_url)

    assert "Remote hello world action." in cloned_action_file.read_text(encoding="utf-8")
    assert not untracked_file.exists()
    status = run_shell_command(
        "git status --short",
        cwd=cloned_repo_root,
        silence_output=True,
        use_wsl_on_windows=False,
    )
    assert status.output_stripped == ""


def test_retrieve_action_repo_updates_cached_main_branch(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_action_repo

    action_repo_url = str(remote_actions_git_repo)
    cloned_actions_directory = retrieve_action_repo(action_repo_url)
    cloned_action_file = cloned_actions_directory / "hello_world" / "hello_world.py"

    _write_remote_hello_world_action(remote_actions_git_repo, "Updated remote hello world action.")
    _commit_remote_action_repo(remote_actions_git_repo, "Update hello world action")

    retrieve_action_repo(action_repo_url)

    assert "Updated remote hello world action." in cloned_action_file.read_text(encoding="utf-8")


def test_retrieve_ci_action_script_defaults_to_main(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval import retrieve_ci_action_script
    from python_ci_toolkit.environment.paths import purge_temporary_files

    purge_temporary_files()

    action_script_path, action_source = retrieve_ci_action_script("hello_world", None)

    assert action_script_path.exists()
    assert action_source == f"'main' at '{remote_actions_git_repo}'"


def test_retrieve_ci_action_script_from_git(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_ci_action_script_from_git, get_remote_action_repo

    TEST_ACTION_NAME = "hello_world"
    TEST_ACTION_VERSION = "main"

    action_repo = get_remote_action_repo()
    assert action_repo is not None
    action_repo_url, action_repo_ssh_private_key = action_repo
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


def test_retrieve_ci_action_script_from_git_checks_out_branch(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_ci_action_script_from_git

    TEST_ACTION_NAME = "hello_world"
    TEST_ACTION_VERSION = "feature/hello-world"
    _create_remote_action_branch(
        remote_actions_git_repo,
        TEST_ACTION_VERSION,
        "Feature branch hello world action."
    )

    action_script_path = retrieve_ci_action_script_from_git(
        git_repo_url=str(remote_actions_git_repo),
        action_name=TEST_ACTION_NAME,
        action_version=TEST_ACTION_VERSION,
    )
    cloned_repo_root = _get_cloned_repo_root(action_script_path.parent.parent)
    current_branch = run_shell_command(
        "git branch --show-current",
        cwd=cloned_repo_root,
        silence_output=True,
        use_wsl_on_windows=False,
    )

    assert "Feature branch hello world action." in action_script_path.read_text(encoding="utf-8")
    assert current_branch.output_stripped == TEST_ACTION_VERSION


def test_retrieve_ci_action_script_from_git_checks_out_tag(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_ci_action_script_from_git

    TEST_ACTION_NAME = "hello_world"
    TEST_ACTION_VERSION = "v1.0.0"
    _create_remote_action_tag(remote_actions_git_repo, TEST_ACTION_VERSION, "Tagged hello world action.")

    action_script_path = retrieve_ci_action_script_from_git(
        git_repo_url=str(remote_actions_git_repo),
        action_name=TEST_ACTION_NAME,
        action_version=TEST_ACTION_VERSION,
    )
    cloned_repo_root = _get_cloned_repo_root(action_script_path.parent.parent)
    current_branch = run_shell_command(
        "git symbolic-ref -q --short HEAD",
        cwd=cloned_repo_root,
        silence_output=True,
        raise_on_error=False,
        use_wsl_on_windows=False,
    )
    cloned_head = run_shell_command("git rev-parse HEAD", cwd=cloned_repo_root, silence_output=True, use_wsl_on_windows=False)
    tag_head = run_shell_command(f'git rev-list -n 1 "{TEST_ACTION_VERSION}"', cwd=remote_actions_git_repo, silence_output=True, use_wsl_on_windows=False)

    assert "Tagged hello world action." in action_script_path.read_text(encoding="utf-8")
    assert current_branch.is_failed
    assert cloned_head.output_stripped == tag_head.output_stripped


def test_retrieve_ci_action_script_from_git_rejects_ambiguous_branch_and_tag(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_ci_action_script_from_git
    from python_ci_toolkit.actions.retrieval.exceptions import AmbiguousGitActionRefError

    TEST_ACTION_VERSION = "release"
    _create_remote_action_branch(remote_actions_git_repo, TEST_ACTION_VERSION, "Release branch hello world action.")
    run_shell_command(f'git tag "{TEST_ACTION_VERSION}"', cwd=remote_actions_git_repo, silence_output=True, use_wsl_on_windows=False)

    with pytest.raises(AmbiguousGitActionRefError) as error:
        retrieve_ci_action_script_from_git(
            git_repo_url=str(remote_actions_git_repo),
            action_name="hello_world",
            action_version=TEST_ACTION_VERSION,
        )

    assert error.value.exit_code == 2


def test_retrieve_ci_action_script_from_git_rejects_missing_ref(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_ci_action_script_from_git
    from python_ci_toolkit.actions.retrieval.exceptions import MissingGitActionRefError

    with pytest.raises(MissingGitActionRefError) as error:
        retrieve_ci_action_script_from_git(
            git_repo_url=str(remote_actions_git_repo),
            action_name="hello_world",
            action_version="missing-version",
        )

    assert error.value.exit_code == 3


def test_retrieve_action_repo_rejects_missing_actions_directory(tmp_path: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_action_repo
    from python_ci_toolkit.actions.retrieval.exceptions import ActionRepositoryLayoutError

    remote_repo = _create_git_repo_without_actions(tmp_path / "remote-actions-without-actions")

    with pytest.raises(ActionRepositoryLayoutError) as error:
        retrieve_action_repo(str(remote_repo))

    assert error.value.exit_code == 1


def test_retrieve_ci_action_script_from_git_rejects_missing_action(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_ci_action_script_from_git
    from python_ci_toolkit.actions.retrieval.exceptions import RemoteActionScriptNotFoundError

    with pytest.raises(RemoteActionScriptNotFoundError) as error:
        retrieve_ci_action_script_from_git(
            git_repo_url=str(remote_actions_git_repo),
            action_name="missing_action",
            action_version="main",
        )

    assert error.value.exit_code == 4


def test_retrieve_ci_action_script_from_cache_rejects_missing_action(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.caching import retrieve_ci_action_script_from_cache
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_action_repo
    from python_ci_toolkit.actions.retrieval.exceptions import CachedActionScriptNotFoundError

    retrieve_action_repo(str(remote_actions_git_repo))

    with pytest.raises(CachedActionScriptNotFoundError) as error:
        retrieve_ci_action_script_from_cache(
            git_repo_url=str(remote_actions_git_repo),
            action_name="missing_action",
            action_version="main",
        )

    assert error.value.exit_code == 5


def test_retrieve_ci_action_script_from_git_rejects_local_version(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import retrieve_ci_action_script_from_git

    with pytest.raises(ValueError, match="reserved for local action retrieval"):
        retrieve_ci_action_script_from_git(
            git_repo_url=str(remote_actions_git_repo),
            action_name="hello_world",
            action_version="local",
        )


def test_remote_branch_action_cache_uses_explicit_branch_checkout(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval import retrieve_ci_action_script

    TEST_ACTION_VERSION = "feature/cached-branch"
    _create_remote_action_branch(
        remote_actions_git_repo,
        TEST_ACTION_VERSION,
        "Cached branch hello world action."
    )

    action_script_path, action_source = retrieve_ci_action_script("hello_world", TEST_ACTION_VERSION)
    action_script_path.write_text("dirty cached branch checkout", encoding="utf-8")

    action_script_path, action_source = retrieve_ci_action_script("hello_world", TEST_ACTION_VERSION)

    assert "Cached branch hello world action." in action_script_path.read_text(encoding="utf-8")
    assert action_source == f"'{TEST_ACTION_VERSION}' at '{remote_actions_git_repo}' (cached)"


def test_remote_tag_action_cache_uses_explicit_detached_checkout(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval import retrieve_ci_action_script

    TEST_ACTION_VERSION = "v2.0.0"
    _create_remote_action_tag(remote_actions_git_repo, TEST_ACTION_VERSION, "Cached tag hello world action.")

    action_script_path, action_source = retrieve_ci_action_script("hello_world", TEST_ACTION_VERSION)
    action_script_path.write_text("dirty cached tag checkout", encoding="utf-8")

    action_script_path, action_source = retrieve_ci_action_script("hello_world", TEST_ACTION_VERSION)
    cloned_repo_root = _get_cloned_repo_root(action_script_path.parent.parent)
    current_branch = run_shell_command(
        "git symbolic-ref -q --short HEAD",
        cwd=cloned_repo_root,
        silence_output=True,
        raise_on_error=False,
        use_wsl_on_windows=False,
    )
    cloned_head = run_shell_command("git rev-parse HEAD", cwd=cloned_repo_root, silence_output=True, use_wsl_on_windows=False)
    tag_head = run_shell_command(f'git rev-list -n 1 "{TEST_ACTION_VERSION}"', cwd=remote_actions_git_repo, silence_output=True, use_wsl_on_windows=False)

    assert "Cached tag hello world action." in action_script_path.read_text(encoding="utf-8")
    assert action_source == f"'{TEST_ACTION_VERSION}' at '{remote_actions_git_repo}' (cached)"
    assert current_branch.is_failed
    assert cloned_head.output_stripped == tag_head.output_stripped


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


def test_remote_action_cache_is_scoped_to_configured_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from python_ci_toolkit.actions.retrieval import retrieve_ci_action_script
    from python_ci_toolkit.actions.retrieval.sources.git.caching import is_action_cache_fresh
    from python_ci_toolkit.environment.paths import purge_temporary_files

    purge_temporary_files()

    repo_a = _create_remote_actions_git_repo(tmp_path / "remote-actions-a", "Repo A hello world action.")
    repo_b = _create_remote_actions_git_repo(tmp_path / "remote-actions-b", "Repo B hello world action.")
    monkeypatch.delenv("PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY", raising=False)

    monkeypatch.setenv("PYTHON_CI_ACTIONS_GIT_REPO_URL", str(repo_a))
    action_script_path, action_source = retrieve_ci_action_script("hello_world", "main")

    assert "Repo A hello world action." in action_script_path.read_text(encoding="utf-8")
    assert action_source == f"'main' at '{repo_a}'"
    assert is_action_cache_fresh(str(repo_a), "hello_world", "main")
    assert not is_action_cache_fresh(str(repo_b), "hello_world", "main")

    monkeypatch.setenv("PYTHON_CI_ACTIONS_GIT_REPO_URL", str(repo_b))
    action_script_path, action_source = retrieve_ci_action_script("hello_world", "main")

    assert "Repo B hello world action." in action_script_path.read_text(encoding="utf-8")
    assert action_source == f"'main' at '{repo_b}'"


def test_remote_action_cache_is_stale_when_cloned_repo_is_missing(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval import retrieve_ci_action_script
    from python_ci_toolkit.actions.retrieval.sources.git.caching import (
        create_action_cache_timestamp,
        is_action_cache_fresh,
    )
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import get_clone_directory_from_action_repo_url
    from python_ci_toolkit.environment.paths import purge_temporary_files

    purge_temporary_files()

    repo_url = str(remote_actions_git_repo)
    create_action_cache_timestamp(repo_url, "hello_world", "main")

    assert not get_clone_directory_from_action_repo_url(repo_url).exists()
    assert not is_action_cache_fresh(repo_url, "hello_world", "main")

    action_script_path, action_source = retrieve_ci_action_script("hello_world", "main")

    assert action_script_path.exists()
    assert action_source == f"'main' at '{remote_actions_git_repo}'"


def test_remote_action_cache_is_stale_when_timestamp_expires(remote_actions_git_repo: Path):
    import os
    import time

    from python_ci_toolkit.actions.retrieval import retrieve_ci_action_script
    from python_ci_toolkit.actions.retrieval.sources.git.caching import (
        DEFAULT_REMOTE_ACTIONS_CACHE_INVALIDATION_TIMEOUT,
        _get_action_cache_timestamp_path,
    )
    from python_ci_toolkit.environment.paths import purge_temporary_files

    purge_temporary_files()

    repo_url = str(remote_actions_git_repo)
    action_script_path, action_source = retrieve_ci_action_script("hello_world", "main")
    assert action_script_path.exists()
    assert action_source == f"'main' at '{remote_actions_git_repo}'"

    _write_remote_hello_world_action(remote_actions_git_repo, "Updated after cache expiry.")
    _commit_remote_action_repo(remote_actions_git_repo, "Update hello world action after cache expiry")

    timestamp_path = _get_action_cache_timestamp_path(repo_url, "hello_world", "main")
    expired_timestamp = time.time() - DEFAULT_REMOTE_ACTIONS_CACHE_INVALIDATION_TIMEOUT - 1
    os.utime(timestamp_path, (expired_timestamp, expired_timestamp))

    action_script_path, action_source = retrieve_ci_action_script("hello_world", "main")

    assert "Updated after cache expiry." in action_script_path.read_text(encoding="utf-8")
    assert action_source == f"'main' at '{remote_actions_git_repo}'"


def test_remote_action_cache_is_stale_when_cached_action_script_is_missing(remote_actions_git_repo: Path):
    from python_ci_toolkit.actions.retrieval import retrieve_ci_action_script
    from python_ci_toolkit.actions.retrieval.sources.git.caching import is_action_cache_fresh
    from python_ci_toolkit.environment.paths import purge_temporary_files

    purge_temporary_files()

    repo_url = str(remote_actions_git_repo)
    action_script_path, action_source = retrieve_ci_action_script("hello_world", "main")
    assert action_script_path.exists()
    assert action_source == f"'main' at '{remote_actions_git_repo}'"

    action_script_path.unlink()
    assert not is_action_cache_fresh(repo_url, "hello_world", "main")

    action_script_path, action_source = retrieve_ci_action_script("hello_world", "main")

    assert "Remote hello world action." in action_script_path.read_text(encoding="utf-8")
    assert action_source == f"'main' at '{remote_actions_git_repo}'"


def test_remote_action_repo_is_optional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import get_remote_action_repo

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTHON_CI_ACTIONS_GIT_REPO_URL", raising=False)
    monkeypatch.delenv("PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY", raising=False)

    assert get_remote_action_repo() is None


def test_remote_action_repo_can_come_from_project_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remote_actions_git_repo_path: Path,
):
    from python_ci_toolkit.config import get_pyci_config_path
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import get_remote_action_repo

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTHON_CI_ACTIONS_GIT_REPO_URL", raising=False)
    monkeypatch.delenv("PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY", raising=False)
    config_path = get_pyci_config_path()
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "[actions]\n"
        f'remote_repository = "{remote_actions_git_repo_path}"\n',
        encoding="utf-8"
    )

    assert get_remote_action_repo() == (str(remote_actions_git_repo_path), None)


def test_remote_action_repo_env_var_overrides_project_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remote_actions_git_repo_path: Path,
):
    from python_ci_toolkit.config import get_pyci_config_path
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import get_remote_action_repo

    configured_repo_path = tmp_path / "configured-actions"
    configured_repo_path.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHON_CI_ACTIONS_GIT_REPO_URL", str(remote_actions_git_repo_path))
    monkeypatch.delenv("PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY", raising=False)
    config_path = get_pyci_config_path()
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "[actions]\n"
        f'remote_repository = "{configured_repo_path}"\n',
        encoding="utf-8"
    )

    assert get_remote_action_repo() == (str(remote_actions_git_repo_path), None)


def test_remote_action_without_config_fails_clearly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from python_ci_toolkit.actions.retrieval import retrieve_ci_action_script
    from python_ci_toolkit.actions.retrieval.sources.git.cloning import RemoteActionRepoNotConfiguredError

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTHON_CI_ACTIONS_GIT_REPO_URL", raising=False)
    monkeypatch.delenv("PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY", raising=False)

    with pytest.raises(RemoteActionRepoNotConfiguredError, match="Remote action repository is not configured"):
        retrieve_ci_action_script("hello_world", "main")


def test_action_cli_renders_retrieval_errors_without_traceback(monkeypatch: pytest.MonkeyPatch):
    import python_ci_toolkit.actions as actions_module
    from click.testing import CliRunner

    from python_ci_toolkit.actions.retrieval.exceptions import MissingGitActionRefError
    from python_ci_toolkit.cli.action.action import action

    def fail_run_ci_action(action_name: str, action_version: str | None = None, args: list[str] | None = None) -> None:
        raise MissingGitActionRefError("Cannot pull action 'hello_world@missing-version' from Git.")

    monkeypatch.setattr(actions_module, "run_ci_action", fail_run_ci_action)

    result = CliRunner().invoke(action, ["hello_world@missing-version"])

    assert result.exit_code == MissingGitActionRefError.exit_code
    assert "Cannot pull action 'hello_world@missing-version' from Git." in result.output
    assert "Traceback" not in result.output


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
