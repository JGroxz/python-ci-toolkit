import os
from unittest.mock import patch

import pytest

from python_ci_toolkit.environment import retrieve_environment_variable, is_environment_variable_set, ci_platform


def test_environment_variable_set(variable_name: str):
    TEST_VALUE = "some test value"

    os.environ[variable_name] = TEST_VALUE

    assert is_environment_variable_set(variable_name), \
        f"Environment variable '{variable_name}' must be set."

    value = retrieve_environment_variable(variable_name)
    assert value == TEST_VALUE, \
        f"Environment variable '{variable_name}' must be set to '{TEST_VALUE}'."


def test_environment_variable_not_set(variable_name: str):
    os.environ[variable_name] = ""

    assert not is_environment_variable_set(variable_name), \
        f"Environment variable '{variable_name}' must not be set."

    with pytest.raises(ValueError):
        assert retrieve_environment_variable(variable_name)


def test_environment_variable_not_set_raises_value_error(variable_name: str):
    os.environ[variable_name] = ""

    with pytest.raises(ValueError):
        assert retrieve_environment_variable(variable_name)


def test_invalid_fallback_type_raises_type_error(variable_name: str):
    TEST_FALLBACK_VALUE = [1, 3, 2]

    os.environ[variable_name] = ""

    with pytest.raises(TypeError):
        assert retrieve_environment_variable(variable_name, fallback=TEST_FALLBACK_VALUE)  # type: ignore


def test_environment_variable_fallback(variable_name: str):
    TEST_FALLBACK_VALUE = "bloops"

    os.environ[variable_name] = ""

    assert not is_environment_variable_set(variable_name), \
        f"Environment variable '{variable_name}' must not be set."

    value = retrieve_environment_variable(variable_name, fallback=TEST_FALLBACK_VALUE)
    assert value == TEST_FALLBACK_VALUE, \
        f"Retrieved value of environment variable '{variable_name}' must be equal to provided fallback value."

    value = retrieve_environment_variable(variable_name, fallback=lambda: TEST_FALLBACK_VALUE)
    assert value == TEST_FALLBACK_VALUE, \
        f"Retrieved value of environment variable '{variable_name}' must be equal the value provided by the given fallback value getter function."


def test_multiline_environment_variable_set_supports_multiline(variable_name: str):
    TEST_VALUE = ("ama\n"
                  "longa\n"
                  "multilina\n"
                  "varaiabelle")

    os.environ[variable_name] = TEST_VALUE

    # pretend that current CI platform supports multiline environment variables
    with patch.object(ci_platform, "supports_multiline_envvars", return_value=True):
        value = retrieve_environment_variable(variable_name)
        assert ci_platform.supports_multiline_envvars(), \
            f"This part of the test must be run in an environment that supports multiline environment variables."
        assert value == TEST_VALUE, \
            f"Environment variable '{variable_name}' must be set to '{TEST_VALUE}'."


def test_multiline_environment_variable_set_does_not_support_multiline(variable_name: str):
    TEST_VALUE = ("ama\n"
                  "longa\n"
                  "multilina\n"
                  "varaiabelle")

    os.environ[variable_name] = TEST_VALUE

    # pretend that current CI platform does not support multiline environment variables
    with patch.object(ci_platform, "supports_multiline_envvars", return_value=False):
        # test value restoration in environments that do not support multiline environment variables
        TEST_NEWLINE_SUBSTITUTION_CHARACTER = "+"
        TEST_VALUE_ENCODED = TEST_VALUE.replace("\n", TEST_NEWLINE_SUBSTITUTION_CHARACTER)
        os.environ[variable_name] = TEST_VALUE_ENCODED

        assert not ci_platform.supports_multiline_envvars(), \
            f"This part of the test must be run in an environment that does not support multiline environment variables."
        value = retrieve_environment_variable(variable_name, newline_substitution_character=TEST_NEWLINE_SUBSTITUTION_CHARACTER)
        assert value == TEST_VALUE, \
            f"Environment variable '{variable_name}' must be set to '{TEST_VALUE}'."


def test_multiline_environment_variable_fallback():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_FALLBACK_VALUE = ("ama\n"
                           "longa\n"
                           "multilina\n"
                           "varaiabelle")

    os.environ[VARIABLE_NAME] = ""

    ci_platform.supports_multiline_envvars = lambda: False  # <- pretend that the current environment does not support multiline environment variables

    value = retrieve_environment_variable(VARIABLE_NAME, fallback=TEST_FALLBACK_VALUE)
    assert value == TEST_FALLBACK_VALUE, \
        f"Retrieved value of environment variable '{VARIABLE_NAME}' must be equal to provided fallback value."
