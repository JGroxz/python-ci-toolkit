"""
Utility functions for inspecting and interacting with current CI environment.
"""

import os


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
    if is_running_in_bitbucket_ci():
        return "Bitbucket CI"

    return "Default/Local"


def assert_environment_variable_set(variable_name: str) -> None:
    """
    Assert that the given environment variable is set and available.

    Args:
        variable_name: Name of the environment variable to assert.
    """
    assert os.environ.get(variable_name), f"'{variable_name}' environment variable is not set, but is required by CI logic."

