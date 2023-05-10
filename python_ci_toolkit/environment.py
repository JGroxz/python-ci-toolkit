"""
Utility functions for inspecting and interacting with current CI environment.
"""
from __future__ import annotations

import logging
import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import List, Callable

from git import Repo, InvalidGitRepositoryError

from python_ci_toolkit.shell import run_shell_command

logger = logging.getLogger(__name__)


# CI environment information

class CiEnvironmentType(Enum):
    """Enum containing CI environments supported by the toolkit."""
    Unknown = 0
    """Unknown type of CI environment, or running on a local machine"""
    BitbucketPipelines = 1
    """Bitbucket Pipelines"""


def get_current_ci_environment() -> CiEnvironmentType:
    """
    Tries to detect current CI environment type.

    Returns:
        CiEnvironmentType enum value corresponding to the CI environment this script is being run at.
    """
    if os.environ.get("BITBUCKET_PIPELINE_UUID"):
        return CiEnvironmentType.BitbucketPipelines

    return CiEnvironmentType.Unknown


def get_ci_environment_name() -> str:
    """
    Returns the name of the current CI environment.

    Returns:
        Name of the CI environment.
    """
    if ci_environment_type == CiEnvironmentType.BitbucketPipelines:
        return "Bitbucket Pipelines"
    elif ci_environment_type == CiEnvironmentType.Unknown:
        return "Unknown/Local"


ci_environment_type = get_current_ci_environment()
"""
Type of the current CI environment (e.g. BitbucketPipelines).

Notes:
    See CiEnvironmentType enum for all supported CI environment types. 
"""


# Common paths used in CI


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


# Functions for working with environment variables

def is_environment_variable_set(variable_name: str) -> bool:
    """
    Checks whether the given environment variable is set.

    Notes:
        Variables defined with empty string as a value are considered unset.

    Args:
        variable_name: Name of the environment variable to check.

    Returns:
        True if variable is set, False otherwise.
    """
    value = os.environ.get(variable_name)
    return (value is not None) and (value != "")


def assert_environment_variable_set(variable_name: str, usage_explanation: str = None,
                                    fallback_value_getter: Callable[[], str | None] = None) -> str:
    """
    Assert that the given environment variable is set and available.

    Args:
        variable_name: Name of the environment variable to assert.
        usage_explanation: Optional string with an explanation of why the given environment variable must be set.
        fallback_value_getter: Optional callable to retrieve the fallback value of this variable in case it is not set.
            Can be used to provide default values to variables. If this callable returns None, assertion will still fail.
            If the fallback value exists, it will also be automatically written into the given environment variable.

    Returns:
        Value of the given environment variable.
    """
    # use fallback value if required and available
    is_fallback_provided = (fallback_value_getter is not None)
    if (not is_environment_variable_set(variable_name)) and is_fallback_provided:
        logger.debug(f"'{variable_name}' environment variable is not set, but fallback getter function is defined.\n"
                     f"  Trying to retrieve a fallback value...")

        # Retrieve fallback value
        fallback_value = fallback_value_getter()

        if isinstance(fallback_value, str):
            os.environ[variable_name] = fallback_value
        elif fallback_value is not None:
            raise TypeError(
                f"Value returned by fallback getter function {fallback_value_getter} is of type {type(fallback_value)}, which is neither a string nor None.\n"
                f"  Fallback value functions are only allowed to return strings or None to avoid ambiguity, because environment variables can only have string or no value.\n")

        if is_environment_variable_set(variable_name):
            logger.debug(f"Retrieved fallback value for '{variable_name}' environment variable.")
            return os.environ[variable_name]
        else:
            logger.warning(f"Could not retrieve a fallback value for '{variable_name}' environment variable.")

    # craft message
    message = f"'{variable_name}' environment variable is not set, but is required by CI logic."
    if is_fallback_provided:
        message = (f"{message}\n"
                   f"  Fallback value could not be retrieved either. Please see previous log messages for details (before the stack trace).")
    if usage_explanation is not None:
        message = (f"{message}\n"
                   f"  Explanation: {usage_explanation}")

    assert is_environment_variable_set(variable_name), message

    return os.environ[variable_name]


def assert_multiline_environment_variable_set(variable_name: str, usage_explanation: str = None,
                                              fallback_value_getter: Callable[[], str | None] = None,
                                              newline_substitution_character: str = "|") -> str:
    """
    A version of assert_environment_variable_set() function which recovers multiline environment variable from its inlined form on platforms which don't support multiline ones.

    Notes:
        Use this function when you need to read a multiline environment variable from your CI environment.

        If the current CI environment supports multiline environment variables,
        this function will return variable's original value without modifying it.

        Certain CI environments (e.g. BitBucket Pipelines) do not support multiline environment variables.
        A workaround is to use a substitution character instead of newline ('\\\\n') in their values when defining them in the CI interface,
        and then recover the value back to multi-line one when running. This is exactly what this function does.

    Args:
        variable_name: Name of the variable to assert and recover.
        usage_explanation: Optional string with an explanation of why the given environment variable must be set.
        fallback_value_getter: Optional callable to retrieve the fallback value of this variable in case it is not set.
            Can be used to provide default values to variables. If this callable returns None, assertion will still fail.
            If the fallback value exists, it will also be automatically written into the given environment variable.

            NOTE: Fallback is expected to return a value with ACTUAL newline characters.
            Substitution characters will not be replaced in the fallback value.
            This is done so that you don't have to care about CI environment type when returning fallback values.

        newline_substitution_character: Character used in the environment variable instead of newline.
            The default value is pipe ('|').

    Returns:
        Recovered multiline value of the given environment variable.
    """
    # we have to be cautious to
    is_fallback_used = (not is_environment_variable_set(variable_name)) and (fallback_value_getter is not None)

    # retrieve the value
    value = assert_environment_variable_set(variable_name, usage_explanation, fallback_value_getter)

    if not is_fallback_used:
        # list of CI environment types which do not support defining multiline environment variables
        unsupported_environments: List[CiEnvironmentType] = [
            CiEnvironmentType.BitbucketPipelines
        ]

        # recover if we are in an unsupported environment
        if ci_environment_type in unsupported_environments:
            return value.replace(newline_substitution_character, "\n")

    # return original value otherwise
    return value
