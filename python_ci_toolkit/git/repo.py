from pathlib import Path

from ..shell import run_shell_command

ci_repo: Path | None = None
"""
Path to the local Git repository of the current CI project.

Notes:
    This legacy value is no longer resolved at import time. Use get_git_repo_root()
    with an explicit project path for current Git repository detection.
"""


def add_git_safe_directory(project_root: Path) -> None:
    run_shell_command(
        f'git config --global --add safe.directory "{project_root}"',
        silence_output=True,
        use_wsl_on_windows=False,
    )


def get_git_repo_root(project_root: Path) -> Path | None:
    try:
        result = run_shell_command(
            "git rev-parse --show-toplevel",
            cwd=project_root,
            silence_output=True,
            raise_on_error=False,
            use_wsl_on_windows=False,
        )
    except OSError:
        return None

    return Path(result.output_stripped) if result.is_successful and result.output_value else None
