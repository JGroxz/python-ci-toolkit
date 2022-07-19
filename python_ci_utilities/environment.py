"""
Utility functions for inspecting current CI environment.
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
