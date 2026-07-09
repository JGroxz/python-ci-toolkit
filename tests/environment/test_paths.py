import tempfile
from pathlib import Path

from rich import print

from python_ci_toolkit.shell import ShellCommandResult, quiet_shell_command_runner
from python_ci_toolkit.environment.paths import ci_paths


def test_ci_paths_singleton_is_reexported_from_core():
    from python_ci_toolkit.environment.paths import ci_paths as package_ci_paths
    from python_ci_toolkit.environment.paths.core import ci_paths as core_ci_paths

    assert package_ci_paths is core_ci_paths


def test_ci_paths_constructor_does_not_probe_git(monkeypatch):
    from python_ci_toolkit.environment.paths import core

    def fail_if_called(*args, **kwargs):
        raise AssertionError("CiPaths construction must not run shell commands.")

    monkeypatch.setattr(core, "probe_shell_command_runner", fail_if_called)

    core.CiPaths()


def test_project_root_directory_path():
    project_root = ci_paths.project_root

    print(f"Project root: '{project_root}'")

    assert project_root == Path(__file__).parent.parent.parent


def test_temp_directory_path():
    print(f"Python-provided temp directory: {tempfile.gettempdir()}")

    from python_ci_toolkit.environment.paths.internal import ci_temp_files_root_directory, ci_temp_files_shared_directory, ci_temp_files_projects_root_directory
    print(f"Root temp directory:      '{ci_temp_files_root_directory}'")
    print(f"Shared temp directory:    '{ci_temp_files_shared_directory}'")
    print(f"Projects temp directory:  '{ci_temp_files_projects_root_directory}'")

    from python_ci_toolkit.environment import ci_paths
    print(f"Project's temp directory: '{ci_paths.temp_files_directory}'")

    # from python_ci_toolkit.environment import ci_temp_files_directory_relative
    # print(f"Project's temp directory (relative): '{ci_temp_files_directory_relative}'")
    #
    # from python_ci_toolkit.environment import ci_project_root
    # assert ci_temp_files_directory.samefile(ci_project_root / ci_temp_files_directory_relative), \
    #     "Relative temp CI directory path does not point to the same directory as the absolute temp CI directory path."


def test_temp_directory_uses_shared_directory_outside_git_repo(tmp_path: Path, monkeypatch):
    from python_ci_toolkit.environment.paths import core
    from python_ci_toolkit.environment.paths.internal import ci_temp_files_shared_directory

    project_root = tmp_path / "not-a-git-repo"
    project_root.mkdir()

    monkeypatch.setattr(core.ci_platform, "get_ci_project_root", lambda: project_root)
    monkeypatch.setattr(
        core,
        "probe_shell_command_runner",
        lambda command, **kwargs: ShellCommandResult(command, exit_code=1, output=""),
    )

    assert core.CiPaths().temp_files_directory == ci_temp_files_shared_directory


def test_temp_directory_uses_first_commit_sha_for_git_repo(tmp_path: Path, monkeypatch):
    from python_ci_toolkit.environment.paths import core
    from python_ci_toolkit.environment.paths.internal import ci_temp_files_projects_root_directory

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "README.md").write_text("test project\n", encoding="utf-8")
    project_command_runner = quiet_shell_command_runner.with_options(cwd=project_root)
    project_command_runner("git init")
    project_command_runner("git symbolic-ref HEAD refs/heads/main")
    project_command_runner("git add .")
    project_command_runner(
        'git -c user.name="Python CI Toolkit Tests" -c user.email="tests@example.invalid" commit -m "Initial commit"',
    )
    first_commit_sha = project_command_runner("git rev-list --max-parents=0 HEAD").output_stripped

    monkeypatch.setattr(core.ci_platform, "get_ci_project_root", lambda: project_root)

    assert core.CiPaths().temp_files_directory == ci_temp_files_projects_root_directory / first_commit_sha[:7]
