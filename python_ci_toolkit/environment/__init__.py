from .paths import ci_paths
from .platform import ci_platform, platforms
from .variables import retrieve_environment_variable, is_environment_variable_set

__all__ = [
    "ci_platform",
    "platforms",
    "ci_paths",
    "retrieve_environment_variable",
    "is_environment_variable_set",
]
