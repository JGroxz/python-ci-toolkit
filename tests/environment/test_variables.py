import os

from python_ci_toolkit.environment import assert_environment_variable_set, assert_multiline_environment_variable_set


def test_environment_variable_set():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_VALUE = "some test value"

    os.environ[VARIABLE_NAME] = TEST_VALUE

    value = assert_environment_variable_set(VARIABLE_NAME)

    assert value == TEST_VALUE


def test_environment_variable_fallback():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_FALLBACK_VALUE = "bloops"

    os.environ[VARIABLE_NAME] = ""

    def get_fallback_value() -> str:
        print("Running fallback getter...")
        return TEST_FALLBACK_VALUE

    value = assert_environment_variable_set(VARIABLE_NAME, fallback_value_getter=get_fallback_value)

    assert value == TEST_FALLBACK_VALUE


def test_multiline_environment_variable_set():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_VALUE = ("ama\n"
                  "longa\n"
                  "multilina\n"
                  "varaiabelle")

    os.environ[VARIABLE_NAME] = TEST_VALUE

    value = assert_multiline_environment_variable_set(VARIABLE_NAME)

    assert value == TEST_VALUE


def test_multiline_environment_variable_fallback():
    VARIABLE_NAME = "TEST_ENVIRONMENT_VARIABLE"
    TEST_FALLBACK_VALUE = ("ama\n"
                           "longa\n"
                           "multilina\n"
                           "varaiabelle")

    os.environ[VARIABLE_NAME] = ""

    def get_fallback_value() -> str:
        print("Running fallback getter...")
        return TEST_FALLBACK_VALUE

    value = assert_multiline_environment_variable_set(VARIABLE_NAME, fallback_value_getter=get_fallback_value)

    assert value == TEST_FALLBACK_VALUE
