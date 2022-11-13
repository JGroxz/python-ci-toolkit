"""
Utility functions for inspecting and interacting with current CI environment.
"""
import logging
import os
from enum import Enum
from pathlib import Path
from typing import List, Callable


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


def assert_environment_variable_set(variable_name: str, usage_explanation: str = None, fallback_value_getter: Callable[[], str | None] = None) -> str:
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
    # Use fallback value if required and available
    if (not is_environment_variable_set(variable_name)) and (fallback_value_getter is not None):
        logging.info(f"'{variable_name}' environment variable is not set, but fallback getter function is defined.\n"
                     f"  Trying to retrieve a fallback value...")

        # Retrieve fallback value
        fallback_value = fallback_value_getter()

        if isinstance(fallback_value, str):
            os.environ[variable_name] = fallback_value
        elif fallback_value is not None:
            raise TypeError(f"Value returned by fallback getter function {fallback_value_getter} is of type {type(fallback_value)}, which is neither a string nor None.\n"
                            f"  Fallback value functions are only allowed to return strings or None to avoid ambiguity, because environment variables can only have string or no value.\n")

        if is_environment_variable_set(variable_name):
            logging.info(f"Retrieved fallback value for '{variable_name}' environment variable.")
            return os.environ[variable_name]
        else:
            logging.warning(f"Could not retrieve a fallback value for '{variable_name}' environment variable.")

    # Craft message
    message = f"'{variable_name}' environment variable is not set, but is required by CI logic."
    if usage_explanation is not None:
        message = (f"{message}\n"
                   f"    Explanation: {usage_explanation}")

    assert is_environment_variable_set(variable_name), message

    return os.environ[variable_name]


def assert_multiline_environment_variable_set(variable_name: str, usage_explanation: str = None, fallback_value_getter: Callable[[], str | None] = None,
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
        # we are dealing with an unknown environment, so we assume we are running on a local developer machine,
        # where this code should be installed as a package inside venv directory located in the project directory
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

        # we found the venv, project directory must be the parent of it
        project_root_path = parent_directory.parent
        return project_root_path


ci_project_root: Path = get_project_root_directory_path()
"""
Absolute path to the current project's root directory.

Notes:
    This is guaranteed to be accurate in cloud CI environments (e.g. Bitbucket Pipelines).
    When on a local machine, it will assume that python_ci_toolkit module is inside the venv directory in the project root directory when searching;
    otherwise, current working directory will be assumed to be project's root.
"""

ci_files_directory_relative: Path = Path(".ci")
"""
Relative path to the CI directory of the current project (relative to the project's root).

Notes:
    This directory can be used to store scripts and configuration files related to the given project's CI workflows.
"""

ci_files_directory: Path = ci_project_root.joinpath(ci_files_directory_relative)
"""
Absolute path to the CI directory of the current project.

Notes:
    This directory can be used to store scripts and configuration files related to the given project's CI workflows.
"""

ci_temp_files_directory_relative: Path = Path("temp")
"""
Relative path to the location for temporary files generated by the CI logic (relative to the project's root).

Notes:
    This directory can and should be used for storing any temporary files generated by CI logic.
    
    Note that this directory is not added to .gitignore automatically, but it it recommended to do so in order to prevent accidentally committing temporary files to your repository's history. 
    Before using this directory in CI scripts, add the following line to your project's .gitignore:
        temp/
"""

ci_temp_files_directory: Path = ci_files_directory.joinpath(ci_temp_files_directory_relative)
"""
Absolute path to the location for temporary files generated by the CI logic.

Notes:
    This directory can and should be used for storing any temporary files generated by CI logic.
    
    Note that this directory is not added to .gitignore automatically, but it it recommended to do so in order to prevent accidentally committing temporary files to your repository's history. 
    Before using this directory in CI scripts, add the following line to your project's .gitignore:
        temp/
"""

# Make sure that the temporary files' directory exists
if not ci_temp_files_directory.exists():
    os.makedirs(ci_temp_files_directory, exist_ok=True)
