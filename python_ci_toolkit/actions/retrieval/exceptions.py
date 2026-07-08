"""
Exceptions raised while retrieving CI action scripts.
"""


class ActionRetrievalError(RuntimeError):
    """
    Base class for action retrieval failures that should become clean CLI errors.
    """

    exit_code = 1


class RemoteActionRepoNotConfiguredError(ActionRetrievalError):
    """
    Raised when a remote action is requested without a configured action repository.
    """


class ActionRepositoryLayoutError(ActionRetrievalError):
    """
    Raised when the configured action repository does not have the expected action layout.
    """

    exit_code = 1


class AmbiguousGitActionRefError(ActionRetrievalError):
    """
    Raised when an action version matches both a Git branch and a Git tag.
    """

    exit_code = 2


class MissingGitActionRefError(ActionRetrievalError):
    """
    Raised when an action version does not match a Git branch or tag.
    """

    exit_code = 3


class RemoteActionScriptNotFoundError(ActionRetrievalError):
    """
    Raised when a remote action repository does not contain the requested action script.
    """

    exit_code = 4


class CachedActionScriptNotFoundError(ActionRetrievalError):
    """
    Raised when a cached action repository does not contain the requested action script.
    """

    exit_code = 5
