"""
Functions to access the information about the current CI environment.
"""

import logging

from .platforms.base import CiPlatform

logger = logging.getLogger(__name__)


def _get_ci_environment() -> type[CiPlatform]:
    """
    Tries to detect current CI environment type.

    Returns:
        CiEnvironmentType enum value corresponding to the CI environment this script is being run at.
    """
    from .platforms import BitbucketPipelines, GitHubActions, Local

    if BitbucketPipelines.is_current():
        return BitbucketPipelines
    elif GitHubActions.is_current():
        return GitHubActions

    return Local


ci_platform = _get_ci_environment()
"""
Object containing the info about the current CI environment (Bitbucket Pipelines, GitHub Actions etc.).
"""
