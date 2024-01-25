from git import Repo, InvalidGitRepositoryError

from python_ci_toolkit.environment import ci_platform, ci_paths, platforms
from python_ci_toolkit.shell import run_shell_command

ci_repo: Repo | None
"""
GitPython reference to the local Git repository of the current CI project.

Notes:
    This is None if current CI project is not a Git repository.
"""

try:
    ci_repo: Repo = Repo(ci_paths.project_root, search_parent_directories=True)

    if ci_platform == platforms.GitHubActions:
        # GitHub Actions workspace directory belongs to a different user out-of-the-box,
        # so we have to mark it as safe to be able to run all git commands without errors.
        # See for more info: https://github.com/python-semantic-release/python-semantic-release/issues/560
        run_shell_command(f'git config --global --add safe.directory "{ci_paths.project_root}"',
                          silence_output=True, use_wsl_on_windows=False)

except InvalidGitRepositoryError as e:
    ci_repo = None
