"""
Functions for working with environment variables.
"""
import logging
import os
from typing import Callable

from ..environment import ci_platform

logger = logging.getLogger(__name__)


def is_environment_variable_set(variable_name: str) -> bool:
    """
    Checks whether the given environment variable is set.

    Notes:
        Variables defined with empty string as a value are considered unset.

    Args:
        variable_name: Name of the environment variable to check.

    Returns:
        True if variable is set, False otherwise.
    """
    value = os.environ.get(variable_name)
    return (value is not None) and (value != "")


def retrieve_environment_variable(variable_name: str, usage_explanation: str = None,
                                  fallback: Callable[[], str | None] | str = None,
                                  newline_substitution_character: str = "|") -> str:
    """
    Retrieve the value of the given environment variable.

    Notes:
        Certain CI platforms (e.g. BitBucket Pipelines) do not support multiline environment variables.
        A workaround is to use a substitution character instead of newline ('\\\\n') in their values when defining them in the CI interface,
        and then recover the value back to multi-line one when running. This function does this exact thing. For details, look into 'newline_substitution_character'.

        If current CI platform supports multiline environment variables, this function will return variable's original value without modifying it.

    Args:
        variable_name: Name of the environment variable to assert.
        usage_explanation: Optional string with an explanation of why the given environment variable must be set.
        fallback: Value to be returned if the given environment variable is not set.
            If a callable is provided instead, it will be called to retrieve the fallback value.

            If the fallback value is None, assertion will still fail.
            If the fallback value exists, it will also be automatically written into the given environment variable.

            NOTE: If multiline, fallback value is expected to have ACTUAL newline characters.
                Substitution characters will not be replaced in the fallback value.
                This is done so that you don't have to care about CI platform when returning fallback values.
        newline_substitution_character: (only applies to CI platforms without multiline env vars support)
            Character used in the environment variable instead of newline.
            The default value is pipe ('|').

    Returns:
        Value of the given environment variable.

    Raises:
        ValueError: If the given environment variable is not set and no fallback value exists.
        TypeError: If the fallback value is not a string or None.
    """

    # sanity checks
    if len(newline_substitution_character) < 1:
        raise ValueError(f"Newline substitution character must be at least one character long.")

    # if the value is available, return it immediately
    if is_environment_variable_set(variable_name):
        value = os.environ.get(variable_name)

        if ci_platform.supports_multiline_envvars():
            return value

        # restore
        if newline_substitution_character in value:
            logger.debug(f"Value of '{variable_name}' contains newline substitution characters ('{newline_substitution_character}').\n"
                         f"Line breaks will be restored.")
        return value.replace(newline_substitution_character, "\n")

    # use fallback value if required and available
    fallback_is_provided = fallback is not None
    if fallback_is_provided:
        logger.debug(f"'{variable_name}' environment variable is not set, but fallback is defined.\n"
                     f"  Trying to retrieve a fallback value...")

        # if given a callable, retrieve fallback value first
        fallback_is_a_callable = callable(fallback)
        if fallback_is_a_callable:
            fallback = fallback()

        # if fallback value is a non-empty string, set the value and return it immediately
        if isinstance(fallback, str):
            logger.debug(f"Retrieved fallback value for '{variable_name}' environment variable.")
            os.environ[variable_name] = fallback
            return fallback
        # if fallback value is not a string and not empty, raise a TypeError
        elif fallback is not None:
            if fallback_is_a_callable:
                message = (f"Fallback getter function '{fallback}' returned value of type {type(fallback)}, which is neither a string nor None.\n"
                           f"  Fallback value getters are only allowed to return strings to avoid ambiguity, because environment variables can only have string values.")
            else:
                message = (f"Fallback value '{fallback}' is of type {type(fallback)}, which is neither a string nor None.\n"
                           f"  Fallback values are only allowed to be strings to avoid ambiguity, because environment variables can only have string values.")

            raise TypeError(message)

    # if we are here, no value could be retrieved; raise a ValueError
    message = f"'{variable_name}' environment variable is not set, but is required by CI logic."
    if fallback_is_provided:
        message += (f"\n"
                    f"  Fallback value could not be retrieved either. Please see previous log messages for details (before the stack trace).")
    if usage_explanation is not None:
        message += (f"\n"
                    f"  Explanation: {usage_explanation}")

    raise ValueError(message)
