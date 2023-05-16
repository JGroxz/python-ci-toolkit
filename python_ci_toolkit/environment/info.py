"""
Functions to access the information about the current CI environment.
"""

import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)


class CiEnvironmentType(Enum):
    """Enum containing CI environments supported by the toolkit."""
    Unknown = 0
    """Unknown type of CI environment, or running on a local machine"""
    BitbucketPipelines = 1
    """Bitbucket Pipelines"""
    GitHubActions = 2
    """GitHub Actions"""


def get_current_ci_environment() -> CiEnvironmentType:
    """
    Tries to detect current CI environment type.

    Returns:
        CiEnvironmentType enum value corresponding to the CI environment this script is being run at.
    """
    if os.environ.get("BITBUCKET_PIPELINE_UUID"):
        return CiEnvironmentType.BitbucketPipelines

    if os.environ.get("GITHUB_WORKSPACE"):
        return CiEnvironmentType.GitHubActions

    return CiEnvironmentType.Unknown


def get_ci_environment_name() -> str:
    """
    Returns the name of the current CI environment.

    Returns:
        Name of the CI environment.
    """
    if ci_environment_type == CiEnvironmentType.BitbucketPipelines:
        return "Bitbucket Pipelines"
    elif ci_environment_type == CiEnvironmentType.GitHubActions:
        return "GitHub Actions"
    elif ci_environment_type == CiEnvironmentType.Unknown:
        return "Unknown/Local"


ci_environment_type = get_current_ci_environment()
"""
Type of the current CI environment (e.g. BitbucketPipelines).

Notes:
    See CiEnvironmentType enum for all supported CI environment types. 
"""
