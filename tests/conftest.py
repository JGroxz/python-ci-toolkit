from pathlib import Path

import pytest

from python_ci_toolkit.shell import run_shell_command


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
def remote_actions_git_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Creates a local Git repository with a test CI action and configures the toolkit to use it as the remote action repo.
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

    run_shell_command("git init", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    run_shell_command("git symbolic-ref HEAD refs/heads/main", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    run_shell_command("git add .", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)
    run_shell_command(
        'git -c user.name="Python CI Toolkit Tests" -c user.email="tests@example.invalid" commit -m "Add hello world action"',
        cwd=repo_path,
        silence_output=True,
        use_wsl_on_windows=False
    )

    monkeypatch.setenv("PYTHON_CI_ACTIONS_GIT_REPO_URL", str(repo_path))
    monkeypatch.delenv("PYTHON_CI_ACTIONS_SSH_PRIVATE_KEY", raising=False)

    return repo_path
