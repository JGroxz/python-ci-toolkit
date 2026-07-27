"""
Exceptions raised while executing CI actions.
"""


class ActionRuntimeError(RuntimeError):
    """
    Base class for internal action runtime failures that should become clean CLI errors.
    """

    exit_code = 1


class ActionRuntimeStartupError(ActionRuntimeError):
    """
    Raised when uv or the action bootstrap cannot start an action.
    """

    def __init__(self, action_display_name: str, exit_code: int, details: str | None = None):
        self.exit_code = exit_code or 1
        message = (
            f"Could not start isolated runtime for action '{action_display_name}' "
            f"(exit code {self.exit_code})."
        )
        if details:
            message = f"{message}\n{details}"
        super().__init__(message)


class ActionProcessError(ActionRuntimeError):
    """
    Raised when an action fails inside its isolated process.
    """

    def __init__(
        self,
        action_display_name: str,
        exit_code: int,
        exception_type: str | None = None,
        details: str | None = None,
    ):
        self.exit_code = exit_code or 1
        message = f"Action '{action_display_name}' failed with exit code {self.exit_code}"
        if exception_type:
            message = f"{message} ({exception_type})"
        if details:
            message = f"{message}: {details}"
        super().__init__(message)


class InvalidActionOutputError(ActionRuntimeError):
    """
    Raised when an action writes an invalid JSON output document.
    """

    def __init__(self, action_display_name: str, details: str):
        super().__init__(f"Action '{action_display_name}' produced invalid JSON output: {details}")


class InvalidActionResultError(ActionRuntimeError):
    """
    Raised when the internal action bootstrap result is missing or malformed.
    """

    def __init__(self, action_display_name: str, details: str):
        super().__init__(f"Action '{action_display_name}' produced an invalid runtime result: {details}")


class RecursiveActionError(ActionRuntimeError):
    """
    Raised when an action calls itself through a nested action chain.
    """

    def __init__(self, action_name: str):
        super().__init__(f"Action '{action_name}' is already running. Recursive action calls are not allowed.")


class ActionOutputUnavailableError(ActionRuntimeError):
    """
    Raised when output is written outside an action runtime.
    """

    def __init__(self):
        super().__init__("PYCI_ACTION_OUTPUT is not set. Action outputs can only be written during an action run.")


class MissingActionEntrypointError(ActionRuntimeError):
    """
    Raised when an action module does not define the required entrypoint function.
    """

    def __init__(self, action_display_name: str, entrypoint_name: str):
        super().__init__(
            f"Action '{action_display_name}' does not have a '{entrypoint_name}()' function, so it won't be executed.\n"
            f"Please make sure that the action module has a '{entrypoint_name}()' "
            f"function which serves as an entry point for the action logic."
        )
