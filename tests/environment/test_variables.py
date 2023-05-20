import os

import pytest

from python_ci_toolkit.environment import ci_environment_type
from python_ci_toolkit.environment.variables import is_environment_variable_set, retrieve_environment_variable, ENVIRONMENTS_WITHOUT_MULTILINE_SUPPORT


def test_environment_variable_set():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_VALUE = "some test value"

    os.environ[VARIABLE_NAME] = TEST_VALUE

    assert is_environment_variable_set(VARIABLE_NAME), \
        f"Environment variable '{VARIABLE_NAME}' must be set."

    value = retrieve_environment_variable(VARIABLE_NAME)
    assert value == TEST_VALUE, \
        f"Environment variable '{VARIABLE_NAME}' must be set to '{TEST_VALUE}'."


def test_environment_variable_not_set_raises_value_error():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"

    os.environ[VARIABLE_NAME] = ""

    with pytest.raises(ValueError):
        assert retrieve_environment_variable(VARIABLE_NAME)


def test_invalid_fallback_type_raises_type_error():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_FALLBACK_VALUE = [1, 3, 2]

    os.environ[VARIABLE_NAME] = ""

    with pytest.raises(TypeError):
        assert retrieve_environment_variable(VARIABLE_NAME, fallback_value=TEST_FALLBACK_VALUE)


def test_environment_variable_fallback():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_FALLBACK_VALUE = "bloops"

    os.environ[VARIABLE_NAME] = ""

    assert not is_environment_variable_set(VARIABLE_NAME), \
        f"Environment variable '{VARIABLE_NAME}' must not be set."

    value = retrieve_environment_variable(VARIABLE_NAME, fallback_value=TEST_FALLBACK_VALUE)
    assert value == TEST_FALLBACK_VALUE, \
        f"Retrieved value of environment variable '{VARIABLE_NAME}' must be equal to provided fallback value."

    value = retrieve_environment_variable(VARIABLE_NAME, fallback_value=lambda: TEST_FALLBACK_VALUE)
    assert value == TEST_FALLBACK_VALUE, \
        f"Retrieved value of environment variable '{VARIABLE_NAME}' must be equal the value provided by the given fallback value getter function."


def test_multiline_environment_variable_set():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_VALUE = ("ama\n"
                  "longa\n"
                  "multilina\n"
                  "varaiabelle")

    os.environ[VARIABLE_NAME] = TEST_VALUE

    # test normal behavior in environments that support multiline environment variables
    value = retrieve_environment_variable(VARIABLE_NAME)
    assert ci_environment_type not in ENVIRONMENTS_WITHOUT_MULTILINE_SUPPORT, \
        f"This part of the test must be run in an environment that supports multiline environment variables."
    assert value == TEST_VALUE, \
        f"Environment variable '{VARIABLE_NAME}' must be set to '{TEST_VALUE}'."

    # test value restoration in environments that do not support multiline environment variables
    TEST_NEWLINE_SUBSTITUTION_CHARACTER = "+"
    TEST_VALUE_ENCODED = TEST_VALUE.replace("\n", TEST_NEWLINE_SUBSTITUTION_CHARACTER)
    os.environ[VARIABLE_NAME] = TEST_VALUE_ENCODED

    ENVIRONMENTS_WITHOUT_MULTILINE_SUPPORT.append(ci_environment_type)  # <- pretend that the current environment does not support multiline environment variables

    assert ci_environment_type in ENVIRONMENTS_WITHOUT_MULTILINE_SUPPORT, \
        f"This part of the test must be run in an environment that does not support multiline environment variables."
    value = retrieve_environment_variable(VARIABLE_NAME, newline_substitution_character=TEST_NEWLINE_SUBSTITUTION_CHARACTER)
    assert value == TEST_VALUE, \
        f"Environment variable '{VARIABLE_NAME}' must be set to '{TEST_VALUE}'."


def test_multiline_environment_variable_fallback():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_FALLBACK_VALUE = ("ama\n"
                           "longa\n"
                           "multilina\n"
                           "varaiabelle")

    os.environ[VARIABLE_NAME] = ""

    ENVIRONMENTS_WITHOUT_MULTILINE_SUPPORT.append(ci_environment_type)  # <- pretend that the current environment does not support multiline environment variables

    value = retrieve_environment_variable(VARIABLE_NAME, fallback_value=TEST_FALLBACK_VALUE)
    assert value == TEST_FALLBACK_VALUE, \
        f"Retrieved value of environment variable '{VARIABLE_NAME}' must be equal to provided fallback value."
