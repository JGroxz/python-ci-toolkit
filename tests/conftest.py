from pathlib import Path

import pytest

from python_ci_toolkit.shell import quiet_shell_command_runner


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call():
    print()  # <- newline at the start of the logs to make them more readable
    yield


@pytest.fixture
def variable_name() -> str:
    """
    Returns:
        Name of the environment variable that is used to test environment variable access functions.
    """
    return "TEST_ENVIRONMENT_VARIABLE"


@pytest.fixture
def remote_actions_git_repo_path(tmp_path: Path) -> Path:
    """
    Creates a local Git repository with a test CI action.
    """
    repo_path = tmp_path / "remote-actions"
    action_directory = repo_path / ".ci" / "actions" / "hello_world"
    action_directory.mkdir(parents=True)
    (action_directory / "hello_world.py").write_text(
        '"""\n'
        'Remote hello world action.\n'
        '"""\n'
        '\n'
        '\n'
        'def main() -> None:\n'
        '    print("hello world")\n',
        encoding="utf-8"
    )

    repo_command_runner = quiet_shell_command_runner.with_options(cwd=repo_path)
    repo_command_runner("git init")
    repo_command_runner("git symbolic-ref HEAD refs/heads/main")
    repo_command_runner("git add .")
    repo_command_runner(
        'git -c user.name="Python CI Toolkit Tests" -c user.email="tests@example.invalid" commit -m "Add hello world action"',
    )

    return repo_path


@pytest.fixture
def remote_actions_git_repo(remote_actions_git_repo_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Creates a local Git repository with a test CI action and configures the toolkit to use it as the remote action repo.
    """
    repo_path = remote_actions_git_repo_path

    monkeypatch.setenv("PYTHON_CI_ACTIONS_GIT_REPO_URL", str(repo_path))

    return repo_path
