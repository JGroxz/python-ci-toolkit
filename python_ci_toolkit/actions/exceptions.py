"""
Exceptions raised while executing CI actions.
"""


class ActionRuntimeError(RuntimeError):
    """
    Base class for internal action runtime failures that should become clean CLI errors.
    """

    exit_code = 1


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
