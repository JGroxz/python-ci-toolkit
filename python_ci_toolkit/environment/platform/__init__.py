from enum import Enum

from .base import CiPlatform
from .bitbucket import BitbucketPipelines
from .github import GitHubActions
from .local import Local


def _get_ci_platform() -> type[CiPlatform]:
    """
    Tries to detect current CI environment type.

    Returns:
        CiEnvironmentType enum value corresponding to the CI environment this script is being run at.
    """
    if BitbucketPipelines.is_current():
        return BitbucketPipelines
    elif GitHubActions.is_current():
        return GitHubActions

    return Local


ci_platform = _get_ci_platform()
"""
Object containing the info about the current CI platform (Bitbucket Pipelines, GitHub Actions etc.).
"""


class Platforms(Enum):
    Local = Local
    BitbucketPipelines = BitbucketPipelines
    GitHubActions = GitHubActions


platforms = Platforms
"""
Enum containing all supported CI platforms.
"""

__all__ = [
    "ci_platform",
    "platforms"
]
