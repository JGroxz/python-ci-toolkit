from pathlib import Path

from python_ci_toolkit.shell import run_shell_command


def _init_git_repo(repo_path: Path) -> None:
    repo_path.mkdir()
    run_shell_command("git init", cwd=repo_path, silence_output=True, use_wsl_on_windows=False)


def _get_remote_origin_url(repo_path: Path) -> str:
    return run_shell_command(
        "git remote get-url origin",
        cwd=repo_path,
        silence_output=True,
        use_wsl_on_windows=False,
    ).output_stripped


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

    monkeypatch.setattr(git_repo, "run_shell_command", capture_shell_command)

    git_repo.add_git_safe_directory(tmp_path)

    assert commands == [
        (
            f'git config --global --add safe.directory "{tmp_path}"',
            {
                "silence_output": True,
                "use_wsl_on_windows": False,
            },
        )
    ]


def test_ensure_remote_is_ssh_converts_https_origin(tmp_path: Path):
    from python_ci_toolkit.git.remote import ensure_remote_is_ssh

    repo_path = tmp_path / "project"
    _init_git_repo(repo_path)
    run_shell_command(
        "git remote add origin https://github.com/example/project.git",
        cwd=repo_path,
        silence_output=True,
        use_wsl_on_windows=False,
    )

    ensure_remote_is_ssh(repo_path)

    assert _get_remote_origin_url(repo_path) == "git@github.com:example/project.git"


def test_ensure_remote_is_https_converts_ssh_origin(tmp_path: Path):
    from python_ci_toolkit.git.remote import ensure_remote_is_https

    repo_path = tmp_path / "project"
    _init_git_repo(repo_path)
    run_shell_command(
        "git remote add origin git@github.com:example/project.git",
        cwd=repo_path,
        silence_output=True,
        use_wsl_on_windows=False,
    )

    ensure_remote_is_https(repo_path)

    assert _get_remote_origin_url(repo_path) == "https://github.com/example/project.git"
