from pathlib import Path

from python_ci_toolkit.shell import quiet_shell_command_runner


def _init_git_repo(repo_path: Path) -> None:
    repo_path.mkdir()
    quiet_shell_command_runner("git init", cwd=repo_path)


def test_get_git_repo_root_returns_none_outside_git_repo(tmp_path: Path):
    from python_ci_toolkit.git.repo import get_git_repo_root

    project_root = tmp_path / "not-a-git-repo"
    project_root.mkdir()

    assert get_git_repo_root(project_root) is None


def test_get_git_repo_root_returns_repo_root(tmp_path: Path):
    from python_ci_toolkit.git.repo import get_git_repo_root

    repo_path = tmp_path / "project"
    _init_git_repo(repo_path)
    nested_path = repo_path / "src" / "package"
    nested_path.mkdir(parents=True)

    assert get_git_repo_root(nested_path) == repo_path


def test_add_git_safe_directory_configures_global_safe_directory(monkeypatch, tmp_path: Path):
    import python_ci_toolkit.git.repo as git_repo

    commands: list[tuple[str, dict]] = []

    def capture_shell_command(command: str, **kwargs):
        commands.append((command, kwargs))

    monkeypatch.setattr(git_repo, "quiet_shell_command_runner", capture_shell_command)

    git_repo.add_git_safe_directory(tmp_path)

    assert commands == [
        (
            f'git config --global --add safe.directory "{tmp_path}"',
            {},
        )
    ]
