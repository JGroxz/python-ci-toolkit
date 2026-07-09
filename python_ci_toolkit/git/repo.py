from pathlib import Path

from ..shell import probe_shell_command_runner, quiet_shell_command_runner


def add_git_safe_directory(project_root: Path) -> None:
    quiet_shell_command_runner(f'git config --global --add safe.directory "{project_root}"')


def get_git_repo_root(project_root: Path) -> Path | None:
    try:
        result = probe_shell_command_runner(
            "git rev-parse --show-toplevel",
            cwd=project_root,
        )
    except OSError:
        return None

    return Path(result.output_stripped) if result.is_successful and result.output_value else None
