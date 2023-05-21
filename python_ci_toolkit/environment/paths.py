"""
Functions for working with common paths used in CI scripts.
"""

import logging
import os
import tempfile
from pathlib import Path

from git import Repo, InvalidGitRepositoryError

from .info import ci_environment_type, CiEnvironmentType, get_ci_environment_name
from ..shell import run_shell_command

logger = logging.getLogger(__name__)


def get_project_root_directory_path() -> Path:
    """
    Tries to find the path to the current project's root directory.

    Notes:
        This is guaranteed to be accurate in cloud CI environments (e.g. Bitbucket Pipelines).
        When run on a local machine, this function will assume that python_ci_toolkit module is inside the venv directory in the project root directory when searching;
        otherwise, current working directory will be assumed to be project's root.

    Returns:
        Absolute path to the root directory of the current CI project.
    """
    if ci_environment_type == CiEnvironmentType.BitbucketPipelines:
        return Path(os.environ["BITBUCKET_CLONE_DIR"])
    elif ci_environment_type == CiEnvironmentType.GitHubActions:
        return Path(os.environ["GITHUB_WORKSPACE"])
    elif ci_environment_type == CiEnvironmentType.Unknown:
        # general case: find the root of the enclosing Git repository
        result = run_shell_command("git rev-parse --show-toplevel", use_wsl_on_windows=False,
                                   raise_on_error=False, silence_output=True,
                                   cwd=os.getcwd())

        if result.is_successful:
            git_repo_root = result.output_stripped
            return Path(git_repo_root)

        # other case: we are not inside a Git repo, so the root cannot be reliably determined
        logger.debug(f"Could not determine project's root directory: not a Git repo.\n"
                     f"  CI environment: '{get_ci_environment_name()}'\n"
                     f"  CWD: '{os.getcwd()}'\n"
                     f"Assuming current working directory as the current CI project's root.")
        return Path(os.getcwd())


ci_project_root: Path = get_project_root_directory_path()
"""
Absolute path to the current project's root directory.

Notes:
    This is guaranteed to be accurate in cloud CI environments (e.g. Bitbucket Pipelines).

    When on a local machine, it will look for the outermost Git repository's root relative tom the current working directory;
    if no Git repo is found, current working directory will be assumed to be the project's root.
"""

try:
    ci_repo: Repo | None = Repo(ci_project_root)
    """
    GitPython reference to the local Git repository of the current CI project.

    If current CI project root is not a Git repository, this will be set to None.
    """

    if ci_environment_type == CiEnvironmentType.GitHubActions:
        # GitHub Actions workspace directory belongs to a different user out-of-the-box,
        # so we have to mark it as safe to be able to run all git commands without errors.
        # See for more info: https://github.com/python-semantic-release/python-semantic-release/issues/560
        run_shell_command(f'git config --global --add safe.directory "{ci_project_root}"', silence_output=True, use_wsl_on_windows=False)

except InvalidGitRepositoryError as e:
    ci_repo = None

ci_files_directory_relative: Path = Path(".ci")
"""
Relative path to the CI directory of the current project (relative to the project's root).

Notes:
    This directory can be used to store scripts and configuration files related to the given project's CI workflows.
"""

ci_files_directory: Path = ci_project_root / ci_files_directory_relative
"""
Absolute path to the CI directory in the current project.

Notes:
    This directory can be used to store scripts and configuration files related to the given project's CI workflows.
"""

_ci_temp_files_root_directory: Path = Path(tempfile.gettempdir()) / "python-ci-toolkit" / "temp"
"""Common root directory of all temporary file directories used by the toolkit."""

_ci_temp_files_shared_directory = _ci_temp_files_root_directory / "shared"
"""Common root directory of all temporary file directories used by the toolkit."""

_ci_temp_files_projects_root_directory = _ci_temp_files_root_directory / "project-specific"
"""Common root directory of all project-specific temporary file directories used by the toolkit."""


def _get_temp_files_directory_of_current_ci_project() -> Path:
    """
    Returns path to the location for temporary files specific to the current CI project.
    """
    if ci_repo:
        # when inside a CI project repo, generate the path based on the initial commit's SHA
        first_ci_repo_commit_sha = next(ci_repo.iter_commits(reverse=True)).hexsha
        return _ci_temp_files_projects_root_directory / first_ci_repo_commit_sha
    else:
        # when outside any repo, point to the shared temp directory
        return _ci_temp_files_shared_directory


ci_temp_files_directory: Path = _get_temp_files_directory_of_current_ci_project()
"""
Absolute path to the location for temporary files generated by the CI logic.

Notes:
    This directory can and should be used for storing any temporary files generated by CI logic.

    This directory is unique per CI project, so there is no risk of temporary CI files clashing with those from another CI project on the same machine.
    Name of the directory is tied to the SHA of the first commit in this repo's repository; this means the project's temp directory persists even if the path to the 
    project's directory changes.

    If current CI project path is not a Git repo, this return a shared temp directory.
"""

ci_temp_files_directory_relative: Path = Path(os.path.relpath(ci_temp_files_directory, ci_project_root))
"""
Relative path to the location for temporary files generated by the CI logic (relative to the project's root).

Notes:
    This directory can and should be used for storing any temporary files generated by CI logic.

    Note that this directory is not added to .gitignore automatically, but it it recommended to do so in order to prevent accidentally committing temporary files to your repository's history. 
    Before using this directory in CI scripts, add the following line to your project's .gitignore:
        temp/
"""


def _ensure_ci_temp_files_directories_exist() -> None:
    """
    Ensures that the directories for temporary CI files exist.
    """
    os.makedirs(_ci_temp_files_root_directory, exist_ok=True)
    os.makedirs(_ci_temp_files_shared_directory, exist_ok=True)
    os.makedirs(_ci_temp_files_projects_root_directory, exist_ok=True)
    os.makedirs(ci_temp_files_directory, exist_ok=True)


_ensure_ci_temp_files_directories_exist()
