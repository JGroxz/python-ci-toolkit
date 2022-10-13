"""
Utility functions for inspecting and interacting with current CI environment.
"""
import logging
import os
from enum import Enum
from pathlib import Path


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


ci_environment_type = get_current_ci_environment()
"""
Type of the current CI environment (e.g. BitbucketPipelines).

Notes:
    See CiEnvironmentType enum for all supported CI environment types. 
"""


def is_running_in_bitbucket_ci() -> bool:
    """
    Checks whether this code is running in Bitbucket CI environment.

    Returns:
        True if running in Bitbucket CI, False otherwise.
    """
    return os.environ.get("BITBUCKET_PIPELINE_UUID") is not None


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


def assert_environment_variable_set(variable_name: str, usage_explanation: str = None) -> str:
    """
    Assert that the given environment variable is set and available.

    Args:
        variable_name: Name of the environment variable to assert.
        usage_explanation: Optional string with an explanation of why the given environment variable must be set.

    Returns:
        Value of the given environment variable.
    """
    message = f"'{variable_name}' environment variable is not set, but is required by CI logic."
    if usage_explanation is not None:
        message = (f"{message}\n"
                   f"Explanation: {usage_explanation}")

    assert os.environ.get(variable_name), message

    return os.environ[variable_name]


def get_project_root_directory_path() -> Path:
    """
    Tries to find the path to the current project's root folder.

    Notes:
        This is guaranteed to be accurate in cloud CI environments (e.g. Bitbucket Pipelines).
        When run on a local machine, this function will assume that python_ci_toolkit module is inside the venv folder in the project root directory when searching;
        otherwise, current working directory will be assumed to be project's root.

    Returns:
        Absolute path to the root folder of the current CI project.
    """
    if ci_environment_type == CiEnvironmentType.BitbucketPipelines:
        return Path(os.environ["BITBUCKET_CLONE_DIR"])
    elif ci_environment_type == CiEnvironmentType.Unknown:
        # we are dealing with an unknown environment, so we assume we are running on a local developer machine,
        # where this code should be installed as a package inside venv folder located in the project directory
        script_parent_directory = Path(__file__).parent

        # special case: the project is a dev version of python-ci-toolkit itself
        if (script_parent_directory.name == "python_ci_toolkit"
                and Path(script_parent_directory.parent, "pyproject.toml").exists()):
            return script_parent_directory.parent

        # normal case: the package is installed inside a venv
        parent_directory = script_parent_directory
        while parent_directory.name != "venv":
            if parent_directory == parent_directory.parent:
                # we have reached the root of the file system; this means that the package inside the venv;
                # the best we can do in this case is treat current working directory as the project directory and print a warning
                logging.warning(f"Could not determine project's root directory (CI environment is '{get_ci_environment_name()}' and python-ci-toolkit is not installed inside a venv).\n"
                                f"Assuming current working directory as the current CI project's root.")
                project_root_path = Path(os.getcwd())
                return project_root_path

            parent_directory = parent_directory.parent

        # we found the venv, project folder must be the parent of it
        project_root_path = parent_directory.parent
        return project_root_path


ci_project_root = get_project_root_directory_path()
"""
Absolute path to the current project's root folder.

Notes:
    This is guaranteed to be accurate in cloud CI environments (e.g. Bitbucket Pipelines).
    When on a local machine, it will assume that python_ci_toolkit module is inside the venv folder in the project root directory when searching;
    otherwise, current working directory will be assumed to be project's root.
"""
