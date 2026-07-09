"""
CI platform detection and platform identity exports.

The selected ``ci_platform`` value is the platform class itself, not an enum
wrapper or instance. Compare it with identity checks such as
``ci_platform is Local`` or ``ci_platform is GitHubActions``.
"""

from .base import CiPlatform
from .bitbucket import BitbucketPipelines
from .github import GitHubActions
from .local import Local

SUPPORTED_CI_PLATFORMS = (
    BitbucketPipelines,
    GitHubActions,
)


def _get_ci_platform() -> type[CiPlatform]:
    """
    Tries to detect current CI environment type.

    Returns:
        Platform class corresponding to the CI environment this script is being run at.
    """
    for platform in SUPPORTED_CI_PLATFORMS:
        if platform.is_current():
            return platform

    return Local


ci_platform = _get_ci_platform()
"""
Object containing the info about the current CI platform (Bitbucket Pipelines, GitHub Actions etc.).
"""


__all__ = [
    "BitbucketPipelines",
    "CiPlatform",
    "GitHubActions",
    "Local",
    "SUPPORTED_CI_PLATFORMS",
    "ci_platform",
]
