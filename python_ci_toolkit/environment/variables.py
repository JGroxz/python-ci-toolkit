"""
Functions for working with environment variables.
"""
import logging
import os
from typing import Callable

from python_ci_toolkit.environment import CiEnvironmentType, ci_environment_type

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


def assert_environment_variable_set(variable_name: str, usage_explanation: str = None,
                                    fallback_value_getter: Callable[[], str | None] = None) -> str:
    """
    Assert that the given environment variable is set and available.

    Args:
        variable_name: Name of the environment variable to assert.
        usage_explanation: Optional string with an explanation of why the given environment variable must be set.
        fallback_value_getter: Optional callable to retrieve the fallback value of this variable in case it is not set.
            Can be used to provide default values to variables. If this callable returns None, assertion will still fail.
            If the fallback value exists, it will also be automatically written into the given environment variable.

    Returns:
        Value of the given environment variable.
    """
    # use fallback value if required and available
    is_fallback_provided = (fallback_value_getter is not None)
    if (not is_environment_variable_set(variable_name)) and is_fallback_provided:
        logger.debug(f"'{variable_name}' environment variable is not set, but fallback getter function is defined.\n"
                     f"  Trying to retrieve a fallback value...")

        # Retrieve fallback value
        fallback_value = fallback_value_getter()

        if isinstance(fallback_value, str):
            os.environ[variable_name] = fallback_value
        elif fallback_value is not None:
            raise TypeError(
                f"Value returned by fallback getter function {fallback_value_getter} is of type {type(fallback_value)}, which is neither a string nor None.\n"
                f"  Fallback value functions are only allowed to return strings or None to avoid ambiguity, because environment variables can only have string or no value.\n")

        if is_environment_variable_set(variable_name):
            logger.debug(f"Retrieved fallback value for '{variable_name}' environment variable.")
            return os.environ[variable_name]
        else:
            logger.warning(f"Could not retrieve a fallback value for '{variable_name}' environment variable.")

    # craft message
    message = f"'{variable_name}' environment variable is not set, but is required by CI logic."
    if is_fallback_provided:
        message = (f"{message}\n"
                   f"  Fallback value could not be retrieved either. Please see previous log messages for details (before the stack trace).")
    if usage_explanation is not None:
        message = (f"{message}\n"
                   f"  Explanation: {usage_explanation}")

    assert is_environment_variable_set(variable_name), message

    return os.environ[variable_name]


def assert_multiline_environment_variable_set(variable_name: str, usage_explanation: str = None,
                                              fallback_value_getter: Callable[[], str | None] = None,
                                              newline_substitution_character: str = "|") -> str:
    """
    A version of assert_environment_variable_set() function which recovers multiline environment variable from its inlined form on platforms which don't support multiline ones.

    Notes:
        Use this function when you need to read a multiline environment variable from your CI environment.

        If the current CI environment supports multiline environment variables,
        this function will return variable's original value without modifying it.

        Certain CI environments (e.g. BitBucket Pipelines) do not support multiline environment variables.
        A workaround is to use a substitution character instead of newline ('\\\\n') in their values when defining them in the CI interface,
        and then recover the value back to multi-line one when running. This is exactly what this function does.

    Args:
        variable_name: Name of the variable to assert and recover.
        usage_explanation: Optional string with an explanation of why the given environment variable must be set.
        fallback_value_getter: Optional callable to retrieve the fallback value of this variable in case it is not set.
            Can be used to provide default values to variables. If this callable returns None, assertion will still fail.
            If the fallback value exists, it will also be automatically written into the given environment variable.

            NOTE: Fallback is expected to return a value with ACTUAL newline characters.
            Substitution characters will not be replaced in the fallback value.
            This is done so that you don't have to care about CI environment type when returning fallback values.

        newline_substitution_character: Character used in the environment variable instead of newline.
            The default value is pipe ('|').

    Returns:
        Recovered multiline value of the given environment variable.
    """
    # we have to be cautious to
    is_fallback_used = (not is_environment_variable_set(variable_name)) and (fallback_value_getter is not None)

    # retrieve the value
    value = assert_environment_variable_set(variable_name, usage_explanation, fallback_value_getter)

    if not is_fallback_used:
        # list of CI environment types which do not support defining multiline environment variables
        unsupported_environments: list[CiEnvironmentType] = [
            CiEnvironmentType.BitbucketPipelines
        ]

        # recover if we are in an unsupported environment
        if ci_environment_type in unsupported_environments:
            return value.replace(newline_substitution_character, "\n")

    # return original value otherwise
    return value
