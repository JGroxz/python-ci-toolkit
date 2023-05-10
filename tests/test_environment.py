import os
import tempfile
from pathlib import Path

from rich import print

from python_ci_toolkit.environment import get_project_root_directory_path, assert_environment_variable_set, assert_multiline_environment_variable_set


def test_project_root_directory_path():
    project_root = get_project_root_directory_path()

    print(f"Project root: '{project_root}'")

    assert project_root == Path(__file__).parent.parent


def test_temp_directory_path():
    print(f"Python-provided temp directory: {tempfile.gettempdir()}")

    from python_ci_toolkit.environment.paths import _ci_temp_files_root_directory, _ci_temp_files_shared_directory, _ci_temp_files_projects_root_directory
    print(f"Root temp directory:      '{_ci_temp_files_root_directory}'")
    print(f"Shared temp directory:    '{_ci_temp_files_shared_directory}'")
    print(f"Projects temp directory:  '{_ci_temp_files_projects_root_directory}'")

    from python_ci_toolkit.environment import ci_temp_files_directory
    print(f"Project's temp directory: '{ci_temp_files_directory}'")

    from python_ci_toolkit.environment import ci_temp_files_directory_relative
    print(f"Project's temp directory (relative): '{ci_temp_files_directory_relative}'")

    from python_ci_toolkit.environment import ci_project_root
    assert ci_temp_files_directory.samefile(ci_project_root / ci_temp_files_directory_relative), ("Relative temp CI directory path is does not point to the same "
                                                                                                  "directory as the absolute temp CI directory path.")


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


if __name__ == '__main__':
    from python_ci_toolkit.logging import configure_ci_logging

    configure_ci_logging("DEBUG")

    test_project_root_directory_path()
    test_environment_variable_set()
    test_environment_variable_fallback()
    test_multiline_environment_variable_fallback()
    test_temp_directory_path()
